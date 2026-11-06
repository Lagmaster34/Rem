"""config.py — configuración compartida de Rem: carga de .env y config.toml.

Lo usan rem_chat.py, bench_chat.py, llm/ y habla.py: un solo lugar que lee
.env (API keys) y config.toml, en vez de una lectura por script.
"""
import os

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ENV_PATH  = os.path.join(BASE_DIR, ".env")
TOML_PATH = os.path.join(BASE_DIR, "config.toml")


def cargar_dotenv(ruta: str = ENV_PATH) -> None:
    """Carga variables de `ruta` (.env) al entorno vía os.environ.setdefault
    — no sobreescribe variables que ya vengan exportadas del shell.
    split("=", 1) en vez de split("=") para tolerar valores que traigan "="
    dentro (las API keys pueden llevarlo)."""
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def leer_config_toml(ruta: str = TOML_PATH) -> dict:
    """Devuelve config.toml parseado (dict-like, soporta .get() anidado), o
    {} si el archivo no existe."""
    if not os.path.exists(ruta):
        return {}
    import tomlkit
    with open(ruta, encoding="utf-8") as f:
        return tomlkit.parse(f.read())


def leer_modelo_avatar() -> str:
    """Ruta (relativa a la raíz del proyecto) del modelo VRM a cargar en el
    avatar: la preferencia del panel (preferencias.json -> modelo.vrm) o, si no
    hay, config.toml [avatar].modelo (default "models/vrm/neru.vrm"). La sirve
    rem_avatar_server.py (que sirve todo BASE_DIR) y la consume
    rem_avatar.html vía el query param ?modelo=... que arma
    rem_avatar_server.url_avatar()."""
    import preferencias
    return preferencias.obtener("modelo")["vrm"]


def leer_modelo_tts() -> str:
    """Ruta ABSOLUTA del modelo Piper (.onnx) de la voz de salida, desde
    config.toml [tts].modelo (relativa a la raíz del proyecto; default
    models/piper/model.onnx). Su config (.onnx.json, con el sample rate) va al lado, con el
    mismo nombre + ".json" — es la convención de Piper."""
    ruta = str(leer_config_toml().get("tts", {}).get("modelo", "models/piper/model.onnx")).strip()
    return ruta if os.path.isabs(ruta) else os.path.join(BASE_DIR, ruta)


def leer_modo_app() -> str:
    """Modo de presentación de rem_chat.py, desde config.toml [app].modo:
    "ventana" (default), "overlay" o "escritorio". Cualquier otro valor cae a
    "ventana". rem_chat.py --modo lo pisa."""
    valor = str(leer_config_toml().get("app", {}).get("modo", "ventana")).strip().lower()
    return valor if valor in ("ventana", "overlay", "escritorio") else "ventana"


def leer_config_overlay() -> dict:
    """[overlay] de config.toml con defaults: geometría, capa y zona exclusiva
    de la layer surface del modo overlay."""
    cfg = leer_config_toml().get("overlay", {})
    def _int(clave, default):
        try:
            return int(cfg.get(clave, default))
        except (TypeError, ValueError):
            return default
    capa = str(cfg.get("capa", "top")).strip().lower()
    return {
        "ancho": max(100, _int("ancho", 420)),
        "alto": max(100, _int("alto", 600)),
        "margen_izquierdo": _int("margen_izquierdo", 0),
        "margen_inferior": _int("margen_inferior", 0),
        "capa": capa if capa in ("top", "overlay") else "top",
        "zona_exclusiva": _int("zona_exclusiva", 0),
    }


def leer_config_escritorio() -> dict:
    """[escritorio] de config.toml con defaults: tamaño y capa de la superficie
    del avatar de escritorio (rem_chat.py --modo escritorio), margen inicial y
    tamaño de la ventana de chat aparte."""
    cfg = leer_config_toml().get("escritorio", {})
    def _int(clave, default, minimo=None):
        try:
            v = int(cfg.get(clave, default))
        except (TypeError, ValueError):
            v = default
        return v if minimo is None else max(minimo, v)
    capa = str(cfg.get("capa", "top")).strip().lower()
    return {
        "ancho": _int("ancho", 380, 160),
        "alto": _int("alto", 620, 200),
        "margen_izquierdo": _int("margen_izquierdo", 40),
        "margen_inferior": _int("margen_inferior", 0),
        "capa": capa if capa in ("top", "overlay", "bottom") else "top",
        "zona_exclusiva": _int("zona_exclusiva", 0),
        "chat_ancho": _int("chat_ancho", 440, 300),
        "chat_alto": _int("chat_alto", 640, 300),
    }


_PALABRAS_FECHA_DEFAULT = [
    "qué hora", "hora es", "tienes hora", "dime la hora",
    "qué fecha", "fecha de hoy", "dime la fecha",
    "qué día es", "qué día estamos", "a qué día estamos", "a cuántos estamos",
    "día de la semana", "qué año es", "en qué año estamos", "qué mes es", "en qué mes estamos",
]


def leer_config_contexto() -> dict:
    """[contexto] de config.toml: cuándo se le inyecta al LLM la línea de
    fecha/hora del contexto dinámico (ver personalidad.construir_contexto_dinamico()).
    El estado de la PC ya no va en el contexto (ni existe la herramienta
    estado_pc desde 2026-11-05).

    linea_fecha: "condicional" (default; solo si el mensaje del usuario
                 contiene alguna palabra de palabras_fecha), "siempre" o "nunca".
    Coincidencia por palabra completa, sin distinguir mayúsculas ni tildes."""
    cfg = leer_config_toml().get("contexto", {})
    def _modo(clave):
        m = str(cfg.get(clave, "condicional")).strip().lower()
        return m if m in ("condicional", "siempre", "nunca") else "condicional"
    return {
        "linea_fecha": _modo("linea_fecha"),
        "palabras_fecha": [str(x) for x in cfg.get("palabras_fecha", _PALABRAS_FECHA_DEFAULT)],
    }


# Ver [herramientas] en config.toml. "*" al final = cualquier terminación.
DISPARADORES_HERRAMIENTAS_DEFAULT = [
    "abre*", "abrir*", "abrime",
    "lanza", "lanzar*", "lanzame", "inicia", "iniciar*", "iniciame", "ejecuta*", "arranca*",
    "busca*", "googlea*", "google",
    "apaga*", "shutdown",
    "archivo*", "carpeta*", "encuentra*", "encontrar", "localiza*",
]


def leer_disparadores_herramientas() -> list[str]:
    """[herramientas].disparadores de config.toml: palabras que, si aparecen en
    el mensaje del usuario, hacen que el turno le ofrezca las tools al modelo
    (ver chat_sesion.pide_herramientas()). Sin ninguna, el turno va sin tools."""
    cfg = leer_config_toml().get("herramientas", {})
    return [str(x) for x in cfg.get("disparadores", DISPARADORES_HERRAMIENTAS_DEFAULT)]


def leer_config_modo_serio() -> dict:
    """[modo_serio] de config.toml (ver chat_sesion.detectar_modo_serio()):
    `categorias` {nombre: [disparadores]} en el orden del archivo (la primera
    que coincide gana), `excepciones` y `glosario` {"la u": "la universidad"}.
    Sin la sección, el modo serio no se dispara nunca."""
    cfg = leer_config_toml().get("modo_serio", {})
    return {
        "categorias": {str(k): [str(x) for x in v]
                       for k, v in dict(cfg.get("categorias", {})).items()},
        "excepciones": [str(x) for x in cfg.get("excepciones", [])],
        "glosario": {str(k): str(v) for k, v in dict(cfg.get("glosario", {})).items()},
    }


def leer_max_oraciones() -> int:
    """[respuesta].max_oraciones: tope de oraciones por respuesta (0 = sin tope)."""
    try:
        return max(0, int(leer_config_toml().get("respuesta", {}).get("max_oraciones", 0)))
    except (TypeError, ValueError):
        return 0
