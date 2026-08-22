"""Contrato común para cualquier backend de LLM (Groq, Claude, un modelo local...).

Diseñado async nativo a propósito: el backend de Rem hoy es síncrono (Tkinter +
hilos), pero esta capa no debe cargar con ese detalle — el puente sync→async
vive en Rem.py (ver `_drenar_stream_llm`), no acá. Cuando Tkinter se reemplace
por un backend async, esta capa no cambia.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Literal, Union


@dataclass
class Message:
    """Un turno de la conversación. El system prompt NO es un Message — ver
    LLMProvider.stream_chat."""
    role: Literal["user", "assistant"]
    content: str


@dataclass
class ToolSpec:
    """Una acción que el modelo puede invocar: nombre, descripción y sus
    parámetros como JSON Schema."""
    name: str
    description: str
    parameters: dict


@dataclass
class ToolCall:
    """Una invocación de tool ya resuelta: argumentos parseados como dict, no
    como string JSON crudo."""
    id: str
    name: str
    arguments: dict


@dataclass
class TextDelta:
    """Fragmento de texto de la respuesta, en el orden en que llega."""
    text: str


@dataclass
class ToolCallChunk:
    """Una tool call completa (ya reensamblada de sus fragmentos de red, si el
    provider los entrega partidos)."""
    call: ToolCall


@dataclass
class Done:
    """Fin del stream: motivo de parada ('stop', 'tool_calls', etc., según lo
    reporte el provider) y uso de tokens si el provider lo entrega."""
    reason: str | None = None
    usage: dict | None = None


Chunk = Union[TextDelta, ToolCallChunk, Done]


class LLMProvider(ABC):
    """Contrato común para cualquier backend de LLM.

    El system prompt viaja como parámetro explícito de `stream_chat`, NUNCA
    dentro de `messages`. Motivo: Claude lo lleva como campo de nivel superior
    (`system=`) y los endpoints OpenAI-compatible (Groq incluido) lo esperan
    como un mensaje más del array con `role="system"`. Si lo metiéramos en la
    lista de `messages`, cada provider tendría que extraerlo de ahí para
    dárselo a su API en el formato que le corresponda — y ese paso de ida y
    vuelta es justo donde se rompe el prompt caching: el prefijo deja de ser
    idéntico byte a byte entre llamadas si depende de cómo cada provider lo
    reconstruye.
    """

    @abstractmethod
    def stream_chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[Chunk]:
        """Implementaciones: async def con `yield` (async generator), no
        `async def` con `return` de un valor — así llamar a stream_chat(...)
        devuelve el generador directamente, sin necesitar `await` previo."""
        ...
