#!/usr/bin/env bash
# Abre Rem en modo ventana (avatar + panel de chat).
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-ventana
comprobar_venv
cerrar_rem_chat
cd "$RAIZ"
exec "$PYTHON" rem_chat.py --modo ventana >>"$LOG" 2>&1
