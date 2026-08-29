#!/usr/bin/env python3
"""
Ventana de escritorio para Rem — GTK3 + WebKit2, decorada y con foco.

En la línea de rem_overlay.py (mismo WebView, mismo motor rem_avatar.html),
pero para el caso opuesto: una ventana normal de verdad, no una layer surface
transparente y click-through. Sin gtk-layer-shell, sin transparencia, sin
click-through — con barra de título, redimensionable, y capaz de recibir
foco de teclado (para cuando el chat se conecte acá, en una etapa futura;
esta etapa es solo la ventana y la escena 3D).

Cambio de escena: rem_avatar.html se carga con ?modo=ventana (fondo oscuro
opaco, suelo de cuadrícula synthwave, Rem centrada en el tercio izquierdo),
a diferencia de rem_overlay.py que la carga sin parámetro (modo "overlay":
fondo transparente, sin suelo — ver rem_avatar.html para el resto).

Puede lanzarse sola (levanta ella misma el servidor del avatar) o junto al
overlay/Rem.py/bench_chat.py (detecta que el servidor ya está corriendo y se
conecta directo, sin competir por el puerto — ver
rem_avatar_server.iniciar_servidor_avatar()). A diferencia del overlay, esta
ventana SÍ corre con el venv (venv/bin/python rem_chat.py): PyGObject/pycairo
se instalaron ahí sin problema, construidos contra las libs GTK3/WebKit2GTK
ya instaladas en el sistema (ver requirements.txt y CLAUDE.md) — no hacía
falta el python3 del sistema para esto, a diferencia de lo que se pensaba.

    venv/bin/python rem_chat.py
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_PATH = os.path.join(BASE_DIR, "rem_chat.log")

# Puerto del inspector remoto de WebKit para ESTA ventana — distinto del 9222
# que usa rem_overlay.py, para que no compitan por el mismo puerto si las dos
# corren juntas. Debe fijarse ANTES de que WebKit2 se inicialice (import gi
# más abajo), como GDK_BACKEND en rem_overlay.py.
os.environ.setdefault('WEBKIT_INSPECTOR_SERVER', '127.0.0.1:9223')

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, WebKit2, Gdk, GLib

import config

ANCHO_DEFAULT = 1100
ALTO_DEFAULT  = 620


def main():
    # sys.stdout/stderr quedan con buffer de BLOQUE (no de línea) apenas se
    # redirigen a un archivo/pipe en vez de una terminal real — sin esto,
    # cualquier print() de este script puede quedarse en el buffer de Python
    # sin escribirse a ningún lado hasta que el proceso cierre limpio (no
    # pasa si se lo mata, el caso normal al probar/usar la ventana).
    # reconfigure(line_buffering=True) lo deja como una terminal: cada línea
    # se escribe al toque. Tiene que ir ANTES de cualquier print() de acá
    # abajo, no solo antes del os.dup2() — si no, incluso flusheado a
    # destiempo puede terminar escribiendo en rem_chat.log en vez de la
    # terminal real donde se supone que hay que anunciar dónde quedó el log.
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # El log propio de esta ventana: se anuncia acá, en la terminal real,
    # ANTES de redirigir stdout/stderr al archivo — mismo patrón que
    # rem_avatar_server._lanzar_overlay() usa para rem_overlay.log, pero acá
    # lo hace el propio proceso (rem_chat.py se lanza directo, no como
    # subprocess de otro Python que le redirija la salida).
    print(f"[Chat] Log: {LOG_PATH}  (tail -f para seguirlo)")
    print(f"[Chat] Inspector remoto: http://127.0.0.1:9223")
    # os.dup2 sobre los file descriptors reales (1 y 2), no solo reasignar
    # sys.stdout/sys.stderr: WebKit2 escribe su volcado de consola
    # (set_enable_write_console_messages_to_stdout) directo al fd 1 nativo
    # del proceso, sin pasar por el objeto sys.stdout de Python — reasignar
    # solo ese objeto deja afuera justo lo que más importa capturar acá.
    # Mismo resultado que logra rem_avatar_server._lanzar_overlay() pasando
    # stdout=/stderr=<archivo> a subprocess.Popen, pero rem_chat.py no puede
    # spawnearse a sí mismo así — se redirige desde adentro.
    log_file = open(LOG_PATH, 'w', buffering=1, encoding='utf-8')
    os.dup2(log_file.fileno(), sys.stdout.fileno())
    os.dup2(log_file.fileno(), sys.stderr.fileno())

    config.cargar_dotenv()

    import rem_avatar_server
    rem_avatar_server.iniciar_servidor_avatar()

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("Rem")
    win.set_default_size(ANCHO_DEFAULT, ALTO_DEFAULT)
    win.set_resizable(True)
    # Decorada, opaca, con foco: todo lo contrario del overlay a propósito.
    # (set_decorated/accept_focus ya son True por defecto en un Gtk.Window
    # normal — no hace falta tocarlos. Sin set_app_paintable ni visual RGBA:
    # sin eso el compositor ya la pinta opaca.)

    # ── WebView — mismo patrón que rem_overlay.py: Settings y
    # WebsitePolicies armados en objetos APARTE, completos, ANTES de crear
    # el WebView (ver CLAUDE.md, "Regresión repetida de la política de
    # autoplay" — el orden de los set_* sobre un WebView ya creado rompió
    # el autoplay dos veces en el overlay).
    settings = WebKit2.Settings()
    settings.set_enable_webgl(True)
    settings.set_enable_javascript(True)
    try:
        settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)
    except Exception:
        pass

    # Esta ventana SÍ recibe gestos de usuario reales (no es click-through),
    # pero igual hace falta lo mismo que en el overlay: el audio puede
    # empezar a sonar sin que el usuario haya interactuado con la página
    # todavía (primera respuesta de Rem apenas se abre la ventana).
    try:
        settings.set_media_playback_requires_user_gesture(False)
        print("[Chat] media-playback-requires-user-gesture desactivado (autoplay permitido)")
    except Exception as e:
        print(f"[Chat] set_media_playback_requires_user_gesture no disponible en esta WebKit2 ({e})")

    try:
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_enable_developer_extras(True)
        print("[Chat] console.* del frontend -> stdout (rem_chat.log), developer extras habilitados")
    except Exception as e:
        print(f"[Chat] no se pudo habilitar el volcado de consola ({e})")

    # WebsitePolicies.autoplay = ALLOW: imprescindible, no alcanza con la
    # Settings de arriba (WebKitGTK 2.52 tiene un mecanismo separado y más
    # nuevo que es el que de verdad decide si HTMLMediaElement.play() se
    # rechaza con NotAllowedError — confirmado en vivo en el overlay, ver
    # CLAUDE.md). Sin esto no habrá audio.
    try:
        policies = WebKit2.WebsitePolicies(autoplay=WebKit2.AutoplayPolicy.ALLOW)
        print("[Chat] WebsitePolicies.autoplay = ALLOW")
    except Exception as e:
        policies = None
        print(f"[Chat] WebsitePolicies no disponible en esta WebKit2 ({e})")

    if policies is not None:
        webview = WebKit2.WebView(settings=settings, website_policies=policies)
    else:
        webview = WebKit2.WebView.new_with_settings(settings)

    # Fondo oscuro (no transparente) mientras carga la página, a tono con la
    # estética synthwave del suelo de la escena en modo ventana — evita un
    # flash blanco antes de que rem_avatar.html pinte su propio fondo.
    webview.set_background_color(Gdk.RGBA(0.02, 0.0, 0.06, 1.0))

    win.add(webview)

    url = f"http://localhost:{rem_avatar_server.HTTP_PORT}/rem_avatar.html?modo=ventana"

    # ── Carga con retry exponencial — mismo motivo que en rem_overlay.py:
    # el Network Process de WebKit2GTK 2.52.5 puede crashear en el peor
    # momento (ver CLAUDE.md, "Segunda regresión del overlay").
    _intentos = [0]
    MAX_INTENTOS = 10

    def _cargar(_=None):
        _intentos[0] += 1
        webview.load_uri(url)
        return False

    def _on_load_failed(wv, load_event, failing_uri, error, *_a):
        if _intentos[0] < MAX_INTENTOS:
            espera = min(500 * (2 ** _intentos[0]), 5000)
            print(f"[Chat] Carga fallida (intento {_intentos[0]}), reintentando en {espera}ms...")
            GLib.timeout_add(espera, _cargar)
        else:
            print(f"[Chat] No se pudo cargar el avatar tras {MAX_INTENTOS} intentos")
        return False

    webview.connect('load-failed', _on_load_failed)
    GLib.timeout_add(300, _cargar)

    win.connect('destroy', Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
