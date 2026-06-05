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
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
HTTP_PORT = 18765
WS_PORT   = 18766

# ── Clientes WebSocket conectados ────────────────────────────────────
_ws_clients = set()
_ws_lock    = threading.Lock()
_ws_loop    = None

def enviar_estado(estado: str):
    """Llamar desde cualquier hilo para mandar el estado al browser."""
    if _ws_loop is None:
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
    asyncio.run_coroutine_threadsafe(_broadcast(), _ws_loop)


# Estados válidos para el avatar
ESTADOS_VALIDOS = {'idle', 'talking', 'thinking', 'happy', 'sad', 'angry', 'surprised'}

def enviar_estado_emocional(emocion: str):
    """Envía un estado emocional al avatar. Válidos: happy, sad, angry, surprised."""
    if emocion in ESTADOS_VALIDOS:
        enviar_estado(emocion)


# ── Servidor HTTP silencioso ──────────────────────────────────────────
class _SilentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE_DIR, **kw)

    def log_message(self, *_):
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def _iniciar_http():
    srv = ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), _SilentHandler)
    srv.serve_forever()


# ── Servidor WebSocket ────────────────────────────────────────────────
async def _ws_handler(websocket):
    with _ws_lock:
        _ws_clients.add(websocket)
    try:
        async for _ in websocket:
            pass
    finally:
        with _ws_lock:
            _ws_clients.discard(websocket)


async def _iniciar_ws():
    global _ws_loop
    _ws_loop = asyncio.get_event_loop()
    import websockets
    async with websockets.serve(_ws_handler, "127.0.0.1", WS_PORT):
        await asyncio.Future()


def _thread_ws():
    asyncio.run(_iniciar_ws())


# ── Lanzar overlay GTK transparente ──────────────────────────────────
_overlay_proc = None

def _lanzar_overlay():
    overlay_script = os.path.join(BASE_DIR, "rem_overlay.py")
    try:
        proc = subprocess.Popen(
            ["/usr/bin/python3", overlay_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except Exception as e:
        print(f"[Avatar] No se pudo lanzar overlay: {e}")
        return None


# ── Iniciar todo ─────────────────────────────────────────────────────
def iniciar_avatar(screen_w=1920, screen_h=1080):
    """Llamar una vez al arrancar Rem."""
    global _overlay_proc

    th_http = threading.Thread(target=_iniciar_http, daemon=True, name="AvatarHTTP")
    th_http.start()

    th_ws = threading.Thread(target=_thread_ws, daemon=True, name="AvatarWS")
    th_ws.start()

    time.sleep(0.6)

    _overlay_proc = _lanzar_overlay()
    if _overlay_proc:
        print(f"[Avatar] Overlay GTK lanzado (PID {_overlay_proc.pid})")
    else:
        print("[Avatar] No se pudo lanzar el overlay")


def cerrar_avatar():
    """Llamar al cerrar Rem."""
    global _overlay_proc
    if _overlay_proc:
        try: _overlay_proc.terminate()
        except Exception: pass
        _overlay_proc = None
