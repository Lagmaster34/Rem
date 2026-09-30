#!/usr/bin/env bash
# Instala los .desktop de esta carpeta en ~/.local/share/applications/ para
# que aparezcan en el lanzador de apps.
#
# No son symlinks: un .desktop necesita la ruta ABSOLUTA en Exec=, así que se
# escribe una copia con la ruta real de esta carpeta. Si se mueve el proyecto,
# volver a correr este script (los .sh no hace falta tocarlos).
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DEST"

# El proyecto no trae ícono propio: si algún día se deja un rem.png/rem.svg en
# esta carpeta se usa ese; si no, uno genérico del tema.
ICONO="avatar-default"
for f in "$DIR/rem.svg" "$DIR/rem.png"; do
    [[ -f "$f" ]] && { ICONO="$f"; break; }
done

chmod +x "$DIR"/rem-*.sh
for plantilla in "$DIR"/rem-*.desktop; do
    nombre="$(basename "$plantilla")"
    sed -e "s|@LANZADORES@|$DIR|g" -e "s|@ICONO@|$ICONO|g" \
        "$plantilla" >"$DEST/$nombre"
    echo "instalado: $DEST/$nombre"
done
command -v update-desktop-database >/dev/null && update-desktop-database "$DEST" 2>/dev/null || true
