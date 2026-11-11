#!/usr/bin/env bash
# Instala los .desktop de esta carpeta en ~/.local/share/applications/ para
# que aparezcan en el lanzador de apps: hoy «Yoru» (rem.desktop) y «Rem Debug»
# (rem-debug.desktop, con NoDisplay=true: instalado pero oculto). Las copias
# instaladas de lanzadores que ya no existen aquí (Rem Panel, Rem Cerrar, Rem
# Ventana, Rem Overlay, Rem Escritorio...) se borran: solo las que apuntan a
# esta carpeta, nunca un .desktop ajeno.
#
# No son symlinks: un .desktop necesita la ruta ABSOLUTA en Exec=, así que se
# escribe una copia con la ruta real de esta carpeta. Si se mueve el proyecto,
# volver a correr este script (los .sh no hace falta tocarlos).
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DEST"

# El proyecto no trae ícono propio (no se versiona). Por orden: un rem.png/rem.svg
# dejado en esta carpeta; si no, el ícono «yoru» instalado a mano en el tema del
# usuario (~/.local/share/icons/hicolor/<tamaño>/apps/yoru.png); si no, uno
# genérico del tema.
ICONO="avatar-default"
ICONOS_USUARIO="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
if compgen -G "$ICONOS_USUARIO/*/apps/yoru.png" >/dev/null || [[ -f "$ICONOS_USUARIO/scalable/apps/yoru.svg" ]]; then
    ICONO="yoru"
fi
for f in "$DIR/rem.svg" "$DIR/rem.png"; do
    [[ -f "$f" ]] && { ICONO="$f"; break; }
done

chmod +x "$DIR"/rem*.sh
for instalado in "$DEST"/rem*.desktop; do
    [[ -e "$instalado" ]] || continue
    [[ -e "$DIR/$(basename "$instalado")" ]] && continue
    grep -q "^Exec=$DIR/" "$instalado" || continue
    rm -f "$instalado"
    echo "borrado (ya no existe en lanzadores/): $instalado"
done
for plantilla in "$DIR"/rem*.desktop; do
    nombre="$(basename "$plantilla")"
    sed -e "s|@LANZADORES@|$DIR|g" -e "s|@ICONO@|$ICONO|g" \
        "$plantilla" >"$DEST/$nombre"
    echo "instalado: $DEST/$nombre"
done
command -v update-desktop-database >/dev/null && update-desktop-database "$DEST" 2>/dev/null || true
