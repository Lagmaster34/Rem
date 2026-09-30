#!/usr/bin/env bash
# Cierra cualquier rem_chat.py abierto (ventana u overlay): SIGTERM, y SIGKILL
# si no se cerró en 5 s. No toca bench_chat.py.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-cerrar
if pgrep -f "$_PATRON_REM_CHAT" >/dev/null; then
    cerrar_rem_chat
    echo "rem_chat.py cerrado" >>"$LOG"
else
    echo "No había ningún rem_chat.py abierto" >>"$LOG"
fi
