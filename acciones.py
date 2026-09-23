"""acciones.py — las herramientas (tool calling nativo) que Rem puede
ejecutar desde rem_chat, más las protecciones que reutiliza de la auditoría
de seguridad original de Rem.py.

Alcance deliberadamente chico (ver CLAUDE.md, "Pendiente: portar el
ejecutor de acciones a rem_chat"): NO es el catálogo completo de Rem.py —
solo 4 herramientas de bajo riesgo o con confirmación obligatoria.
`ejecutar_comando` y el resto del catálogo viejo (JSON en texto) se quedan
fuera; el hueco de `pacman` sin restricción de subcomando (ver esa sección
de CLAUDE.md) no aplica más porque `ejecutar_comando` no se porta.

Solo se extrajo de Rem.py lo que estas 4 herramientas necesitan:
`_ruta_segura`/`_filtrar_rutas_seguras` (la validación de rutas) y el
soporte de `memoria_sistema` para `buscar_archivos` (registrar/consultar
la caché de archivos ya encontrados). El resto del catálogo de Rem.py
(ejecutar_comando, mover/copiar/eliminar archivo, crear_carpeta,
optimizar, descargar, etc.) sigue viviendo solo ahí — no se tocó.

`memoria_sistema` se recibe como parámetro en cada función que lo necesita
(igual que ya hace personalidad.py), nunca como global del módulo: la
sesión de chat de rem_avatar_server.py ya mantiene su propia copia viva
(obtener_sesion_chat()) — si acciones.py tuviera su propia copia aparte,
las dos podrían pisarse al escribir memoria_sistema.json por separado.
"""
import configparser
import fnmatch
import os
import re
import shlex
import subprocess
import urllib.parse

from llm import ToolSpec

# ── Rutas seguras (idéntico a Rem.py, mismo motivo: ver CLAUDE.md
# "Seguridad de acciones del sistema") ──────────────────────────────────
_ZONA_SEGURA = os.path.realpath(os.path.expanduser("~"))
_DIRS_PROHIBIDOS = ("/etc", "/boot", "/sys", "/proc", "/root", "/bin", "/sbin",
                    "/usr/bin", "/usr/sbin", "/lib", "/lib64")
_PROYECTO_DIR = os.path.dirname(os.path.abspath(__file__))
_RUTAS_PROHIBIDAS_HOME = tuple(
    os.path.realpath(os.path.expanduser(p)) for p in (
        "~/.ssh", "~/.gnupg", "~/.config", "~/.local/share/keyrings", "~/.mozilla",
    )
) + (
    os.path.realpath(os.path.join(_PROYECTO_DIR, ".env")),
    os.path.realpath(os.path.join(_PROYECTO_DIR, ".git")),
)


def _ruta_segura(ruta, permitir_raiz=False):
    """Copia de Rem.py — ver ese archivo para el razonamiento completo de
    cada chequeo. Solo la usa buscar_archivos() acá, con permitir_raiz=True
    (es de solo lectura, igual que en Rem.py)."""
    ruta = os.path.realpath(os.path.expanduser(str(ruta)))
    if os.path.commonpath([ruta, _ZONA_SEGURA]) != _ZONA_SEGURA:
        return False, f"Solo puedo operar dentro de {_ZONA_SEGURA}."
    if ruta == _ZONA_SEGURA and not permitir_raiz:
        return False, f"No puedo operar sobre {_ZONA_SEGURA} completo."
    for d in _DIRS_PROHIBIDOS:
        if os.path.commonpath([ruta, d]) == d:
            return False, f"No puedo tocar {d}."
    for d in _RUTAS_PROHIBIDAS_HOME:
        if os.path.commonpath([ruta, d]) == d:
            return False, f"No puedo tocar {d} (ruta protegida)."
    return True, ruta


def _filtrar_rutas_seguras(rutas):
    """Copia de Rem.py — glob.glob('**') puede encontrar coincidencias
    dentro de ~/.ssh/~/.config/etc. igual si están debajo de la base
    validada; hay que filtrar cada resultado, no solo la carpeta de
    partida."""
    return [r for r in rutas if _ruta_segura(r, permitir_raiz=True)[0]]


# ── Memoria del sistema (caché de archivos ya encontrados) ──────────────
_MEM_SIS_MAX = 200


def _guardar_memoria_sistema(memoria_sistema):
    import json
    import personalidad
    try:
        with open(personalidad.MEMORIA_SISTEMA_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(memoria_sistema, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Acciones] Error guardando memoria_sistema: {e}", flush=True)


def _rotar_memoria_sistema(memoria_sistema):
    total = len(memoria_sistema["archivos"]) + len(memoria_sistema["carpetas"])
    if total <= _MEM_SIS_MAX:
        return
    exceso = total - _MEM_SIS_MAX
    claves = list(memoria_sistema["archivos"].keys())
    for k in claves[:exceso]:
        del memoria_sistema["archivos"][k]


def _registrar_archivo_sistema(memoria_sistema, nombre, ruta):
    """Mismo filtro que Rem.py: memoria_sistema se reinyecta en prompts
    futuros sin filtrar de nuevo, así que una entrada indebida acá quedaría
    expuesta hasta que se borre a mano — ver CLAUDE.md."""
    ok, _ = _ruta_segura(ruta, permitir_raiz=True)
    if not ok:
        return
    memoria_sistema.setdefault("archivos", {})[nombre] = ruta
    _rotar_memoria_sistema(memoria_sistema)
    _guardar_memoria_sistema(memoria_sistema)


def _buscar_en_memoria_sistema(memoria_sistema, nombre):
    ruta = memoria_sistema.get("archivos", {}).get(nombre)
    if ruta and _ruta_segura(ruta, permitir_raiz=True)[0]:
        return ruta
    return None


# ── Herramienta 1: abrir_programa ────────────────────────────────────────
# A diferencia del "abrir" viejo de Rem.py (que caía a xdg-open o a exec
# directo con el string que mandara el LLM si no encontraba un atajo
# configurado), esto SOLO resuelve contra .desktop realmente instalados —
# nunca ejecuta un nombre arbitrario. Ambigüedad (0 o >1 coincidencias) se
# reporta, no se adivina.
_DIRS_DESKTOP = ("/usr/share/applications", os.path.expanduser("~/.local/share/applications"))
_FIELD_CODES = re.compile(r"%[fFuUick%]")


def _listar_apps_desktop():
    apps = {}  # archivo -> {nombre, exec} — el último dir listado gana (usuario sobre sistema)
    for d in _DIRS_DESKTOP:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".desktop"):
                continue
            try:
                cfg = configparser.ConfigParser(interpolation=None, strict=False)
                cfg.read(os.path.join(d, fn), encoding="utf-8")
                sec = cfg["Desktop Entry"]
                if sec.get("Type", "Application") != "Application":
                    continue
                if sec.get("NoDisplay", "false").strip().lower() == "true":
                    continue
                if "Exec" not in sec:
                    continue
                apps[fn] = {"nombre": sec.get("Name", fn), "exec": sec["Exec"]}
            except Exception:
                continue
    return list(apps.values())


def abrir_programa(nombre: str) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        return "No me dijiste qué programa abrir."
    q = nombre.lower()
    candidatos = [a for a in _listar_apps_desktop()
                  if q in a["nombre"].lower() or a["nombre"].lower() in q]
    if not candidatos:
        return f"No encontré ningún programa instalado que coincida con '{nombre}'."
    if len(candidatos) > 1:
        # Puede haber duplicados exactos (mismo Name en system+user dirs con
        # distinto archivo) — dedup por nombre antes de reportar ambigüedad.
        nombres_unicos = sorted({a["nombre"] for a in candidatos})
        if len(nombres_unicos) == 1:
            candidatos = candidatos[:1]
        else:
            return (f"Hay varias coincidencias para '{nombre}': "
                    f"{', '.join(nombres_unicos[:8])}. Decime cuál exactamente.")
    app = candidatos[0]
    exec_limpio = _FIELD_CODES.sub("", app["exec"]).strip()
    try:
        args = shlex.split(exec_limpio)
    except ValueError:
        return f"No pude interpretar cómo lanzar {app['nombre']}."
    if not args:
        return f"No pude interpretar cómo lanzar {app['nombre']}."
    try:
        subprocess.Popen(args, start_new_session=True)
        return f"Abriendo {app['nombre']}."
    except Exception as e:
        return f"No pude abrir {app['nombre']}: {e}"


# ── Herramienta 2: apagar_pc (requiere confirmación) ─────────────────────
def apagar_pc() -> str:
    """`shutdown -h +1` — probado en vivo en esta máquina, funciona sin sudo
    (systemd-logind se lo permite al usuario de la sesión activa). Da un
    minuto real de margen, cancelable con `shutdown -c`."""
    try:
        subprocess.run(["shutdown", "-h", "+1"], capture_output=True, timeout=10)
        return "Apagando en 1 minuto. Si te arrepentís, corré 'shutdown -c' en una terminal."
    except Exception as e:
        return f"No pude apagar la PC: {e}"


# ── Herramienta 3: buscar_en_navegador ───────────────────────────────────
def buscar_en_navegador(consulta: str) -> str:
    consulta = (consulta or "").strip()
    if not consulta:
        return "No me dijiste qué buscar."
    url = "https://www.google.com/search?q=" + urllib.parse.quote(consulta)
    try:
        subprocess.Popen(["xdg-open", url], start_new_session=True)
        return f"Buscando '{consulta}' en el navegador."
    except Exception as e:
        return f"No pude abrir el navegador: {e}"


# ── Herramienta 4: buscar_archivos ───────────────────────────────────────
LIMITE_RESULTADOS_BUSQUEDA = 5
_TOPE_CANDIDATOS = 50  # frena el recorrido del disco una vez que hay de sobra para elegir


def buscar_archivos(memoria_sistema: dict, patron: str) -> str:
    """Coincidencia por FRAGMENTO, sin distinguir mayúsculas: 'contrato'
    encuentra 'Contrato_Final_Definitivo_2024.PDF' sin que haga falta el
    nombre exacto ni la extensión — el modelo casi nunca la sabe de
    antemano. Si `patron` ya trae comodines (*, ?, [) se respeta tal cual
    en vez de envolverlo en asteriscos, para no romper un patrón que el
    modelo arme a propósito."""
    patron = (patron or "").strip()
    if not patron:
        return "No me dijiste qué archivo buscar."
    en_memoria = _buscar_en_memoria_sistema(memoria_sistema, patron)
    if en_memoria:
        return f"Ya sé dónde está '{patron}': {en_memoria}"
    base = os.path.expanduser("~")
    patron_glob = patron if any(c in patron for c in "*?[") else f"*{patron}*"
    regex = re.compile(fnmatch.translate(patron_glob), re.IGNORECASE)
    candidatos = []
    try:
        for raiz, _dirs, archivos in os.walk(base):
            for nombre in archivos:
                if regex.match(nombre):
                    candidatos.append(os.path.join(raiz, nombre))
                    if len(candidatos) >= _TOPE_CANDIDATOS:
                        break
            if len(candidatos) >= _TOPE_CANDIDATOS:
                break
    except Exception as e:
        return f"Error buscando: {e}"
    res = _filtrar_rutas_seguras(candidatos)
    if not res:
        return f"No encontré ningún archivo que coincida con '{patron}'."
    _registrar_archivo_sistema(memoria_sistema, os.path.basename(res[0]), res[0])
    listado = "\n".join(res[:LIMITE_RESULTADOS_BUSQUEDA])
    extra = (f" (mostrando los primeros {LIMITE_RESULTADOS_BUSQUEDA} de {len(res)})"
             if len(res) > LIMITE_RESULTADOS_BUSQUEDA else "")
    return f"Encontré {len(res)}{extra}:\n{listado}"


# ── Catálogo de tools + confirmación ─────────────────────────────────────
_SPEC_ABRIR_PROGRAMA = ToolSpec(
    name="abrir_programa",
    description=("Abre un programa instalado en el sistema por su nombre. Úsala SOLO "
                  "cuando Esteban pida explícitamente abrir, lanzar o iniciar una "
                  "aplicación concreta."),
    parameters={
        "type": "object",
        "properties": {"nombre": {"type": "string",
                                   "description": "Nombre del programa tal como lo mencionó Esteban, ej. 'firefox', 'discord'"}},
        "required": ["nombre"],
    },
)

_SPEC_APAGAR_PC = ToolSpec(
    name="apagar_pc",
    description=("Apaga la PC. Úsala SOLO cuando Esteban pida explícita y literalmente "
                  "apagar/shutdown SU PC — nunca en preguntas hipotéticas, sobre otra "
                  "máquina, o como figura del lenguaje."),
    parameters={"type": "object", "properties": {}, "required": []},
)

_SPEC_BUSCAR_EN_NAVEGADOR = ToolSpec(
    name="buscar_en_navegador",
    description=("Abre el navegador con una búsqueda web. Úsala cuando Esteban pida "
                  "buscar algo en internet, en Google o en la web."),
    parameters={
        "type": "object",
        "properties": {"consulta": {"type": "string", "description": "Los términos de búsqueda"}},
        "required": ["consulta"],
    },
)

_SPEC_BUSCAR_ARCHIVOS = ToolSpec(
    name="buscar_archivos",
    description=("Busca archivos por nombre dentro de la carpeta personal de Esteban en "
                  "su PC. Úsala cuando pida encontrar o buscar un archivo específico en "
                  "su sistema — NO para búsquedas en internet."),
    parameters={
        "type": "object",
        "properties": {"patron": {"type": "string",
                                   "description": "Nombre o patrón del archivo a buscar, ej. 'factura.pdf'"}},
        "required": ["patron"],
    },
)

TOOLS_QUE_CONFIRMAN = {"apagar_pc"}
TOOLS_EXCLUIDAS_OVERLAY = {"apagar_pc"}

_DESCRIPCIONES_CONFIRMACION = {
    "apagar_pc": lambda args: "⚠️ Apagar la PC en 1 minuto",
}

_DISPATCH = {
    "abrir_programa": lambda args, memoria_sistema: abrir_programa(args.get("nombre", "")),
    "apagar_pc": lambda args, memoria_sistema: apagar_pc(),
    "buscar_en_navegador": lambda args, memoria_sistema: buscar_en_navegador(args.get("consulta", "")),
    "buscar_archivos": lambda args, memoria_sistema: buscar_archivos(memoria_sistema, args.get("patron", "")),
}


class ConfirmacionExpirada(Exception):
    """La confirmación de una acción (accion_confirmar/accion_confirmar_resp
    por WS) no llegó dentro del timeout. procesar_turno() no la atrapa — se
    propaga hasta _procesar_mensaje_chat(), que ya sabe liberar el turno y
    avisar al cliente por su manejo genérico de excepciones."""


def tools_disponibles(modo: str) -> list[ToolSpec]:
    """`modo`: 'ventana' u 'overlay' — apagar_pc no se ofrece en overlay
    (no hay forma de confirmar una acción destructiva ahí, ver CLAUDE.md)."""
    specs = [_SPEC_ABRIR_PROGRAMA, _SPEC_APAGAR_PC, _SPEC_BUSCAR_EN_NAVEGADOR, _SPEC_BUSCAR_ARCHIVOS]
    if modo == "overlay":
        specs = [s for s in specs if s.name not in TOOLS_EXCLUIDAS_OVERLAY]
    return specs


async def ejecutar_tool_async(nombre, argumentos, *, memoria_sistema, on_confirmar_accion=None):
    """Ejecuta la tool `nombre` (ya resuelta por el modelo) y devuelve el
    texto de respuesta ya armado — nunca el resultado crudo del LLM.
    Corre la función real en un hilo (asyncio.to_thread): son llamadas
    bloqueantes (subprocess, glob, I/O de archivo) y esto corre dentro del
    loop de _ws_loop, que no debe frenarse.

    Si `nombre` requiere confirmación (apagar_pc) llama a
    `on_confirmar_accion(nombre, argumentos, descripcion) -> bool | None`
    (async): None = expiró sin respuesta (lanza ConfirmacionExpirada, que el
    llamador debe dejar propagar), False = el usuario dijo que no (se
    devuelve un texto neutro, sin ejecutar nada), True = se ejecuta.
    Si no hay callback (p.ej. un contexto sin panel para confirmar), la
    acción se rechaza por defecto — nunca se ejecuta sin poder confirmar."""
    import asyncio

    if nombre in TOOLS_QUE_CONFIRMAN:
        if on_confirmar_accion is None:
            return "Esa acción necesita confirmación y no está disponible en este modo."
        descripcion = _DESCRIPCIONES_CONFIRMACION[nombre](argumentos)
        resultado = await on_confirmar_accion(nombre, argumentos, descripcion)
        if resultado is None:
            raise ConfirmacionExpirada(f"confirmación de '{nombre}' expiró sin respuesta")
        if not resultado:
            return "Bueno, no hago nada entonces."

    fn = _DISPATCH.get(nombre)
    if fn is None:
        return f"No sé cómo ejecutar la acción '{nombre}'."
    return await asyncio.to_thread(fn, argumentos, memoria_sistema)
