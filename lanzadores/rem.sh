#!/usr/bin/env bash
# «Yoru», el lanzador visible: abre el último modo usado (rem_chat.py sin
# --modo: lo lee de preferencias.json -> app.modo, que rem_chat.py guarda al
# arrancar), o escritorio la primera vez. El modo se cambia desde el menú del
# clic derecho. Si ya está abierta no arranca otra: en escritorio la vuelve a
# mostrar (por si se ocultó) con rem_escritorio.py, y si el WebSocket no
# responde, con SIGUSR1; en ventana la deja como está.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem
comprobar_venv
modo="$(modo_rem_chat)"
if [[ -n "$modo" ]]; then
    if [[ "$modo" == escritorio ]]; then
        if "$PYTHON" "$RAIZ/rem_escritorio.py" mostrar >>"$LOG" 2>&1; then
            echo "Ya estaba abierta en escritorio: mostrar" >>"$LOG"
        else
            echo "Ya estaba abierta en escritorio y el WebSocket no respondió: SIGUSR1" >>"$LOG"
            kill -USR1 "$(pid_rem_chat)" 2>/dev/null || true
        fi
    else
        echo "Ya estaba abierta (modo $modo): no se abre otra" >>"$LOG"
    fi
    exit 0
fi
cd "$RAIZ"
exec "$PYTHON" rem_chat.py >>"$LOG" 2>&1
