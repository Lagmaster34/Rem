#!/usr/bin/env bash
# Abre el panel de control. No toca rem_chat.py: el panel es un cliente de su
# servidor, así que Rem tiene que estar abierto (ventana u overlay); si no,
# rem_panel.py avisa con un diálogo. Abrirlo de nuevo trae al frente el que ya está.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/_comun.sh"
abrir_log rem-panel
comprobar_venv
cd "$RAIZ"
exec "$PYTHON" rem_panel.py >>"$LOG" 2>&1
