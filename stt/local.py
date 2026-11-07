"""LocalSTTProvider — faster-whisper (CTranslate2) corriendo en CPU.

EN CPU a propósito: la VRAM de esta máquina (RTX 3050, 4 GB) es para Ollama
(ver config.toml [llm.ollama].num_gpu), así que el STT no toca la GPU. Modelo, cuantización, idioma y vocabulario salen de
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


class _Cancelada(Exception):
    """Una transcripción adelantada que ya no sirve, abandonada al salir del
    codificador (ver LocalSTTProvider.transcribir_adelantada)."""


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
        # habla._voz_lock. WhisperModel tampoco está pensado para llamadas
        # concurrentes sobre la misma instancia.
        self._lock = threading.Lock()

    def _obtener_modelo(self):
        # Llamar SIEMPRE con self._lock tomado.
        if self._modelo is None:
            from faster_whisper import WhisperModel
            rss0 = _rss_mb()
            t0 = time.perf_counter()
            opciones = dict(device=self.device, compute_type=self.compute_type,
                            cpu_threads=self.cpu_threads)
            # Primero solo la caché local: sin esto, huggingface_hub consulta
            # el Hub en CADA arranque aunque el modelo ya esté descargado (y
            # sin red espera a que falle). A la red solo se sale si falta.
            try:
                self._modelo = WhisperModel(self.model, local_files_only=True, **opciones)
            except Exception as e:
                _log(f"faster-whisper '{self.model}' no está en la caché local ({type(e).__name__}) "
                     f"— descargándolo una vez del Hub de Hugging Face")
                self._modelo = WhisperModel(self.model, **opciones)
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

    # Umbrales con los que faster-whisper decide reintentar con otra temperatura
    # (sus valores por defecto). La adelantada no reintenta: si un segmento no
    # los pasa, su texto no se usa y se transcribe de nuevo como siempre.
    _COMPRESION_MAX = 2.4
    _LOGPROB_MIN = -1.0
    _NO_HABLA_MIN = 0.6

    def transcribir_adelantada(self, audio: np.ndarray, cancelar=None) -> str | None:
        """Una sola pasada a temperatura 0 (sin los reintentos a temperaturas
        más altas, que sobre un trozo que alucina tardaban ~3 s y bloqueaban a
        la transcripción de verdad). None si algún segmento no es fiable, o si
        `cancelar` se activó: se mira al salir del codificador (~1 s de los
        ~1,5 s de Whisper, no se puede cortar a mitad) y se salta la
        decodificación (~0,5 s). Sin eso, una adelantada que quedó vieja por
        una continuación corta («…videojuegos, ¿y tú?») seguía ocupando
        Whisper al cortar y la transcripción de verdad la esperaba: medido
        (2026-11-07), 3,58 s de media frente a 3,38 sin adelantar."""
        return self._transcribir(audio, vad=True, adelantada=True, cancelar=cancelar)

    def _transcribir(self, audio, vad, adelantada=False, cancelar=None):
        with self._lock:
            modelo = self._obtener_modelo()
            if cancelar is None:
                return self._transcribir_con(modelo, audio, vad, adelantada)
            if cancelar.is_set():
                return None
            # generate_segments() de faster-whisper llama a self.encode() y
            # después decodifica: se envuelve encode() SOLO en esta instancia y
            # solo mientras dura esta llamada (con el lock tomado, ninguna otra
            # transcripción lo ve).
            encode = modelo.encode

            def encode_cancelable(*a, **k):
                salida = encode(*a, **k)
                if cancelar.is_set():
                    raise _Cancelada
                return salida
            modelo.encode = encode_cancelable
            try:
                return self._transcribir_con(modelo, audio, vad, adelantada)
            except _Cancelada:
                _log("adelantada abandonada tras el codificador (hubo voz después)")
                return None
            finally:
                del modelo.encode   # vuelve el método de la clase

    def _transcribir_con(self, modelo, audio, vad, adelantada):
        # Llamar con self._lock tomado (desde _transcribir).
        # transcribe() es un generador perezoso: la inferencia real ocurre
        # al iterar los segmentos, así que se consume acá adentro.
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
            **({"temperature": 0.0} if adelantada else {}),
        )
        segmentos = list(segmentos)
        if adelantada:
            for s in segmentos:
                silencio = s.no_speech_prob > self._NO_HABLA_MIN
                if s.compression_ratio > self._COMPRESION_MAX or \
                        (s.avg_logprob < self._LOGPROB_MIN and not silencio):
                    _log(f"adelantada no fiable (compresión {s.compression_ratio:.2f}, "
                         f"logprob {s.avg_logprob:.2f}): se transcribirá de nuevo")
                    return None
        return " ".join(s.text.strip() for s in segmentos).strip()
