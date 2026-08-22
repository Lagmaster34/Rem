"""Convierte el stream de un LLMProvider en oraciones completas, para poder
hablar (TTS) apenas termina cada una en vez de esperar la respuesta entera.

Reutiliza la misma regla de corte que _partir_oraciones() en Rem.py: partir en
. ! ? seguidos de espacio (así "…" queda pegado a la frase), descartando
fragmentos de menos de 3 caracteres.
"""
import re
from typing import AsyncIterator

from .base import Chunk, Done, TextDelta

_CORTE_ORACION = re.compile(r'(?<=[.!?])\s+')
_LARGO_MINIMO = 3


async def dividir_en_oraciones(chunks: AsyncIterator[Chunk]) -> AsyncIterator[str]:
    """Acumula los TextDelta de `chunks` y emite cada oración completa apenas
    se detecta su final. Una oración puede llegar partida entre dos chunks de
    red — lo que no cierra en oración se queda en el buffer hasta el próximo
    fragmento. Al recibir Done, emite lo que haya quedado pendiente."""
    buffer = ""

    async for chunk in chunks:
        if isinstance(chunk, TextDelta):
            buffer += chunk.text
            *completas, buffer = _CORTE_ORACION.split(buffer)
            for oracion in completas:
                oracion = oracion.strip()
                if len(oracion) >= _LARGO_MINIMO:
                    yield oracion
        elif isinstance(chunk, Done):
            resto = buffer.strip()
            if len(resto) >= _LARGO_MINIMO:
                yield resto
            buffer = ""
