"""Capa de abstracción de LLM: contrato común (base.py) + un provider por
backend (groq.py, claude.py, local.py). get_provider() decide cuál instanciar
según configuración, sin que el resto del código sepa cuál es."""
import os

import config as _config

from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolCall, ToolCallChunk, ToolSpec
from .sentence_splitter import dividir_en_oraciones

__all__ = [
    "Chunk", "Done", "LLMProvider", "Message", "TextDelta",
    "ToolCall", "ToolCallChunk", "ToolSpec", "get_provider",
    "dividir_en_oraciones",
]


def _leer_config_llm() -> dict:
    return dict(_config.leer_config_toml().get("llm", {}))


def get_provider() -> LLMProvider:
    """Decide qué LLMProvider instanciar. Precedencia: REM_LLM_PROVIDER (env)
    > [llm].provider en config.toml > "groq" por defecto.
    Falla acá (al arrancar) si falta la API key del provider elegido, en vez
    de dejar que reviente recién en la primera petición con un error de
    conexión genérico."""
    llm_config = _leer_config_llm()
    proveedor = (
        os.environ.get("REM_LLM_PROVIDER", "").strip().lower()
        or str(llm_config.get("provider", "groq")).strip().lower()
    )

    if proveedor == "groq":
        from .groq import GroqProvider
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Proveedor 'groq' seleccionado pero falta GROQ_API_KEY en el entorno "
                "(revisá tu .env). Sin esto Groq fallaría recién en la primera "
                "petición con un error de conexión genérico — mejor fallar acá."
            )
        groq_config = dict(llm_config.get("groq", {}))
        return GroqProvider(
            api_key=api_key,
            model=str(groq_config.get("model", "llama-3.3-70b-versatile")),
        )

    if proveedor == "claude":
        from .claude import ClaudeProvider
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Proveedor 'claude' seleccionado pero falta ANTHROPIC_API_KEY en el "
                "entorno (revisá tu .env). Sin esto Claude fallaría recién en la "
                "primera petición con un error de conexión genérico — mejor fallar acá."
            )
        claude_config = dict(llm_config.get("claude", {}))
        return ClaudeProvider(
            api_key=api_key,
            model=str(claude_config.get("model", "claude-sonnet-5")),
            max_tokens=int(claude_config.get("max_tokens", 1024)),
        )

    if proveedor == "ollama":
        from .local import OllamaProvider
        ollama_config = dict(llm_config.get("ollama", {}))
        return OllamaProvider(
            base_url=str(ollama_config.get("base_url", "http://127.0.0.1:11434")),
            model=str(ollama_config.get(
                "model", "hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M"
            )),
            keep_alive=ollama_config.get("keep_alive", 0),
            options={
                "temperature": ollama_config.get("temperature", 0.7),
                "top_p": ollama_config.get("top_p", 0.8),
                "top_k": ollama_config.get("top_k", 20),
                "min_p": ollama_config.get("min_p", 0),
                "num_ctx": ollama_config.get("num_ctx", 8192),
                "num_gpu": ollama_config.get("num_gpu", 28),
            },
        )

    if proveedor == "echo":
        from .echo import EchoProvider
        return EchoProvider()

    raise ValueError(
        f"Proveedor de LLM desconocido: '{proveedor}'. "
        "Implementados: 'groq', 'claude', 'ollama', 'echo'."
    )
