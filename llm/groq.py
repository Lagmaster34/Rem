"""GroqProvider — implementación del contrato LLMProvider sobre la API de Groq
(OpenAI-compatible), con streaming real vía AsyncGroq.
"""
import asyncio
import json
from typing import AsyncIterator

from groq import AsyncGroq

from ._retry import reintentar_con_backoff
from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolCall, ToolCallChunk, ToolSpec

_MAX_REINTENTOS = 3
_MODELO_DEFAULT = "llama-3.3-70b-versatile"


class GroqProvider(LLMProvider):
    """El cliente AsyncGroq (httpx por debajo) NO se crea acá en __init__: un
    httpx.AsyncClient que llega a abrir una conexión real queda con su pool
    interno atado al event loop que estaba corriendo en ese momento. Si este
    GroqProvider se usa como singleton (p.ej. get_provider() cacheado a
    futuro) y alguien lo llama desde un loop nuevo — el patrón exacto de
    _drenar_stream_llm() en Rem.py, un loop descartable por turno — reusar
    ese cliente revienta con "RuntimeError: Event loop is closed" en cuanto
    intenta reusar la conexión pooleada del loop viejo (reproducido con
    httpx.AsyncClient puro, sin mocks: falla en el segundo request, no en el
    primero). Por eso el cliente se crea perezoso, por loop — ver
    _obtener_cliente()."""

    def __init__(self, api_key: str, model: str = _MODELO_DEFAULT,
                 base_url: str | None = None, timeout: float = 30.0):
        if not api_key:
            raise ValueError(
                "GroqProvider necesita una api_key no vacía. Sin esto, el cliente "
                "se construiría igual y recién fallaría en la primera petición con "
                "un error de conexión/auth genérico, en vez de acá con un mensaje claro."
            )
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._model = model
        self._client: AsyncGroq | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None

    def _obtener_cliente(self) -> AsyncGroq:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            self._client = AsyncGroq(api_key=self._api_key, base_url=self._base_url, timeout=self._timeout)
            self._client_loop = loop
        return self._client

    async def stream_chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[Chunk]:
        client = self._obtener_cliente()
        payload_messages = [{"role": "system", "content": system}]
        payload_messages += [{"role": m.role, "content": m.content} for m in messages]

        kwargs = dict(model=self._model, messages=payload_messages, stream=True)
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        # El retry con espera exponencial solo cubre conectar y obtener el
        # stream: si la conexión ya empezó a entregar texto y se corta a
        # mitad de camino, reintentar reharía la respuesta desde cero y
        # duplicaría lo que el consumidor ya recibió — en ese caso es más
        # honesto dejar que la excepción se propague sin reintentar.
        stream = await reintentar_con_backoff(
            lambda: client.chat.completions.create(**kwargs), _MAX_REINTENTOS, "Groq",
        )

        # tool_calls llegan partidos en fragmentos de red por índice (varias
        # tool calls en paralelo comparten el mismo stream) — se acumulan acá
        # y se emiten completas recién al final.
        tool_calls_parciales: dict[int, dict] = {}
        finish_reason = None
        usage = None

        async for chunk in stream:
            if chunk.usage:
                usage = chunk.usage.model_dump()

            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if delta.content:
                yield TextDelta(delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    acumulado = tool_calls_parciales.setdefault(
                        tc.index, {"id": None, "name": None, "arguments": ""}
                    )
                    if tc.id:
                        acumulado["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acumulado["name"] = tc.function.name
                        if tc.function.arguments:
                            acumulado["arguments"] += tc.function.arguments

            if choice.finish_reason:
                finish_reason = choice.finish_reason

        for datos in tool_calls_parciales.values():
            try:
                argumentos = json.loads(datos["arguments"]) if datos["arguments"] else {}
            except json.JSONDecodeError:
                argumentos = {}
            yield ToolCallChunk(ToolCall(
                id=datos["id"] or "", name=datos["name"] or "", arguments=argumentos
            ))

        yield Done(reason=finish_reason, usage=usage)
