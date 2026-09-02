"""
Servidor para el avatar 3D de Rem.
  - HTTP  en :18765 → sirve rem_avatar.html, rem.vrm y los clips de Animaciones/
  - WS    en :18766 → bidireccional: Python -> browser (estado/audio/chat_*),
                       y browser -> Python (chat_message/cambiar_modo/reset/voz/
                       estado, ver _ws_handler/chat_sesion.py)

La ventana que muestra el avatar es rem_chat.py (GTK3 + WebKit2, decorada). Este
módulo solo levanta el servidor — no lanza ninguna ventana. rem_chat.py llama a
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

TMP_AUDIO_DIR   = os.path.join(BASE_DIR, "tmp_audio")
AUDIO_MAX_AGE_S = 5 * 60  # borrar audios servidos hace más de 5 minutos
os.makedirs(TMP_AUDIO_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# ── Clientes WebSocket conectados ────────────────────────────────────
_ws_clients = set()
_ws_lock    = threading.Lock()
_ws_loop    = None
_ws_ready   = threading.Event()   # se activa cuando el loop WS está listo

# Aviso "sin destinatarios" con antirrebote: si el avatar no está abierto, un
# turno de chat entero puede irse al vacío en silencio — hay que decirlo, pero
# sin spamear una línea por cada enviar_estado() de cada turno.
_ultimo_aviso_sin_clientes = 0.0

def _avisar_sin_destinatarios(que: str):
    global _ultimo_aviso_sin_clientes
    ahora = time.monotonic()
    if ahora - _ultimo_aviso_sin_clientes > 10.0:
        _ultimo_aviso_sin_clientes = ahora
        logger.warning("[Avatar] %s: ningún cliente WS conectado — el mensaje no llega a nadie "
                       "(¿está abierta la ventana de rem_chat.py?)", que)


def _emitir_ws(payload: dict, que: str) -> int:
    """Serializa y manda `payload` a todos los clientes WS. Devuelve a cuántos
    clientes se despachó (0 si el servidor no está listo o no hay nadie
    conectado — en ese caso avisa por log, con antirrebote). Único punto por
    el que salen mensajes Python -> browser: estado, audio y todos los del
    panel de chat (chat_delta/chat_done/modo_actual/error)."""
    if not _ws_ready.is_set() or _ws_loop is None:
        _avisar_sin_destinatarios(que)
        return 0
    with _ws_lock:
        clientes = set(_ws_clients)
    if not clientes:
        _avisar_sin_destinatarios(que)
        return 0
    msg = json.dumps(payload)
    async def _enviar():
        for ws in clientes:
            try:
                await ws.send(msg)
            except Exception:
                pass
    asyncio.run_coroutine_threadsafe(_enviar(), _ws_loop)
    return len(clientes)


def enviar_estado(estado: str) -> int:
    """Llamar desde cualquier hilo para mandar el estado al browser. Devuelve
    a cuántos clientes llegó (0 = nadie, con aviso en el log)."""
    return _emitir_ws({"estado": estado}, f"estado {estado!r}")


def _broadcast_ws(payload: dict) -> int:
    """Manda `payload` a todos los clientes WS conectados. Genérico — lo usan
    los mensajes del panel de chat (chat_delta/chat_done/modo_actual/error)."""
    return _emitir_ws(payload, f"mensaje {payload.get('tipo', '?')!r}")


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

    Devuelve True si había al menos un cliente WS conectado (y por tanto se envió).
    Si no hay clientes, no copia nada y devuelve False — quien llama debe usar el
    fallback de sounddevice en ese caso.
    """
    if not _ws_ready.is_set():
        _avisar_sin_destinatarios("audio")
        return False
    loop = _ws_loop
    if loop is None:
        _avisar_sin_destinatarios("audio")
        return False

    with _ws_lock:
        clientes = set(_ws_clients)
    if not clientes:
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

def enviar_estado_emocional(emocion: str):
    """Envía un estado emocional al avatar. Válidos: happy, sad, angry, surprised."""
    if emocion in ESTADOS_VALIDOS:
        enviar_estado(emocion)


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
        super().end_headers()

    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()


def _iniciar_http():
    srv = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), _LocalHandler)
    srv.serve_forever()


# ── Chat de texto (panel HTML de rem_chat.py + REPL de bench_chat.py) ──
# Ver chat_sesion.py para SesionChat/procesar_turno(). Todo perezoso: se
# construye recién en el primer chat_message/cambiar_modo/reset real, no al
# importar este módulo — Rem.py también importa rem_avatar_server pero tiene
# su propio pipeline de conversación aparte, no necesita esto, y no debería
# pagar el costo de get_provider()/leer memoria (ni arriesgarse a que
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
# mismo RVC (habla._rvc_cache/_rvc_lock), pero no la cola: cada turno se
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


def voz_chat_activa() -> bool:
    return _chat_voz_activa


def set_voz_chat_activa(activa: bool) -> None:
    global _chat_voz_activa
    _chat_voz_activa = bool(activa)


def _obtener_cola_habla():
    """Crea la cola + worker de voz del panel la primera vez que hace falta.
    Debe llamarse siempre desde una coroutine que ya corre en _ws_loop (ver
    _procesar_mensaje_chat(), el único llamador) — asyncio.create_task() liga
    la tarea a ESE loop."""
    global _chat_cola_habla, _chat_worker_habla_task
    if _chat_cola_habla is None:
        from habla import worker_habla
        _chat_cola_habla = asyncio.Queue()
        _chat_worker_habla_task = asyncio.create_task(worker_habla(_chat_cola_habla, True))
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


async def _procesar_mensaje_chat(texto: str):
    """Maneja un chat_message del panel: corre el turno completo contra el
    LLM (chat_sesion.procesar_turno()) emitiendo chat_delta por cada
    fragmento tal como llega, y si la voz del panel está activa (ver
    voz_chat_activa()/set_voz_chat_activa()) también encola cada oración
    para hablar (TTS -> RVC -> enviar_audio, mismo pipeline que el REPL de
    bench_chat.py, ver habla.py) apenas dividir_en_oraciones() la completa.
    Mueve el estado del avatar a 'thinking' antes del primer fragmento y a
    'talking' con el primero — mismo canal (enviar_estado) que usa el resto
    del proyecto — así el indicador del panel y el cuerpo del avatar quedan
    en sintonía incluso en modo eco (sin audio real). Serializado con un
    flag simple (no una cola): un chat_message mientras ya hay un turno en
    curso se rechaza con error, en vez de interlear dos streams en el mismo
    panel."""
    global _chat_turno_activo
    with _chat_lock:
        if _chat_turno_activo:
            _broadcast_ws({"tipo": "error", "mensaje": "Rem ya está respondiendo — esperá a que termine."})
            return
        _chat_turno_activo = True

    from chat_sesion import procesar_turno
    sesion, memoria_larga, memoria_sistema = obtener_sesion_chat()

    enviar_estado("thinking")
    primer_fragmento = True

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
        await procesar_turno(sesion, texto, memoria_larga, memoria_sistema,
                              on_delta=_on_delta, cola_habla=cola_habla,
                              incluir_contexto=incluir_contexto)
        _broadcast_ws({"tipo": "chat_done"})
    except Exception as e:
        logger.exception("[Chat] error procesando turno")
        _broadcast_ws({"tipo": "error", "mensaje": str(e)})
    finally:
        enviar_estado("idle")
        with _chat_lock:
            _chat_turno_activo = False


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

            if tipo == "chat_message":
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
                set_voz_chat_activa(data.get("activa"))

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

            # cualquier otro tipo (o mensaje sin 'tipo') se ignora — el
            # cliente no manda nada más que el servidor necesite procesar.
    except ConnectionClosed as e:
        # Cierre normal (pestaña cerrada, recargada, etc.) — no es un error real,
        # no hace falta el traceback completo de ConnectionClosedError/OK.
        logger.info("[Avatar] cliente WS desconectado (%s)", type(e).__name__)
    finally:
        with _ws_lock:
            _ws_clients.discard(websocket)


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
        server = await websockets.serve(_ws_handler, "127.0.0.1", WS_PORT)
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


def iniciar_servidor_avatar() -> bool:
    """Levanta HTTP (:18765) + WS (:18766) si no están corriendo ya en otro
    proceso. Lo llama rem_chat.py (la aplicación) al arrancar. Si ya hay un
    servidor (p.ej. otra instancia de rem_chat.py, o bench_chat.py en modo
    standalone), lo detecta vía _puerto_activo() y no intenta levantar uno
    nuevo — así no se compite por el puerto.

    Devuelve True si el servidor (este proceso u otro) queda disponible."""
    if _puerto_activo("127.0.0.1", HTTP_PORT):
        print(f"[Avatar] Servidor ya corriendo en :{HTTP_PORT} — reusando, no se levanta uno nuevo.")
        return True

    th_http = threading.Thread(target=_iniciar_http, daemon=True, name="AvatarHTTP")
    th_http.start()

    th_ws = threading.Thread(target=_thread_ws, daemon=True, name="AvatarWS")
    th_ws.start()

    if not _ws_ready.wait(timeout=5.0):
        print(f"[Avatar] el WebSocket no pudo levantar en :{WS_PORT} "
              f"({_ws_bind_error or 'timeout esperando el bind'}) — "
              "el avatar puede no sincronizar estado/audio.")
        return False

    print(f"[Avatar] Servidor propio levantado: HTTP :{HTTP_PORT}, WS :{WS_PORT}")
    return True


# ── Compat: Rem.py (Tkinter, legacy) todavía llama a estas dos ────────
# El overlay GTK (rem_overlay.py) se eliminó — la ventana es rem_chat.py.
# iniciar_avatar() queda como alias de iniciar_servidor_avatar() para no
# romper Rem.py; cerrar_avatar() ya no tiene nada que cerrar (los hilos del
# servidor son daemon y mueren con el proceso).
def iniciar_avatar(screen_w=1920, screen_h=1080):
    return iniciar_servidor_avatar()


def cerrar_avatar():
    pass
