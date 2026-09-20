"""LocalSTTProvider — faster-whisper (CTranslate2) corriendo en CPU.

EN CPU a propósito: la VRAM de esta máquina (RTX 3050, 4 GB) ya está llena con
Ollama + RVC (ver CLAUDE.md, "RVC vuelve a GPU: calibración de num_gpu"), así
que el STT no toca la GPU. Modelo, cuantización, idioma y vocabulario salen de
config.toml [stt.local].
"""
import threading
import time

import numpy as np

from .base import SAMPLE_RATE, STTProvider


def _rss_mb() -> float:
    """RAM residente de ESTE proceso, en MiB (VmRSS de /proc/self/status)."""
    with open("/proc/self/status") as f:
        for linea in f:
            if linea.startswith("VmRSS:"):
                return int(linea.split()[1]) / 1024
    return 0.0


def _log(msg):
    print(f"  [STT] {msg}", flush=True)


class LocalSTTProvider(STTProvider):
    def __init__(self, model="small", compute_type="int8", device="cpu",
                 language="es", beam_size=1, cpu_threads=0, initial_prompt=None):
        self.model = model
        self.compute_type = compute_type
        self.device = device
        self.language = language
        self.beam_size = beam_size
        self.cpu_threads = cpu_threads
        self.initial_prompt = initial_prompt or None
        self._modelo = None
        # Serializa carga y transcripciones: la precarga (hilo de fondo al
        # arrancar) y un primer ptt_stop pueden coincidir — mismo motivo que
        # habla._rvc_lock. WhisperModel tampoco está pensado para llamadas
        # concurrentes sobre la misma instancia.
        self._lock = threading.Lock()

    def _obtener_modelo(self):
        # Llamar SIEMPRE con self._lock tomado.
        if self._modelo is None:
            from faster_whisper import WhisperModel
            rss0 = _rss_mb()
            t0 = time.perf_counter()
            self._modelo = WhisperModel(
                self.model, device=self.device, compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            _log(f"faster-whisper '{self.model}' ({self.compute_type}, {self.device}) cargado en "
                 f"{time.perf_counter() - t0:.1f}s — RAM del proceso {rss0:.0f} -> {_rss_mb():.0f} MiB")
        return self._modelo

    def precargar(self) -> None:
        """Carga el modelo y hace una transcripción de calentamiento sobre
        silencio (descartada) — la primera inferencia en frío es más lenta
        que las siguientes (asignación de buffers de CTranslate2)."""
        with self._lock:
            self._obtener_modelo()
        t0 = time.perf_counter()
        self._transcribir(np.zeros(SAMPLE_RATE, dtype=np.float32), vad=False)
        _log(f"calentamiento listo en {time.perf_counter() - t0:.2f}s — RAM {_rss_mb():.0f} MiB")

    def transcribir(self, audio: np.ndarray) -> str:
        return self._transcribir(audio, vad=True)

    def _transcribir(self, audio, vad):
        with self._lock:
            modelo = self._obtener_modelo()
            # transcribe() es un generador perezoso: la inferencia real ocurre
            # al iterar los segmentos, así que se consume acá adentro, con el
            # lock tomado.
            segmentos, _info = modelo.transcribe(
                audio.astype(np.float32, copy=False),
                language=self.language,
                beam_size=self.beam_size,
                initial_prompt=self.initial_prompt,
                # El VAD (silero, viene con faster-whisper) recorta el silencio
                # antes de decodificar: sin él Whisper alucina texto ("Gracias
                # por ver el video...") sobre pausas y ruido de fondo.
                vad_filter=vad,
                # Cada push-to-talk es un enunciado suelto: arrastrar el texto
                # previo como contexto solo propaga alucinaciones.
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            return " ".join(s.text.strip() for s in segmentos).strip()
