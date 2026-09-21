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
from llm import Done, Message, TextDelta, ToolCallChunk, dividir_en_oraciones, get_provider
from llm.echo import EchoProvider

MODOS_VALIDOS = ("ia", "eco")


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
                          incluir_contexto=True, t_ref=None):
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

    Devuelve (texto_completo, done_chunk, turno_habla) — turno_habla es la
    instancia de habla.TurnoHabla (mide tiempo hasta el primer audio) si
    cola_habla no era None, o None si no se pidió voz.
    """
    # El HISTORIAL guarda solo lo que dijo el usuario. El contexto dinámico va
    # únicamente en la copia del último mensaje que se le manda al LLM en ESTE
    # turno: antes se guardaba pegado a cada mensaje, y cada turno viejo
    # arrastraba para siempre su propio bloque de fecha/PC — datos caducos que
    # el modelo, además, terminaba comentando.
    sesion.historial.append(Message(role="user", content=texto))
    mensajes = sesion.historial
    if incluir_contexto:
        cfg = config.leer_config_contexto()
        contexto = personalidad.construir_contexto_dinamico(
            memoria_sistema, texto,
            linea_pc=cfg["linea_pc"], palabras_pc=cfg["palabras_pc"],
            linea_fecha=cfg["linea_fecha"], palabras_fecha=cfg["palabras_fecha"],
            # rem_chat no ejecuta acciones de búsqueda: los archivos conocidos
            # solo serían ruido (ver personalidad.construir_prompt_sistema).
            incluir_memoria_sistema=False)
        partes_ctx = [n for n, marca in (("fecha", "[FECHA"), ("PC", "[ESTADO")) if marca in contexto]
        print(f"  [Contexto] {'+'.join(partes_ctx) or 'nada'} "
              f"(pc={cfg['linea_pc']}, fecha={cfg['linea_fecha']})", flush=True)
        if contexto:
            mensajes = sesion.historial[:-1] + [Message(role="user", content=f"{contexto}\n{texto}")]

    # Sin el catálogo de acciones/seguridad: rem_chat no tiene ejecutor de
    # acciones (solo Rem.py, legacy). Ver personalidad.construir_prompt_sistema.
    system = personalidad.construir_prompt_sistema(memoria_larga, con_acciones=False)
    partes = []
    done_chunk = None

    def _on_chunk(chunk):
        nonlocal done_chunk
        if isinstance(chunk, TextDelta):
            partes.append(chunk.text)
            if on_delta:
                on_delta(chunk.text)
        elif isinstance(chunk, ToolCallChunk):
            if on_tool_call:
                on_tool_call(chunk.call)
        elif isinstance(chunk, Done):
            done_chunk = chunk

    stream = sesion.provider.stream_chat(system, mensajes)

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
    sesion.historial.append(Message(role="assistant", content=texto_completo))
    return texto_completo, done_chunk, turno_habla
