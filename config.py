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
    "ventana" (default) u "overlay". Cualquier otro valor cae a "ventana".
    rem_chat.py --modo lo pisa."""
    valor = str(leer_config_toml().get("app", {}).get("modo", "ventana")).strip().lower()
    return valor if valor in ("ventana", "overlay") else "ventana"


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


_PALABRAS_FECHA_DEFAULT = [
    "hora", "fecha", "día", "dia", "hoy", "mañana", "ayer", "semana", "mes", "año",
    "anoche", "madrugada", "tarde", "noche",
]


def leer_config_contexto() -> dict:
    """[contexto] de config.toml: cuándo se le inyecta al LLM la línea de
    fecha/hora del contexto dinámico (ver personalidad.construir_contexto_dinamico()).
    El estado de la PC ya no va en el contexto: es la herramienta estado_pc
    (acciones.py).

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
