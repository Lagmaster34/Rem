#!/usr/bin/env python3
"""
Panel de control de Rem — GTK3 + WebKit2, ventana APARTE de rem_chat.py.

Es solo un cliente: no levanta servidor ni abre puertos. Carga
http://localhost:18765/rem_panel.html del servidor de rem_chat.py y habla con
el backend por el mismo WebSocket (:18766), con los mensajes prefs_* (ver
preferencias.py y "Preferencias del panel de control" en CLAUDE.md). Por eso
necesita a Yoru corriendo (ventana o escritorio): si no, avisa y sale.

Instancia única vía Gtk.Application: lanzarlo otra vez trae al frente la
ventana ya abierta. Log propio en rem_panel.log; inspector remoto en :9223
(el :9222 es de rem_chat.py).

    venv/bin/python rem_panel.py [--pestana ID]

--pestana abre en esa pestaña (apariencia, avatar, escritorio, animaciones,
voz, chat, personalidad). Si el panel ya está abierto, el cambio de pestaña le
llega por el WebSocket (panel_pestana, lo manda el menú del avatar); esto solo
cubre el panel recién abierto.
"""
import argparse
import urllib.parse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
LOG_PATH = config.ruta_datos("rem_panel.log")
INSPECTOR = "127.0.0.1:9223"

# Antes de que WebKit2 se inicialice. Fijo, no setdefault: si el entorno trae
# el de rem_chat.py (:9222), los dos procesos se pelearían el puerto.
os.environ["WEBKIT_INSPECTOR_SERVER"] = INSPECTOR

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from webview_comun import cargar_con_retry, crear_webview, redirigir_salida_a_log
import rem_avatar_server as srv

APP_ID = "dev.rem.panel"
URL_PANEL = f"http://localhost:{srv.HTTP_PORT}/rem_panel.html"
ANCHO, ALTO = 900, 640


def _rem_corriendo():
    # Solo el HTTP (sin él no hay página que cargar). Sondear el WS con un
    # connect/close crudo deja un traceback de handshake fallido en
    # rem_chat.log; si el WS falta, la página lo muestra y reintenta sola.
    return srv._puerto_activo("127.0.0.1", srv.HTTP_PORT)


class PanelApp(Gtk.Application):
    def __init__(self, pestana=None):
        super().__init__(application_id=APP_ID)
        self.win = None
        self.pestana = pestana

    def do_activate(self):
        if self.win is not None:   # segunda invocación: Gtk la reenvía acá
            self.win.present()
            return
        import personalidad
        self.win = Gtk.ApplicationWindow(application=self, title=f"{personalidad.NOMBRE_PERSONAJE} — Panel de control")
        self.win.set_default_size(ANCHO, ALTO)
        webview = crear_webview(transparente=False, prefijo="[Panel]")
        self.win.add(webview)
        params = {"personaje": personalidad.NOMBRE_PERSONAJE}
        if self.pestana:
            params["pestana"] = self.pestana
        url = URL_PANEL + "?" + urllib.parse.urlencode(params)
        cargar_con_retry(webview, url, prefijo="[Panel]")
        self.win.show_all()


def _avisar_sin_rem():
    """Sin servidor no hay página que cargar: diálogo + mensaje a la terminal
    y salida con código 1 — un lanzador sin terminal también se entera."""
    msg = ("Rem no está corriendo: el panel necesita su servidor "
           f"(:{srv.HTTP_PORT}/:{srv.WS_PORT}). Abre Yoru (lanzador «Yoru») y vuelve a abrir el panel.")
    print(f"[Panel] ERROR: {msg}", file=sys.stderr, flush=True)
    dialogo = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.CLOSE,
                                text="Rem no está corriendo")
    dialogo.format_secondary_text("Abre Yoru (lanzador «Yoru») y vuelve a abrir el panel.")
    dialogo.run()
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Panel de control de Rem.")
    ap.add_argument("--pestana", default=None, help="pestaña con la que abrir")
    pestana = ap.parse_args().pestana

    if not _rem_corriendo():
        _avisar_sin_rem()

    app = PanelApp(pestana)
    # register() ANTES de abrir el log: si ya hay un panel abierto, esta
    # invocación solo le pide que se muestre y sale — abrir el log con 'w'
    # truncaría el del panel que sigue vivo (mismo cuidado que rem_chat.py).
    app.register(None)
    if app.get_is_remote():
        print("[Panel] ya hay un panel abierto — se trae al frente")
        sys.exit(app.run(None))   # reenvía 'activate' a la otra instancia y se desregistra

    sys.stdout.reconfigure(line_buffering=True)
    print(f"[Panel] Log: {LOG_PATH}  (tail -f para seguirlo)")
    print(f"[Panel] Inspector remoto: http://{INSPECTOR}")
    redirigir_salida_a_log(LOG_PATH)

    # Cierre limpio con SIGTERM/SIGINT, igual que rem_chat.py.
    for sig in (15, 2):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: app.quit() or False)
    sys.exit(app.run(None))


if __name__ == '__main__':
    main()
