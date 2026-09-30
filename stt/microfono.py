"""Captura de micrófono para push-to-talk: sounddevice (PortAudio -> PipeWire),
abierto SOLO entre iniciar() y detener() — fuera de ese intervalo el micrófono
no está abierto (ni el indicador de captura del escritorio encendido)."""
import threading

import numpy as np
import sounddevice as sd

from .base import SAMPLE_RATE


class Grabador:
    """Un uso por grabación: iniciar() abre el stream, detener() lo cierra y
    devuelve todo lo capturado como float32 mono a 16 kHz."""

    def __init__(self, max_s=30.0, dispositivo=None):
        self.dispositivo = dispositivo   # None = predeterminado del sistema
        self.max_frames = int(max_s * SAMPLE_RATE)
        self._stream = None
        self._trozos = []
        self._frames = 0
        self._lock = threading.Lock()

    @property
    def grabando(self) -> bool:
        return self._stream is not None

    def _callback(self, indata, frames, time_info, status):
        # Corre en el hilo de audio de PortAudio: nada pesado acá.
        with self._lock:
            if self._frames < self.max_frames:
                self._trozos.append(indata[:, 0].copy())
                self._frames += frames

    def iniciar(self):
        if self._stream is not None:
            raise RuntimeError("el micrófono ya está abierto")
        self._trozos, self._frames = [], 0
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=self._callback,
            device=self.dispositivo,
        )
        self._stream.start()

    def detener(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            audio = np.concatenate(self._trozos) if self._trozos else np.zeros(0, np.float32)
            self._trozos = []
        return audio
