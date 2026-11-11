#!/usr/bin/env python3
"""
Yoru de escritorio — GTK3 + WebKit2. ES LA APLICACIÓN: levanta el servidor
HTTP/WS del avatar (mismo servidor, mismo pipeline de voz y LLM, un solo
proceso) y abre UNA de estas presentaciones, nunca dos a la vez:

  --modo ventana   Ventana normal decorada, opaca, con foco de teclado:
                   avatar de cuerpo entero + panel de chat.
  --modo escritorio  Avatar sobre el escritorio (layer surface) que se
                   arrastra con el ratón (Hyprland), reacciona a los clics y
                   tiene menú propio; el chat va en una ventana aparte. Con
                   «Fijar en la esquina» (menú, en vivo) queda quieto abajo a la
                   izquierda, a medio cuerpo y con una caja de texto. Ver
                   escritorio.py.
  --modo overlay   Alias de escritorio fijado en la esquina (el modo overlay se
                   fusionó con el de escritorio el 2026-11-10).

Sin --modo se usa el último modo usado (preferencias.json -> app.modo; lo
guarda este programa al arrancar), si no config.toml -> [app].modo, si no
escritorio. Cambiar de modo desde el menú reinicia el proceso (el tipo de
ventana se decide al arrancar) y la conversación pasa al nuevo
(--recuperar-conversacion). Si ya hay una instancia corriendo (puertos
:18765/:18766 ocupados) sale con un error claro en vez de abrir una segunda
presentación pegada a un servidor ajeno.

Al arrancar también precarga la voz (Piper) y el modelo de STT (faster-whisper) en hilos
de fondo, y llama a rem_avatar_server.iniciar_servidor_avatar().

Corre con el venv (venv/bin/python rem_chat.py): PyGObject/pycairo se
instalaron ahí sin problema, construidos contra las libs GTK3/WebKit2GTK ya
instaladas en el sistema (ver requirements.txt y CLAUDE.md). El modo escritorio
además necesita el paquete de sistema gtk-layer-shell.

    venv/bin/python rem_chat.py [--modo ventana|escritorio|overlay] [--recuperar-conversacion]
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

LOG_PATH = config.ruta_datos("rem_chat.log")


def _parsear_args():
    ap = argparse.ArgumentParser(
        description="Yoru: asistente virtual de escritorio (ventana o escritorio).")
    ap.add_argument("--modo", choices=("ventana", "escritorio", "overlay"), default=None,
                    help="presentación (default: el último usado; overlay = escritorio fijado en la esquina)")
    ap.add_argument("--recuperar-conversacion", action="store_true",
                    help="cargar la conversación que dejó el modo anterior (lo usa el cambio de modo)")
    return ap.parse_args()


_ARGS = _parsear_args()
# FIJAR_ESQUINA: arrancar con el escritorio fijado en la esquina (alias overlay).
MODO, FIJAR_ESQUINA = (config.resolver_modo(_ARGS.modo) if _ARGS.modo else config.leer_modo_app())

# Inspector remoto de WebKit — abrir http://127.0.0.1:9222 en un navegador
# normal para depurar rem_avatar.html como cualquier página. Debe fijarse
# ANTES de que WebKit2 se inicialice (import gi más abajo).
os.environ.setdefault('WEBKIT_INSPECTOR_SERVER', '127.0.0.1:9222')
# gtk-layer-shell solo funciona con GDK sobre Wayland nativo (con XWayland
# init_for_window falla) — se fuerza ANTES de que GDK se inicialice.
CAPA = MODO == "escritorio"   # layer surface (gtk-layer-shell)
# El valor de antes de forzarlo: un cambio de modo relanza con el entorno original.
_GDK_BACKEND_ORIGINAL = os.environ.get('GDK_BACKEND')
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

from gi.repository import Gtk, GLib

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
                 f"        Ciérrala primero (p. ej. lanzadores/rem-cerrar.sh); solo puede haber una, "
                 f"en un solo modo.")


# Pidfile: lo leen los lanzadores para cerrar o encontrar esta instancia sin
# buscar procesos por patrón. Línea 1: pid; línea 2: modo.
PID_PATH = config.ruta_datos("rem_chat.pid")


def _escribir_pidfile():
    """Se llama con el servidor ya levantado (esta instancia es la única).
    Escritura atómica: un lanzador nunca lee un archivo a medias. Se borra en
    atexit, que Python corre DESPUÉS de esperar a los hilos: si la salida se
    atasca ahí, el pidfile sigue y lanzadores/rem-cerrar.sh todavía encuentra el proceso."""
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
    import personalidad
    win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    win.set_title(personalidad.NOMBRE_PERSONAJE)
    win.set_default_size(ANCHO_DEFAULT, ALTO_DEFAULT)
    win.set_resizable(True)
    # Decorada, opaca, con foco (set_decorated/accept_focus ya son True por
    # defecto en un Gtk.Window normal). Sin set_app_paintable ni visual RGBA:
    # sin eso el compositor ya la pinta opaca.
    webview = crear_webview(transparente=False)
    win.add(webview)
    return win, webview


# ── Acciones de la app (menú del clic derecho, cualquier modo) ───────────
def _log_lanzador():
    """Log para lo que el proceso relanzado diga antes de abrir rem_chat.log
    (mismo sitio que los lanzadores: lanzadores/logs, o REM_DATOS/lanzadores_logs)."""
    d = (os.path.join(config.DATOS_DIR, "lanzadores_logs") if config.ENTORNO_AISLADO
         else os.path.join(BASE_DIR, "lanzadores", "logs"))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "rem-cambio-modo.log")


def _cambiar_modo_app(nuevo):
    """Reinicia en otro modo: guarda la conversación, deja lanzado un proceso
    que espera a que este termine (y suelte los puertos) y arranca el modo
    nuevo con --recuperar-conversacion, y cierra este."""
    import rem_avatar_server
    nuevo, _ = config.resolver_modo(nuevo)
    if nuevo == MODO:
        print(f"[Chat] cambio de modo ignorado: ya está en {MODO}", flush=True)
        return
    n = rem_avatar_server.guardar_conversacion_para_cambio()
    env = dict(os.environ)
    if _GDK_BACKEND_ORIGINAL is None:
        env.pop("GDK_BACKEND", None)
    else:
        env["GDK_BACKEND"] = _GDK_BACKEND_ORIGINAL
    pid = os.getpid()
    # Espera a que este proceso deje de existir (un zombi cuenta como muerto:
    # ya soltó los puertos), con un tope de 20 s.
    espera = (f'i=0; while [ -e /proc/{pid} ] && [ "$(cut -d" " -f3 /proc/{pid}/stat 2>/dev/null)" != Z ] '
              f'&& [ $i -lt 200 ]; do sleep 0.1; i=$((i+1)); done; ')
    orden = espera + (f"exec {shlex.quote(sys.executable)} {shlex.quote(os.path.join(BASE_DIR, 'rem_chat.py'))} "
                      f"--modo {nuevo} --recuperar-conversacion")
    log = _log_lanzador()
    with open(log, "a") as f:
        f.write(f"===== cambio de modo {MODO} -> {nuevo} (pid {pid}) =====\n")
    with open(log, "a") as salida:
        subprocess.Popen(["sh", "-c", orden], cwd=BASE_DIR, env=env, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=salida, stderr=subprocess.STDOUT)
    print(f"[Chat] cambio de modo {MODO} -> {nuevo}: {n} mensajes guardados; se cierra este proceso", flush=True)
    Gtk.main_quit()


def _accion_app(d):
    """En el hilo de GTK (GLib.idle_add desde el WS): ver establecer_oyente_app."""
    accion = d.get("accion")
    print(f"[Chat] acción del menú: {accion}{' -> ' + str(d.get('modo')) if accion == 'modo' else ''}", flush=True)
    if accion == "panel":
        import rem_avatar_server
        rem_avatar_server.abrir_panel(str(d.get("pestana") or ""))
    elif accion == "cerrar":
        Gtk.main_quit()
    elif accion == "modo":
        _cambiar_modo_app(str(d.get("modo") or ""))
    return False


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
    if config.ENTORNO_AISLADO:
        print(f"[Chat] ENTORNO AISLADO (REM_DATOS): datos de ejecución en {config.DATOS_DIR}")
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
    # Frases fijas con voz (frases_voz.py): las reacciones del escritorio y los
    # avisos (micrófono, errores, confirmar), que valen en cualquier modo.
    import frases_voz
    threading.Thread(target=frases_voz.precargar, daemon=True).start()

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

    # El último modo: el lanzador «Yoru» (sin --modo) abre este la próxima vez.
    import preferencias
    try:
        preferencias.aplicar("app", {"modo": MODO})
    except preferencias.PreferenciaInvalida as e:
        print(f"[Chat] no se pudo guardar el último modo ({e})")
    if _ARGS.recuperar_conversacion:
        n = rem_avatar_server.recuperar_conversacion()
        print(f"[Chat] conversación del modo anterior: {n} mensajes recuperados" if n
              else "[Chat] no había conversación que recuperar del modo anterior")
    rem_avatar_server.establecer_oyente_app(lambda d: GLib.idle_add(_accion_app, d))

    if MODO == "escritorio":
        import escritorio
        try:
            avatar, _chat = escritorio.crear_escritorio(
                lambda fijo, aire: rem_avatar_server.url_avatar(MODO, fijo, aire),
                rem_avatar_server.url_chat_ventana(), fijar=FIJAR_ESQUINA)
        except RuntimeError as e:
            _fatal(str(e))
        win = avatar.win
        # El lanzador «Yoru» con una instancia ya abierta en escritorio manda
        # SIGUSR1 si el WebSocket no responde: vuelve a mostrar el avatar.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 10, avatar.mostrar)
    else:
        win, webview = _crear_ventana()
        cargar_con_retry(webview, rem_avatar_server.url_avatar(MODO))

    _iniciar_vigilante()
    win.connect('destroy', Gtk.main_quit)
    # Cierre limpio con SIGTERM/SIGINT (pkill, Ctrl+C, lanzadores/rem-cerrar.sh).
    for sig in (15, 2):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: Gtk.main_quit() or False)
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()