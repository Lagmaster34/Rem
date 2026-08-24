"""ClaudeProvider — implementación del contrato LLMProvider sobre la API de
Anthropic (Claude), con streaming real vía AsyncAnthropic. Groq queda como
fallback (ver llm/groq.py y get_provider()).

Elección de modelo: Claude Sonnet 5 (familia intermedia), no el modelo tope
(Opus 5 / Fable 5). Para un asistente conversacional de escritorio como Rem
la latencia importa más que la capacidad máxima de razonamiento, y cada
turno reenvía el system prompt completo (aunque cacheado) — el modelo tope
es caro y lento para charla. Sonnet 5 balancea fidelidad de personaje/
instrucciones (necesaria para que el catálogo de acciones en JSON se
formatee bien dentro de la respuesta) contra costo/latencia; Haiku 4.5 es la
alternativa más barata/rápida si hace falta apretar más la latencia, a costa
de fidelidad de personaje. Ambos configurables vía config.toml [llm.claude].
"""
import asyncio
import json
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from ._retry import reintentar_con_backoff
from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolCall, ToolCallChunk, ToolSpec

_MAX_REINTENTOS = 3
_MODELO_DEFAULT = "claude-sonnet-5"
_MAX_TOKENS_DEFAULT = 1024  # respuesta conversacional corta, no una tarea agéntica


class ClaudeProvider(LLMProvider):
    """Mismo patrón de cliente perezoso por loop que GroqProvider (ver la
    nota ahí): AsyncAnthropic envuelve un cliente HTTP async también, y uno
    que llega a abrir una conexión real queda atado al loop en el que corrió
    esa primera vez. Si este provider se usa como singleton y se lo llama
    desde un loop nuevo (el patrón de _drenar_stream_llm() en Rem.py),
    reusar el cliente viejo revienta con "Event loop is closed"."""

    def __init__(self, api_key: str, model: str = _MODELO_DEFAULT,
                 max_tokens: int = _MAX_TOKENS_DEFAULT, timeout: float = 30.0):
        if not api_key:
            raise ValueError(
                "ClaudeProvider necesita una api_key no vacía. Sin esto, el "
                "cliente se construiría igual y recién fallaría en la primera "
                "petición con un error de conexión/auth genérico, en vez de "
                "acá con un mensaje claro."
            )
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._client: AsyncAnthropic | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None

    def _obtener_cliente(self) -> AsyncAnthropic:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            self._client = AsyncAnthropic(api_key=self._api_key, timeout=self._timeout)
            self._client_loop = loop
        return self._client

    async def stream_chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[Chunk]:
        client = self._obtener_cliente()

        # Lista de bloques (no string plano) con cache_control en el bloque
        # (el único, acá) — así es como Anthropic cachea el prefijo. El
        # system prompt de Rem (construir_prompt_sistema()) ya es idéntico
        # byte a byte entre turnos (ver "Nada volátil en el system prompt"
        # en CLAUDE.md), así que esto cachea limpio desde el primer turno.
        system_bloques = [{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }]

        payload_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs = dict(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_bloques,
            messages=payload_messages,
            stream=True,
        )
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]

        # Igual que en Groq: el retry solo cubre conectar y obtener el
        # stream, no una respuesta que ya empezó a llegar y se corta a
        # mitad de camino (ver la nota en groq.py).
        stream = await reintentar_con_backoff(
            lambda: client.messages.create(**kwargs), _MAX_REINTENTOS, "Claude",
        )

        # Por índice de content_block: tipo (tool_use o no) y, para tool_use,
        # id/nombre + el JSON parcial acumulado. Los fragmentos de
        # input_json_delta son *parciales* (no se pueden parsear uno por
        # uno) — se concatenan acá y se parsean recién en content_block_stop.
        bloques: dict[int, dict] = {}
        stop_reason = None
        usage: dict = {}

        async for event in stream:
            tipo = event.type

            if tipo == "message_start":
                usage.update(event.message.usage.model_dump())

            elif tipo == "content_block_start":
                cb = event.content_block
                if cb.type == "tool_use":
                    bloques[event.index] = {"tool_use": True, "id": cb.id, "name": cb.name, "json": ""}
                else:
                    bloques[event.index] = {"tool_use": False}

            elif tipo == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield TextDelta(delta.text)
                elif delta.type == "input_json_delta":
                    bloques[event.index]["json"] += delta.partial_json

            elif tipo == "content_block_stop":
                info = bloques.get(event.index) or {}
                if info.get("tool_use"):
                    try:
                        argumentos = json.loads(info["json"]) if info["json"] else {}
                    except json.JSONDecodeError:
                        argumentos = {}
                    yield ToolCallChunk(ToolCall(id=info["id"], name=info["name"], arguments=argumentos))

            elif tipo == "message_delta":
                if event.delta.stop_reason:
                    stop_reason = event.delta.stop_reason
                usage.update(event.usage.model_dump())

        escritura = usage.get("cache_creation_input_tokens", 0)
        lectura = usage.get("cache_read_input_tokens", 0)
        print(f"[Claude] cache: {escritura} tokens de escritura, {lectura} tokens de lectura")

        yield Done(reason=stop_reason, usage=usage or None)
