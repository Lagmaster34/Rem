"""OllamaProvider — implementación del contrato LLMProvider sobre la API
*nativa* de Ollama (`/api/chat`), no la compatible con OpenAI
(`/v1/chat/completions`): esa no acepta `think` ni `keep_alive`, y ambos son
imprescindibles acá (ver más abajo). Streaming NDJSON real vía httpx.

Contexto de memoria (medido en esta máquina, RTX 3050 4 GB): el modelo
Qwen3.5-4B Q4_K_M con sus 32 capas completas en GPU (num_gpu=32, el default
de Ollama) ocupa ~2994 MiB, dejando solo ~1100 MiB libres — insuficiente
para RVC en la misma GPU (confirmado: CUDA out of memory de forma
consistente). La solución no es serializar LLM y RVC ni forzar RVC a CPU
(~4,5x más lento, no le sigue el ritmo a la cola del SentenceSplitter), sino
bajarle capas al LLM: con `num_gpu=28` (ver config.toml → [llm.ollama],
incluye la tabla completa de calibración) el modelo ocupa ~2714 MiB y le
deja sitio de sobra a RVC, a costa de bajar de ~40,7 a ~25,8 tok/s — sigue
siendo una velocidad de generación cómoda.
"""
import asyncio
import json
import uuid
from typing import AsyncIterator

import httpx

from ._retry import reintentar_con_backoff
from .base import Chunk, Done, LLMProvider, Message, TextDelta, ToolCall, ToolCallChunk, ToolSpec

_MAX_REINTENTOS = 3
_BASE_URL_DEFAULT = "http://127.0.0.1:11434"
_MODELO_DEFAULT = "hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M"
_KEEP_ALIVE_DEFAULT = 0
# Sampling recomendado por el autor del modelo para modo no-thinking.
_OPTIONS_DEFAULT = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0, "num_ctx": 8192}


class OllamaProvider(LLMProvider):
    """Mismo patrón de cliente perezoso por loop que GroqProvider/ClaudeProvider
    (ver la nota en groq.py): httpx.AsyncClient queda atado al loop en el que
    abrió su primera conexión real, así que se recrea si el loop cambió."""

    def __init__(self, base_url: str = _BASE_URL_DEFAULT, model: str = _MODELO_DEFAULT,
                 keep_alive=_KEEP_ALIVE_DEFAULT, options: dict | None = None,
                 timeout: float = 60.0):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._keep_alive = keep_alive
        self._options = {**_OPTIONS_DEFAULT, **(options or {})}
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._client_loop: asyncio.AbstractEventLoop | None = None

    def _obtener_cliente(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._client_loop is not loop:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
            self._client_loop = loop
        return self._client

    async def stream_chat(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[Chunk]:
        client = self._obtener_cliente()

        # El system prompt en /api/chat va como un mensaje con rol "system"
        # dentro del array, no como parámetro de nivel superior (a diferencia
        # de Claude) — el contrato lo recibe aparte igual, la conversión pasa
        # acá adentro.
        payload_messages = [{"role": "system", "content": system}]
        payload_messages += [{"role": m.role, "content": m.content} for m in messages]

        payload = {
            "model": self._model,
            "messages": payload_messages,
            # think=false: con el thinking activo el modelo genera cientos de
            # tokens de razonamiento antes de responder — inviable para un
            # asistente hablado (verificado en vivo). No es configurable a
            # propósito, a diferencia de keep_alive/options más abajo.
            "think": False,
            "keep_alive": self._keep_alive,
            "stream": True,
            "options": self._options,
        }
        if tools:
            payload["tools"] = [
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

        async def _conectar():
            req = client.build_request("POST", "/api/chat", json=payload)
            resp = await client.send(req, stream=True)
            resp.raise_for_status()
            return resp

        # Igual que en Groq/Claude: el retry solo cubre conectar y obtener el
        # stream, no una respuesta que ya empezó a llegar y se corta a mitad
        # de camino (ver la nota en groq.py).
        resp = await reintentar_con_backoff(_conectar, _MAX_REINTENTOS, "Ollama")

        finish_reason = None
        usage: dict = {}

        try:
            async for linea in resp.aiter_lines():
                if not linea.strip():
                    continue
                data = json.loads(linea)

                mensaje = data.get("message") or {}
                contenido = mensaje.get("content")
                if contenido:
                    yield TextDelta(contenido)

                # A diferencia de Groq/Claude, acá los tool_calls llegan
                # completos (argumentos ya como dict), sin fragmentar entre
                # chunks — más simple, no hace falta acumular ni parsear.
                # La API nativa tampoco manda un id por tool call, así que se
                # genera uno acá para cumplir el contrato normalizado.
                for tc in mensaje.get("tool_calls") or []:
                    funcion = tc.get("function", {})
                    yield ToolCallChunk(ToolCall(
                        id=uuid.uuid4().hex,
                        name=funcion.get("name", ""),
                        arguments=funcion.get("arguments") or {},
                    ))

                if data.get("done"):
                    finish_reason = data.get("done_reason")
                    usage = {
                        "prompt_eval_count": data.get("prompt_eval_count"),
                        "eval_count": data.get("eval_count"),
                        "load_duration_ms": (data.get("load_duration") or 0) / 1e6,
                        "prompt_eval_duration_ms": (data.get("prompt_eval_duration") or 0) / 1e6,
                        "eval_duration_ms": (data.get("eval_duration") or 0) / 1e6,
                        "total_duration_ms": (data.get("total_duration") or 0) / 1e6,
                    }
                    # Sin `break`: el servidor cierra el body de la respuesta
                    # justo después de la línea con done=true, así que dejar
                    # que aiter_lines() termine sola evita abandonarla a
                    # mitad de iteración — un generador async abandonado (en
                    # vez de agotado) necesita un athrow(GeneratorExit) de
                    # limpieza que asyncio programa como Task aparte; si el
                    # loop ya cerró para cuando el GC lo recolecta, esa Task
                    # se destruye a mitad de camino ("Task was destroyed but
                    # it is pending!") — reproducido y confirmado así.
        finally:
            await resp.aclose()

        # Con keep_alive=0 el modelo se recarga en cada turno — medir carga
        # aparte de generación es lo que permite decidir después si compensa
        # (la hipótesis es que la caché de páginas del sistema lo hace rápido,
        # pero hay que verlo medido, no asumido).
        print(f"[Ollama] carga del modelo: {usage.get('load_duration_ms', 0):.0f}ms | "
              f"generación: {usage.get('eval_duration_ms', 0):.0f}ms "
              f"({usage.get('eval_count', 0)} tokens) | "
              f"total: {usage.get('total_duration_ms', 0):.0f}ms")

        yield Done(reason=finish_reason, usage=usage or None)
