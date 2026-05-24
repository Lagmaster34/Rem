#!/usr/bin/env python3
"""
Overlay transparente de escritorio para el avatar 3D de Rem.
Usa GTK3 + WebKit2 con system Python.
"""
import sys, os
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, WebKit2, Gdk, GLib


def main():
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor()
    geo     = monitor.get_geometry()

    W = geo.width
    H = geo.height
    X = 0
    Y = 0

    # ── Ventana sin decoración, siempre encima ────────────────────────
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title("rem_avatar_overlay")
    win.set_decorated(False)
    win.set_app_paintable(True)
    win.set_keep_above(True)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_type_hint(Gdk.WindowTypeHint.DOCK)
    win.set_accept_focus(False)
    win.set_resizable(False)
    win.resize(W, H)
    win.move(X, Y)

    # ── Transparencia RGBA ────────────────────────────────────────────
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual and screen.is_composited():
        win.set_visual(visual)

    # Fondo transparente via CSS (evita cairo foreign type issues)
    css = b"""
    window, webview {
        background-color: transparent;
        background: transparent;
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    # ── WebView ───────────────────────────────────────────────────────
    webview = WebKit2.WebView()
    webview.set_background_color(Gdk.RGBA(0, 0, 0, 0))

    settings = webview.get_settings()
    settings.set_enable_webgl(True)
    settings.set_enable_javascript(True)
    try:
        settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.ALWAYS)
    except Exception:
        pass

    # Sin menú contextual
    webview.connect('context-menu', lambda *a: True)

    win.add(webview)

    # ── Cargar página ─────────────────────────────────────────────────
    def _cargar(_=None):
        webview.load_uri('http://localhost:18765/rem_avatar.html')
        return False

    GLib.timeout_add(1200, _cargar)

    # ── Re-raise periódico para mantenerse encima ─────────────────────
    def _reraise(_=None):
        try:
            gdk_win = win.get_window()
            if gdk_win:
                gdk_win.raise_()
        except Exception:
            pass
        return True

    GLib.timeout_add(3000, _reraise)

    win.connect('destroy', Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
