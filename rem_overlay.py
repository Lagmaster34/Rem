#!/usr/bin/env python3
"""
Overlay de escritorio para Rem — gtk-layer-shell (zwlr_layer_shell_v1).

Capa configurable (en orden de precedencia):
  1. --layer top|overlay   (argumento de línea de comandos)
  2. REM_LAYER=top|overlay (variable de entorno / .env de Rem.py)
  3. default: top

  top     → sobre ventanas normales, debajo de fullscreen exclusivo.
             La opción más compatible con el escritorio diario.
  overlay → sobre todo, incluyendo juegos en fullscreen exclusivo.
             Úsala solo para probar; algunos compositors la reservan para notificaciones.
"""
import sys
import os

# Forzar backend Wayland ANTES de que GDK inicialice.
# gtk-layer-shell aborta si GDK arranca con XWayland.
# Esto debe ocurrir antes de cualquier llamada a Gtk/Gdk, incluso antes del import.
os.environ['GDK_BACKEND'] = 'wayland'

import argparse
import cairo

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
gi.require_version('Gdk', '3.0')
try:
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import GtkLayerShell
    _LAYER_SHELL_OK = True
except ValueError:
    _LAYER_SHELL_OK = False
    print("[Overlay] ADVERTENCIA: gtk-layer-shell no está instalado.")
    print("          Instala con: sudo pacman -S gtk-layer-shell")
    print("          El overlay usará el modo de compatibilidad X11 (posición no garantizada en Wayland).")

from gi.repository import Gtk, WebKit2, Gdk, GLib


# ── Determinar capa: argumento CLI > env var > default ────────────────
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--layer', choices=['top', 'overlay'], default=None)
_args, _ = _parser.parse_known_args()

_layer_str = (
    _args.layer
    or os.environ.get('REM_LAYER', 'top').lower()
)
if _layer_str not in ('top', 'overlay'):
    _layer_str = 'top'

# Tamaño fijo de la layer surface (esquina inferior-derecha), configurable por .env.
# Antes se anclaba a los 4 bordes: el compositor estiraba un canvas WebGL
# transparente del tamaño del monitor entero, renderizando a 60fps sobre todo
# el escritorio de forma permanente — con las ~103 cadenas de spring bones de
# este modelo, un costo constante innecesario.
def _leer_dimension_env(nombre, default):
    try:
        return int(os.environ.get(nombre, str(default)))
    except ValueError:
        return default

ANCHO_OVERLAY = _leer_dimension_env('REM_OVERLAY_W', 520)
ALTO_OVERLAY  = _leer_dimension_env('REM_OVERLAY_H', 860)

if _LAYER_SHELL_OK:
    CAPA = GtkLayerShell.Layer.OVERLAY if _layer_str == 'overlay' else GtkLayerShell.Layer.TOP
    print(f"[Overlay] Capa: {_layer_str.upper()}")


def _aplicar_click_through(win, *_args):
    """Establece una input region vacía: ningún punto del overlay captura clics.

    Se conecta a 'realize', 'size-allocate' y se vuelve a llamar tras show_all():
    con el anclaje RIGHT+BOTTOM + set_size_request() nuevos, el compositor puede
    reasignar/redimensionar la superficie después de realizarse, y la input
    region vacía no sobrevive a esa reasignación — sin este refuerzo el overlay
    deja de ser click-through y bloquea los clics en su esquina de pantalla.
    *_args absorbe el argumento allocation que manda la señal 'size-allocate'.
    """
    gdk_win = win.get_window()
    if gdk_win:
        gdk_win.input_shape_combine_region(cairo.Region(), 0, 0)


def main():
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("rem_avatar_overlay")
    win.set_decorated(False)
    win.set_app_paintable(True)
    win.set_accept_focus(False)

    if _LAYER_SHELL_OK:
        # ── Verificar soporte del compositor ANTES de init_for_window ─
        # is_supported() requiere que el display ya esté abierto (ocurre al crear la ventana)
        if not GtkLayerShell.is_supported():
            print("[Overlay] FATAL: el compositor no anuncia zwlr_layer_shell_v1.")
            print(f"[Overlay] GDK_BACKEND={os.environ.get('GDK_BACKEND','(sin establecer)')}")
            display = Gdk.Display.get_default()
            print(f"[Overlay] Display activo: {type(display).__name__} — {display.get_name() if display else 'None'}")
            print("[Overlay] En Hyprland esto no debería pasar. Verifica que Hyprland esté corriendo.")
            sys.exit(1)

        # ── gtk-layer-shell ───────────────────────────────────────────
        GtkLayerShell.init_for_window(win)

        if not GtkLayerShell.is_layer_window(win):
            print("[Overlay] FATAL: init_for_window no configuró la ventana como layer surface.")
            print("[Overlay] Posible causa: GDK arrancó con XWayland en lugar de Wayland nativo.")
            print(f"[Overlay] GDK_BACKEND={os.environ.get('GDK_BACKEND','(sin establecer)')}")
            sys.exit(1)

        GtkLayerShell.set_layer(win, CAPA)
        GtkLayerShell.set_keyboard_mode(win, GtkLayerShell.KeyboardMode.NONE)
        # Anclar solo a RIGHT/BOTTOM: superficie acotada a una esquina, tamaño fijo
        # (ver ANCHO_OVERLAY/ALTO_OVERLAY), no todo el monitor.
        for edge in (GtkLayerShell.Edge.RIGHT, GtkLayerShell.Edge.BOTTOM):
            GtkLayerShell.set_anchor(win, edge, True)
        win.set_size_request(ANCHO_OVERLAY, ALTO_OVERLAY)
        # -1: la superficie no respeta zonas exclusivas de paneles (se solapa con todo)
        GtkLayerShell.set_exclusive_zone(win, -1)
    else:
        # Fallback X11 / XWayland (sin garantías en Wayland puro)
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor()
        geo     = monitor.get_geometry()
        win.set_type_hint(Gdk.WindowTypeHint.DOCK)
        win.set_keep_above(True)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_resizable(False)
        win.resize(geo.width, geo.height)
        win.move(geo.x, geo.y)

    # ── Transparencia RGBA ────────────────────────────────────────────
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual and screen.is_composited():
        win.set_visual(visual)

    css = b"window, webview { background-color: transparent; background: transparent; }"
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    # ── WebView ───────────────────────────────────────────────────────
    webview = WebKit2.WebView()
    webview.set_background_color(Gdk.RGBA(0, 0, 0, 0))

    settings = webview.get_settings()

    # El overlay es click-through por diseño (ver _aplicar_click_through): nunca va
    # a llegar un gesto de usuario real. Se aplica ANTES que cualquier otra
    # configuración y antes de la primera llamada a load_uri (más abajo, recién
    # a los 1200ms vía GLib.timeout_add) — por si WebKit fija esta política al
    # navegar y no la reevalúa luego para el documento ya cargado.
    try:
        settings.set_media_playback_requires_user_gesture(False)
        print("[Overlay] media-playback-requires-user-gesture desactivado (autoplay permitido)")
    except Exception as e:
        print(f"[Overlay] set_media_playback_requires_user_gesture no disponible en esta WebKit2 ({e})")

    settings.set_enable_webgl(True)
    settings.set_enable_javascript(True)
    try:
        settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.ALWAYS)
    except Exception:
        pass

    # Diagnóstico: volcar los console.log/warn/error de rem_avatar.html a stdout
    # (y de ahí a rem_overlay.log) — hasta ahora no había forma de ver la consola
    # del overlay real, solo se podía inferir desde un navegador aparte.
    try:
        settings.set_enable_write_console_messages_to_stdout(True)
        settings.set_enable_developer_extras(True)
        print("[Overlay] console.* del frontend -> stdout, developer extras habilitados")
    except Exception as e:
        print(f"[Overlay] no se pudo habilitar el volcado de consola ({e})")

    webview.connect('context-menu', lambda *a: True)
    win.add(webview)

    # ── Click-through total — reforzado en varios momentos (ver docstring
    #    de _aplicar_click_through) porque el anclaje RIGHT+BOTTOM con tamaño
    #    fijo puede reasignar la superficie después de realizarse ──────────
    win.connect('realize', _aplicar_click_through)
    win.connect('size-allocate', _aplicar_click_through)

    # ── Carga del avatar con retry exponencial ────────────────────────
    _intentos = [0]
    MAX_INTENTOS = 10

    def _cargar(_=None):
        _intentos[0] += 1
        webview.load_uri('http://localhost:18765/rem_avatar.html')
        return False

    def _on_load_failed(wv, load_event, failing_uri, error, *_a):
        if _intentos[0] < MAX_INTENTOS:
            espera = min(500 * (2 ** _intentos[0]), 5000)
            print(f"[Overlay] Carga fallida (intento {_intentos[0]}), "
                  f"reintentando en {espera}ms...")
            GLib.timeout_add(espera, _cargar)
        else:
            print(f"[Overlay] No se pudo cargar el avatar tras {MAX_INTENTOS} intentos")
        return False

    webview.connect('load-failed', _on_load_failed)
    GLib.timeout_add(1200, _cargar)

    # ── Vigilar proceso padre — cierra el overlay si Rem.py muere ────
    _ppid = os.getppid()

    def _check_parent(_=None):
        try:
            os.kill(_ppid, 0)
        except (OSError, ProcessLookupError):
            print("[Overlay] Proceso padre terminó, cerrando overlay.")
            Gtk.main_quit()
        return True

    GLib.timeout_add(5000, _check_parent)

    win.connect('destroy', Gtk.main_quit)
    win.show_all()
    _aplicar_click_through(win)
    Gtk.main()


if __name__ == '__main__':
    main()
