#!/usr/bin/env bash
# Corre un comando de prueba en un entorno aislado: todo lo que Rem escribe en
# tiempo de ejecución (preferencias, estado del escritorio, memorias, caché de
# frases, logs, pidfile, datos de WebKit) va a una carpeta aparte (REM_DATOS,
# ver config.DATOS_DIR), sembrada con una COPIA de los datos reales. Al terminar
# comprueba que ningún archivo real se tocó.
#
# Uso:  tests/entorno_aislado.sh [-d CARPETA] [--] comando [args...]
#   -d CARPETA  carpeta del entorno, fuera del repo (se crea y se siembra si no
#               existe; si ya existe se reusa tal cual). Por defecto, una nueva
#               en ${TMPDIR:-/tmp} (rem_prueba.XXXXXX).
# Lo que abre ventanas va dentro de un Hyprland anidado, o se abre en el
# escritorio real: arrancarlo antes con `Hyprland -c tests/anidado.lua` y pasar
# su WAYLAND_DISPLAY y HYPRLAND_INSTANCE_SIGNATURE al comando (el más reciente en
# $XDG_RUNTIME_DIR/hypr/). Cerrarlo al terminar, solo su pid.
# Ejemplos:
#   tests/entorno_aislado.sh -- venv/bin/python rem_chat.py --modo escritorio
#   tests/entorno_aislado.sh -d /tmp/rem_prueba -- notas_fase2/prueba_arrastre/verificar.sh overlay x
#
# Se niega a correr (sale con 4) si hay una instancia real viva: con los puertos
# ocupados, la app de la prueba no levantaría y sus clientes WS hablarían con la
# real, que sí escribe en los archivos reales. La carpeta del entorno tiene que
# quedar fuera del repo.
#
# Sale con el código del comando, 3 si algún archivo real cambió, 4 si había una
# instancia real viva, 2 si el uso es incorrecto.
set -uo pipefail
RAIZ="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"

DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d) DIR="$2"; shift 2 ;;
        --) shift; break ;;
        *) break ;;
    esac
done
[[ $# -gt 0 ]] || { sed -n 2,22p "$0" | sed 's/^# \{0,1\}//'; exit 2; }

# Lo que se siembra en el entorno (copias) y se vigila en el proyecto.
SEMBRAR=(preferencias.json escritorio_estado.json memoria_larga.json memoria_sistema.json cache_frases)
VIGILAR=("${SEMBRAR[@]/#/$RAIZ/}" "$RAIZ/rem_chat.log" "$RAIZ/rem_panel.log" "$RAIZ/rem_chat.pid"
         "$RAIZ/lanzadores/logs"
         "$HOME/.cache/rem_chat.py" "$HOME/.cache/rem_panel.py"
         "$HOME/.local/share/rem_chat.py" "$HOME/.local/share/rem_panel.py")

# ¿Instancia real viva? Pidfile real válido (con las mismas comprobaciones que
# los lanzadores) o los puertos del avatar ocupados por quien sea (una instancia
# de antes del pidfile, un bench_chat.py standalone...).
pid_real="$(LOG=/dev/null; unset REM_DATOS; source "$RAIZ/lanzadores/_comun.sh"; pid_rem_chat 2>/dev/null)"
puertos="$(ss -ltnpH 2>/dev/null | grep -E '127\.0\.0\.1:(18765|18766) |\[::1\]:(18765|18766) |\*:(18765|18766) |0\.0\.0\.0:(18765|18766) ' || true)"
if [[ -n "$pid_real$puertos" ]]; then
    echo "[aislado] hay una instancia real de Rem viva: no se corre la prueba." >&2
    [[ -n "$pid_real" ]] && echo "  pidfile real: rem_chat.py pid $pid_real" >&2
    [[ -n "$puertos" ]] && echo "$puertos" | sed 's/^/  puerto ocupado: /' >&2
    echo "  Ciérrala (menú → Cerrar, o lanzadores/rem-cerrar.sh) y vuelve a correr la prueba." >&2
    exit 4
fi

if [[ -z "$DIR" ]]; then
    DIR="$(mktemp -d "${TMPDIR:-/tmp}/rem_prueba.XXXXXX")"
fi
DIR="$(readlink -m "$DIR")"
if [[ "$DIR" == "$RAIZ" || "$DIR" == "$RAIZ"/* ]]; then
    echo "[aislado] la carpeta del entorno tiene que quedar fuera del repo ($RAIZ)" >&2; exit 2
fi

if [[ ! -e "$DIR/.sembrado" ]]; then
    mkdir -p "$DIR"
    for f in "${SEMBRAR[@]}"; do
        [[ -e "$RAIZ/$f" ]] && cp -a "$RAIZ/$f" "$DIR/"
    done
    touch "$DIR/.sembrado"
    echo "[aislado] entorno nuevo en $DIR (copia de: $(cd "$DIR" && ls -A | grep -v '^\.sembrado$' | tr '\n' ' '))" >&2
else
    echo "[aislado] reusando el entorno $DIR" >&2
fi

# Antes: marca de tiempo y lista de lo que existe (para ver también borrados).
MARCA="$DIR/.inicio"; touch "$MARCA"
antes="$(for p in "${VIGILAR[@]}"; do [[ -e "$p" ]] && find "$p"; done | sort)"

REM_DATOS="$DIR" "$@"
codigo=$?

despues="$(for p in "${VIGILAR[@]}"; do [[ -e "$p" ]] && find "$p"; done | sort)"
cambiados="$(for p in "${VIGILAR[@]}"; do [[ -e "$p" ]] && find "$p" -newer "$MARCA"; done | sort)"
borrados="$(comm -23 <(echo "$antes") <(echo "$despues"))"
if [[ -n "$cambiados$borrados" ]]; then
    echo "[aislado] ¡ARCHIVOS REALES TOCADOS!" >&2
    [[ -n "$cambiados" ]] && echo "$cambiados" | sed 's/^/  cambiado: /' >&2
    [[ -n "$borrados" ]] && echo "$borrados" | sed 's/^/  borrado:  /' >&2
    exit 3
fi
echo "[aislado] archivos reales intactos (entorno: $DIR)" >&2
exit $codigo
