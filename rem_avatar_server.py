"""
Servidor para el avatar 3D de Rem.
  - HTTP  en :18765 → sirve rem_avatar.html y rem.vrm
  - WS    en :18766 → recibe estado desde Python, lo reenvía al browser
  - Lanza rem_overlay.py (GTK3 + WebKit2) como overlay transparente de escritorio
"""
import asyncio
import threading
import subprocess
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

def enviar_estado(estado: str):
    """Llamar desde cualquier hilo para mandar el estado al browser."""
    if not _ws_ready.is_set():
        return
    loop = _ws_loop
    if loop is None:
        return
    msg = json.dumps({"estado": estado})
    async def _broadcast():
        with _ws_lock:
            clientes = set(_ws_clients)
        for ws in clientes:
            try:
                await ws.send(msg)
            except Exception:
                pass
    asyncio.run_coroutine_threadsafe(_broadcast(), loop)


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
        return False
    loop = _ws_loop
    if loop is None:
        return False

    with _ws_lock:
        clientes = set(_ws_clients)
    if not clientes:
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


# ── Servidor WebSocket ────────────────────────────────────────────────
async def _ws_handler(websocket):
    from websockets.exceptions import ConnectionClosed

    with _ws_lock:
        _ws_clients.add(websocket)
    try:
        async for _ in websocket:
            pass  # el cliente no manda mensajes que el servidor necesite procesar
    except ConnectionClosed as e:
        # Cierre normal (pestaña cerrada, recargada, etc.) — no es un error real,
        # no hace falta el traceback completo de ConnectionClosedError/OK.
        logger.info("[Avatar] cliente WS desconectado (%s)", type(e).__name__)
    finally:
        with _ws_lock:
            _ws_clients.discard(websocket)


async def _iniciar_ws():
    global _ws_loop
    _ws_loop = asyncio.get_running_loop()
    _ws_ready.set()
    import websockets
    async with websockets.serve(_ws_handler, "127.0.0.1", WS_PORT):
        await asyncio.Future()


def _thread_ws():
    asyncio.run(_iniciar_ws())


# ── Lanzar overlay GTK transparente ──────────────────────────────────
_overlay_proc = None
_overlay_log  = None   # handle del archivo de log — mantenerlo vivo

LOG_OVERLAY = os.path.join(BASE_DIR, "rem_overlay.log")

def _lanzar_overlay(layer: str = 'top'):
    global _overlay_log
    overlay_script = os.path.join(BASE_DIR, "rem_overlay.py")
    try:
        # line-buffered (buffering=1) para que los prints lleguen inmediatamente al log
        _overlay_log = open(LOG_OVERLAY, 'w', buffering=1, encoding='utf-8')
        env = os.environ.copy()
        env['GDK_BACKEND'] = 'wayland'   # belt-and-suspenders junto al setenv interno
        # Diagnóstico: inspector remoto de WebKit — abrir http://127.0.0.1:9222
        # en un navegador normal para depurar el overlay como cualquier página.
        env['WEBKIT_INSPECTOR_SERVER'] = '127.0.0.1:9222'
        proc = subprocess.Popen(
            ["/usr/bin/python3", overlay_script, "--layer", layer],
            stdout=_overlay_log,
            stderr=_overlay_log,
            env=env,
        )
        print(f"[Avatar] Overlay log: {LOG_OVERLAY}  (tail -f para seguirlo)")
        return proc
    except Exception as e:
        print(f"[Avatar] No se pudo lanzar overlay: {e}")
        return None


# ── Iniciar todo ─────────────────────────────────────────────────────
def iniciar_avatar(screen_w=1920, screen_h=1080):
    """Llamar una vez al arrancar Rem."""
    global _overlay_proc

    # Capa configurable via REM_LAYER=top|overlay en el .env del proyecto
    layer = os.environ.get('REM_LAYER', 'top').lower()
    if layer not in ('top', 'overlay'):
        layer = 'top'

    th_http = threading.Thread(target=_iniciar_http, daemon=True, name="AvatarHTTP")
    th_http.start()

    th_ws = threading.Thread(target=_thread_ws, daemon=True, name="AvatarWS")
    th_ws.start()

    # Esperar a que el WS esté listo (máx 5s) antes de lanzar el overlay
    _ws_ready.wait(timeout=5.0)

    _overlay_proc = _lanzar_overlay(layer=layer)
    if _overlay_proc:
        print(f"[Avatar] Overlay GTK lanzado (PID {_overlay_proc.pid}) — capa: {layer.upper()}")
    else:
        print("[Avatar] No se pudo lanzar el overlay")


def cerrar_avatar():
    """Llamar al cerrar Rem."""
    global _overlay_proc, _overlay_log
    if _overlay_proc:
        try:
            _overlay_proc.terminate()
            _overlay_proc.wait(timeout=3)
        except Exception:
            pass
        _overlay_proc = None
    if _overlay_log:
        try:
            _overlay_log.close()
        except Exception:
            pass
        _overlay_log = None
