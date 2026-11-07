#!/usr/bin/env bash
# Abre Rem en modo escritorio (avatar que se arrastra + chat en ventana aparte).
# Si ya está abierto en modo escritorio, no arranca otro: lo vuelve a mostrar
# (por si se ocultó) con rem_escritorio.py, y si el WebSocket no responde, con
# SIGUSR1. Si hay otra instancia (ventana u overlay), la cierra: nunca quedan dos.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-escritorio
comprobar_venv
if [[ "$(modo_rem_chat)" == escritorio ]]; then
    if "$PYTHON" "$RAIZ/rem_escritorio.py" mostrar >>"$LOG" 2>&1; then
        echo "Ya estaba abierto: mostrar" >>"$LOG"
    else
        echo "Ya estaba abierto y el WebSocket no respondió: SIGUSR1" >>"$LOG"
        kill -USR1 "$(pid_rem_chat)" 2>/dev/null || true
    fi
    exit 0
fi
cerrar_rem_chat
cd "$RAIZ"
exec "$PYTHON" rem_chat.py --modo escritorio >>"$LOG" 2>&1
