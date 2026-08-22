"""GroqProvider — implementación del contrato LLMProvider sobre la API de Groq
(OpenAI-compatible), con streaming real vía AsyncGroq.
"""
import asyncio
import json
from typing import AsyncIterator

from groq import AsyncGroq

from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolCall, ToolCallChunk, ToolSpec

_MAX_REINTENTOS = 3
_MODELO_DEFAULT = "llama-3.3-70b-versatile"


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = _MODELO_DEFAULT,
                 base_url: str | None = None, timeout: float = 30.0):
        self._client = AsyncGroq(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model

    async def stream_chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[Chunk]:
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

        # El retry con espera exponencial (heredado de _groq_completions) solo
        # cubre conectar y obtener el stream: si la conexión ya empezó a
        # entregar texto y se corta a mitad de camino, reintentar reharía la
        # respuesta desde cero y duplicaría lo que el consumidor ya recibió —
        # en ese caso es más honesto dejar que la excepción se propague.
        ultimo_error = None
        stream = None
        for intento in range(_MAX_REINTENTOS):
            try:
                stream = await self._client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                ultimo_error = e
                if intento < _MAX_REINTENTOS - 1:
                    espera = 2 ** intento
                    print(f"[Groq] Error (intento {intento+1}/{_MAX_REINTENTOS}): {e}. Reintentando en {espera}s...")
                    await asyncio.sleep(espera)
        else:
            raise ultimo_error

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
