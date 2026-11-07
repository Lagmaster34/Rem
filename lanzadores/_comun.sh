#!/usr/bin/env bash
# Funciones compartidas por los lanzadores (se carga con `source`, no se ejecuta).
# Todo se calcula desde la ubicación de este archivo: si se mueve el proyecto,
# los lanzadores siguen funcionando sin tocar nada.

LANZADORES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(dirname "$LANZADORES_DIR")"
PYTHON="$RAIZ/venv/bin/python"
# Con REM_DATOS (entorno aislado de pruebas, ver config.DATOS_DIR) los logs y el
# pidfile van ahí: un lanzador corrido dentro de una prueba nunca encuentra ni
# cierra la instancia real.
DATOS="${REM_DATOS:-$RAIZ}"
LOG_DIR="${REM_DATOS:+$REM_DATOS/lanzadores_logs}"
LOG_DIR="${LOG_DIR:-$LANZADORES_DIR/logs}"
mkdir -p "$LOG_DIR"

# Abre el log del lanzador (se agrega, no se pisa) con una cabecera por arranque.
# La consola de WebKit y casi todo lo de rem_chat.py va además a rem_chat.log;
# acá queda lo anterior a eso (arranque, errores de import, instancia ocupada).
abrir_log() {
    LOG="$LOG_DIR/$1.log"
    echo "===== $(date '+%F %T') — $1 =====" >>"$LOG"
}

comprobar_venv() {
    if [[ ! -x "$PYTHON" ]]; then
        echo "No existe $PYTHON — recreá el venv (ver CLAUDE.md, 'Ruta del proyecto')." | tee -a "$LOG" >&2
        command -v notify-send >/dev/null && notify-send "Rem" "No se encontró el venv en $RAIZ/venv"
        exit 1
    fi
}

# rem_chat.py escribe su pid (línea 1) y su modo (línea 2) en este archivo al
# levantar el servidor y lo borra al salir. Los lanzadores lo usan en vez de
# buscar procesos por patrón.
PIDFILE="$DATOS/rem_chat.pid"
# Segundos de espera al cierre limpio antes de darlo por colgado y matarlo.
_ESPERA_CIERRE_S=5

# Imprime el pid de la instancia de Rem abierta, o nada. Antes de fiarse del
# pidfile comprueba que ese pid sigue siendo un python con ESTE rem_chat.py
# (argv[1] resuelto contra su directorio de trabajo): tras un SIGKILL el
# archivo queda y el pid puede haberlo reusado otro proceso. Un pidfile
# viejo se borra.
pid_rem_chat() {
    local pid arg0 arg1 cwd
    [[ -f "$PIDFILE" ]] || return 0
    pid="$(head -n1 "$PIDFILE" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && [[ -r /proc/$pid/cmdline ]]; then
        { IFS= read -r -d '' arg0; IFS= read -r -d '' arg1; } <"/proc/$pid/cmdline" || true
        cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
        [[ "$arg1" == /* ]] || arg1="$cwd/$arg1"
        if [[ "$(basename "$arg0")" =~ ^python[0-9.]*$ ]] &&
           [[ "$(readlink -f "$arg1" 2>/dev/null)" == "$RAIZ/rem_chat.py" ]]; then
            echo "$pid"
            return 0
        fi
    fi
    echo "pidfile viejo (pid ${pid:-?} ya no es rem_chat.py): se borra" >>"$LOG"
    rm -f "$PIDFILE"
}

# El modo de la instancia abierta (ventana/overlay/escritorio), o nada.
modo_rem_chat() {
    [[ -n "$(pid_rem_chat)" ]] && sed -n 2p "$PIDFILE" 2>/dev/null || true
}

# Todos los descendientes de los pids dados (WebKitWebProcess, WebKitNetworkProcess,
# bwrap, xdg-dbus-proxy...), a cualquier profundidad.
_descendientes() {
    ps -eo pid=,ppid= | awk -v raices="$*" '
        { padre[$1] = $2 }
        END {
            n = split(raices, r, " "); for (i = 1; i <= n; i++) en[r[i]] = 1
            do { nuevo = 0
                 for (p in padre) if (!(p in en) && (padre[p] in en)) { en[p] = 1; nuevo = 1 }
            } while (nuevo)
            for (i = 1; i <= n; i++) delete en[r[i]]
            for (p in en) print p
        }'
}

# Los pids de la lista que siguen vivos (un zombi cuenta como muerto).
_vivos() {
    local p
    for p in "$@"; do
        [[ -d /proc/$p ]] || continue
        [[ "$(awk '{print $3}' "/proc/$p/stat" 2>/dev/null)" == Z ]] && continue
        echo "$p"
    done
}

# Cierra la instancia de Rem abierta, si hay (ver cerrar_procesos), y espera a
# que suelte el puerto.
cerrar_rem_chat() {
    local pid
    pid="$(pid_rem_chat)"
    [[ -z "$pid" ]] && return 0
    cerrar_procesos "$pid"
    rm -f "$PIDFILE"   # tras un SIGKILL nadie lo borra
    _esperar_puerto_libre
}

# Cierre limpio y, si no responde, forzado, de los pids dados y su árbol.
# Con la interfaz colgada SIGTERM no hace nada (el manejador corre dentro del
# bucle de GTK). Al matar Python, el WebKitWebProcess muere solo (WebKit le pone
# PR_SET_PDEATHSIG), pero otros hijos pueden seguir vivos un rato (el de red, en
# la prueba) y como huérfanos con ppid 1 ya no se encuentran por el árbol: por
# eso el árbol se apunta ANTES de mandar ninguna señal.
cerrar_procesos() {
    local pids="$*" hijos vivos
    hijos="$(_descendientes $pids | tr '\n' ' ')"
    echo "Cerrando rem_chat.py (pid $pids; descendientes: ${hijos:-ninguno})" >>"$LOG"
    kill -TERM $pids 2>/dev/null || true
    for _ in $(seq $((_ESPERA_CIERRE_S * 10))); do
        [[ -z "$(_vivos $pids)" ]] && break
        sleep 0.1
    done
    vivos="$(_vivos $pids | tr '\n' ' ')"
    if [[ -n "${vivos// }" ]]; then
        echo "No cerró en ${_ESPERA_CIERRE_S} s: se le da por colgado" >>"$LOG"
        # Antes de matarlo, sus pilas de Python al rem_chat.log (faulthandler):
        # sirven para saber dónde se colgó.
        kill -USR2 $vivos 2>/dev/null || true
        sleep 0.3
        # Los hijos que hayan nacido mientras tanto también.
        hijos="$(printf '%s\n' $hijos $(_descendientes $vivos) | sort -un | tr '\n' ' ')"
        echo "SIGKILL a $vivos" >>"$LOG"
        kill -KILL $vivos 2>/dev/null || true
        command -v notify-send >/dev/null && \
            notify-send "Rem" "No respondía: se cerró a la fuerza" || true
    fi
    # Los hijos que sigan vivos (huérfanos de un cierre forzado, o colgados ellos
    # mismos): SIGTERM y, si en 2 s no se van, SIGKILL.
    vivos="$(_vivos $hijos | tr '\n' ' ')"
    if [[ -n "${vivos// }" ]]; then
        echo "Quedaban procesos hijos vivos, SIGTERM a $vivos" >>"$LOG"
        kill -TERM $vivos 2>/dev/null || true
        for _ in $(seq 20); do
            [[ -z "$(_vivos $vivos)" ]] && break
            sleep 0.1
        done
        vivos="$(_vivos $vivos | tr '\n' ' ')"
        if [[ -n "${vivos// }" ]]; then
            echo "SIGKILL a los hijos $vivos" >>"$LOG"
            kill -KILL $vivos 2>/dev/null || true
        fi
    fi
}

_esperar_puerto_libre() {
    # Espera a que el puerto quede libre (el SO puede tardar un instante).
    for _ in $(seq 30); do
        ss -ltn 2>/dev/null | grep -q ':18765 ' || return 0
        sleep 0.1
    done
    echo "Aviso: el puerto 18765 sigue ocupado por otro proceso" >>"$LOG"
}
