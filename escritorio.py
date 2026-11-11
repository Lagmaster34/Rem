"""escritorio.py — el modo escritorio de rem_chat.py (--modo escritorio).

Dos ventanas en el mismo proceso que el servidor:

  * El AVATAR: layer surface (gtk-layer-shell) transparente, anclada
    IZQUIERDA+ABAJO, con el modelo de cuerpo entero. Click-through salvo el
    cuerpo dibujado: la página manda la región (cajas alrededor de los huesos
    proyectados, ver avatar/escritorio_ui.js) y se aplica con
    input_shape_combine_region. Se arrastra con el botón izquierdo: la posición
    sale del cursor GLOBAL (`j/cursorpos` del socket de Hyprland), no de deltas
    locales — con deltas el arrastre se pasaba de largo (+7 % lento, ~+80 %
    rápido) porque llegan eventos antes de que el compositor mueva la capa
    (etapa 0 de la fase 2, ver CLAUDE.md). Un clic sin arrastre se le pasa a la
    página (reacciones); el derecho lo resuelve la página (su menú).
    FIJADO EN LA ESQUINA (menú → «Fijar en la esquina», o --modo overlay, el
    antiguo modo overlay): sin arrastre, anclado abajo a la izquierda con el
    tamaño y los márgenes de config.toml [overlay], a medio cuerpo y con una caja
    de texto. Se activa y se quita en vivo; la posición libre se conserva. El
    teclado solo se toma con el puntero sobre la caja o escribiendo en ella.
  * El CHAT: ventana GTK normal con rem_chat_ventana.html (el panel de chat de
    siempre, con su propio WebSocket). Se crea la primera vez que se pide y al
    cerrarla solo se oculta.

Se importa DESPUÉS de que rem_chat.py fije GDK_BACKEND=wayland e importe
GtkLayerShell (tiene que enlazarse antes que libwayland-client).
"""
import json
import math
import os
import socket
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import GtkLayerShell, Gtk, Gdk, GLib  # noqa: E402

from webview_comun import cargar_con_retry, crear_webview  # noqa: E402

import config  # noqa: E402

BASE_DIR = config.BASE_DIR
ESTADO_PATH = config.ruta_datos("escritorio_estado.json")
UMBRAL_ARRASTRE_PX = 6
TICK_ARRASTRE_MS = 16
SUAVIZADO_VEL_S = 0.06    # constante de tiempo del filtro de la velocidad de arrastre
TICK_CURSOR_MS = 100      # posición del cursor para que la cabeza lo siga
# Cuánto puede salirse la superficie de la pantalla, en fracción de su tamaño:
# es más grande que el modelo (aire para la burbuja y los botones), y sin esto
# el cuerpo nunca llegaría al borde.
SALIDA_X = 0.30
SALIDA_ARRIBA = 0.10


def _log(msg):
    print(f"[Escritorio] {msg}", flush=True)


class Hyprland:
    """Consultas JSON al socket de control de Hyprland. disponible=False fuera
    de Hyprland: entonces no hay arrastre (la posición del cursor global no se
    puede saber de otra forma en Wayland)."""

    def __init__(self):
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
        run = os.environ.get("XDG_RUNTIME_DIR", "")
        self.ruta = f"{run}/hypr/{sig}/.socket.sock" if sig else None
        self.disponible = bool(self.ruta and os.path.exists(self.ruta))

    def consultar(self, cmd):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as so:
            so.settimeout(0.5)
            so.connect(self.ruta)
            so.sendall(f"j/{cmd}".encode())
            datos = b""
            while True:
                parte = so.recv(65536)
                if not parte:
                    break
                datos += parte
        return json.loads(datos)

    def despachar(self, orden):
        """`hyprctl dispatch <orden>` por el socket."""
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as so:
            so.settimeout(0.5)
            so.connect(self.ruta)
            so.sendall(f"dispatch {orden}".encode())
            return so.recv(256).decode(errors="replace").strip()

    def monitores(self):
        """[{nombre, x, y, w, h, res: [izq, arriba, der, abajo], enfocado}] en
        coordenadas LÓGICAS (las de cursorpos y de los márgenes)."""
        res = []
        for m in self.consultar("monitors"):
            if m.get("disabled"):
                continue
            esc = float(m.get("scale") or 1) or 1
            w, h = m["width"] / esc, m["height"] / esc
            if int(m.get("transform", 0)) % 2 == 1:
                w, h = h, w
            res.append({"nombre": m["name"], "x": m["x"], "y": m["y"], "w": w, "h": h,
                        "res": list(m.get("reserved") or [0, 0, 0, 0]),
                        "enfocado": bool(m.get("focused"))})
        return res


_CAPAS = {"overlay": GtkLayerShell.Layer.OVERLAY, "bottom": GtkLayerShell.Layer.BOTTOM,
          "top": GtkLayerShell.Layer.TOP}


def _monitor_de_punto(monitores, x, y):
    for m in monitores:
        if m["x"] <= x < m["x"] + m["w"] and m["y"] <= y < m["y"] + m["h"]:
            return m
    return None


def _gdk_monitor(m):
    """El Gdk.Monitor del monitor de Hyprland `m` (por la posición: GTK3 no da
    el nombre del conector)."""
    disp = Gdk.Display.get_default()
    for i in range(disp.get_n_monitors()):
        gm = disp.get_monitor(i)
        g = gm.get_geometry()
        if g.x == int(m["x"]) and g.y == int(m["y"]):
            return gm
    return None


class VentanaChat:
    """La ventana de chat aparte. Perezosa: el WebView (y su proceso) se crea
    al abrirla por primera vez; al cerrarla se oculta y conserva la charla."""

    def __init__(self, cfg, url):
        self.cfg = cfg
        self.url = url
        self.win = None

    def _crear(self):
        import personalidad
        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_title(f"{personalidad.NOMBRE_PERSONAJE} — chat")
        win.set_default_size(self.cfg["chat_ancho"], self.cfg["chat_alto"])
        webview = crear_webview(transparente=False, prefijo="[ChatVentana]")
        win.add(webview)
        win.connect("delete-event", lambda w, _e: w.hide() or True)
        cargar_con_retry(webview, self.url, prefijo="[ChatVentana]")
        self.win = win

    def visible(self):
        return bool(self.win and self.win.get_visible())

    def mostrar(self, monitor=None, hypr=None):
        """`monitor`: el del avatar. Se enfoca antes de mapear la ventana: Hyprland
        abre las ventanas en el monitor enfocado, y la regla `center` (ver
        CLAUDE.md, "Modo escritorio") la centra ahí."""
        if self.win is None:
            self._crear()
        if not self.visible() and monitor and hypr and hypr.disponible:
            try:
                hypr.despachar(f"focusmonitor {monitor}")
            except OSError:
                pass
        self.win.show_all()
        self.win.present()

    def alternar(self, monitor=None, hypr=None):
        if self.visible():
            self.win.hide()
        else:
            self.mostrar(monitor, hypr)


class AvatarEscritorio:
    def __init__(self, cfg, url_avatar, chat, fijar=False):
        """`url_avatar(fijo, aire) -> str`: la URL de la página (fijo añade
        ?fijo=1 y el aire lateral en px).
        `fijar`: arrancar fijado en la esquina aunque no estuviera guardado así
        (alias --modo overlay)."""
        self.cfg = cfg
        self.cfg_fijo = config.leer_config_overlay()
        self.chat = chat
        self.hypr = Hyprland()
        guardado = self._leer_estado()
        self.fijado = bool(guardado.get("fijado")) or fijar
        # Capa, barras y tamaño: preferencias del panel (pestaña Escritorio)
        # sobre config.toml [escritorio]; se aplican también en vivo.
        import preferencias
        self.prefs = preferencias.obtener("escritorio")
        self.ancho, self.alto = self._tamano(self.prefs["tamano"])
        self.rects = []                 # región del cuerpo + interfaz, px de superficie
        self.region_recibida = False
        self.izq, self.inf = cfg["margen_izquierdo"], cfg["margen_inferior"]
        self.libre = (self.izq, self.inf)   # posición suelta, la que se guarda
        # Caja de texto (solo fijado): puntero encima / escribiendo en ella.
        self.caja = {"encima": False, "foco": False}
        self._modo_teclado = None
        self.monitor = None             # dict de Hyprland.monitores()
        self.pulsado = None             # estado del botón izquierdo, o None
        self._soltado = None            # último soltar sin 'presion' todavía (ver _on_mensaje)
        self._tick = None
        self.oculto = False
        self._ultimo_cursor = None

        win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        win.set_title("rem_escritorio")
        win.set_decorated(False)
        win.set_app_paintable(True)
        if not GtkLayerShell.is_supported():
            raise RuntimeError("el compositor no anuncia zwlr_layer_shell_v1 (¿no es Wayland/Hyprland?)")
        GtkLayerShell.init_for_window(win)
        GtkLayerShell.set_namespace(win, "rem_escritorio")   # para layerrule de Hyprland
        GtkLayerShell.set_layer(win, _CAPAS.get(self.prefs["capa"], GtkLayerShell.Layer.TOP))
        GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(win, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_exclusive_zone(win, 0 if self.prefs["respetarBarras"] else -1)
        win.set_size_request(self.ancho, self.alto)

        screen = win.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            win.set_visual(visual)
        css = Gtk.CssProvider()
        css.load_from_data(b"window, webview { background-color: transparent; background: transparent; }")
        Gtk.StyleContext.add_provider_for_screen(screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        webview = crear_webview(transparente=True)
        # Sin el menú contextual de WebKit: el clic derecho abre el de la página.
        webview.connect("context-menu", lambda *a: True)
        webview.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                           | Gdk.EventMask.POINTER_MOTION_MASK)
        # connect() (no connect_after): estos corren ANTES que el manejador
        # propio del WebView, y devuelven False para que la página también
        # reciba el evento.
        webview.connect("button-press-event", self._on_press)
        webview.connect("motion-notify-event", self._on_motion)
        webview.connect("button-release-event", self._on_release)
        win.add(webview)
        win.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        win.connect("enter-notify-event", self._on_cruce, True)
        win.connect("leave-notify-event", self._on_cruce, False)

        # Mensajes de la página: por el WebSocket del servidor (mismo proceso),
        # no por un script message handler — ver establecer_oyente_escritorio
        # en rem_avatar_server.py (cuelgue de JavaScriptCore).
        import rem_avatar_server
        rem_avatar_server.establecer_oyente_escritorio(
            lambda datos: GLib.idle_add(self._on_mensaje, datos))
        win.connect("realize", self.aplicar_region)
        win.connect("size-allocate", self.aplicar_region)
        win.connect("map", self.aplicar_region)

        self.win, self.webview = win, webview
        # Teclado: NONE salvo con el puntero sobre la caja de texto o
        # escribiendo en ella (solo fijado). Ver _actualizar_teclado.
        self._actualizar_teclado()
        self._posicion_inicial(guardado)
        if fijar and not guardado.get("fijado"):
            self._guardar()   # el alias --modo overlay deja fijado como estado: «Yoru» lo reabre así
        preferencias.al_cambiar("escritorio", lambda v: GLib.idle_add(self._aplicar_prefs, v))
        cargar_con_retry(webview, url_avatar(self.fijado, self._aire()))
        GLib.timeout_add_seconds(20, self._avisar_si_no_hay_region)
        if not self.hypr.disponible:
            _log("AVISO: no es Hyprland (sin HYPRLAND_INSTANCE_SIGNATURE): el avatar no se podrá arrastrar.")
        else:
            GLib.timeout_add(TICK_CURSOR_MS, self._tick_cursor)

    def _tamano(self, pct):
        if self.fijado:
            ancho = self.cfg_fijo["ancho"] + 2 * self.cfg_fijo["aire_lateral"]
            return int(round(ancho * pct / 100)), int(round(self.cfg_fijo["alto"] * pct / 100))
        return int(round(self.cfg["ancho"] * pct / 100)), int(round(self.cfg["alto"] * pct / 100))

    def _aire(self):
        """Aire transparente a cada lado del cuadro de Yoru fijado (px de
        superficie), para los codos de los clips con los brazos abiertos."""
        return int(round(self.cfg_fijo["aire_lateral"] * self.prefs["tamano"] / 100)) if self.fijado else 0

    def _margenes_fijo(self):
        """Fijado: el cuadro de Yoru en los márgenes de [overlay]; la superficie,
        corrida a la izquierda lo que mide su aire (puede quedar fuera de la pantalla)."""
        return self.cfg_fijo["margen_izquierdo"] - self._aire(), self.cfg_fijo["margen_inferior"]

    def _aplicar_prefs(self, v):
        """Oyente de la sección "escritorio" (en el hilo de GTK): capa, respetar
        barras y tamaño, en vivo. La esquina inferior izquierda queda donde
        estaba; crecer o encoger va hacia arriba y a la derecha."""
        anterior, self.prefs = self.prefs, v
        GtkLayerShell.set_layer(self.win, _CAPAS.get(v["capa"], GtkLayerShell.Layer.TOP))
        GtkLayerShell.set_exclusive_zone(self.win, 0 if v["respetarBarras"] else -1)
        if v["tamano"] != anterior["tamano"]:
            self.ancho, self.alto = self._tamano(v["tamano"])
            self.win.set_size_request(self.ancho, self.alto)
            self.win.resize(self.ancho, self.alto)
            if self.monitor and not self.fijado:
                self.izq, self.inf = self._acotar(self.monitor, self.izq, self.inf)
                self.libre = (self.izq, self.inf)
                self._fijar_margenes()
            elif self.fijado:
                self.izq, self.inf = self._margenes_fijo()
                self._fijar_margenes()
                self._js(f"fijado(true, {self._aire()})")
        _log(f"preferencias: capa {v['capa']}, barras {'respetadas' if v['respetarBarras'] else 'ignoradas'}, "
             f"tamaño {v['tamano']}% ({self.ancho}x{self.alto})")
        return False

    # ── posición ────────────────────────────────────────────────────────
    @staticmethod
    def _leer_estado():
        try:
            with open(ESTADO_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _posicion_inicial(self, guardado):
        if self.hypr.disponible:
            try:
                mons = self.hypr.monitores()
                self.monitor = (next((m for m in mons if m["nombre"] == guardado.get("monitor")), None)
                                or next((m for m in mons if m["enfocado"]), None)
                                or (mons[0] if mons else None))
            except Exception as e:
                _log(f"no se pudieron leer los monitores ({e})")
        if self.monitor and guardado.get("monitor") == self.monitor["nombre"]:
            # Se acota con el tamaño suelto aunque arranque fijado (es la posición suelta).
            fijado, self.fijado = self.fijado, False
            ancho, alto = self.ancho, self.alto
            self.ancho, self.alto = self._tamano(self.prefs["tamano"])
            self.izq, self.inf = self._acotar(self.monitor, guardado.get("izq", self.izq),
                                              guardado.get("inf", self.inf))
            self.fijado, self.ancho, self.alto = fijado, ancho, alto
        self.libre = (self.izq, self.inf)
        if self.fijado:
            self.izq, self.inf = self._margenes_fijo()
        if self.monitor:
            gm = _gdk_monitor(self.monitor)
            if gm:
                GtkLayerShell.set_monitor(self.win, gm)
        self._fijar_margenes()
        _log(f"{self.ancho}x{self.alto} en {self.monitor['nombre'] if self.monitor else '?'} "
             f"(izq={self.izq}, inf={self.inf}), capa {self.prefs['capa']}"
             + (", FIJADO en la esquina" if self.fijado else ""))

    def fijar(self, si):
        """Fijar en la esquina o soltar, en vivo: tamaño, márgenes, teclado y
        la página (encuadre, caja de texto, clips aptos). La posición suelta se
        conserva y se vuelve a ella al soltar."""
        si = bool(si)
        if si == self.fijado:
            self._js(f"fijado({'true' if si else 'false'}, {self._aire()})")
            return
        if self.pulsado:
            self._on_release(None, None)   # un arrastre en curso termina aquí
        if si:
            self.libre = (self.izq, self.inf)
        self.fijado = si
        self.ancho, self.alto = self._tamano(self.prefs["tamano"])
        self.win.set_size_request(self.ancho, self.alto)
        self.win.resize(self.ancho, self.alto)
        if si:
            self.izq, self.inf = self._margenes_fijo()
        else:
            self.izq, self.inf = self.libre
            if self.monitor:
                self.izq, self.inf = self._acotar(self.monitor, self.izq, self.inf)
            self.caja = {"encima": False, "foco": False}
        self._fijar_margenes()
        self._actualizar_teclado()
        self._js(f"fijado({'true' if si else 'false'}, {self._aire()})")
        self._guardar()
        _log(f"{'fijado en la esquina' if si else 'suelto'}: {self.ancho}x{self.alto}, izq={self.izq}, inf={self.inf}")

    def _actualizar_teclado(self):
        """Medido en vivo con el overlay (CLAUDE.md, "Modo overlay"): con
        ON_DEMAND fijo, en Hyprland basta pasar el puntero para que la capa se
        quede el teclado. Así que NONE siempre, salvo fijado con el puntero
        sobre la caja o escribiendo en ella."""
        dentro = self.fijado and (self.caja["encima"] or self.caja["foco"])
        modo = GtkLayerShell.KeyboardMode.ON_DEMAND if dentro else GtkLayerShell.KeyboardMode.NONE
        if modo == self._modo_teclado:
            return
        self._modo_teclado = modo
        GtkLayerShell.set_keyboard_mode(self.win, modo)
        self.win.queue_draw()   # el cambio se aplica en el próximo commit
        _log(f"teclado -> {'ON_DEMAND' if dentro else 'NONE'} (caja: encima={self.caja['encima']}, "
             f"escribiendo={self.caja['foco']})")

    def _area(self, m):
        """Rectángulo utilizable del monitor (sin las zonas reservadas por
        barras): los márgenes de la capa cuentan desde ahí."""
        r = m["res"]
        return m["x"] + r[0], m["y"] + r[1], m["w"] - r[0] - r[2], m["h"] - r[1] - r[3]

    def _acotar(self, m, izq, inf):
        _, _, aw, ah = self._area(m)
        izq = max(-self.ancho * SALIDA_X, min(aw - self.ancho * (1 - SALIDA_X), izq))
        inf = max(0, min(ah - self.alto * (1 - SALIDA_ARRIBA), inf))
        return int(round(izq)), int(round(inf))

    def _fijar_margenes(self):
        GtkLayerShell.set_margin(self.win, GtkLayerShell.Edge.LEFT, self.izq)
        GtkLayerShell.set_margin(self.win, GtkLayerShell.Edge.BOTTOM, self.inf)

    def _esquina_global(self, m=None, izq=None, inf=None):
        """Esquina superior izquierda de la superficie en coordenadas globales."""
        m = m or self.monitor
        ax, ay, _, ah = self._area(m)
        izq = self.izq if izq is None else izq
        inf = self.inf if inf is None else inf
        return ax + izq, ay + ah - inf - self.alto

    def _guardar(self):
        if not self.monitor:
            return
        izq, inf = self.libre if self.fijado else (self.izq, self.inf)
        try:
            tmp = ESTADO_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"monitor": self.monitor["nombre"], "izq": izq, "inf": inf,
                           "fijado": self.fijado}, f)
            os.replace(tmp, ESTADO_PATH)
        except OSError as e:
            _log(f"no se pudo guardar la posición ({e})")

    # ── región de entrada ───────────────────────────────────────────────
    def aplicar_region(self, *_a):
        import cairo
        gdk_win = self.win.get_window()
        if not gdk_win:
            return
        rects = [] if self.oculto else self.rects
        region = cairo.Region([cairo.RectangleInt(*r) for r in rects]) if rects else cairo.Region()
        gdk_win.input_shape_combine_region(region, 0, 0)
        # La región se manda en el próximo commit del toplevel; sin forzar un
        # redibujado podía quedarse sin aplicar (ver "Modo overlay" en CLAUDE.md).
        self.win.queue_draw()

    def _avisar_si_no_hay_region(self):
        if not self.region_recibida:
            _log("AVISO: la página no mandó la región del cuerpo en 20 s: todo es click-through.")
        return False

    # ── página → Python ─────────────────────────────────────────────────
    def _on_mensaje(self, d):
        """Corre en el hilo de GTK (GLib.idle_add desde el hilo del WS)."""
        try:
            self._procesar_mensaje(d)
        except Exception as e:
            _log(f"mensaje de la página ilegible ({type(e).__name__}: {e})")
        return False

    def _procesar_mensaje(self, d):
        tipo = d.get("tipo")
        if tipo == "region":
            rects = []
            for r in d.get("rects") or []:
                x, y, w, h = (int(v) for v in r)
                if w > 0 and h > 0:
                    rects.append((x, y, w, h))
            if not self.region_recibida:
                _log(f"primera región del cuerpo: {len(rects)} cajas")
            self.region_recibida = True
            self.rects = rects
            self.aplicar_region()
        elif tipo == "presion":
            # La página confirma que el botón se pulsó sobre el cuerpo (no sobre
            # un botón o el menú): solo entonces mover el ratón arrastra. Puede
            # llegar DESPUÉS de los movimientos (o hasta del soltar) si el bucle
            # de GTK va cargado — p. ej. con el STT calentándose se vio un
            # arrastre entero tomado como clic —, así que el orden no importa.
            if self.pulsado is not None:
                self.pulsado["armado"] = True
                self._quizas_arrastrar()
            elif self._soltado and time.monotonic() - self._soltado["t"] < 0.5:
                p, self._soltado = self._soltado, None
                if not p["movido"]:
                    self._js(f"clic({p['x']:.0f},{p['y']:.0f})")
        elif tipo == "accion":
            self._accion(str(d.get("accion")), d)
        elif tipo == "teclado":
            # La caja de texto (fijado): puntero encima / foco de escritura.
            self.caja = {"encima": bool(d.get("encima")), "foco": bool(d.get("foco"))}
            self._actualizar_teclado()
        elif tipo == "sin_frames":
            # La página está viva pero no le llegan frames (avatar/bucle.js).
            # Puede ser que la superficie dejara de recibir frame callbacks del
            # compositor: se fuerza un commit (redibujado + márgenes otra vez).
            _log(f"la página lleva {d.get('s')} s sin frames: se fuerza un redibujado de la superficie")
            self.webview.queue_draw()
            self.win.queue_draw()
            self._fijar_margenes()
            self.aplicar_region()

    def _accion(self, accion, d=None):
        d = d or {}
        _log(f"acción: {accion}")
        mon = self.monitor["nombre"] if self.monitor else None
        if accion == "chat":
            self.chat.alternar(mon, self.hypr)
        elif accion == "chat_abrir":
            self.chat.mostrar(mon, self.hypr)
        elif accion in ("panel", "ajustes"):
            import rem_avatar_server
            rem_avatar_server.abrir_panel(str(d.get("pestana") or "") if accion == "ajustes" else "")
        elif accion == "fijar":
            self.fijar(bool(d.get("si")))
        elif accion == "posicion_inicial" and not self.fijado:
            izq, inf = self.cfg["margen_izquierdo"], self.cfg["margen_inferior"]
            self.izq, self.inf = self._acotar(self.monitor, izq, inf) if self.monitor else (izq, inf)
            self._fijar_margenes()
            self._guardar()
        elif accion == "ocultar":
            self.ocultar(True)
        elif accion == "mostrar":
            self.ocultar(False)
        elif accion == "alternar":
            self.ocultar(not self.oculto)
        elif accion == "salir":
            Gtk.main_quit()

    def ocultar(self, si):
        """Ocultar NO desmapea la capa (en la sesión real, volver a mapearla no
        siempre la hacía reaparecer): la página deja de dibujar y se vacía la
        región de clic, así que queda invisible y atravesable."""
        if si == self.oculto:
            return
        self.oculto = si
        self._js(f"ocultar({'true' if si else 'false'})")
        self.aplicar_region()
        _log("oculto — vuelve con el lanzador «Rem Escritorio» o el atajo" if si else "visible otra vez")

    def mostrar(self):
        """SIGUSR1 (respaldo del lanzador si el WebSocket no responde)."""
        if not self.win.get_visible():
            self.win.show_all()
        self.ocultar(False)
        return GLib.SOURCE_CONTINUE

    # ── Python → página ─────────────────────────────────────────────────
    def _js(self, codigo):
        codigo = f"window.__remEscritorio && window.__remEscritorio.{codigo};"
        try:
            self.webview.evaluate_javascript(codigo, -1, None, None, None, None, None)
        except (AttributeError, TypeError):
            self.webview.run_javascript(codigo, None, None, None)

    def _tick_cursor(self):
        """La página hace que la cabeza siga al cursor: le pasa su posición en
        px de la superficie (puede estar fuera de ella) cuando cambia."""
        if self.oculto or self.pulsado or not self.monitor or not self.win.get_visible():
            return True
        try:
            cur = self.hypr.consultar("cursorpos")
        except Exception:
            return True
        ex, ey = self._esquina_global()
        pos = (round(cur["x"] - ex), round(cur["y"] - ey))
        if pos != self._ultimo_cursor:
            self._ultimo_cursor = pos
            self._js(f"cursor({pos[0]},{pos[1]})")
        return True

    def _on_cruce(self, _w, evento, entra):
        if evento.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._js(f"puntero({'true' if entra else 'false'})")
        # Saliendo de la superficie directamente desde la caja de texto la
        # página no recibe mouseleave (visto en el anidado): sin esto el
        # teclado se quedaba tomado. Escribiendo (foco) sí se conserva.
        if not entra and self.caja["encima"]:
            self.caja["encima"] = False
            self._actualizar_teclado()
        return False

    # ── arrastre y clic ─────────────────────────────────────────────────
    def _on_press(self, _w, e):
        if e.button != 1 or e.type != Gdk.EventType.BUTTON_PRESS:
            return False
        self.pulsado = {"x": e.x, "y": e.y, "armado": False, "movido": False, "arrastrando": False}
        self._soltado = None
        if self.hypr.disponible and self.monitor:
            try:
                cur = self.hypr.consultar("cursorpos")
                ex, ey = self._esquina_global()
                self.pulsado.update(agarre=(cur["x"] - ex, cur["y"] - ey),
                                    monitores=self.hypr.monitores())
                # El monitor actual con sus zonas reservadas de ESTE momento.
                self.monitor = next((m for m in self.pulsado["monitores"]
                                     if m["nombre"] == self.monitor["nombre"]), self.monitor)
            except Exception as ex:
                _log(f"cursorpos falló al pulsar ({ex}): sin arrastre esta vez")
        return False

    def _on_motion(self, _w, e):
        p = self.pulsado
        if not p or p["movido"]:
            return False
        if ((e.x - p["x"]) ** 2 + (e.y - p["y"]) ** 2) ** 0.5 > UMBRAL_ARRASTRE_PX:
            p["movido"] = True
            self._quizas_arrastrar()
        return False

    def _quizas_arrastrar(self):
        """Arranca el arrastre cuando se cumplen las dos cosas, en el orden que
        lleguen: la página confirmó que se pulsó el cuerpo y el ratón pasó el
        umbral. La posición sale del cursor global, así que empezar tarde no
        pierde nada del recorrido."""
        p = self.pulsado
        if (not p or p["arrastrando"] or not (p["armado"] and p["movido"]) or "agarre" not in p
                or self.fijado):
            return
        p["arrastrando"] = True
        p["t0"] = time.perf_counter()
        self._js(f"arrastreInicio({p['x']:.0f},{p['y']:.0f})")
        self._tick = GLib.timeout_add(TICK_ARRASTRE_MS, self._tick_arrastre)

    def _destino(self):
        """(monitor bajo el cursor, izq, inf) para el cursor actual. Mientras se
        arrastra, la capa se queda en su monitor (pegada al borde): cambiarla
        de monitor la vuelve a crear y se perdería el arrastre en curso."""
        cur = self.hypr.consultar("cursorpos")
        gx, gy = self.pulsado["agarre"]
        ex, ey = cur["x"] - gx, cur["y"] - gy
        bajo = _monitor_de_punto(self.pulsado["monitores"], cur["x"], cur["y"]) or self.monitor
        return bajo, ex, ey

    def _margenes_en(self, m, ex, ey):
        ax, ay, _, ah = self._area(m)
        return self._acotar(m, ex - ax, (ay + ah) - (ey + self.alto))

    def _tick_arrastre(self):
        if not self.pulsado or not self.pulsado["arrastrando"]:
            self._tick = None
            return False
        try:
            _, ex, ey = self._destino()
        except Exception:
            return True
        izq, inf = self._margenes_en(self.monitor, ex, ey)
        if (izq, inf) != (self.izq, self.inf):
            self.izq, self.inf = izq, inf
            self._fijar_margenes()
        gx, gy = self._esquina_global()
        # Velocidad de la superficie (px/s) con las marcas de tiempo de AQUÍ:
        # las llamadas a la página pueden llegarle a ráfagas, y calcularla allí
        # daba picos y ceros (la inclinación casi no se veía en la sesión real).
        p = self.pulsado
        ahora = time.monotonic()
        if "ult" in p:
            dt = ahora - p["ult"][2]
            if dt > 1e-3:
                a = 1 - math.exp(-dt / SUAVIZADO_VEL_S)
                p["vx"] += ((gx - p["ult"][0]) / dt - p["vx"]) * a
                p["vy"] += ((gy - p["ult"][1]) / dt - p["vy"]) * a
        else:
            p["vx"] = p["vy"] = 0.0
        p["ult"] = (gx, gy, ahora)
        self._js(f"posicion({gx:.1f},{gy:.1f},{p['vx']:.0f},{p['vy']:.0f})")
        return True

    def _on_release(self, _w, e):
        """`e` None: cortar un arrastre en curso (al fijar en la esquina)."""
        if e is not None and e.button != 1:
            return False
        p, self.pulsado = self.pulsado, None
        if self._tick:
            GLib.source_remove(self._tick)
            self._tick = None
        if not p:
            return False
        if p["arrastrando"]:
            try:
                bajo, ex, ey = self._destino_final(p)
                if bajo and bajo["nombre"] != self.monitor["nombre"]:
                    gm = _gdk_monitor(bajo)
                    if gm:
                        self.monitor = bajo
                        GtkLayerShell.set_monitor(self.win, gm)
                        _log(f"pasa al monitor {bajo['nombre']}")
                self.izq, self.inf = self._margenes_en(self.monitor, ex, ey)
                self._fijar_margenes()
            except Exception as ex_:
                _log(f"fin de arrastre sin cursorpos ({ex_})")
            self._js("arrastreFin()")
            self.libre = (self.izq, self.inf)
            self._guardar()
            _log(f"arrastre: {time.perf_counter() - p['t0']:.2f}s -> {self.monitor['nombre']} "
                 f"izq={self.izq} inf={self.inf}")
        elif e is None:
            pass
        elif p["armado"] and not p["movido"]:
            self._js(f"clic({e.x:.0f},{e.y:.0f})")
        elif not p["armado"]:
            # El 'presion' de la página aún no llegó: puede ser un clic en el
            # cuerpo o en un botón; lo decide su llegada (o su ausencia).
            self._soltado = {"x": e.x, "y": e.y, "movido": p["movido"], "t": time.monotonic()}
        return False

    def _destino_final(self, p):
        self.pulsado = p          # _destino() lo lee
        try:
            return self._destino()
        finally:
            self.pulsado = None


def crear_escritorio(url_avatar, url_chat, fijar=False):
    """Crea las dos ventanas; devuelve (avatar, chat). La del avatar se muestra
    desde rem_chat.py (show_all) como las otras presentaciones.
    `url_avatar(fijo, aire) -> str`; `fijar`: arrancar fijado en la esquina."""
    cfg = config.leer_config_escritorio()
    chat = VentanaChat(cfg, url_chat)
    avatar = AvatarEscritorio(cfg, url_avatar, chat, fijar=fijar)
    return avatar, chat
