"""EchoProvider — no llama a ningún modelo. Devuelve tal cual el último
mensaje del usuario, para que Rem repita con su voz lo que se escriba, sin
IA de por medio: sirve para probar TTS/RVC/lipsync/avatar de punta a punta
sin gastar tokens de un LLM real ni depender de que haya red o API key.

Ignora `system` y `tools` a propósito — no hay ningún modelo del otro lado
que los necesite. Sigue el contrato de LLMProvider igual (async generator,
mismos tipos de Chunk) para que el resto del pipeline (SentenceSplitter,
_drenar_stream_llm, etc.) no note la diferencia con un provider real.
"""
from typing import AsyncIterator

from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolSpec


class EchoProvider(LLMProvider):
    """Sin estado, sin cliente HTTP, sin API key — no hay nada que
    inicializar ni que limpiar entre turnos."""

    async def stream_chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[Chunk]:
        # Se busca desde el final por role == "user" en vez de asumir
        # messages[-1]: es lo mismo en el uso normal (el turno recién
        # agregado antes de llamar a stream_chat), pero no depende de que
        # sea así — si el último mensaje fuera de otro rol, sigue devolviendo
        # lo último que dijo el usuario en vez de romper o quedar en blanco.
        ultimo_usuario = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        if ultimo_usuario:
            yield TextDelta(ultimo_usuario)
        yield Done(reason="stop")
