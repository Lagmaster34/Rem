#!/usr/bin/env bash
# Abre Rem en modo escritorio (avatar que se arrastra + chat en ventana aparte).
# Si ya está abierto en modo escritorio, no arranca otro: lo vuelve a mostrar
# (por si se ocultó) con rem_escritorio.py, y si el WebSocket no responde, con
# SIGUSR1. Si hay otra instancia (ventana u overlay), la cierra: nunca quedan dos.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-escritorio
comprobar_venv
PATRON_ESCRITORIO='^[^ ]*python[0-9.]* ([^ ]*/)?rem_chat\.py .*--modo escritorio'
if pgrep -f "$PATRON_ESCRITORIO" >/dev/null; then
    if "$PYTHON" "$RAIZ/rem_escritorio.py" mostrar >>"$LOG" 2>&1; then
        echo "Ya estaba abierto: mostrar" >>"$LOG"
    else
        echo "Ya estaba abierto y el WebSocket no respondió: SIGUSR1" >>"$LOG"
        pkill -USR1 -f "$PATRON_ESCRITORIO"
    fi
    exit 0
fi
cerrar_rem_chat
cd "$RAIZ"
exec "$PYTHON" rem_chat.py --modo escritorio >>"$LOG" 2>&1
