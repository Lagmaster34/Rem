#!/usr/bin/env python3
"""
Ventana de escritorio para Rem — GTK3 + WebKit2, decorada y con foco.
ES LA APLICACIÓN: levanta el servidor HTTP/WS del avatar y abre la ventana.

Ventana normal (barra de título, redimensionable, con foco de teclado para el
panel de chat), opaca. rem_avatar.html se carga con ?modo=ventana — hoy ese
parámetro ya no cambia nada (había un modo "overlay" transparente y
click-through, rem_overlay.py, que se eliminó: esta ventana lo sustituye por
completo).

Al arrancar llama a rem_avatar_server.iniciar_servidor_avatar(): levanta el
servidor, o detecta que ya está corriendo (otra instancia, o bench_chat.py en
modo standalone) y lo reusa sin competir por el puerto.

Corre con el venv (venv/bin/python rem_chat.py): PyGObject/pycairo se
instalaron ahí sin problema, construidos contra las libs GTK3/WebKit2GTK ya
instaladas en el sistema (ver requirements.txt y CLAUDE.md).

    venv/bin/python rem_chat.py
"""
import os
import sys
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_PATH = os.path.join(BASE_DIR, "rem_chat.log")

# Inspector remoto de WebKit — abrir http://127.0.0.1:9222 en un navegador
# normal para depurar rem_avatar.html como cualquier página. Debe fijarse
# ANTES de que WebKit2 se inicialice (import gi más abajo).
os.environ.setdefault('WEBKIT_INSPECTOR_SERVER', '127.0.0.1:9222')

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
    # ANTES de redirigir stdout/stderr al archivo.
    print(f"[Chat] Log: {LOG_PATH}  (tail -f para seguirlo)")
    print(f"[Chat] Inspector remoto: http://127.0.0.1:9222")
    # os.dup2 sobre los file descriptors reales (1 y 2), no solo reasignar
    # sys.stdout/sys.stderr: WebKit2 escribe su volcado de consola
    # (set_enable_write_console_messages_to_stdout) directo al fd 1 nativo
    # del proceso, sin pasar por el objeto sys.stdout de Python — reasignar
    # solo ese objeto deja afuera justo lo que más importa capturar acá.
    # rem_chat.py se lanza directo (no como subprocess), así que la
    # redirección la hace el propio proceso.
    log_file = open(LOG_PATH, 'w', buffering=1, encoding='utf-8')
    os.dup2(log_file.fileno(), sys.stdout.fileno())
    os.dup2(log_file.fileno(), sys.stderr.fileno())

    config.cargar_dotenv()

    # Precarga de RVC en un hilo de fondo, antes de levantar el servidor —
    # se solapa con ese arranque en vez de sumarse después, igual que en
    # bench_chat.py (ver CLAUDE.md, "Precarga de RVC y fin de la recarga del
    # .pth en cada frase"). La ventana existe para hablar con Rem (ver panel
    # de chat en rem_avatar.html), así que la voz es una capacidad de
    # primera clase acá, no algo opcional como en el REPL (que la tiene
    # detrás de --no-rvc): no hace falta un flag propio, siempre precarga.
    import habla
    threading.Thread(target=habla.precargar_rvc, daemon=True).start()

    import rem_avatar_server
    rem_avatar_server.iniciar_servidor_avatar()

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("Rem")
    win.set_default_size(ANCHO_DEFAULT, ALTO_DEFAULT)
    win.set_resizable(True)
    # Decorada, opaca, con foco (set_decorated/accept_focus ya son True por
    # defecto en un Gtk.Window normal). Sin set_app_paintable ni visual RGBA:
    # sin eso el compositor ya la pinta opaca.

    # ── WebView — Settings y WebsitePolicies armados en objetos APARTE,
    # completos, ANTES de crear el WebView (ver CLAUDE.md, "Regresión
    # repetida de la política de autoplay" — el orden de los set_* sobre un
    # WebView ya creado rompió el autoplay dos veces antes de dar con esto).
    settings = WebKit2.Settings()
    settings.set_enable_webgl(True)
    settings.set_enable_javascript(True)
    try:
        settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.ALWAYS)
    except Exception:
        pass

    # El audio puede empezar a sonar sin que el usuario haya interactuado con
    # la página todavía (primera respuesta de Rem apenas se abre la ventana).
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
    # rechaza con NotAllowedError — ver CLAUDE.md). Sin esto no hay audio.
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

    # ── Carga con retry exponencial: el Network Process de WebKit2GTK 2.52.5
    # puede crashear en el peor momento (ver CLAUDE.md, "crash interno del
    # Network Process de WebKit").
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
