#!/usr/bin/env bash
# Cierra cualquier rem_chat.py abierto (ventana, overlay o escritorio): SIGTERM,
# y si no se cerró en 5 s (interfaz colgada) vuelca sus pilas al rem_chat.log,
# lo mata con SIGKILL y cierra los procesos de WebKit que le queden. No toca
# bench_chat.py.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-cerrar
if [[ -n "$(pid_rem_chat)" ]]; then
    cerrar_rem_chat
    echo "rem_chat.py cerrado" >>"$LOG"
else
    echo "No había ningún rem_chat.py abierto" >>"$LOG"
fi
