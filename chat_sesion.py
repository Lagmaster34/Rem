"""chat_sesion.py — estado de una conversación de chat (modo activo,
provider, historial) y el turno "en crudo" contra el LLM.

Extraído de bench_chat.py (donde SesionChat y el turno vivían originalmente,
como dos copias casi idénticas: _chat() en bench_chat.py para el REPL y
_procesar_mensaje_chat() en rem_avatar_server.py para el panel de chat, que
solo diferían en el destino del texto/audio) para que el REPL de
bench_chat.py y el panel de chat HTML de rem_chat.py (servido vía
rem_avatar_server.py) usen la MISMA clase — y, cuando corren en el mismo
proceso, la MISMA instancia (ver rem_avatar_server.obtener_sesion_chat()) —
y la MISMA función de turno, en vez de mantener dos copias de "modo activo +
historial + cambiar de provider en caliente + armar el turno + consumir el
stream".

procesar_turno() cubre los dos casos (con y sin voz) mediante callbacks: cada
consumidor decide qué hacer con el texto (on_delta) y si quiere que se hable
(cola_habla) — ver su docstring.
"""
import re

import config
import personalidad
from ejemplos_tono import EJEMPLOS_TONO
from llm import Done, Message, TextDelta, ToolCallChunk, dividir_en_oraciones, get_provider
from llm.echo import EchoProvider
from tokens_contexto import PresupuestoContexto

MODOS_VALIDOS = ("ia", "eco")

# Turnos de ejemplo del tono de Rem (few-shot), convertidos una sola vez: van
# entre el system prompt y todo lo demás, idénticos en cada turno, para que
# system + ejemplos sea un prefijo cacheable. El último marca el fin de ese
# prefijo (punto de caché explícito para Claude, ver llm/claude.py).
_EJEMPLOS = tuple(
    Message(role=e["role"], content=e["content"], fin_prefijo_cache=(i == len(EJEMPLOS_TONO) - 1))
    for i, e in enumerate(EJEMPLOS_TONO)
)


def _prefijo_fijo(memoria_larga) -> list[Message]:
    """Lo que va entre el system prompt y el historial: ejemplos de tono + la
    memoria larga (si hay). Compartido por procesar_turno() y
    precargar_prefijo(), para que la precarga evalúe exactamente lo mismo."""
    prefijo = list(_EJEMPLOS)
    memoria = personalidad.construir_bloque_memoria(memoria_larga)
    if memoria:
        prefijo.append(Message(role="user", content=memoria))
    return prefijo


def precargar_prefijo(tools=None):
    """Precarga del LLM al arrancar rem_chat.py (hilo de fondo): además de
    cargar el modelo, le hace evaluar system + tools + ejemplos de tono (+
    memoria larga), el prefijo fijo de todos los turnos, para que quede en la
    caché de Ollama y el primer turno tras una (re)carga no lo pague. `tools`
    tienen que ser las mismas que ofrecerá el panel (acciones.tools_disponibles()
    del modo activo): en el template del modelo van dentro del bloque system,
    y si difieren el prefijo ya no coincide. No hace nada con Claude.

    Con tools bajo demanda (pide_herramientas()) hay dos prefijos: sin tools
    (el caso normal) y con tools. Se precargan los dos: Ollama conserva ambos
    en caché y alternar después cuesta lo mismo que no alternar (medido
    2026-11-05: solo la primera aparición de cada variante paga la evaluación
    completa, ~0,9 s sin tools y ~1,7 s con tools; luego ~130 ms por turno)."""
    import llm
    system = personalidad.construir_prompt_sistema()
    prefijo = _prefijo_fijo(personalidad.cargar_memoria_larga())
    if tools:
        llm.precargar_provider(system, prefijo, tools)
    llm.precargar_provider(system, prefijo, None)


class SesionChat:
    """Estado de una conversación: modo activo, provider y su historial.

    Agrupados acá para que cambiar_modo() sea una función limpia y reusable,
    sin nada de input()/print() ni de WebSocket pegado — eso lo maneja cada
    consumidor (repl() en bench_chat.py, _ws_handler() en
    rem_avatar_server.py).
    """

    def __init__(self, modo_inicial="ia"):
        self.modo = None
        self.provider = None
        self.historial: list[Message] = []
        self.cambiar_modo(modo_inicial)

    def cambiar_modo(self, modo):
        """Cambia el provider activo en caliente, sin reiniciar el proceso.
        Devuelve True si hubo un cambio real, False si ya estaba en ese modo
        (no-op: no pierde el historial por las dudas de un "modo ia"
        repetido). El historial no se mezcla entre modos: se limpia al
        cambiar — más simple que mantener dos historiales en paralelo, y
        evita que un modo arranque con contexto real de una conversación que
        tuvo el otro."""
        if modo not in MODOS_VALIDOS:
            raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}, no {modo!r}")
        if modo == self.modo:
            return False
        # get_provider() puede lanzar (p.ej. falta la API key del provider
        # configurado, ver llm/__init__.py) — se arma el provider nuevo ANTES
        # de tocar self.modo/self.historial, así que si falla la sesión queda
        # exactamente como estaba, no a mitad de cambio.
        nuevo_provider = EchoProvider() if modo == "eco" else get_provider()
        self.modo = modo
        self.provider = nuevo_provider
        self.historial = []
        # Presupuesto de contexto (tokens_contexto.py): solo si el provider
        # tiene un num_ctx que respetar (Ollama); Claude y eco no recortan.
        num_ctx = getattr(nuevo_provider, "num_ctx", None)
        self.presupuesto = PresupuestoContexto(num_ctx) if num_ctx else None
        return True


# ── Emoción de la respuesta ─────────────────────────────────────────────
# El modelo abre la respuesta con una etiqueta [FELIZ]/[TRISTE]/[ENOJADA]/
# [SORPRENDIDA] cuando hay una emoción clara (regla EMOCIÓN de personalidad.py
# y los ejemplos de tono). Se quita del texto ANTES de que llegue al chat y a
# la voz (si no, Piper la leería en voz alta) y se avisa por on_emocion(). Idea
# tomada del sistema de animación de Nerumi (etiqueta al inicio, sin
# etiqueta = neutral). Solo se mira el PRINCIPIO: el resto pasa tal cual.
EMOCIONES = {
    "FELIZ": "happy", "ALEGRE": "happy", "CONTENTA": "happy", "HAPPY": "happy",
    "TRISTE": "sad", "SAD": "sad",
    "ENOJADA": "angry", "ENOJADO": "angry", "BRAVA": "angry", "ANGRY": "angry",
    "SORPRENDIDA": "surprised", "SORPRENDIDO": "surprised", "SURPRISED": "surprised",
}
# Cualquier palabra entre corchetes al inicio se trata como etiqueta y se
# quita (también una desconocida, p. ej. [NEUTRAL] o [PENSATIVA]: leerla en
# voz alta sería peor); solo las de EMOCIONES disparan algo.
_RE_ETIQUETA = re.compile(r"\s*\[([A-Za-zÁÉÍÓÚÑáéíóúñ]{3,15})\]\s*")
_MAX_ETIQUETA = 24  # más que esto sin cerrar el corchete: no era una etiqueta


async def _extraer_emocion(chunks, on_etiqueta):
    """Deja pasar el stream, pero retiene el principio del texto hasta saber
    si empieza con una etiqueta de emoción; si sí, la quita y llama
    on_etiqueta(palabra). Si no, suelta lo retenido tal cual."""
    retenido = ""
    decidido = False
    inicio_pendiente = True   # el espacio inicial (tras la etiqueta o no) se quita
    async for chunk in chunks:
        if decidido:
            if inicio_pendiente and isinstance(chunk, TextDelta):
                texto = chunk.text.lstrip()
                if not texto:
                    continue
                inicio_pendiente = False
                chunk = TextDelta(texto)
            yield chunk
            continue
        if not isinstance(chunk, TextDelta):
            # Tool call o fin antes de decidir: lo retenido no era etiqueta.
            decidido = True
            if retenido:
                yield TextDelta(retenido)
            yield chunk
            continue
        retenido += chunk.text
        inicio = retenido.lstrip()
        if not inicio:
            continue
        if not inicio.startswith("["):
            decidido = True
            inicio_pendiente = False
            yield TextDelta(inicio)
            continue
        m = _RE_ETIQUETA.match(retenido)
        if m:
            decidido = True
            on_etiqueta(m.group(1))
            if retenido[m.end():].strip():
                inicio_pendiente = False
                yield TextDelta(retenido[m.end():].lstrip())
        elif "]" in inicio or len(inicio) > _MAX_ETIQUETA:
            decidido = True
            inicio_pendiente = False
            yield TextDelta(inicio)
    if not decidido and retenido.strip():
        yield TextDelta(retenido.lstrip())


# ── Marcas que el modelo no debería escribir nunca ───────────────────────
# El modelo chico a veces escribe como TEXTO lo que debería ser una tool call o
# una etiqueta inventada ("[ENJOYED abrir_programa('steam')]", medido en el
# banco del 2026-11-05). Se quita del texto antes de que llegue al chat, a la
# voz y al historial (si quedara en el historial, el modelo lo imitaría), y se
# registra en el log. La etiqueta de emoción del principio ya la sacó antes
# _extraer_emocion(). Una llamada es un nombre con "_" seguido de paréntesis,
# o cualquier nombre con un único argumento entre comillas: "print('hola')"
# también se quita (Yoru habla, no escribe código).
_RE_CORCHETES = re.compile(r"\[[^\[\]\n]{0,200}\]")
_RE_LLAMADA = re.compile(r"\b\w*_\w*\([^()\n]{0,200}\)"
                         r"|\b[^\W\d]\w*\(\s*(['\"])[^'\"\n]{0,200}\1\s*\)")
# Lo que podría ser el principio de una marca todavía incompleta al final del
# texto recibido: un "[" sin cerrar, o la última palabra (con o sin "(..."
# abierto), que se retiene hasta ver qué la sigue.
_RE_MARCA_PENDIENTE = re.compile(r"(\[[^\]\n]{0,200}|\b\w+(\([^)\n]{0,200})?)$")


def _limpiar_marcas(texto: str) -> tuple[str, list[str]]:
    """Quita corchetes y llamadas tipo funcion('...'). Devuelve (texto, quitados)."""
    quitados = []

    def _quitar(m):
        quitados.append(m.group(0))
        return ""
    texto = _RE_LLAMADA.sub(_quitar, _RE_CORCHETES.sub(_quitar, texto))
    if quitados:
        texto = re.sub(r"[ \t]{2,}", " ", texto)
        texto = re.sub(r" +([.,;:…?])", r"\1", texto)
        texto = re.sub(r"[,;:]+([.…?])", r"\1", texto)
    return texto, quitados


async def _quitar_marcas(chunks, on_quitado):
    """Deja pasar el stream sin las marcas de _limpiar_marcas(). Retiene solo
    la cola que podría ser una marca a medio llegar (un "[" abierto o la
    última palabra): el texto visible va como mucho una palabra por detrás."""
    pendiente = ""
    fin_con_espacio = True   # lo ya emitido termina en espacio (o no hay nada)
    tras_marca = False       # se quitó una marca y todavía no salió texto después

    def _soltar(final):
        nonlocal pendiente, fin_con_espacio, tras_marca
        limpio, quitados = _limpiar_marcas(pendiente)
        for q in quitados:
            on_quitado(q)
        tras_marca = tras_marca or bool(quitados)
        if tras_marca and fin_con_espacio:
            # El espacio de antes de la marca ya salió: no duplicarlo.
            limpio = limpio.lstrip(" \t")
        m = None if final else _RE_MARCA_PENDIENTE.search(limpio)
        corte = m.start() if m else len(limpio)
        pendiente = limpio[corte:]
        listo = limpio[:corte]
        if final and tras_marca:
            listo = listo.rstrip(" \t")
        if listo:
            fin_con_espacio = listo[-1].isspace()
            tras_marca = tras_marca and not listo.strip()
        return listo

    async for chunk in chunks:
        if isinstance(chunk, TextDelta):
            pendiente += chunk.text
            listo = _soltar(final=False)
            if listo:
                yield TextDelta(listo)
            continue
        if pendiente:
            listo = _soltar(final=True)
            if listo:
                yield TextDelta(listo)
        yield chunk
    if pendiente:
        listo = _soltar(final=True)
        if listo:
            yield TextDelta(listo)


# ── Filtro previo al TTS (solo el audio: el chat muestra el texto tal cual) ──
# Yoru nunca exclama: "!" y "¡" pasan a punto, así Piper no le pone entonación
# de exclamación si al modelo se le escapa una. Y Piper (espeak "es") no lee
# japonés: la muletilla va en romaji. Ojo con lo que espeak "es" hace con el
# romaji (medido con voz.phonemize, WAV en ~/Descargas/prueba-voz): "ii" lo lee
# como el número romano II ("dos") y una "í" sola como "í acentuada"; "íi" da
# una i larga. La jerga en inglés va escrita como suena.
_SUSTITUCIONES_VOZ = (
    (re.compile(r"まあ[、,\s]*どうでもいい"), "maa, dou demo íi"),
    (re.compile(r"\bskill issue\b", re.IGNORECASE), "skil íshiu"),
    (re.compile(r"\bnpcs\b", re.IGNORECASE), "enpisís"),
    (re.compile(r"\bnpc\b", re.IGNORECASE), "enpisí"),
    (re.compile(r"¡"), ""),     # el de apertura se quita: como punto partía la frase
    (re.compile(r"!"), "."),
)


def _para_voz(texto: str) -> str:
    # Red de seguridad: el stream ya viene sin marcas (_quitar_marcas), pero
    # nada entre corchetes ni ninguna llamada a función debe llegar a Piper.
    texto, quitados = _limpiar_marcas(texto)
    if quitados:
        print(f"  [Marcas] quitado antes del TTS: {quitados}", flush=True)
    for patron, reemplazo in _SUSTITUCIONES_VOZ:
        texto = patron.sub(reemplazo, texto)
    # "¡Hola" quedaría ".Hola": sin punto suelto al inicio.
    return texto.lstrip(". ").strip() or texto.strip()


async def _pasar_por(chunks, on_chunk):
    """Deja pasar cada chunk tal cual, pero además llama on_chunk(chunk) al
    vuelo. Los async generators son de un solo consumidor — esto es lo que
    permite recolectar TextDelta/ToolCallChunk/Done y, A LA VEZ, que
    dividir_en_oraciones() extraiga oraciones del MISMO stream para la voz,
    sin tener que bifurcarlo de verdad."""
    async for chunk in chunks:
        on_chunk(chunk)
        yield chunk


# Verbos que piden abrir algo (normalizados, sin tildes): "ábreme el navegador"
# puede llegar como abrir_programa('firefox') sin nombrarlo, así que basta el
# verbo; sin verbo, tiene que aparecer el nombre del programa.
_RE_PEDIDO_ABRIR = re.compile(r"\b(abr|lanz|inici|ejecut|arranc|corr[ea]|pon(e|me|le)?\b|open)")


def pide_herramientas(texto_usuario: str, disparadores: list[str]) -> str | None:
    """¿El mensaje muestra intención clara de usar una tool? Devuelve el primer
    disparador que coincide (config.toml [herramientas]) o None. Palabra
    completa, sin mayúsculas ni tildes; "*" al final acepta cualquier
    terminación ("busca*" -> "búscame"). Sin coincidencia, el turno va sin
    tools: el modelo chico no puede llamarlas por error y el prompt pesa menos."""
    t = personalidad._normalizar(texto_usuario)
    for d in disparadores:
        raiz = personalidad._normalizar(d.rstrip("*"))
        cola = r"\w*" if d.endswith("*") else ""
        if raiz and re.search(r"\b" + re.escape(raiz) + cola + r"\b", t):
            return d
    return None


def _tool_pertinente(call, texto_usuario: str) -> bool:
    """¿El mensaje del usuario de verdad pide esta tool? Hoy solo se filtra
    abrir_programa (la única con falsos positivos medidos); el resto pasa."""
    if call.name != "abrir_programa":
        return True
    t = personalidad._normalizar(texto_usuario)
    if _RE_PEDIDO_ABRIR.search(t):
        return True
    nombre = personalidad._normalizar(str((call.arguments or {}).get("nombre", "")))
    return any(len(p) >= 3 and p in t for p in re.split(r"[\s._-]+", nombre))


async def procesar_turno(sesion, texto, memoria_larga, memoria_sistema, *,
                          on_delta=None, on_tool_call=None, cola_habla=None,
                          incluir_contexto=True, t_ref=None,
                          tools=None, on_confirmar_accion=None, on_emocion=None):
    """Manda `texto` al provider activo de `sesion` y consume stream_chat().
    Compartido entre el REPL de bench_chat.py y el panel de chat de
    rem_chat.py (vía rem_avatar_server.py) — cada consumidor decide qué hacer
    con el texto/audio mediante callbacks, en vez de tener su propia copia de
    "armar el turno, consumir el stream, actualizar el historial":

    - on_delta(fragmento): cada TextDelta tal como llega (texto crudo,
      streaming palabra a palabra) — consola en el REPL, la burbuja del
      panel en la ventana.
    - on_tool_call(call): cada ToolCallChunk reensamblado (en la práctica no
      debería dispararse: stream_chat() se llama sin `tools=`, ver
      llm/__init__.py — se preserva el callback igual, para que un cambio
      futuro que sí pase tools no lo pierda en silencio).
    - cola_habla: si no es None, cada oración completa (dividir_en_
      oraciones()) se encola ahí para hablar (ver habla.py: worker_habla()
      la consume y hace Piper -> enviar_audio()) apenas está lista, sin
      esperar el resto de la respuesta. None (default) no habla nada — la
      sesión sigue funcionando solo como texto.

    Contexto dinámico (ver personalidad.construir_contexto_dinamico y config.toml
    [contexto]): cada línea (fecha/hora, estado de la PC) solo si el mensaje la pide;
    nunca en el historial. `incluir_contexto=False` omite el bloque de fecha/hora/estado de la PC
    (modo eco: no hay LLM al que informarle, y anteponerlo igual solo logra
    que se repita en voz/texto el porcentaje de CPU en vez de lo que se
    escribió).

    `t_ref` (time.perf_counter(), opcional): instante desde el que se mide
    "tiempo hasta el primer audio" además del propio inicio del turno — el
    push-to-talk pasa el momento en que se soltó la tecla.

    `tools` (opcional): lista de llm.ToolSpec a ofrecerle al modelo (ver
    acciones.py). Si el modelo responde con una tool call, el texto que haya
    generado junto a ella se DESCARTA (nunca se habla ni se guarda en el
    historial) y se reemplaza por la respuesta de acciones.ejecutar_tool_async()
    — una sola acción por turno, la primera que llegue si hubiera más de una.
    `on_confirmar_accion` se reenvía tal cual a ejecutar_tool_async() para las
    tools que requieren confirmación; una ConfirmacionExpirada se deja
    propagar sin atrapar, para que el llamador libere el turno.

    `on_emocion(emocion)` (opcional): la emoción de la etiqueta con que abre la
    respuesta ("happy"/"sad"/"angry"/"surprised", ver EMOCIONES), una vez por
    turno y solo si la hay. La etiqueta nunca llega a on_delta ni a la voz.

    Devuelve (texto_completo, done_chunk, turno_habla) — turno_habla es la
    instancia de habla.TurnoHabla (mide tiempo hasta el primer audio) si
    cola_habla no era None, o None si no se pidió voz.
    """
    # El HISTORIAL guarda solo lo que dijo el usuario. El contexto dinámico va
    # únicamente en la copia del último mensaje que se le manda al LLM en ESTE
    # turno: antes se guardaba pegado a cada mensaje, y cada turno viejo
    # arrastraba para siempre su propio bloque de fecha (y antes, de estado de la PC) — datos caducos que
    # el modelo, además, terminaba comentando.
    sesion.historial.append(Message(role="user", content=texto))
    # Tools bajo demanda: solo si el mensaje muestra intención clara (ver
    # pide_herramientas()). Ir y venir entre con/sin tools cambia el bloque
    # system de la plantilla y rompe la caché del prefijo — medido, ver CLAUDE.md.
    if tools:
        disparo = pide_herramientas(texto, config.leer_disparadores_herramientas())
        print(f"  [Tools] {'sí, por ' + repr(disparo) if disparo else 'no (sin intención clara)'}",
              flush=True)
        if not disparo:
            tools = None
    contexto = ""
    if incluir_contexto:
        cfg = config.leer_config_contexto()
        contexto = personalidad.construir_contexto_dinamico(
            texto, linea_fecha=cfg["linea_fecha"], palabras_fecha=cfg["palabras_fecha"])
        print(f"  [Contexto] {'fecha' if contexto else 'nada'} (fecha={cfg['linea_fecha']})",
              flush=True)

    # Orden final: system → ejemplos de tono → memoria larga → historial, con
    # el contexto dinámico pegado solo al último mensaje. Todo lo que cambia
    # queda detrás de system + ejemplos, que son idénticos byte a byte en cada
    # turno (el prefijo que reusan las cachés de Ollama/Claude). El
    # contexto va en el último mensaje y no antes del historial: si fuera
    # antes, cada turno que lo trae invalidaría también todo el historial.
    # En eco no va nada de esto: no hay modelo del otro lado.
    es_llm = not isinstance(sesion.provider, EchoProvider)
    prefijo = _prefijo_fijo(memoria_larga) if es_llm else []
    # Sin la memoria larga, que va como mensaje aparte (ver arriba).
    system = personalidad.construir_prompt_sistema()

    # Si no cabe en num_ctx, fuera los turnos más viejos del historial (nunca
    # system/tools/ejemplos/memoria): si no, Ollama recortaría por su cuenta
    # empezando por los ejemplos de tono (ver tokens_contexto.py). Se estima
    # con las tools de la primera llamada; el reintento sin tools pesa menos.
    presupuesto = getattr(sesion, "presupuesto", None) if es_llm else None
    if presupuesto:
        presupuesto.recortar(sesion.historial, system, prefijo, tools, contexto)

    mensajes = sesion.historial
    if contexto:
        mensajes = sesion.historial[:-1] + [Message(role="user", content=f"{contexto}\n{texto}")]
    historial_enviado = list(mensajes)
    mensajes = prefijo + mensajes
    partes = []
    done_chunk = None
    tool_calls_recibidas = []

    def _on_chunk(chunk):
        nonlocal done_chunk
        if isinstance(chunk, TextDelta):
            partes.append(chunk.text)
            if on_delta:
                on_delta(chunk.text)
        elif isinstance(chunk, ToolCallChunk):
            tool_calls_recibidas.append(chunk.call)
            if on_tool_call:
                on_tool_call(chunk.call)
        elif isinstance(chunk, Done):
            done_chunk = chunk

    etiqueta = None

    def _on_etiqueta(palabra):
        nonlocal etiqueta
        etiqueta = palabra.upper()
        emocion = EMOCIONES.get(etiqueta)
        print(f"  [Emoción] [{etiqueta}] -> {emocion or 'sin efecto'}", flush=True)
        if emocion and on_emocion:
            on_emocion(emocion)

    turno_habla = None
    if cola_habla is not None:
        from habla import TurnoHabla
        turno_habla = TurnoHabla(t_ref)

    tools_usadas = tools  # las de la última llamada real (para calibrar el prefijo)

    async def _consumir(tools_turno):
        nonlocal tools_usadas
        tools_usadas = tools_turno
        stream = sesion.provider.stream_chat(system, mensajes, tools=tools_turno)
        if not isinstance(sesion.provider, EchoProvider):
            stream = _extraer_emocion(stream, _on_etiqueta)
            stream = _quitar_marcas(stream, lambda q: print(
                f"  [Marcas] quitado de la respuesta (chat, voz e historial): {q!r}", flush=True))
        if cola_habla is not None:
            async for oracion in dividir_en_oraciones(_pasar_por(stream, _on_chunk)):
                cola_habla.put_nowait((_para_voz(oracion), turno_habla))
        else:
            async for chunk in stream:
                _on_chunk(chunk)

    await _consumir(tools)
    # Tool call sin pedido real (falso positivo del modelo chico: "invéntate
    # una canción" -> abrir_programa('vlc')): se descarta y el turno se repite
    # SIN tools, para que conteste en personaje en vez del mensaje fijo de la tool.
    if tool_calls_recibidas and not "".join(partes).strip() \
            and not _tool_pertinente(tool_calls_recibidas[0], texto):
        call = tool_calls_recibidas[0]
        print(f"  [Tool] {call.name}({call.arguments}) descartada: el mensaje no la pide — se repite sin tools",
              flush=True)
        tool_calls_recibidas.clear()
        await _consumir(None)

    texto_completo = "".join(partes)

    if presupuesto and done_chunk and done_chunk.usage:
        # Sin llamadas extra: el prompt_eval_count de esta respuesta (incluye
        # lo cacheado) fija el costo exacto del prefijo para el próximo turno.
        presupuesto.calibrar(done_chunk.usage.get("prompt_eval_count"),
                             None if tool_calls_recibidas else done_chunk.usage.get("eval_count"),
                             texto_completo, system, prefijo, tools_usadas, historial_enviado)

    if tool_calls_recibidas:
        # Se descarta cualquier texto que el modelo haya generado junto a la
        # tool call (no se habla ni se guarda) — la respuesta real la arma
        # acciones.ejecutar_tool_async(), nunca lo que dijo el LLM en crudo.
        import acciones
        call = tool_calls_recibidas[0]
        texto_completo = await acciones.ejecutar_tool_async(
            call.name, call.arguments,
            memoria_sistema=memoria_sistema, on_confirmar_accion=on_confirmar_accion)
        if on_delta:
            on_delta(texto_completo)
        if cola_habla is not None:
            if turno_habla is None:
                from habla import TurnoHabla
                turno_habla = TurnoHabla(t_ref)
            cola_habla.put_nowait((_para_voz(texto_completo), turno_habla))

    # El historial conserva la etiqueta (si el turno no fue una tool): así el
    # modelo ve sus respuestas anteriores en el mismo formato que se le pide.
    guardado = f"[{etiqueta}] {texto_completo}" if etiqueta and not tool_calls_recibidas else texto_completo
    sesion.historial.append(Message(role="assistant", content=guardado))
    return texto_completo, done_chunk, turno_habla
