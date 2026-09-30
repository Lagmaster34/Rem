#!/usr/bin/env bash
# Abre Rem en modo overlay (avatar sobre el escritorio + caja de texto).
# Cierra cualquier rem_chat.py abierto (ventana u overlay): nunca quedan los dos.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-overlay
comprobar_venv
cerrar_rem_chat
cd "$RAIZ"
exec "$PYTHON" rem_chat.py --modo overlay >>"$LOG" 2>&1
