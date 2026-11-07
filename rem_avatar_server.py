"""
Servidor para el avatar 3D de Rem.
  - HTTP  en :18765 → sirve rem_avatar.html, los VRM de models/vrm/ y los clips de Animaciones/
  - WS    en :18766 → bidireccional: Python -> browser (estado/audio/chat_*),
                       y browser -> Python (chat_message/cambiar_modo/reset/voz/
                       estado, ver _ws_handler/chat_sesion.py)

La ventana que muestra el avatar es rem_chat.py (GTK3 + WebKit2): normal y decorada
(--modo ventana) o layer surface transparente (--modo overlay). Este módulo solo
levanta el servidor — no lanza ninguna ventana. También orquesta el push-to-talk
(ptt_start/ptt_stop -> micrófono -> STT -> turno de chat), ver "Push-to-talk" abajo. rem_chat.py llama a
iniciar_servidor_avatar(); bench_chat.py se conecta al servidor ya levantado como
cliente WS, o lo levanta él mismo si no hay ninguno.
"""
import asyncio
import threading
import socket
import os
import time
import json
import logging
import glob
import shutil
import uuid
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
HTTP_PORT = 18765
WS_PORT   = 18766

# Orígenes aceptados en el handshake del WS. Un navegador deja que CUALQUIER
# página abra ws://localhost:18766 (el WebSocket no tiene CORS), y eso basta
# para mandar chat_message (que dispara tools) — por eso se filtra el Origin:
# solo las páginas servidas por nuestro HTTP (avatar, y el panel después), más
# `None` = sin cabecera Origin, que es lo que mandan los clientes Python
# (bench_chat.py, rem_ptt.py). Un proceso local puede falsificar el Origin, pero
# ese ya tiene el mismo acceso que el usuario: esto cierra la puerta al navegador.
WS_ORIGENES_PERMITIDOS = [
    f"http://localhost:{HTTP_PORT}",
    f"http://127.0.0.1:{HTTP_PORT}",
    None,
]

TMP_AUDIO_DIR   = os.path.join(BASE_DIR, "tmp_audio")
AUDIO_MAX_AGE_S = 5 * 60  # borrar audios servidos hace más de 5 minutos
os.makedirs(TMP_AUDIO_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# ── Clientes WebSocket conectados ────────────────────────────────────
_ws_clients = set()
# Rol con que se identificó cada cliente ({"tipo": "hola", "rol": ...}, lo
# primero que manda al conectar). Los mensajes se siguen difundiendo a TODOS;
# el rol solo decide quién CUENTA como destinatario para el aviso de "no llegó
# a nadie": un panel de control abierto no reproduce audio ni mueve el avatar,
# así que con el avatar cerrado el aviso tiene que saltar igual. Un cliente sin
# identificar (rem_ptt.py, que solo manda un ptt_* y se va) no cuenta.
# "chat" = la ventana de chat aparte del modo escritorio (rem_chat_ventana.html).
ROLES_WS = {"avatar", "panel", "debug", "chat"}
_ws_roles = {}   # websocket -> rol (bajo _ws_lock, igual que _ws_clients)
DESTINO_AVATAR = ("avatar",)            # estado, audio, debug_clip
DESTINO_CHAT   = ("avatar", "debug", "chat")  # chat_delta/chat_done/modo_actual/error
# Tipos de mensaje que la ventana de chat le reenvía al avatar (al_avatar) y
# que el avatar le devuelve (del_avatar). El estado de los clips, el baile y el
# modelo cargado vive en la página del avatar; la de chat solo lo pide/muestra.
CMDS_AL_AVATAR = {"estado_get", "baile", "clip", "saludar", "gesto"}
INFOS_DEL_AVATAR = {"estado", "sistema", "modelo_cargado", "baile", "clip_lanzado"}
_ws_lock    = threading.Lock()
_ws_loop    = None
_ws_ready   = threading.Event()   # se activa cuando el loop WS está listo

# Aviso "sin destinatarios" con antirrebote: si el avatar no está abierto, un
# turno de chat entero puede irse al vacío en silencio — hay que decirlo, pero
# sin spamear una línea por cada enviar_estado() de cada turno.
_ultimo_aviso_sin_clientes = 0.0

# Modo activo (ventana|overlay) — lo fija rem_chat.py una sola vez al
# arrancar, ANTES de iniciar_servidor_avatar(). Decide qué tools ofrece
# _procesar_mensaje_chat() (ver acciones.tools_disponibles(): apagar_pc no
# se ofrece en overlay, no hay forma de confirmar una acción ahí).
_modo_actual = "ventana"


def establecer_modo(modo: str) -> None:
    global _modo_actual
    _modo_actual = modo


# Modo escritorio: la página del avatar le habla a escritorio.py (región de
# clic, pulsación sobre el cuerpo, acciones del menú) por ESTE WebSocket, no
# por un script message handler de WebKit: cada mensaje de esos crea objetos
# JSCValue en Python, y con la región mandándose cada ~90 ms el bucle de GTK
# acababa colgado para siempre en JSC::Heap::acquireAccessSlow (visto con gdb;
# probablemente el recolector de Python liberando alguno desde otro hilo).
# El oyente se llama en el hilo del WS: tiene que pasarle el trabajo a GTK él
# mismo (GLib.idle_add).
_oyente_escritorio = None

# Último latido de la página del avatar (latido_pagina, cada 10 s desde el
# bucle de render: avatar/bucle.js). Lo mira el vigilante de rem_chat.py.
ultimo_latido_pagina = None


def establecer_oyente_escritorio(fn) -> None:
    global _oyente_escritorio
    _oyente_escritorio = fn

def _avisar_sin_destinatarios(que: str):
    global _ultimo_aviso_sin_clientes
    ahora = time.monotonic()
    if ahora - _ultimo_aviso_sin_clientes > 10.0:
        _ultimo_aviso_sin_clientes = ahora
        logger.warning("[Avatar] %s: ningún cliente WS que lo use conectado — el mensaje no llega "
                       "a nadie (¿está abierta la ventana de rem_chat.py?)", que)


def _clientes_ws(destino):
    """(todos los clientes, cuántos de ellos tienen un rol de `destino`)."""
    with _ws_lock:
        clientes = set(_ws_clients)
        utiles = sum(1 for ws in clientes if _ws_roles.get(ws) in destino)
    return clientes, utiles


def _emitir_ws(payload: dict, que: str, destino=DESTINO_AVATAR, avisar=True) -> int:
    """Serializa y manda `payload` a todos los clientes WS. Devuelve cuántos de
    ellos tienen un rol de `destino` (0 si el servidor no está listo o no hay
    ninguno — en ese caso avisa por log, con antirrebote; se manda igual al
    resto). Único punto por el que salen mensajes Python -> browser: estado,
    audio y todos los del panel de chat (chat_delta/chat_done/modo_actual/error)."""
    if not _ws_ready.is_set() or _ws_loop is None:
        if avisar:
            _avisar_sin_destinatarios(que)
        return 0
    clientes, utiles = _clientes_ws(destino)
    if not utiles and avisar:
        _avisar_sin_destinatarios(que)
    if not clientes:
        return 0
    msg = json.dumps(payload)
    async def _enviar():
        for ws in clientes:
            try:
                await ws.send(msg)
            except Exception:
                pass
    asyncio.run_coroutine_threadsafe(_enviar(), _ws_loop)
    return utiles


def enviar_estado(estado: str) -> int:
    """Llamar desde cualquier hilo para mandar el estado al browser. Devuelve
    a cuántos clientes llegó (0 = nadie, con aviso en el log)."""
    return _emitir_ws({"estado": estado}, f"estado {estado!r}")


def enviar_debug_clip(nombre: str) -> int:
    """Depuración: pide al avatar que dispare un clip VRMA por nombre (con o sin
    ".vrma"), como si fuera un gesto de reposo — corre una vez y vuelve a la
    pose de reposo con crossfade. Sirve para grabar un clip concreto sin esperar
    al sorteo aleatorio de updateGestos(). Devuelve a cuántos clientes llegó."""
    return _emitir_ws({"tipo": "debug_clip", "nombre": nombre},
                      f"debug_clip {nombre!r}")


# Emoción de la respuesta (etiqueta [FELIZ] etc. al inicio, ver
# chat_sesion.EMOCIONES): va aparte del estado (talking/thinking), que la
# pisaría al instante. El avatar la usa para la cara y para el clip de esa
# emoción (catálogo -> porEstado), con su propia duración.
EMOCIONES_VALIDAS = {'happy', 'sad', 'angry', 'surprised'}


def enviar_emocion(emocion: str) -> int:
    """Pide al avatar que muestre una emoción (cara + clip). Devuelve a
    cuántos avatares llegó."""
    return _emitir_ws({"tipo": "emocion", "emocion": emocion}, f"emoción {emocion!r}")


def _broadcast_ws(payload: dict, destino=DESTINO_CHAT, avisar=True) -> int:
    """Manda `payload` a todos los clientes WS conectados. Genérico — lo usan
    los mensajes del panel de chat (chat_delta/chat_done/modo_actual/error).
    avisar=False: sin el aviso de "no llega a nadie" (lo que va a una ventana
    de chat que puede estar cerrada a propósito)."""
    return _emitir_ws(payload, f"mensaje {payload.get('tipo', '?')!r}", destino, avisar)


def _limpiar_audio_viejo():
    """Borra de tmp_audio/ los WAV servidos hace más de AUDIO_MAX_AGE_S."""
    ahora = time.time()
    for ruta in glob.glob(os.path.join(TMP_AUDIO_DIR, "*.wav")):
        try:
            if ahora - os.path.getmtime(ruta) > AUDIO_MAX_AGE_S:
                os.remove(ruta)
        except OSError:
            pass


def enviar_audio(ruta_wav: str, timeline: list) -> bool:
    """Copia `ruta_wav` a tmp_audio/ con un id único y lo anuncia por WebSocket
    junto al timeline de visemes, para que el navegador lo reproduzca y sincronice
    la boca.

    Devuelve True si había al menos un AVATAR conectado (y por tanto se envió a
    todos). Si no hay ninguno — aunque haya otros clientes, p. ej. el panel de
    control —, no copia nada y devuelve False.
    """
    if not _ws_ready.is_set():
        _avisar_sin_destinatarios("audio")
        return False
    loop = _ws_loop
    if loop is None:
        _avisar_sin_destinatarios("audio")
        return False

    _, avatares = _clientes_ws(DESTINO_AVATAR)
    if not avatares:
        _avisar_sin_destinatarios("audio")
        return False

    _limpiar_audio_viejo()

    audio_id = uuid.uuid4().hex
    nombre   = f"{audio_id}.wav"
    destino  = os.path.join(TMP_AUDIO_DIR, nombre)
    shutil.copyfile(ruta_wav, destino)

    msg = json.dumps({
        "tipo": "audio",
        "url": f"/tmp_audio/{nombre}",
        "timeline": timeline,
    })

    async def _broadcast():
        with _ws_lock:
            objetivo = set(_ws_clients)
        for ws in objetivo:
            try:
                await ws.send(msg)
            except Exception:
                pass

    asyncio.run_coroutine_threadsafe(_broadcast(), loop)
    return True


# Estados válidos para el avatar
ESTADOS_VALIDOS = {'idle', 'talking', 'thinking', 'happy', 'sad', 'angry', 'surprised'}


def url_chat_ventana() -> str:
    """URL de la ventana de chat aparte del modo escritorio."""
    import urllib.parse
    import personalidad as _personalidad
    qs = urllib.parse.urlencode({"personaje": _personalidad.NOMBRE_PERSONAJE})
    return f"http://localhost:{HTTP_PORT}/rem_chat_ventana.html?{qs}"


def url_avatar(modo: str = "ventana") -> str:
    """URL de rem_avatar.html con el modelo VRM activo (config.toml ->
    [avatar].modelo) como query param — único punto que arma esta URL, para
    que rem_chat.py y bench_chat.py no dupliquen la lectura de config.toml.
    rem_avatar.html lee ?modelo=... para elegir el perfil correspondiente en
    CONFIG.modelos (ver "Selección de modelo" en ese archivo)."""
    import config as _config
    import urllib.parse
    import personalidad as _personalidad
    modelo = _config.leer_modelo_avatar()
    qs = urllib.parse.urlencode({"modo": modo, "modelo": modelo,
                                 "personaje": _personalidad.NOMBRE_PERSONAJE})
    return f"http://localhost:{HTTP_PORT}/rem_avatar.html?{qs}"


# ── Servidor HTTP — solo acepta conexiones de localhost ───────────────
class _LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE_DIR, **kw)

    def log_request(self, code='-', size='-'):
        # code viene tipado desde send_response() — sin adivinar posiciones en *args.
        if isinstance(code, HTTPStatus):
            code = code.value
        if str(code) not in ('200', '204', '304'):
            logger.warning('HTTP %s "%s" %s', code, self.requestline, size)

    def log_message(self, fmt, *args):
        # Robusto ante cualquier cantidad de args (log_error puede pasar menos que
        # log_request) — antes esto asumía siempre 3 args y tiraba traceback en cada 404.
        try:
            logger.warning("HTTP %s", fmt % args)
        except Exception:
            logger.warning("HTTP %s", " ".join(str(a) for a in args))

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", f"http://localhost:{HTTP_PORT}")
        # Sin esto WebKit cachea por heurística (solo hay Last-Modified) y su
        # caché en disco, que sobrevive entre arranques, servía un
        # rem_avatar.html viejo tras editarlo. no-cache = revalidar siempre: un
        # archivo sin cambios vuelve como 304 (If-Modified-Since), sin bajarse.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()


_http_ready      = threading.Event()
_http_bind_error = None  # excepción del bind HTTP, si falló — mismo criterio que _ws_bind_error

def _iniciar_http():
    """Como _iniciar_ws(): si el bind falla (otra instancia ganó la carrera
    por el puerto), el hilo daemon moría en silencio y el llamador creía que
    el servidor había levantado. Ahora el fallo queda en _http_bind_error."""
    global _http_bind_error
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), _LocalHandler)
    except OSError as e:
        _http_bind_error = e
        return
    _http_ready.set()
    srv.serve_forever()


# ── Chat de texto (panel HTML de rem_chat.py + REPL de bench_chat.py) ──
# Ver chat_sesion.py para SesionChat/procesar_turno(). Todo perezoso: se
# construye recién en el primer chat_message/cambiar_modo/reset real, no al
# importar este módulo — quien importe rem_avatar_server sin usar el chat no
# debería pagar el costo de get_provider()/leer memoria (ni arriesgarse a que
# get_provider() lance por falta de API key) solo por importar el módulo.
_chat_lock         = threading.Lock()  # guarda la creación perezosa y el flag de turno activo
_chat_sesion        = None
_chat_memoria_larga   = None
_chat_memoria_sistema = None
_chat_turno_activo    = False

# Voz del panel de chat — equivalente a "voz on|off" del REPL, pero
# independiente: cada uno controla si SUS PROPIOS turnos hablan, no hay
# sincronización entre los dos (ver CLAUDE.md, "Voz en la ventana de chat").
# Arranca en True porque la ventana existe justamente para hablar con Rem —
# el interruptor del panel es para poder silenciarla, no para tener que
# activarla primero.
_chat_voz_activa = True

# Cola + worker de voz PROPIOS del panel de chat — independientes de la cola
# del REPL (asyncio.Queue en bench_chat.py, ver repl()). Ambos comparten el
# misma voz Piper (habla._voz/_voz_lock), pero no la cola: cada turno se
# habla desde la cola de quien lo disparó, así que con la ventana y el REPL
# abiertos a la vez el turno del panel nunca termina también encolado en el
# worker del REPL (o viceversa) — no hay forma de que el mismo turno se
# hable dos veces. Se crean recién en el primer chat_message con voz activa,
# DESDE DENTRO de _procesar_mensaje_chat() (que ya corre como tarea de
# _ws_loop) — asyncio.create_task() liga la tarea al loop que esté corriendo
# en ese momento, así que esta creación nunca debe dispararse desde otro
# hilo/loop (el del REPL, por ejemplo).
_chat_cola_habla = None
_chat_worker_habla_task = None


def set_voz_chat_activa(activa: bool) -> None:
    """Además de guardarla, la difunde (voz_actual): en modo escritorio la
    cambian varios sitios (ventana de chat, menú del avatar, panel) y todos la
    pintan. La llama el oyente de preferencias "voz" (el mensaje WS `voz` pasa
    por preferencias, así se guarda y sobrevive a un reinicio)."""
    global _chat_voz_activa
    _chat_voz_activa = bool(activa)
    _broadcast_ws({"tipo": "voz_actual", "activa": _chat_voz_activa},
                  destino=("avatar", "chat", "panel"), avisar=False)


def _iniciar_voz_desde_prefs():
    """Al levantar el servidor: la voz arranca como quedó guardada, y cada cambio
    de la sección "voz" (WS `voz`, panel) la aplica."""
    global _chat_voz_activa
    import preferencias
    try:
        _chat_voz_activa = bool(preferencias.obtener("voz")["activa"])
    except Exception as e:
        logger.warning("[Prefs] no se pudo leer la voz guardada (%s)", e)
    preferencias.al_cambiar("voz", lambda v: set_voz_chat_activa(v["activa"]))


def _info_llm() -> dict:
    """Proveedor y modelo del LLM activo, para mostrarlo en el panel (solo
    lectura). Sin construir el provider: no hace falta API key para esto."""
    import config as _config
    cfg = _config.leer_config_toml().get("llm", {})
    prov = (os.environ.get("REM_LLM_PROVIDER") or str(cfg.get("provider", "ollama"))).strip().lower()
    sub = cfg.get(prov, {}) if isinstance(cfg.get(prov), dict) else {}
    return {"provider": prov, "modelo": str(sub.get("model", ""))}


def _obtener_cola_habla():
    """Crea la cola + worker de voz del panel la primera vez que hace falta.
    Debe llamarse siempre desde una coroutine que ya corre en _ws_loop (ver
    _procesar_mensaje_chat(), el único llamador) — asyncio.create_task() liga
    la tarea a ESE loop."""
    global _chat_cola_habla, _chat_worker_habla_task
    if _chat_cola_habla is None:
        from habla import worker_habla
        _chat_cola_habla = asyncio.Queue()
        _chat_worker_habla_task = asyncio.create_task(worker_habla(_chat_cola_habla))
    return _chat_cola_habla


def obtener_sesion_chat():
    """Crea (si hace falta) y devuelve (sesion, memoria_larga, memoria_sistema)
    COMPARTIDOS entre el panel de chat de rem_chat.py (vía _ws_handler, más
    abajo) y el REPL de bench_chat.py cuando corren en el mismo proceso: la
    MISMA instancia de SesionChat, así que cambiar de modo o mandar un
    mensaje desde cualquiera de los dos actualiza el otro (ver CLAUDE.md)."""
    global _chat_sesion, _chat_memoria_larga, _chat_memoria_sistema
    with _chat_lock:
        if _chat_sesion is None:
            import personalidad
            from chat_sesion import SesionChat
            _chat_sesion = SesionChat(modo_inicial="ia")
            _chat_memoria_larga = personalidad.cargar_memoria_larga()
            _chat_memoria_sistema = personalidad.cargar_memoria_sistema()
        return _chat_sesion, _chat_memoria_larga, _chat_memoria_sistema


def cambiar_modo_chat(modo: str) -> bool:
    """Cambia el modo de la sesión de chat compartida y avisa a todos los
    clientes WS con un modo_actual, sin importar quién disparó el cambio (el
    botón del panel, otro cliente WS, o el REPL de bench_chat.py vía esta
    misma función). Devuelve lo mismo que SesionChat.cambiar_modo() (True si
    hubo un cambio real). Puede lanzar ValueError (modo inválido) o lo que
    lance get_provider() (falta la API key del provider configurado) — el
    llamador decide qué hacer con eso."""
    sesion, _, _ = obtener_sesion_chat()
    cambio = sesion.cambiar_modo(modo)
    _broadcast_ws({"tipo": "modo_actual", "modo": sesion.modo})
    return cambio


async def _procesar_mensaje_chat(texto: str, t_ref: float | None = None, por_voz: bool = False):
    """Maneja un chat_message del panel: corre el turno completo contra el
    LLM (chat_sesion.procesar_turno()) emitiendo chat_delta por cada
    fragmento tal como llega, y si la voz del panel está activa (ver
    _chat_voz_activa/set_voz_chat_activa()) también encola cada oración
    para hablar (Piper -> enviar_audio, mismo pipeline que el REPL de
    bench_chat.py, ver habla.py) apenas dividir_en_oraciones() la completa.
    Mueve el estado del avatar a 'thinking' antes del primer fragmento y a
    'talking' con el primero — mismo canal (enviar_estado) que usa el resto
    del proyecto — así el indicador del panel y el cuerpo del avatar quedan
    en sintonía incluso en modo eco (sin audio real). Serializado con un
    flag simple (no una cola): un chat_message mientras ya hay un turno en
    curso se rechaza con error, en vez de interlear dos streams en el mismo
    panel.

    `t_ref` (time.perf_counter(), opcional): instante de referencia para medir
    "tiempo hasta el primer audio" — el push-to-talk pasa el momento en que se
    soltó la tecla (ver _ptt_detener()).

    Devuelve el texto de la respuesta (None si no hubo turno): el modo
    conversación mira si termina en "?". Un mensaje escrito (`por_voz=False`)
    cierra el modo conversación."""
    global _chat_turno_activo
    if not por_voz and _conv_activa:
        _conversacion(False, "mensaje escrito")
    if _ptt_estado in ("iniciando", "grabando"):
        # Hablarle a Rem por texto mientras se graba haría sonar su voz
        # encima del micrófono abierto — justo lo que el push-to-talk evita.
        _broadcast_ws({"tipo": "error", "mensaje": "Estás grabando con la tecla de voz — suéltala antes de escribir."})
        return None
    with _chat_lock:
        if _chat_turno_activo:
            _broadcast_ws({"tipo": "error", "mensaje": "Yoru ya está respondiendo — espera a que termine."})
            return None
        _chat_turno_activo = True

    from chat_sesion import procesar_turno
    sesion, memoria_larga, memoria_sistema = obtener_sesion_chat()

    enviar_estado("thinking")
    primer_fragmento = True
    respuesta = None

    def _on_delta(fragmento):
        nonlocal primer_fragmento
        if primer_fragmento:
            enviar_estado("talking")
            primer_fragmento = False
        _broadcast_ws({"tipo": "chat_delta", "texto": fragmento})

    try:
        # En modo eco no hay LLM que necesite el contexto dinámico (fecha/
        # hora/estado de la PC) — incluirlo igual solo hace que el panel
        # muestre/hable ese bloque en vez de repetir tal cual lo que se
        # escribió (mismo motivo que en bench_chat.py, ver
        # chat_sesion.procesar_turno).
        incluir_contexto = sesion.modo != "eco"
        cola_habla = _obtener_cola_habla() if _chat_voz_activa else None
        # Sin tools en modo eco: no hay LLM del otro lado que las use.
        import acciones
        tools = acciones.tools_disponibles(_modo_actual) if sesion.modo != "eco" else None
        respuesta, _done, _turno = await procesar_turno(sesion, texto, memoria_larga, memoria_sistema,
                              on_delta=_on_delta, cola_habla=cola_habla,
                              incluir_contexto=incluir_contexto, t_ref=t_ref,
                              tools=tools, on_confirmar_accion=_pedir_confirmacion_accion,
                              on_emocion=enviar_emocion)
        _broadcast_ws({"tipo": "chat_done"})
    except Exception as e:
        logger.exception("[Chat] error procesando turno")
        _broadcast_ws({"tipo": "error", "mensaje": str(e)})
    finally:
        enviar_estado("idle")
        with _chat_lock:
            _chat_turno_activo = False
        _marcar_fin_habla()
    return respuesta


# ── Push-to-talk (voz de entrada) ────────────────────────────────────
# Flujo: `rem_ptt.py start` (bindr/bind de Hyprland) -> ptt_start por WS ->
# se abre el micrófono; `rem_ptt.py stop` -> ptt_stop -> se cierra, se
# transcribe (stt/, en un hilo: es CPU y bloquearía el loop) -> la
# transcripción se enseña (ptt_transcripcion) y entra a la vez como un
# chat_message normal — mismo turno de LLM/voz que si se
# hubiera escrito.
#
# DECISIÓN — ¿qué pasa con ptt_start mientras Rem habla? SE IGNORA (no la
# interrumpe). Interrumpir exigiría cancelar el turno de LLM en curso, vaciar
# la cola de síntesis (Piper corre en un hilo que no se puede cancelar a
# mitad) y cortar el <audio> del frontend, todo coordinado entre procesos —
# mucha superficie para un beneficio dudoso. Ignorar garantiza además lo que
# importa: el micrófono NUNCA está abierto mientras suena la voz de Rem, así
# que no puede grabarse a sí misma. El pedido ignorado no es silencioso: se
# difunde un ptt_estado "ignorado" con el motivo (lo ve rem_ptt.py y la UI).
# "Rem habla" = turno de LLM en curso, o frases aún en la cola de síntesis, o
# algún frontend reportando audio sonando (voz_estado), o menos de
# [stt].espera_tras_habla_s desde el último audio.
# Todo lo de esta sección corre en _ws_loop (un solo hilo): sin locks.
_ptt_estado       = "idle"    # idle | iniciando | grabando | transcribiendo
_ptt_grabador     = None
_ptt_tope_handle  = None      # call_later del tope de grabación
_ptt_stop_pedido  = False     # ptt_stop llegado mientras aún se abría el micrófono
_ptt_stop_huerfano_t = 0.0    # ptt_stop sin start previo (toque corto: llegó antes que su start)
_ptt_medicion     = None      # {"t_suelta", "t_fin_voz", "t_stt", ...} hasta el primer audio sonando
_ptt_origen       = None      # quién abrió la grabación en curso: "tecla" | "boton" | "conversacion"
_ptt_auto         = None      # grabación en automático: {"detector", "origen", "motivo", "t"}
_ws_reproduciendo = set()     # websockets cuyo frontend reporta audio sonando (voz_estado)
_ultimo_fin_habla = 0.0       # time.monotonic() del último fin de voz/turno


# ── Confirmación de acciones (apagar_pc, ver acciones.py) ────────────────
# Un solo pendiente a la vez alcanza: los turnos ya están serializados por
# _chat_turno_activo (un chat_message nuevo se rechaza si hay uno en curso),
# así que no puede haber dos confirmaciones pedidas a la vez en este proceso.
_CONFIRMACION_TIMEOUT_S = 30.0
_confirmacion_pendiente = None  # asyncio.Future | None
_confirmacion_payload = None    # el accion_confirmar en curso, para quien conecte tarde


async def _pedir_confirmacion_accion(nombre: str, argumentos: dict, descripcion: str):
    """Pasado como on_confirmar_accion a chat_sesion.procesar_turno(). Manda
    accion_confirmar por WS y espera accion_confirmar_resp del mismo panel
    (ver _ws_handler). None = expiró sin respuesta — el llamador
    (acciones.ejecutar_tool_async) lo traduce a ConfirmacionExpirada."""
    global _confirmacion_pendiente, _confirmacion_payload
    loop = asyncio.get_running_loop()
    _confirmacion_pendiente = loop.create_future()
    # En modo escritorio la ventana de chat puede estar cerrada: el avatar le
    # pide a rem_chat.py que la abra, y al conectarse (hola rol chat) recibe
    # este mismo pedido (ver _saludar_chat).
    _confirmacion_payload = {"tipo": "accion_confirmar", "nombre": nombre, "descripcion": descripcion}
    _broadcast_ws(_confirmacion_payload)
    try:
        return await asyncio.wait_for(_confirmacion_pendiente, timeout=_CONFIRMACION_TIMEOUT_S)
    except asyncio.TimeoutError:
        return None
    finally:
        _confirmacion_pendiente = None
        _confirmacion_payload = None


async def _saludar_chat(websocket):
    """Estado inicial para una ventana de chat (o un avatar) que acaba de conectar: el modo
    (ia/eco) y la voz no se mandan solos salvo al cambiar, y una ventana que se
    abre a mitad de sesión los necesita. Más una confirmación en curso, si la
    hay (se abrió justo para eso)."""
    sesion = _chat_sesion
    await websocket.send(json.dumps({"tipo": "modo_actual", "modo": sesion.modo if sesion else "ia"}))
    await websocket.send(json.dumps({"tipo": "voz_actual", "activa": _chat_voz_activa}))
    if _confirmacion_payload is not None:
        await websocket.send(json.dumps(_confirmacion_payload))


def _registrar_voz_sonando():
    """voz_sonando del frontend: el <audio> disparó 'playing' (suena de verdad).
    Cierra la medición del push-to-talk con las dos cifras: hasta que la página
    recibió el audio y hasta que empezó a sonar."""
    global _ptt_medicion
    m = _ptt_medicion
    if m is None:
        return
    _ptt_medicion = None
    ahora = time.perf_counter()
    ref = m.get("t_fin_voz", m["t_suelta"])
    recibido = f"{m['t_recibido'] - ref:.2f}s" if "t_recibido" in m else "n/d"
    print(f"  [PTT] medición: {'fin de frase automático' if m.get('auto') else 'suelto la tecla'} "
          f"| desde que dejó de hablar: audio recibido en la página {recibido}, "
          f"SONANDO {ahora - ref:.2f}s (desde soltar/cortar: {ahora - m['t_suelta']:.2f}s) "
          f"| STT {m['t_stt']:.2f}s de {m['dur']:.1f}s de audio | energía: {m.get('energia', 'n/d')}",
          flush=True)


def _marcar_fin_habla():
    global _ultimo_fin_habla
    _ultimo_fin_habla = time.monotonic()


def _registrar_voz_estado(websocket, reproduciendo: bool):
    """voz_estado del frontend: su cola de audio recibió algo (True, al LLEGAR el
    audio a la página, antes de play()) o se vació (False). Es la única forma de
    saber que Rem sigue hablando cuando el turno de LLM y la síntesis ya
    terminaron pero el <audio> todavía suena. Para la medición del push-to-talk
    solo apunta cuándo llegó: la cierra voz_sonando (_registrar_voz_sonando)."""
    if reproduciendo:
        _ws_reproduciendo.add(websocket)
        m = _ptt_medicion
        if m is not None and "t_recibido" not in m:
            m["t_recibido"] = time.perf_counter()
    else:
        _ws_reproduciendo.discard(websocket)
        _marcar_fin_habla()


def _ptt_motivo_ocupada():
    """Por qué NO se puede empezar a grabar ahora, o None si se puede."""
    if _ptt_estado != "idle":
        return {"iniciando": "ya se está abriendo el micrófono",
                "grabando": "ya se está grabando",
                "transcribiendo": "todavía transcribiendo lo anterior"}[_ptt_estado]
    import personalidad as _personalidad
    nombre = _personalidad.NOMBRE_PERSONAJE
    if _chat_turno_activo:
        return f"{nombre} está respondiendo"
    cola = _chat_cola_habla
    # _unfinished_tasks: lo que Queue.join() espera — frases encoladas O en
    # síntesis que el worker aún no marcó con task_done().
    if cola is not None and getattr(cola, "_unfinished_tasks", 0) > 0:
        return f"{nombre} está preparando su voz"
    if _ws_reproduciendo:
        return f"{nombre} está hablando"
    import stt
    if time.monotonic() - _ultimo_fin_habla < stt.leer_config_stt()["espera_tras_habla_s"]:
        return f"{nombre} acaba de terminar de hablar"
    return None


def _motivo_no_decir_frase():
    """Por qué una frase fija del avatar (frases_voz.py) NO se dice ahora, o
    None. Nunca encima de otra voz ni cortando una respuesta del chat, ni con el
    micrófono abierto (se grabaría a sí misma), ni con la voz apagada."""
    if not _chat_voz_activa:
        return "voz apagada"
    if _ptt_estado != "idle":
        return "micrófono abierto"
    if _chat_turno_activo:
        return "respondiendo"
    cola = _chat_cola_habla
    if cola is not None and getattr(cola, "_unfinished_tasks", 0) > 0:
        return "voz en cola"
    if _ws_reproduciendo:
        return "ya está hablando"
    return None


async def _decir_frase(texto: str):
    """Mensaje decir_frase de la página del avatar: una frase fija con voz,
    desde la caché de frases_voz (sintetizada al arrancar)."""
    import frases_voz
    if texto not in frases_voz.textos():
        logger.warning("[Frases] decir_frase con un texto que no está en frases_escritorio.json: %r", texto)
        return
    motivo = _motivo_no_decir_frase()
    if motivo:
        print(f"  [Frases] \"{texto}\" solo en texto ({motivo})", flush=True)
        return
    r = await asyncio.to_thread(frases_voz.obtener, texto)
    # Se vuelve a mirar: la síntesis (si no estaba en caché) da tiempo a que
    # haya empezado una respuesta.
    if r and _motivo_no_decir_frase() is None:
        enviar_audio(*r)
        print(f"  [Frases] \"{texto}\" con voz", flush=True)


def _ptt_estado_ws(estado: str, **extra):
    _broadcast_ws({"tipo": "ptt_estado", "estado": estado, **extra})


# ── Micrófono en automático y veredicto (etapa 5) ────────────────────────
# Dos formas de grabar:
#   - "tecla": push-to-talk de siempre (ptt_start/ptt_stop: SUPER+H, o mantener
#     el botón 🎙 del chat más de 260 ms). Graba hasta que se suelta.
#   - "auto": un toque del botón 🎙 (mensaje mic_toque) o el modo conversación.
#     stt/analisis.FinDeFrase escucha cada bloque y corta solo: tras 1 s de
#     silencio después de la voz, a los 15 s de voz, si el micrófono no manda
#     nada en 4 s o (conversación) si nadie habla en cierre_inactividad_s.
# En los dos, antes de transcribir se mide la grabación (stt/analisis.veredicto:
# enviar / sin voz / silencio / micrófono muerto) y después se descartan las
# frases que Whisper se inventa con casi nada de voz. Cada veredicto se manda
# como mic_veredicto (lo pinta el chat, la caja del overlay y la burbuja).
_MENSAJES_VEREDICTO = {
    "enviar": "🎙 Voz detectada ({voz})",
    "sin_voz": "🎙 No escuché tu voz (el micrófono sí manda audio).",
    "silencio": "🎙 No llegó audio del micrófono.",
    "muerto": "🎙 El micrófono no manda nada: ¿está silenciado o desconectado? Revisa la entrada de audio del sistema.",
    "inventada": "🎙 Descartado: «{texto}» parece inventado por Whisper (solo {voz} de voz).",
    "espera": "🎙 Nadie habló: cierro el micrófono.",
}


def _emitir_veredicto(tipo: str, v=None, texto: str = ""):
    voz = f"{v.voz_ms / 1000:.1f} s de voz".replace(".", ",") if v and tipo == "enviar" else \
          (f"{v.voz_ms:.0f} ms" if v else "")
    mensaje = _MENSAJES_VEREDICTO[tipo].format(voz=voz, texto=texto)
    _broadcast_ws({"tipo": "mic_veredicto", "veredicto": tipo, "mensaje": mensaje,
                   "voz_ms": round(v.voz_ms) if v else 0, "dur_s": round(v.dur_s, 2) if v else 0},
                  avisar=False)


# Modo conversación: tras un turno POR VOZ cuya respuesta termina en "?", el
# micrófono se reabre en automático (ver _reabrir_conversacion). Sin etiqueta
# nueva del modelo: lo decide el texto. Un mensaje escrito o una respuesta que
# no pregunta lo cierra; también nadie hablando en cierre_inactividad_s.
_conv_activa = False
_conv_tarea = None


def _conversacion(activa: bool, motivo: str = ""):
    global _conv_activa, _conv_tarea
    if not activa and _conv_tarea is not None and not _conv_tarea.done():
        _conv_tarea.cancel()
    if activa == _conv_activa:
        return
    _conv_activa = activa
    print(f"  [Mic] modo conversación {'ON' if activa else 'OFF'}{f' ({motivo})' if motivo else ''}", flush=True)
    _broadcast_ws({"tipo": "conversacion", "activa": activa, "motivo": motivo}, avisar=False)


def _respuesta_pregunta(texto: str) -> bool:
    import re
    return bool(re.search(r"\?[\s\"'»”’)…\.]*$", texto or ""))


async def _reabrir_conversacion():
    """Espera a que Yoru termine de hablar (turno, cola de voz y audio sonando,
    más el margen de eco) y reabre el micrófono en automático
    reabrir_tras_s después."""
    import stt
    cfg = stt.leer_config_stt()
    try:
        limite = time.monotonic() + 120
        while time.monotonic() < limite:
            if _ptt_motivo_ocupada() is None and time.monotonic() - _ultimo_fin_habla >= cfg["reabrir_tras_s"]:
                break
            await asyncio.sleep(0.05)
        else:
            _conversacion(False, "Yoru no terminó de hablar")
            return
        await _ptt_iniciar(auto=True, espera_voz_s=cfg["cierre_inactividad_s"], origen="conversacion")
    except asyncio.CancelledError:
        pass


async def _ptt_iniciar(auto: bool = False, espera_voz_s: float | None = None, origen: str = "tecla"):
    global _ptt_estado, _ptt_grabador, _ptt_tope_handle, _ptt_stop_pedido, _ptt_auto, _ptt_origen
    if time.monotonic() - _ptt_stop_huerfano_t < 0.3 and origen == "tecla":
        # El stop de un toque corto llegó ANTES que su start (son dos procesos
        # de rem_ptt.py): grabar ahora dejaría el micrófono abierto hasta el tope.
        print("  [PTT] ptt_start ignorado: su ptt_stop ya había llegado (toque corto)", flush=True)
        _ptt_estado_ws("idle", nota="toque muy corto")
        return
    motivo = _ptt_motivo_ocupada()
    if motivo:
        print(f"  [PTT] ptt_start ignorado: {motivo}", flush=True)
        if _ptt_estado == "idle":  # un start repetido durante una grabación no debe pisar la UI
            _ptt_estado_ws("ignorado", motivo=motivo)
        if origen == "conversacion":
            _conversacion(False, motivo)
        return
    if origen != "conversacion" and _conv_tarea is not None and not _conv_tarea.done():
        _conv_tarea.cancel()   # se adelantó a mano: la reapertura pendiente sobra

    import stt
    from stt import SAMPLE_RATE
    from stt.analisis import ConfigVoz, FinDeFrase
    from stt.microfono import Grabador
    cfg = stt.leer_config_stt()
    _ptt_estado, _ptt_stop_pedido = "iniciando", False
    _ptt_origen = origen
    al_bloque = None
    _ptt_auto = None
    # Tope de seguridad (por si se pierde el stop): en automático, por detrás
    # de lo que el detector puede tardar en cortar solo (esperar la voz + la
    # frase más larga), para que gane siempre su motivo y no el tope.
    tope_s = cfg["max_grabacion_s"]
    if auto:
        cfg_voz = ConfigVoz.desde_config()
        tope_s = max(tope_s, (espera_voz_s or cfg_voz.muerto_temprano_s) + cfg_voz.max_voz_s + 2)
        loop = asyncio.get_running_loop()
        detector = FinDeFrase(SAMPLE_RATE, cfg_voz, espera_voz_s=espera_voz_s)
        _ptt_auto = {"detector": detector, "origen": origen, "motivo": None}

        def al_bloque(bloque, _det=detector, _estado=_ptt_auto):
            if _estado["motivo"] is not None:
                return
            r = _det.alimentar(bloque)
            if r:
                _estado["motivo"] = r
                _estado["t"] = time.perf_counter()
                loop.call_soon_threadsafe(lambda: asyncio.create_task(_ptt_detener(motivo_auto=r)))
    grabador = Grabador(max_s=tope_s, dispositivo=cfg["dispositivo_entrada"], al_bloque=al_bloque)
    try:
        await asyncio.to_thread(grabador.iniciar)
    except Exception as e:
        _ptt_estado = "idle"
        logger.exception("[PTT] no se pudo abrir el micrófono")
        _broadcast_ws({"tipo": "error", "mensaje": f"No se pudo abrir el micrófono: {e}"})
        _ptt_estado_ws("idle")
        _conversacion(False, "no se pudo abrir el micrófono")
        return
    _ptt_grabador, _ptt_estado = grabador, "grabando"
    _ptt_tope_handle = asyncio.get_running_loop().call_later(
        tope_s, lambda: asyncio.create_task(_ptt_detener(por_tope=True)))
    print(f"  [PTT] grabando ({'automático' if auto else 'mantenido'}, {origen})...", flush=True)
    _ptt_estado_ws("escuchando", auto=auto, origen=origen)
    if _ptt_stop_pedido:  # el stop llegó mientras se abría el micrófono
        await _ptt_detener()


async def _ptt_detener(por_tope: bool = False, motivo_auto: str | None = None):
    global _ptt_estado, _ptt_grabador, _ptt_tope_handle, _ptt_stop_pedido, _ptt_stop_huerfano_t, _ptt_medicion, _ptt_auto
    if _ptt_estado == "iniciando":
        _ptt_stop_pedido = True
        return
    if _ptt_estado != "grabando":
        _ptt_stop_huerfano_t = time.monotonic()
        # Siempre se contesta (rem_ptt.py espera una confirmación): con el
        # estado actual, para no pisar una UI que está transcribiendo.
        _ptt_estado_ws(_ptt_estado, nota="no estaba grabando")
        return
    auto, _ptt_auto = _ptt_auto, None
    # Fin de frase: el instante en que el detector lo decidió (en su hilo), o
    # cuando llegó el stop. "Dejó de hablar" = eso menos el silencio de espera.
    t_suelta = (auto or {}).get("t") or time.perf_counter()
    t_fin_voz = t_suelta
    if auto and auto["detector"].fin_voz_s is not None:
        t_fin_voz = t_suelta - max(0.0, auto["detector"].t - auto["detector"].fin_voz_s)
    origen = auto["origen"] if auto else "tecla"
    if _ptt_tope_handle is not None:
        _ptt_tope_handle.cancel()
        _ptt_tope_handle = None
    grabador, _ptt_grabador = _ptt_grabador, None
    audio = await asyncio.to_thread(grabador.detener)

    import stt
    from stt import SAMPLE_RATE
    from stt.analisis import ConfigVoz, es_inventada, veredicto
    cfg = stt.leer_config_stt()
    cfg_voz = ConfigVoz.desde_config()
    dur = len(audio) / SAMPLE_RATE
    if por_tope:
        print(f"  [PTT] tope de {cfg['max_grabacion_s']:.0f}s alcanzado — se corta la grabación", flush=True)
    if motivo_auto:
        print(f"  [PTT] fin automático: {motivo_auto} ({dur:.2f}s grabados)", flush=True)

    def _terminar(nota=""):
        global _ptt_estado
        _ptt_estado = "idle"
        _ptt_estado_ws("idle", nota=nota)

    if motivo_auto == "espera" and origen == "conversacion":
        # Modo conversación sin que nadie hablara: no hay nada que transcribir.
        _emitir_veredicto("espera")
        _terminar()
        _conversacion(False, f"{cfg['cierre_inactividad_s']:.0f} s sin hablar")
        return
    if dur < cfg["min_grabacion_s"] and not auto:
        print(f"  [PTT] grabación de {dur:.2f}s descartada (< {cfg['min_grabacion_s']}s)", flush=True)
        _terminar("grabación muy corta")
        return

    v = await asyncio.to_thread(veredicto, audio, SAMPLE_RATE, cfg_voz)
    print(f"  [Mic] veredicto {v.resumen()}", flush=True)
    if v.tipo != "enviar":
        _emitir_veredicto(v.tipo, v)
        _terminar()
        _conversacion(False, "sin voz")
        return

    _ptt_estado = "transcribiendo"
    _ptt_estado_ws("transcribiendo")
    try:
        t0 = time.perf_counter()
        texto = await asyncio.to_thread(stt.obtener_stt().transcribir, audio)
        t_stt = time.perf_counter() - t0
    except Exception as e:
        logger.exception("[PTT] falló la transcripción")
        _broadcast_ws({"tipo": "error", "mensaje": f"Falló la transcripción: {e}"})
        _terminar()
        _conversacion(False, "falló la transcripción")
        return
    from llm._energia import estado_alimentacion, perfil_cpu
    energia = f"{estado_alimentacion()}; {perfil_cpu()}"
    voz_s = v.voz_ms / 1000
    print(f"  [PTT] STT: {dur:.2f}s de audio ({voz_s:.2f}s de voz) -> {t_stt:.2f}s "
          f"({t_stt / max(dur, 1e-3):.2f}x el audio, {t_stt / max(voz_s, 1e-3):.2f}x la voz) "
          f"| energía: {energia} | {texto!r}", flush=True)

    if not texto:
        _emitir_veredicto("sin_voz", v)
        _terminar("no se entendió nada")
        _conversacion(False, "no se entendió nada")
        return
    if es_inventada(texto, v.voz_ms, cfg_voz):
        print(f"  [Mic] descartada por inventada: {texto!r} con {v.voz_ms:.0f} ms de voz", flush=True)
        _emitir_veredicto("inventada", v, texto=texto.strip())
        _terminar()
        _conversacion(False, "frase inventada")
        return
    _emitir_veredicto("enviar", v)

    # Se enseña lo entendido (caja del overlay, burbuja del escritorio, burbuja
    # del chat) y el turno arranca YA: `ms` es solo cuánto lo enseña la UI, no
    # una espera (antes el servidor esperaba ese tiempo antes de mandarlo al
    # LLM: 1 s más de latencia). Entre _terminar() y el flag del turno no hay
    # ningún await, así que un ptt_start no puede colarse en medio.
    _broadcast_ws({"tipo": "ptt_transcripcion", "texto": texto,
                   "ms": int(cfg["mostrar_transcripcion_s"] * 1000)})
    _terminar()
    _ptt_medicion = {"t_suelta": t_suelta, "t_fin_voz": t_fin_voz, "t_stt": t_stt, "dur": dur,
                     "auto": bool(auto), "energia": energia}
    respuesta = await _procesar_mensaje_chat(texto, t_ref=t_fin_voz, por_voz=True)

    # Modo conversación: la respuesta pregunta algo -> se reabre el micrófono.
    import preferencias
    if respuesta is not None and preferencias.obtener("microfono")["conversacion"] \
            and _respuesta_pregunta(respuesta):
        global _conv_tarea
        _conversacion(True, "la respuesta pregunta algo")
        _conv_tarea = asyncio.create_task(_reabrir_conversacion())
    elif _conv_activa:
        _conversacion(False, "la respuesta no pregunta nada")


# Pulsadores que mandan ptt_start/ptt_stop: SUPER+H (rem_ptt.py) y mantener el
# botón 🎙 del chat. Cualquier otro valor cuenta como "tecla" (compatibilidad).
ORIGENES_PULSADOR = ("tecla", "boton")


def _origen_pulsador(data: dict) -> str:
    o = data.get("origen")
    return o if o in ORIGENES_PULSADOR else "tecla"


async def _ptt_stop_de(websocket, origen: str):
    """ptt_stop de un pulsador. Solo corta la grabación que abrió ESE pulsador:
    el bindrt de Hyprland manda un stop cada vez que se suelta Super, por
    cualquier motivo, y antes eso cortaba también una grabación automática del
    botón a los 0,15 s (visto en la prueba con el micrófono real). Una
    grabación automática solo la cortan su detector u otro toque del botón."""
    if _ptt_estado in ("iniciando", "grabando") and _ptt_origen != origen:
        tipo = "automática" if _ptt_auto is not None else "mantenida"
        nota = f"stop de {origen} ignorado: la grabación es {tipo} ({_ptt_origen})"
        print(f"  [PTT] {nota}", flush=True)
        # Solo a quien lo mandó (rem_ptt.py espera una confirmación): las
        # interfaces siguen en "escuchando", no hay nada que repintar.
        try:
            await websocket.send(json.dumps({"tipo": "ptt_estado", "estado": "escuchando", "nota": nota}))
        except Exception:
            pass
        return
    await _ptt_detener()


async def _mic_toque():
    """Un toque del botón 🎙 del chat: si no graba, abre en automático; si ya
    graba en automático, corta ahora (lo dicho se procesa)."""
    if _ptt_estado == "grabando":
        if _ptt_auto is not None and _ptt_auto["motivo"] is None:
            _ptt_auto["motivo"] = "manual"
            _ptt_auto["t"] = time.perf_counter()
        await _ptt_detener(motivo_auto="manual" if _ptt_auto else None)
    elif _ptt_estado == "idle":
        import stt
        await _ptt_iniciar(auto=True, origen="boton", espera_voz_s=stt.leer_config_stt()["espera_voz_toque_s"])


# ── Preferencias del panel de control (preferencias.py) ───────────────
# prefs_get -> prefs_estado {prefs, propias, modo} (solo a quien pregunta)
# prefs_set {seccion, cambios, id?} -> prefs_actualizadas {seccion, prefs, propias, id}
#     (a TODOS: el avatar y cualquier otro panel abierto tienen que enterarse)
#   o prefs_error {seccion, mensaje, id}          (solo a quien pidió)
# `id` es opcional y vuelve tal cual: el panel lo usa para saber qué control se
# guardó o falló. `propias` = claves que vienen de preferencias.json (el resto
# es config.toml). No es `error` a secas: ese lo muestra el panel de chat como
# burbuja, y un parche rechazado es asunto del panel de control que lo mandó.
async def _enviar_prefs_estado(websocket):
    import preferencias
    # modo (ventana|overlay): el panel avisa que en overlay no hay clips VRMA.
    await websocket.send(json.dumps({"tipo": "prefs_estado", "prefs": preferencias.todas(),
                                     "propias": preferencias.propias(), "modo": _modo_actual,
                                     "llm": _info_llm()}))


async def _aplicar_prefs(websocket, seccion, cambios, peticion_id=None):
    import preferencias
    try:
        # to_thread: escribe a disco y corre los oyentes de la sección, que no
        # tienen por qué ser instantáneos — el loop del WS sigue atendiendo.
        efectivos = await asyncio.to_thread(preferencias.aplicar, seccion, cambios)
    except Exception as e:
        # PreferenciaInvalida trae un mensaje para el usuario; cualquier otra
        # cosa (disco lleno, permisos) también se contesta, en vez de dejar que
        # suba y cierre la conexión del panel.
        mensaje = str(e) if isinstance(e, preferencias.PreferenciaInvalida) \
            else f"no se pudo guardar ({type(e).__name__}: {e})"
        logger.warning("[Prefs] prefs_set rechazado: %s", mensaje)
        await websocket.send(json.dumps({"tipo": "prefs_error", "seccion": seccion,
                                         "mensaje": mensaje, "id": peticion_id}))
        return
    _broadcast_ws({"tipo": "prefs_actualizadas", "seccion": seccion, "prefs": efectivos,
                   "propias": preferencias.propias().get(seccion, []), "id": peticion_id},
                  destino=("avatar", "panel", "chat"), avisar=False)


# ── Servidor WebSocket ────────────────────────────────────────────────
async def _ws_handler(websocket):
    from websockets.exceptions import ConnectionClosed

    with _ws_lock:
        _ws_clients.add(websocket)
    try:
        async for mensaje in websocket:
            try:
                data = json.loads(mensaje)
            except (json.JSONDecodeError, TypeError):
                continue
            tipo = data.get("tipo") if isinstance(data, dict) else None

            if tipo == "hola":
                rol = str(data.get("rol") or "")
                if rol in ROLES_WS:
                    with _ws_lock:
                        _ws_roles[websocket] = rol
                    logger.info("[Avatar] cliente WS identificado: %s", rol)
                    if rol in ("chat", "avatar", "panel"):
                        await _saludar_chat(websocket)
                else:
                    logger.warning("[Avatar] 'hola' con rol desconocido: %r (no cuenta como destinatario)", rol)

            elif tipo == "chat_message":
                texto = str(data.get("texto") or "").strip()
                if texto:
                    # create_task, no await: así _ws_handler sigue leyendo el
                    # socket (p.ej. un 'reset') mientras el turno corre.
                    asyncio.create_task(_procesar_mensaje_chat(texto))

            elif tipo == "cambiar_modo":
                try:
                    cambiar_modo_chat(data.get("modo"))
                except Exception as e:
                    _broadcast_ws({"tipo": "error", "mensaje": str(e)})

            elif tipo == "reset":
                sesion, _, _ = obtener_sesion_chat()
                sesion.historial.clear()

            elif tipo == "voz":
                await _aplicar_prefs(websocket, "voz", {"activa": bool(data.get("activa"))})

            elif tipo == "voz_estado":
                # El frontend avisa cuándo su cola de audio empieza a sonar / se
                # vacía — el push-to-talk lo necesita para no grabar a Rem.
                _registrar_voz_estado(websocket, bool(data.get("reproduciendo")))

            elif tipo == "voz_sonando":
                # El <audio> empezó a sonar de verdad ('playing'): cierra la
                # medición de latencia del push-to-talk.
                _registrar_voz_sonando()

            elif tipo == "accion_confirmar_resp":
                # Respuesta del panel a un accion_confirmar (ver
                # _pedir_confirmacion_accion) — si ya no hay nadie esperando
                # (expiró, o llegó una segunda respuesta) se ignora en
                # silencio, no es un error del cliente.
                if _confirmacion_pendiente is not None and not _confirmacion_pendiente.done():
                    _confirmacion_pendiente.set_result(bool(data.get("ok")))

            elif tipo == "ptt_start":
                asyncio.create_task(_ptt_iniciar(origen=_origen_pulsador(data)))

            elif tipo == "mic_toque":
                asyncio.create_task(_mic_toque())

            elif tipo == "ptt_stop":
                asyncio.create_task(_ptt_stop_de(websocket, _origen_pulsador(data)))

            elif tipo == "estado":
                # Un cliente (p.ej. bench_chat.py conectado como cliente WS,
                # ver su comando 'state') pide poner el avatar en un estado.
                # Se valida y se re-difunde a TODOS los clientes vía
                # enviar_estado() — así la ventana lo ve aunque el pedido
                # venga de otro proceso.
                est = str(data.get("estado") or "").lower()
                if est in ESTADOS_VALIDOS:
                    enviar_estado(est)
                else:
                    _broadcast_ws({"tipo": "error",
                                   "mensaje": f"estado inválido: {est!r}"})

            elif tipo == "debug_clip":
                # Depuración (comando 'clip <nombre>' de bench_chat.py): igual
                # que 'estado', se re-difunde a TODOS los clientes, porque el
                # pedido puede venir de otro proceso (bench_chat.py en modo
                # cliente) y el avatar vive en el WebView de rem_chat.py.
                nombre = str(data.get("nombre") or "").strip()
                if nombre:
                    enviar_debug_clip(nombre)
                else:
                    _broadcast_ws({"tipo": "error",
                                   "mensaje": "debug_clip sin 'nombre'"})

            elif tipo == "prefs_get":
                await _enviar_prefs_estado(websocket)

            elif tipo == "modelos_get":
                # Los VRM locales de models/vrm/ (selector de modelo de la
                # ventana y del panel). Solo a quien pregunta.
                import modelos_vrm
                await websocket.send(json.dumps({
                    "tipo": "modelos_lista", "modelos": await asyncio.to_thread(modelos_vrm.listar)}))

            elif tipo == "emocion":
                # Depuración (comando 'emocion <x>' de bench_chat.py): se
                # re-difunde como 'estado'/'debug_clip'.
                emo = str(data.get("emocion") or "").lower()
                if emo in EMOCIONES_VALIDAS:
                    enviar_emocion(emo)
                else:
                    _broadcast_ws({"tipo": "error", "mensaje": f"emoción inválida: {emo!r}"})

            elif tipo == "decir_frase":
                texto = str(data.get("texto") or "")
                if texto:
                    asyncio.create_task(_decir_frase(texto))

            elif tipo == "latido_pagina":
                global ultimo_latido_pagina
                ultimo_latido_pagina = time.monotonic()

            elif tipo == "escritorio":
                datos = data.get("datos")
                if _oyente_escritorio is not None and isinstance(datos, dict):
                    _oyente_escritorio(datos)

            elif tipo == "panel_pestana":
                # Abrir el panel de control en una pestaña (menú del avatar): se
                # le reenvía al panel si ya está abierto; si no, escritorio.py lo
                # lanza con --pestana.
                pid = str(data.get("id") or "")
                if pid:
                    _broadcast_ws({"tipo": "panel_pestana", "id": pid}, destino=("panel",), avisar=False)

            elif tipo == "al_avatar":
                # Ventana de chat (modo escritorio) -> página del avatar: pedir
                # la lista de clips, disparar uno, modo baile. Lo resuelve la
                # página del avatar, que es la que tiene el catálogo y el mixer.
                cmd = data.get("cmd")
                if isinstance(cmd, dict) and cmd.get("que") in CMDS_AL_AVATAR:
                    _broadcast_ws({**cmd, "tipo": "cmd_avatar"}, destino=DESTINO_AVATAR)

            elif tipo == "del_avatar":
                # Página del avatar -> ventana(s) de chat: lo que pidió, o avisos
                # (clip lanzado, modelo cargado). Sin aviso si no hay chat abierto.
                info = data.get("info")
                if isinstance(info, dict) and info.get("que") in INFOS_DEL_AVATAR:
                    _broadcast_ws({**info, "tipo": "info_avatar"}, destino=("chat",), avisar=False)

            elif tipo == "prefs_set":
                await _aplicar_prefs(websocket, data.get("seccion"), data.get("cambios"),
                                     data.get("id"))

            # cualquier otro tipo (o mensaje sin 'tipo') se ignora — el
            # cliente no manda nada más que el servidor necesite procesar.
    except ConnectionClosed as e:
        # Cierre normal (pestaña cerrada, recargada, etc.) — no es un error real,
        # no hace falta el traceback completo de ConnectionClosedError/OK.
        logger.info("[Avatar] cliente WS desconectado (%s)", type(e).__name__)
    finally:
        with _ws_lock:
            _ws_clients.discard(websocket)
            _ws_roles.pop(websocket, None)
        _ws_reproduciendo.discard(websocket)


_ws_bind_error = None  # excepción del bind, si falló — para que iniciar_servidor_avatar() la reporte

async def _iniciar_ws():
    """`_ws_ready.set()` va DESPUÉS de que websockets.serve() tenga éxito, no
    antes. El bug original: si el puerto ya estaba ocupado (otra instancia
    corriendo), websockets.serve() lanzaba OSError dentro de este hilo daemon
    — que muere en silencio, sin propagarse — pero _ws_ready ya había quedado
    en True desde antes de intentar el bind, así que el llamador nunca se
    enteraba del fallo (ver CLAUDE.md, "Conflicto de puertos").
    Ahora _iniciar_ws() no silencia el fallo: lo guarda en _ws_bind_error y
    deja _ws_ready sin activar, para que iniciar_servidor_avatar() lo note.
    De todos modos iniciar_servidor_avatar() ya chequea _puerto_activo()
    antes de intentar el bind, así que este camino casi no se toca."""
    global _ws_loop, _ws_bind_error
    _ws_loop = asyncio.get_running_loop()
    import websockets
    try:
        server = await websockets.serve(_ws_handler, "127.0.0.1", WS_PORT,
                                        origins=WS_ORIGENES_PERMITIDOS)
    except OSError as e:
        _ws_bind_error = e
        logger.error("[Avatar] no se pudo abrir el WebSocket en :%d (%s)", WS_PORT, e)
        return
    _ws_ready.set()
    async with server:
        await asyncio.Future()


def _thread_ws():
    asyncio.run(_iniciar_ws())


def _puerto_activo(host: str, port: int, timeout: float = 0.3) -> bool:
    """True si algo ya está escuchando en host:port. Se usa para detectar un
    servidor de avatar ya corriendo en otro proceso, en vez de intentar
    levantar uno nuevo y competir por el mismo puerto — la causa raíz del bug
    de _ws_ready de arriba."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class ServidorOcupadoError(RuntimeError):
    """Ya hay un servidor de avatar (otra instancia) en :HTTP_PORT/:WS_PORT y
    quien llamó pidió no reusarlo (permitir_reuso=False)."""


def iniciar_servidor_avatar(permitir_reuso: bool = True) -> bool:
    """Levanta HTTP (:18765) + WS (:18766) si no están corriendo ya en otro
    proceso.

    permitir_reuso=True (default; bench_chat.py): si ya hay un
    servidor lo detecta vía _puerto_activo() y lo reusa sin competir por el
    puerto. permitir_reuso=False (rem_chat.py, la aplicación): un servidor ya
    corriendo es un ERROR — lanza ServidorOcupadoError en vez de abrir una
    segunda ventana pegada a un servidor ajeno.

    Devuelve True si el servidor (este proceso u otro) queda disponible; False
    si no pudo levantar (el motivo queda impreso)."""
    ocupados = [p for p in (HTTP_PORT, WS_PORT) if _puerto_activo("127.0.0.1", p)]
    if ocupados:
        if not permitir_reuso:
            raise ServidorOcupadoError(
                "ya hay un servidor de Rem escuchando en " + ", ".join(f":{p}" for p in ocupados))
        print(f"[Avatar] Servidor ya corriendo en :{HTTP_PORT} — reusando, no se levanta uno nuevo.")
        return True

    _iniciar_voz_desde_prefs()
    th_http = threading.Thread(target=_iniciar_http, daemon=True, name="AvatarHTTP")
    th_http.start()
    # Sin esperar el bind, un fallo (otra instancia ganó la carrera por el
    # puerto entre el chequeo de arriba y este bind) pasaba inadvertido.
    if not _http_ready.wait(timeout=5.0):
        print(f"[Avatar] el servidor HTTP no pudo levantar en :{HTTP_PORT} "
              f"({_http_bind_error or 'timeout esperando el bind'}).")
        return False

    th_ws = threading.Thread(target=_thread_ws, daemon=True, name="AvatarWS")
    th_ws.start()

    if not _ws_ready.wait(timeout=5.0):
        print(f"[Avatar] el WebSocket no pudo levantar en :{WS_PORT} "
              f"({_ws_bind_error or 'timeout esperando el bind'}) — "
              "el avatar puede no sincronizar estado/audio.")
        return False

    print(f"[Avatar] Servidor propio levantado: HTTP :{HTTP_PORT}, WS :{WS_PORT}")
    return True

