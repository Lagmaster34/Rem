#!/usr/bin/env bash
# Abre Yoru en escritorio fijado en la esquina (--modo overlay es su alias: el
# antiguo modo overlay). Sin entrada en el lanzador: para atajos o la terminal.
# Cierra cualquier rem_chat.py abierto: nunca quedan dos.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-overlay
comprobar_venv
cerrar_rem_chat
cd "$RAIZ"
exec "$PYTHON" rem_chat.py --modo overlay >>"$LOG" 2>&1
