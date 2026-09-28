#!/usr/bin/env python3
"""
Rem de escritorio — GTK3 + WebKit2. ES LA APLICACIÓN: levanta el servidor
HTTP/WS del avatar (mismo servidor, mismo pipeline de voz y LLM, un solo
proceso) y abre UNA de estas dos presentaciones, nunca las dos a la vez:

  --modo ventana   Ventana normal decorada, opaca, con foco de teclado:
                   avatar de cuerpo entero + panel de chat.
  --modo overlay   Layer surface (gtk-layer-shell) transparente anclada
                   IZQUIERDA+ABAJO: avatar de medio cuerpo sobre el escritorio,
                   click-through en todo salvo una caja de texto. Ver
                   "Modo overlay" en CLAUDE.md.

Sin --modo se usa config.toml -> [app].modo (default "ventana"). Si ya hay una
instancia corriendo (puertos :18765/:18766 ocupados) sale con un error claro
en vez de abrir una segunda presentación pegada a un servidor ajeno.

Al arrancar también precarga RVC y el modelo de STT (faster-whisper) en hilos
de fondo, y llama a rem_avatar_server.iniciar_servidor_avatar().

Corre con el venv (venv/bin/python rem_chat.py): PyGObject/pycairo se
instalaron ahí sin problema, construidos contra las libs GTK3/WebKit2GTK ya
instaladas en el sistema (ver requirements.txt y CLAUDE.md). El modo overlay
además necesita el paquete de sistema gtk-layer-shell.

    venv/bin/python rem_chat.py [--modo ventana|overlay]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_PATH = os.path.join(BASE_DIR, "rem_chat.log")

import config


def _parsear_args():
    ap = argparse.ArgumentParser(
        description="Rem: asistente virtual de escritorio (ventana u overlay).")
    ap.add_argument("--modo", choices=("ventana", "overlay"), default=None,
                    help="presentación (default: config.toml [app].modo)")
    return ap.parse_args()


MODO = _parsear_args().modo or config.leer_modo_app()

# Inspector remoto de WebKit — abrir http://127.0.0.1:9222 en un navegador
# normal para depurar rem_avatar.html como cualquier página. Debe fijarse
# ANTES de que WebKit2 se inicialice (import gi más abajo).
os.environ.setdefault('WEBKIT_INSPECTOR_SERVER', '127.0.0.1:9222')
# gtk-layer-shell solo funciona con GDK sobre Wayland nativo (con XWayland
# init_for_window falla) — se fuerza ANTES de que GDK se inicialice.
if MODO == "overlay":
    os.environ['GDK_BACKEND'] = 'wayland'

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
gi.require_version('Gdk', '3.0')

GtkLayerShell = None
if MODO == "overlay":
    try:
        gi.require_version('GtkLayerShell', '0.1')
        # Importado ANTES que Gtk/WebKit2/Gdk (gtk-layer-shell exige enlazarse
        # antes que libwayland-client).
        from gi.repository import GtkLayerShell
    except (ValueError, ImportError):
        sys.exit("[Chat] ERROR: el modo overlay necesita gtk-layer-shell "
                 "(sudo pacman -S gtk-layer-shell).")

from gi.repository import Gtk, WebKit2, Gdk, GLib

ANCHO_DEFAULT = 1100
ALTO_DEFAULT  = 620

_terminal = None  # copia del stderr REAL (la terminal), para errores fatales tras el os.dup2 al log


def _fatal(msg):
    """Error fatal: a la terminal real Y al log, y salida con código 1. Nada
    de fallar en silencio."""
    print(f"[Chat] ERROR: {msg}", file=_terminal or sys.stderr, flush=True)
    if _terminal is not None:
        print(f"[Chat] ERROR: {msg}", flush=True)  # va al log (stdout ya redirigido)
    sys.exit(1)


def _quien_ocupa(puerto):
    """Mejor esfuerzo: 'proceso (pid N)' del que escucha en `puerto`, o ''."""
    try:
        out = subprocess.run(["ss", "-ltnpH", f"sport = :{puerto}"],
                             capture_output=True, text=True, timeout=2).stdout
        m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', out)
        return f" ({m.group(1)}, pid {m.group(2)})" if m else ""
    except Exception:
        return ""


def _comprobar_instancia_unica():
    """Aborta si ya hay una instancia (o un bench_chat.py standalone con su
    propio servidor) escuchando en los puertos del avatar. Va ANTES de abrir
    el log: abrirlo con 'w' truncaría el de la instancia que sí está viva."""
    import rem_avatar_server as srv
    ocupados = [p for p in (srv.HTTP_PORT, srv.WS_PORT) if srv._puerto_activo("127.0.0.1", p)]
    if ocupados:
        detalle = ", ".join(f":{p}{_quien_ocupa(p)}" for p in ocupados)
        sys.exit(f"[Chat] ERROR: ya hay una instancia de Rem corriendo — puerto ocupado: {detalle}.\n"
                 f"        Ciérrala primero (p. ej. `pkill -f rem_chat.py`); solo puede haber una, "
                 f"en modo ventana u overlay, nunca las dos.")


def _precargar_stt():
    import stt
    stt.precargar_stt()


# ── WebView compartido por los dos modos ──────────────────────────────────
def _crear_webview(transparente):
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

    if transparente:
        webview.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    else:
        # Fondo oscuro (no transparente) mientras carga la página, a tono con
        # el suelo synthwave — evita un flash blanco antes de que
        # rem_avatar.html pinte su propio fondo.
        webview.set_background_color(Gdk.RGBA(0.02, 0.0, 0.06, 1.0))
    return webview


def _cargar_con_retry(webview, url):
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
            print(f"[Chat] Carga fallida (intento {intentos[0]}), reintentando en {espera}ms...")
            GLib.timeout_add(espera, _cargar)
        else:
            print(f"[Chat] No se pudo cargar el avatar tras {MAX_INTENTOS} intentos")
        return False

    webview.connect('load-failed', _on_load_failed)
    GLib.timeout_add(300, _cargar)


# ── Modo ventana ──────────────────────────────────────────────────────────
def _crear_ventana():
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("Rem")
    win.set_default_size(ANCHO_DEFAULT, ALTO_DEFAULT)
    win.set_resizable(True)
    # Decorada, opaca, con foco (set_decorated/accept_focus ya son True por
    # defecto en un Gtk.Window normal). Sin set_app_paintable ni visual RGBA:
    # sin eso el compositor ya la pinta opaca.
    webview = _crear_webview(transparente=False)
    win.add(webview)
    return win, webview


# ── Modo overlay ──────────────────────────────────────────────────────────
class _EntradaOverlay:
    """Entrada de la layer surface: (1) input region y (2) modo de teclado.

    (1) REGIÓN — click-through en TODO salvo el rectángulo de la caja de texto.
    El rectángulo lo mide la página (getBoundingClientRect de la caja, ver
    crearOverlayUI en rem_avatar.html) y llega por el message handler "rem" —
    Python no adivina dónde está. Hasta que llega, la región es VACÍA (todo
    click-through): mejor una caja inalcanzable unos segundos que una
    superficie de 420x600 que se traga los clics del escritorio. Se reaplica
    en 'realize', en cada 'size-allocate' y tras show_all(): el compositor
    puede reasignar la superficie y la región no siempre sobrevive (ya pasó
    con el overlay viejo, ver CLAUDE.md, "Layer surface acotada"). Tras fijarla
    se fuerza un redibujado: GDK la manda en el próximo commit del toplevel.

    (2) TECLADO — medido en vivo en Hyprland: con ON_DEMAND fijo, basta PASAR
    el puntero por la caja para que la superficie tome el foco de teclado
    (follow_mouse), y lo CONSERVA al alejarse hasta que se enfoque otra
    ventana a la fuerza: el teclado quedaba secuestrado sin haber hecho clic.
    Por eso el modo es dinámico: NONE por defecto y ON_DEMAND solo mientras el
    puntero está sobre la caja, o la caja de texto tiene el foco (la página lo
    avisa con {"tipo":"foco"}: mientras se escribe no se suelta aunque el
    puntero se vaya). Al cumplirse ninguna, vuelve a NONE y el compositor le
    devuelve el teclado a la ventana de antes."""

    def __init__(self, win):
        self.win = win
        self.rect = None          # (x, y, w, h) en px de superficie, o None = vacía
        self.recibida = False
        self.puntero_dentro = False
        self.input_enfocado = False
        self._modo_teclado = None
        self.actualizar_teclado()

        win.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        win.connect('enter-notify-event', self._on_cruce, True)
        win.connect('leave-notify-event', self._on_cruce, False)

    def aplicar(self, *_args):
        import cairo
        gdk_win = self.win.get_window()
        if not gdk_win:
            return
        if self.rect is None:
            region = cairo.Region()
        else:
            x, y, w, h = self.rect
            region = cairo.Region(cairo.RectangleInt(x, y, w, h))
        gdk_win.input_shape_combine_region(region, 0, 0)
        self.win.queue_draw()

    def actualizar_teclado(self):
        modo = (GtkLayerShell.KeyboardMode.ON_DEMAND if (self.puntero_dentro or self.input_enfocado)
                else GtkLayerShell.KeyboardMode.NONE)
        if modo == self._modo_teclado:
            return
        self._modo_teclado = modo
        GtkLayerShell.set_keyboard_mode(self.win, modo)
        self.win.queue_draw()   # el cambio se aplica en el próximo commit
        print(f"[Overlay] teclado -> {'ON_DEMAND' if modo == GtkLayerShell.KeyboardMode.ON_DEMAND else 'NONE'} "
              f"(puntero dentro={self.puntero_dentro}, caja enfocada={self.input_enfocado})")

    def _on_cruce(self, _win, evento, entra):
        # Solo cruces reales de la superficie (la input region es la caja: el
        # puntero "entra" al pasar sobre ella), no los internos con hijos.
        if evento.detail == Gdk.NotifyType.INFERIOR:
            return False
        self.puntero_dentro = entra
        self.actualizar_teclado()
        return False

    def on_mensaje(self, _ucm, resultado):
        try:
            # WebKit2 4.1: el argumento es un JavascriptResult (hay que pedirle
            # el JSCValue); en otras versiones ya llega como JSCValue.
            valor = resultado.get_js_value() if hasattr(resultado, "get_js_value") else resultado
            datos = json.loads(valor.to_string())
            if datos.get("tipo") == "region":
                self.rect = (int(datos["x"]), int(datos["y"]), int(datos["w"]), int(datos["h"]))
                self.recibida = True
                print(f"[Overlay] región interactiva (caja de texto): {self.rect}")
                self.aplicar()
            elif datos.get("tipo") == "foco":
                self.input_enfocado = bool(datos.get("caja"))
                self.actualizar_teclado()
        except Exception as e:
            print(f"[Overlay] mensaje de la página ilegible ({e})")


def _crear_overlay():
    cfg = config.leer_config_overlay()

    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("rem_overlay")
    win.set_decorated(False)
    win.set_app_paintable(True)
    win.set_accept_focus(True)

    if not GtkLayerShell.is_supported():
        _fatal("el compositor no anuncia zwlr_layer_shell_v1 (¿no es Wayland/Hyprland? "
               f"GDK_BACKEND={os.environ.get('GDK_BACKEND')}).")
    GtkLayerShell.init_for_window(win)
    if not GtkLayerShell.is_layer_window(win):
        _fatal("init_for_window no dejó la ventana como layer surface "
               "(¿GDK arrancó con XWayland en vez de Wayland nativo?).")

    GtkLayerShell.set_namespace(win, "rem_overlay")   # para layerrule de Hyprland
    GtkLayerShell.set_layer(win, GtkLayerShell.Layer.OVERLAY if cfg["capa"] == "overlay"
                                 else GtkLayerShell.Layer.TOP)
    # Teclado: lo gestiona _EntradaOverlay (NONE por defecto, ON_DEMAND solo
    # mientras el puntero está sobre la caja o se escribe en ella) — ver su
    # docstring: ON_DEMAND fijo secuestra el teclado en Hyprland.
    GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.LEFT, True)
    GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.BOTTOM, True)
    GtkLayerShell.set_margin(win, GtkLayerShell.Edge.LEFT, cfg["margen_izquierdo"])
    GtkLayerShell.set_margin(win, GtkLayerShell.Edge.BOTTOM, cfg["margen_inferior"])
    GtkLayerShell.set_exclusive_zone(win, cfg["zona_exclusiva"])
    win.set_size_request(cfg["ancho"], cfg["alto"])
    print(f"[Overlay] {cfg['ancho']}x{cfg['alto']} anclada IZQUIERDA+ABAJO, capa {cfg['capa'].upper()}, "
          f"zona exclusiva {cfg['zona_exclusiva']}, teclado dinámico (NONE / ON_DEMAND sobre la caja)")

    # Transparencia RGBA
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual and screen.is_composited():
        win.set_visual(visual)
    css = Gtk.CssProvider()
    css.load_from_data(b"window, webview { background-color: transparent; background: transparent; }")
    Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    webview = _crear_webview(transparente=True)
    webview.connect('context-menu', lambda *a: True)
    win.add(webview)

    entrada = _EntradaOverlay(win)
    ucm = webview.get_user_content_manager()
    ucm.register_script_message_handler("rem")
    ucm.connect("script-message-received::rem", entrada.on_mensaje)
    win.connect('realize', entrada.aplicar)
    win.connect('size-allocate', entrada.aplicar)

    def _avisar_si_no_llego():
        if not entrada.recibida:
            print("[Overlay] AVISO: la página no reportó la región de la caja de texto en 20s — "
                  "toda la superficie sigue siendo click-through y la caja no se puede usar.")
        return False
    GLib.timeout_add_seconds(20, _avisar_si_no_llego)

    win._region_entrada = entrada   # se reaplica tras show_all() en main()
    return win, webview


def main():
    global _terminal
    _comprobar_instancia_unica()

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

    # El log propio de esta app: se anuncia acá, en la terminal real, ANTES
    # de redirigir stdout/stderr al archivo.
    print(f"[Chat] Modo: {MODO}")
    print(f"[Chat] Log: {LOG_PATH}  (tail -f para seguirlo)")
    print(f"[Chat] Inspector remoto: http://127.0.0.1:9222")
    _terminal = os.fdopen(os.dup(sys.stderr.fileno()), 'w', buffering=1)
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
    print(f"[Chat] Modo: {MODO}")

    # Precargas en hilos de fondo, antes de levantar el servidor — se solapan
    # con ese arranque en vez de sumarse después. RVC: ver CLAUDE.md,
    # "Precarga de RVC y fin de la recarga del .pth en cada frase". STT: el
    # modelo de faster-whisper se carga una sola vez aquí, igual que RVC. La
    # voz (salida y entrada) es una capacidad de primera clase en los dos
    # modos: no hay flag para omitirlas.
    import habla
    threading.Thread(target=habla.precargar_rvc, daemon=True).start()
    threading.Thread(target=_precargar_stt, daemon=True).start()
    # El LLM local también: sin esto el primer turno paga la carga del modelo
    # (~6,7s medidos con Ollama) y la evaluación del prefijo fijo (system +
    # tools + ejemplos de tono). No hace nada con Claude/Groq.
    import acciones
    import chat_sesion
    threading.Thread(target=chat_sesion.precargar_prefijo,
                     args=(acciones.tools_disponibles(MODO),), daemon=True).start()

    import rem_avatar_server
    rem_avatar_server.establecer_modo(MODO)
    try:
        if not rem_avatar_server.iniciar_servidor_avatar(permitir_reuso=False):
            _fatal("el servidor del avatar no pudo levantar (ver el log arriba).")
    except rem_avatar_server.ServidorOcupadoError as e:
        # La comprobación de arriba ya lo cubre; esto atrapa la carrera de dos
        # instancias lanzadas casi a la vez.
        _fatal(f"{e}. Solo puede haber una instancia de Rem.")

    if MODO == "overlay":
        win, webview = _crear_overlay()
    else:
        win, webview = _crear_ventana()

    _cargar_con_retry(webview, rem_avatar_server.url_avatar(MODO))

    win.connect('destroy', Gtk.main_quit)
    # Cierre limpio con SIGTERM/SIGINT (pkill, Ctrl+C): la overlay no tiene
    # botón de cerrar.
    for sig in (15, 2):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: Gtk.main_quit() or False)
    win.show_all()
    if hasattr(win, "_region_entrada"):
        win._region_entrada.aplicar()
    Gtk.main()


if __name__ == '__main__':
    main()