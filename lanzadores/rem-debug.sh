#!/usr/bin/env bash
# Abre el REPL de depuración (bench_chat.py) en una terminal.
#
# A diferencia de los otros lanzadores, NO cierra rem_chat.py: bench_chat.py
# no pelea el puerto — si hay un rem_chat.py corriendo se conecta a él como
# cliente WebSocket (y sus comandos se ven en esa ventana); si no hay ninguno,
# levanta su propio servidor.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-debug
comprobar_venv
cd "$RAIZ"

# `script` conserva una TTY real para el REPL (input(), colores) y a la vez
# copia toda la sesión al log. Al salir, la terminal espera un Enter para que
# se pueda leer un error antes de que se cierre.
cmd="script -q -f -a $(printf %q "$LOG") -c $(printf %q "$(printf %q "$PYTHON") bench_chat.py"); echo; read -rp 'bench_chat.py terminó — Enter para cerrar'"

if [[ -n "${TERMINAL:-}" ]] && command -v "$TERMINAL" >/dev/null; then
    exec "$TERMINAL" -e bash -c "$cmd"
elif command -v foot >/dev/null; then
    exec foot --title "Rem Debug" bash -c "$cmd"
elif command -v kitty >/dev/null; then
    exec kitty --title "Rem Debug" bash -c "$cmd"
elif command -v alacritty >/dev/null; then
    exec alacritty --title "Rem Debug" -e bash -c "$cmd"
else
    echo "No encontré ninguna terminal (foot/kitty/alacritty, o \$TERMINAL)" >>"$LOG"
    command -v notify-send >/dev/null && notify-send "Rem Debug" "No encontré ninguna terminal"
    exit 1
fi
