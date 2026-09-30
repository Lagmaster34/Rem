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
import config
import personalidad
from ejemplos_tono import EJEMPLOS_TONO
from llm import Done, Message, TextDelta, ToolCallChunk, dividir_en_oraciones, get_provider
from llm.echo import EchoProvider

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
    y si difieren el prefijo ya no coincide. No hace nada con Claude/Groq."""
    import llm
    llm.precargar_provider(personalidad.construir_prompt_sistema(),
                           _prefijo_fijo(personalidad.cargar_memoria_larga()), tools)


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
        return True


async def _pasar_por(chunks, on_chunk):
    """Deja pasar cada chunk tal cual, pero además llama on_chunk(chunk) al
    vuelo. Los async generators son de un solo consumidor — esto es lo que
    permite recolectar TextDelta/ToolCallChunk/Done y, A LA VEZ, que
    dividir_en_oraciones() extraiga oraciones del MISMO stream para la voz,
    sin tener que bifurcarlo de verdad."""
    async for chunk in chunks:
        on_chunk(chunk)
        yield chunk


async def procesar_turno(sesion, texto, memoria_larga, memoria_sistema, *,
                          on_delta=None, on_tool_call=None, cola_habla=None,
                          incluir_contexto=True, t_ref=None,
                          tools=None, on_confirmar_accion=None):
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
      la consume y hace TTS -> RVC -> enviar_audio()) apenas está lista, sin
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
    mensajes = sesion.historial
    if incluir_contexto:
        cfg = config.leer_config_contexto()
        contexto = personalidad.construir_contexto_dinamico(
            texto, linea_fecha=cfg["linea_fecha"], palabras_fecha=cfg["palabras_fecha"])
        print(f"  [Contexto] {'fecha' if contexto else 'nada'} (fecha={cfg['linea_fecha']})",
              flush=True)
        if contexto:
            mensajes = sesion.historial[:-1] + [Message(role="user", content=f"{contexto}\n{texto}")]

    # Orden final: system → ejemplos de tono → memoria larga → historial, con
    # el contexto dinámico pegado solo al último mensaje. Todo lo que cambia
    # queda detrás de system + ejemplos, que son idénticos byte a byte en cada
    # turno (el prefijo que reusan las cachés de Ollama/Groq/Claude). El
    # contexto va en el último mensaje y no antes del historial: si fuera
    # antes, cada turno que lo trae invalidaría también todo el historial.
    # En eco no va nada de esto: no hay modelo del otro lado.
    if not isinstance(sesion.provider, EchoProvider):
        mensajes = _prefijo_fijo(memoria_larga) + mensajes

    # Sin la memoria larga, que va como mensaje aparte (ver arriba).
    system = personalidad.construir_prompt_sistema()
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

    stream = sesion.provider.stream_chat(system, mensajes, tools=tools)

    turno_habla = None
    if cola_habla is not None:
        from habla import TurnoHabla
        turno_habla = TurnoHabla(t_ref)
        async for oracion in dividir_en_oraciones(_pasar_por(stream, _on_chunk)):
            cola_habla.put_nowait((oracion, turno_habla))
    else:
        async for chunk in stream:
            _on_chunk(chunk)

    texto_completo = "".join(partes)

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
            cola_habla.put_nowait((texto_completo, turno_habla))

    sesion.historial.append(Message(role="assistant", content=texto_completo))
    return texto_completo, done_chunk, turno_habla
