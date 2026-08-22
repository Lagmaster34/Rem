"""Capa de abstracción de LLM: contrato común (base.py) + un provider por
backend (groq.py, y a futuro claude.py/local.py). get_provider() decide cuál
instanciar según configuración, sin que el resto del código sepa cuál es."""
import os

from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolCall, ToolCallChunk, ToolSpec

__all__ = [
    "Chunk", "Done", "LLMProvider", "Message", "TextDelta",
    "ToolCall", "ToolCallChunk", "ToolSpec", "get_provider",
]

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.toml"
)


def _leer_config_llm() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        return {}
    import tomlkit
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        config = tomlkit.parse(f.read())
    return dict(config.get("llm", {}))


def get_provider() -> LLMProvider:
    """Decide qué LLMProvider instanciar. Precedencia: REM_LLM_PROVIDER (env)
    > [llm].provider en config.toml > "groq" por defecto."""
    llm_config = _leer_config_llm()
    proveedor = (
        os.environ.get("REM_LLM_PROVIDER", "").strip().lower()
        or str(llm_config.get("provider", "groq")).strip().lower()
    )

    if proveedor == "groq":
        from .groq import GroqProvider
        return GroqProvider(
            api_key=os.environ.get("GROQ_API_KEY", ""),
            model=str(llm_config.get("model", "llama-3.3-70b-versatile")),
        )

    raise ValueError(
        f"Proveedor de LLM desconocido: '{proveedor}'. "
        "Por ahora solo está implementado 'groq' — claude/local todavía no existen."
    )
