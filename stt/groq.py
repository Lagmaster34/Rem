"""GroqSTTProvider — Whisper por la API de Groq (transcriptions).

Implementado por ser trivial, pero SIN verificar en vivo en esta máquina (no
se probó con una GROQ_API_KEY real). El provider por defecto es el local.
"""
import io

import numpy as np
import soundfile as sf

from .base import SAMPLE_RATE, STTProvider


class GroqSTTProvider(STTProvider):
    def __init__(self, api_key, model="whisper-large-v3-turbo", language="es"):
        if not api_key:
            raise RuntimeError("GroqSTTProvider requiere una api_key no vacía.")
        from groq import Groq
        self._client = Groq(api_key=api_key)
        self.model = model
        self.language = language

    def transcribir(self, audio: np.ndarray) -> str:
        buf = io.BytesIO()
        sf.write(buf, audio.astype(np.float32, copy=False), SAMPLE_RATE,
                 format="WAV", subtype="PCM_16")
        respuesta = self._client.audio.transcriptions.create(
            file=("audio.wav", buf.getvalue()),
            model=self.model,
            language=self.language,
            response_format="json",
        )
        return (respuesta.text or "").strip()
