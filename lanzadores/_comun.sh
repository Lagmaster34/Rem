#!/usr/bin/env bash
# Funciones compartidas por los lanzadores (se carga con `source`, no se ejecuta).
# Todo se calcula desde la ubicación de este archivo: si se mueve el proyecto,
# los lanzadores siguen funcionando sin tocar nada.

LANZADORES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(dirname "$LANZADORES_DIR")"
PYTHON="$RAIZ/venv/bin/python"
LOG_DIR="$LANZADORES_DIR/logs"
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

# Cierra con SIGTERM cualquier rem_chat.py que esté corriendo (rem_chat.py lo
# atiende con Gtk.main_quit(), cierre limpio) y espera a que suelte el puerto.
# Solo si no se va en 5 s manda SIGKILL.
# Solo procesos cuyo argv[0] es un python y argv[1] es rem_chat.py — no una
# shell o un editor que tenga el texto "rem_chat.py" en su línea de comandos.
_PATRON_REM_CHAT='^[^ ]*python[0-9.]* ([^ ]*/)?rem_chat\.py( |$)'

cerrar_rem_chat() {
    local pids
    pids="$(pgrep -f "$_PATRON_REM_CHAT" || true)"
    [[ -z "$pids" ]] && return 0
    echo "Cerrando instancia previa de rem_chat.py (pid $pids)" >>"$LOG"
    kill -TERM $pids 2>/dev/null || true
    for _ in $(seq 50); do
        pgrep -f "$_PATRON_REM_CHAT" >/dev/null || break
        sleep 0.1
    done
    pids="$(pgrep -f "$_PATRON_REM_CHAT" || true)"
    if [[ -n "$pids" ]]; then
        echo "No cerró en 5 s, SIGKILL a $pids" >>"$LOG"
        kill -KILL $pids 2>/dev/null || true
        sleep 0.5
    fi
    # Espera a que el puerto quede libre (el SO puede tardar un instante).
    for _ in $(seq 30); do
        ss -ltn 2>/dev/null | grep -q ':18765 ' || return 0
        sleep 0.1
    done
    echo "Aviso: el puerto 18765 sigue ocupado por otro proceso" >>"$LOG"
}
