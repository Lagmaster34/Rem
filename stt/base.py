"""Contrato común para cualquier backend de voz a texto (faster-whisper local,
Whisper en la API de Groq...). Mismo criterio que llm/base.py: el resto del
código habla con STTProvider y no sabe cuál hay detrás.

Sincrónico a propósito, a diferencia de LLMProvider: transcribir() es una
llamada bloqueante sobre un audio ya completo (push-to-talk graba entero y
recién después transcribe — no hay stream de entrada), así que el llamador
async la corre con asyncio.to_thread() en vez de pagar un contrato async que
ningún backend aprovecharía.
"""
from abc import ABC, abstractmethod

import numpy as np

SAMPLE_RATE = 16000  # Hz — el que esperan tanto faster-whisper como la API de Groq


class STTProvider(ABC):
    def precargar(self) -> None:
        """Deja el backend listo para el primer transcribir() (cargar el
        modelo, calentar). No-op por defecto: un backend remoto no tiene nada
        que cargar. Seguro de llamar desde un hilo de fondo al arrancar."""

    @abstractmethod
    def transcribir(self, audio: np.ndarray) -> str:
        """`audio`: float32 mono a SAMPLE_RATE (16 kHz), valores en [-1, 1].
        Devuelve el texto (sin espacios sobrantes), o "" si no hay habla."""
