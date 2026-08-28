"""config.py — configuración compartida de Rem: carga de .env y config.toml.

Extraído de Rem.py (donde vivía como _cargar_dotenv(), privada del módulo) a
un módulo compartido porque bench_chat.py no puede importar Rem.py — el
Python 3.10.14 del venv se compiló sin _tkinter, y aunque lo tuviera, Rem.py
ejecuta su GUI Tkinter a nivel de módulo con solo importarlo. Sin este
módulo, ese script nunca veía las variables de .env (ni GROQ_API_KEY antes ni
ANTHROPIC_API_KEY ahora), lo que se manifestaba como un error de conexión
genérico en vez de un mensaje claro de "falta la API key".
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


def leer_dispositivo_rvc() -> str:
    """Dispositivo para RVC: "cpu" o "cuda", desde config.toml [rvc].device
    (default "cuda"). Cualquier valor que no sea exactamente "cpu" se trata
    como "cuda" — ver la nota en CLAUDE.md sobre la calibración de num_gpu
    que le hizo sitio a RVC en la misma GPU que el LLM local (Ollama)."""
    rvc_config = leer_config_toml().get("rvc", {})
    valor = str(rvc_config.get("device", "cuda")).strip().lower()
    return "cpu" if valor == "cpu" else "cuda"
