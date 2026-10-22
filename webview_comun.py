"""webview_comun.py — piezas GTK+WebKit2 compartidas por las ventanas de Rem:
rem_chat.py (avatar, ventana u overlay) y rem_panel.py (panel de control).

Se importa DESPUÉS de que el script fije su entorno (WEBKIT_INSPECTOR_SERVER,
GDK_BACKEND) y, en overlay, después de importar GtkLayerShell — este módulo
importa WebKit2/Gdk al cargarse, y esos dos requisitos tienen que cumplirse
antes de que WebKit2/GDK se inicialicen (ver rem_chat.py).
"""
import os
import sys

import gi
gi.require_version('WebKit2', '4.1')
gi.require_version('Gdk', '3.0')
from gi.repository import WebKit2, Gdk, GLib


def redirigir_salida_a_log(ruta_log):
    """Manda stdout/stderr del proceso a `ruta_log` y devuelve una copia del
    stderr real (la terminal), para los errores fatales posteriores.

    line_buffering ANTES de cualquier print(): redirigido a un archivo, Python
    pasa a buffer de bloque y un print() podía quedarse sin escribir hasta un
    cierre limpio (no pasa si se mata el proceso, el caso normal).

    os.dup2 sobre los fd reales (1 y 2), no reasignar sys.stdout: WebKit2
    escribe su volcado de consola (set_enable_write_console_messages_to_stdout)
    directo al fd 1 nativo, sin pasar por el objeto sys.stdout de Python."""
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    terminal = os.fdopen(os.dup(sys.stderr.fileno()), 'w', buffering=1)
    log_file = open(ruta_log, 'w', buffering=1, encoding='utf-8')
    os.dup2(log_file.fileno(), sys.stdout.fileno())
    os.dup2(log_file.fileno(), sys.stderr.fileno())
    return terminal


def crear_webview(transparente=False, prefijo="[Chat]"):
    # Settings y WebsitePolicies armados en objetos APARTE, completos, ANTES de
    # crear el WebView (ver CLAUDE.md, "Regresión repetida de la política de
    # autoplay" — el orden de los set_* sobre un WebView ya creado rompió el
    # autoplay dos veces antes de dar con esto).
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
        print(f"{prefijo} media-playback-requires-user-gesture desactivado (autoplay permitido)")
    except Exception as e:
        print(f"{prefijo} set_media_playback_requires_user_gesture no disponible en esta WebKit2 ({e})")

    try:
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_enable_developer_extras(True)
        print(f"{prefijo} console.* del frontend -> stdout (log), developer extras habilitados")
    except Exception as e:
        print(f"{prefijo} no se pudo habilitar el volcado de consola ({e})")

    # WebsitePolicies.autoplay = ALLOW: imprescindible, no alcanza con la
    # Settings de arriba (WebKitGTK 2.52 tiene un mecanismo separado y más
    # nuevo que es el que de verdad decide si HTMLMediaElement.play() se
    # rechaza con NotAllowedError — ver CLAUDE.md). Sin esto no hay audio.
    try:
        policies = WebKit2.WebsitePolicies(autoplay=WebKit2.AutoplayPolicy.ALLOW)
        print(f"{prefijo} WebsitePolicies.autoplay = ALLOW")
    except Exception as e:
        policies = None
        print(f"{prefijo} WebsitePolicies no disponible en esta WebKit2 ({e})")

    if policies is not None:
        webview = WebKit2.WebView(settings=settings, website_policies=policies)
    else:
        webview = WebKit2.WebView.new_with_settings(settings)

    if transparente:
        webview.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    else:
        # Fondo oscuro (no transparente) mientras carga la página, a tono con
        # el suelo synthwave — evita un flash blanco antes de que la página
        # pinte su propio fondo.
        webview.set_background_color(Gdk.RGBA(0.02, 0.0, 0.06, 1.0))
    return webview


def cargar_con_retry(webview, url, prefijo="[Chat]"):
    """Carga con retry exponencial: el Network Process de WebKit2GTK 2.52.5
    puede crashear en el peor momento (ver CLAUDE.md, "crash interno del
    Network Process de WebKit")."""
    intentos = [0]
    MAX_INTENTOS = 10

    def _cargar(_=None):
        intentos[0] += 1
        webview.load_uri(url)
        return False

    def _on_load_failed(wv, load_event, failing_uri, error, *_a):
        if intentos[0] < MAX_INTENTOS:
            espera = min(500 * (2 ** intentos[0]), 5000)
            print(f"{prefijo} Carga fallida (intento {intentos[0]}), reintentando en {espera}ms...")
            GLib.timeout_add(espera, _cargar)
        else:
            print(f"{prefijo} No se pudo cargar {url} tras {MAX_INTENTOS} intentos")
        return False

    webview.connect('load-failed', _on_load_failed)
    GLib.timeout_add(300, _cargar)
