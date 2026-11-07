#!/usr/bin/env python3
"""
Rem de escritorio — GTK3 + WebKit2. ES LA APLICACIÓN: levanta el servidor
HTTP/WS del avatar (mismo servidor, mismo pipeline de voz y LLM, un solo
proceso) y abre UNA de estas presentaciones, nunca dos a la vez:

  --modo ventana   Ventana normal decorada, opaca, con foco de teclado:
                   avatar de cuerpo entero + panel de chat.
  --modo overlay   Layer surface (gtk-layer-shell) transparente anclada
                   IZQUIERDA+ABAJO: avatar de medio cuerpo sobre el escritorio,
                   click-through en todo salvo una caja de texto. Ver
                   "Modo overlay" en CLAUDE.md.
  --modo escritorio  Avatar de cuerpo entero sobre el escritorio que se
                   arrastra con el ratón (Hyprland), reacciona a los clics y
                   tiene menú propio; el chat va en una ventana aparte. Ver
                   escritorio.py.

Sin --modo se usa config.toml -> [app].modo (default "ventana"). Si ya hay una
instancia corriendo (puertos :18765/:18766 ocupados) sale con un error claro
en vez de abrir una segunda presentación pegada a un servidor ajeno.

Al arrancar también precarga la voz (Piper) y el modelo de STT (faster-whisper) en hilos
de fondo, y llama a rem_avatar_server.iniciar_servidor_avatar().

Corre con el venv (venv/bin/python rem_chat.py): PyGObject/pycairo se
instalaron ahí sin problema, construidos contra las libs GTK3/WebKit2GTK ya
instaladas en el sistema (ver requirements.txt y CLAUDE.md). El modo overlay
además necesita el paquete de sistema gtk-layer-shell.

    venv/bin/python rem_chat.py [--modo ventana|overlay|escritorio]
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
        description="Rem: asistente virtual de escritorio (ventana, overlay o escritorio).")
    ap.add_argument("--modo", choices=("ventana", "overlay", "escritorio"), default=None,
                    help="presentación (default: config.toml [app].modo)")
    return ap.parse_args()


MODO = _parsear_args().modo or config.leer_modo_app()

# Inspector remoto de WebKit — abrir http://127.0.0.1:9222 en un navegador
# normal para depurar rem_avatar.html como cualquier página. Debe fijarse
# ANTES de que WebKit2 se inicialice (import gi más abajo).
os.environ.setdefault('WEBKIT_INSPECTOR_SERVER', '127.0.0.1:9222')
# gtk-layer-shell solo funciona con GDK sobre Wayland nativo (con XWayland
# init_for_window falla) — se fuerza ANTES de que GDK se inicialice.
CAPA = MODO in ("overlay", "escritorio")   # layer surface (gtk-layer-shell)
if CAPA:
    os.environ['GDK_BACKEND'] = 'wayland'

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
gi.require_version('Gdk', '3.0')

GtkLayerShell = None
if CAPA:
    try:
        gi.require_version('GtkLayerShell', '0.1')
        # Importado ANTES que Gtk/WebKit2/Gdk (gtk-layer-shell exige enlazarse
        # antes que libwayland-client).
        from gi.repository import GtkLayerShell
    except (ValueError, ImportError):
        sys.exit(f"[Chat] ERROR: el modo {MODO} necesita gtk-layer-shell "
                 "(sudo pacman -S gtk-layer-shell).")

from gi.repository import Gtk, Gdk, GLib

# Tras el entorno y GtkLayerShell: este módulo inicializa WebKit2/GDK al importarse.
from webview_comun import cargar_con_retry, crear_webview, redirigir_salida_a_log

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


# Pidfile: lo leen los lanzadores para cerrar o encontrar esta instancia sin
# buscar procesos por patrón. Línea 1: pid; línea 2: modo.
PID_PATH = os.path.join(BASE_DIR, "rem_chat.pid")


def _escribir_pidfile():
    """Se llama con el servidor ya levantado (esta instancia es la única).
    Escritura atómica: un lanzador nunca lee un archivo a medias. Se borra en
    atexit, que Python corre DESPUÉS de esperar a los hilos: si la salida se
    atasca ahí, el pidfile sigue y «Rem Cerrar» todavía encuentra el proceso."""
    import atexit
    tmp = PID_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.write(f"{os.getpid()}\n{MODO}\n")
    os.replace(tmp, PID_PATH)
    atexit.register(_borrar_pidfile)


def _borrar_pidfile():
    """Solo si sigue siendo el nuestro. Tras un SIGKILL queda uno viejo: el
    lanzador lo detecta (el pid ya no es rem_chat.py) y lo borra."""
    try:
        with open(PID_PATH) as f:
            if f.readline().strip() == str(os.getpid()):
                os.remove(PID_PATH)
    except OSError:
        pass


def _precargar_stt():
    import stt
    stt.precargar_stt()


# ── Modo ventana ──────────────────────────────────────────────────────────
def _crear_ventana():
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("Rem")
    win.set_default_size(ANCHO_DEFAULT, ALTO_DEFAULT)
    win.set_resizable(True)
    # Decorada, opaca, con foco (set_decorated/accept_focus ya son True por
    # defecto en un Gtk.Window normal). Sin set_app_paintable ni visual RGBA:
    # sin eso el compositor ya la pinta opaca.
    webview = crear_webview(transparente=False)
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

    webview = crear_webview(transparente=True)
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


def _iniciar_vigilante():
    """Diagnóstico de congelamientos: el bucle de GTK escribe "[GTK] vivo" cada
    10 s, y un hilo aparte avisa (una vez por episodio) si ese latido o el de
    la página del avatar (latido_pagina, ver avatar/bucle.js) dejan de llegar.
    Si se colgó GTK vuelca las pilas de Python al log. Así se distingue un
    cuelgue del proceso de la interfaz (como el de JavaScriptCore de la etapa
    2) de una página que deja de dibujar."""
    import faulthandler
    import time
    import rem_avatar_server as srv
    estado = {"gtk": time.monotonic(), "aviso_gtk": False, "aviso_pagina": False}

    def latido_gtk():
        estado["gtk"] = time.monotonic()
        pag = srv.ultimo_latido_pagina
        print(f"[GTK] vivo (página: {'último latido hace %.0f s' % (time.monotonic() - pag) if pag else 'sin latidos aún'})",
              flush=True)
        return True
    GLib.timeout_add_seconds(10, latido_gtk)

    def vigilar():
        while True:
            time.sleep(5)
            ahora = time.monotonic()
            hace = ahora - estado["gtk"]
            if hace > 25 and not estado["aviso_gtk"]:
                estado["aviso_gtk"] = True
                print(f"[Vigilante] el bucle de GTK no late desde hace {hace:.0f} s: la interfaz está colgada. "
                      "Pilas de Python:", flush=True)
                faulthandler.dump_traceback(all_threads=True)
            elif hace < 15:
                estado["aviso_gtk"] = False
            pag = srv.ultimo_latido_pagina
            if pag is not None:
                hace_p = ahora - pag
                if hace_p > 25 and not estado["aviso_pagina"]:
                    estado["aviso_pagina"] = True
                    print(f"[Vigilante] la página del avatar no manda latido desde hace {hace_p:.0f} s "
                          f"(GTK {'también colgado' if hace > 15 else 'vivo'})", flush=True)
                elif hace_p < 15:
                    estado["aviso_pagina"] = False
    threading.Thread(target=vigilar, daemon=True, name="Vigilante").start()


def main():
    global _terminal
    _comprobar_instancia_unica()

    # line_buffering ya, ANTES de los print() de abajo: si no, alguno puede
    # flushearse tarde y terminar en rem_chat.log en vez de la terminal real.
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # El log propio de esta app: se anuncia acá, en la terminal real, ANTES
    # de redirigir stdout/stderr al archivo.
    print(f"[Chat] Modo: {MODO}")
    print(f"[Chat] Log: {LOG_PATH}  (tail -f para seguirlo)")
    print(f"[Chat] Inspector remoto: http://127.0.0.1:9222")
    _terminal = redirigir_salida_a_log(LOG_PATH)

    config.cargar_dotenv()
    print(f"[Chat] Modo: {MODO}")
    # Diagnóstico: `kill -USR2 <pid>` vuelca al log la pila de todos los hilos
    # de Python (p. ej. si algo no deja cerrar la app con SIGTERM).
    import faulthandler
    import signal
    faulthandler.register(signal.SIGUSR2, all_threads=True)

    # Precargas en hilos de fondo, antes de levantar el servidor — se solapan
    # con ese arranque en vez de sumarse después. Voz: la PiperVoice se carga
    # una sola vez (habla._voz). STT: el modelo de faster-whisper, igual. La
    # voz (salida y entrada) es una capacidad de primera clase en los dos
    # modos: no hay flag para omitirlas.
    import habla
    threading.Thread(target=habla.precargar_tts, daemon=True).start()
    threading.Thread(target=_precargar_stt, daemon=True).start()
    # El LLM local también: sin esto el primer turno paga la carga del modelo
    # (~6,7s medidos con Ollama) y la evaluación del prefijo fijo (system +
    # tools + ejemplos de tono). No hace nada con Claude.
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
    _escribir_pidfile()

    if MODO == "escritorio":
        import escritorio
        try:
            avatar, _chat = escritorio.crear_escritorio(rem_avatar_server.url_avatar(MODO),
                                                        rem_avatar_server.url_chat_ventana())
        except RuntimeError as e:
            _fatal(str(e))
        win = avatar.win
        import frases_voz
        threading.Thread(target=frases_voz.precargar, daemon=True).start()
        # El lanzador «Rem Escritorio» con una instancia ya abierta manda
        # SIGUSR1: vuelve a mostrar el avatar si se ocultó desde su menú.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 10, avatar.mostrar)
    else:
        if MODO == "overlay":
            win, webview = _crear_overlay()
        else:
            win, webview = _crear_ventana()
        cargar_con_retry(webview, rem_avatar_server.url_avatar(MODO))

    _iniciar_vigilante()
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