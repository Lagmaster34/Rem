"""habla.py — síntesis de voz para un turno de conversación: Piper (voz de
Yoru, local, en CPU) -> timeline de visemes (lipsync.py) -> enviar_audio() (al
avatar por WebSocket, con fallback local a sounddevice si no hay ningún
cliente conectado).

Extraído de bench_chat.py (donde vivía todo esto originalmente, atado al
REPL) para que rem_avatar_server.py también pueda usarlo — el panel de chat
de rem_chat.py habla las respuestas igual que el REPL, con el mismo pipeline.
Mismo motivo que chat_sesion.py para SesionChat/procesar_turno(): un solo
lugar para lo que antes vivía nada más en el REPL.

_voz/_voz_lock son MÓDULO-LEVEL (una sola voz por proceso): el REPL de
bench_chat.py y el panel de chat de rem_chat.py tienen cada uno su propia
cola/worker (ver worker_habla() y CLAUDE.md, "Voz en la ventana de chat"),
pero comparten esta MISMA PiperVoice — cargarla dos veces no tiene sentido.
"""
import asyncio
import os
import threading
import time

import numpy as np
import soundfile as sf
import sounddevice as sd

import config
import lipsync
from rem_avatar_server import TMP_AUDIO_DIR, enviar_audio

ESPERA_CLIENTE_S = 8.0  # tiempo máximo para que un cliente WS conecte antes del fallback local

_voz = None
# Serializa la carga y cada síntesis. La carga, para que la precarga y un
# primer turno que llegue antes de que termine no carguen el modelo dos veces.
# La síntesis, porque el fonemizador de Piper (espeak-ng, piper/espeakbridge)
# es estado C global del proceso, no pensado para dos hilos a la vez — y con
# el worker del REPL y el del panel puede haber dos síntesis simultáneas. Cada
# una dura ~0,1-0,3s en CPU: serializarlas no cuesta nada perceptible.
_voz_lock = threading.Lock()


def log(msg):
    print(f"  {msg}", flush=True)


def _obtener_voz():
    """Carga la PiperVoice si hace falta y devuelve la instancia cacheada.
    include_alignments=True parchea el modelo EN MEMORIA (paquete onnx) para
    exponer la duración de cada fonema, que es de donde sale el lipsync — el
    .onnx en disco no se toca. Llamar con _voz_lock tomado."""
    global _voz
    if _voz is None:
        from piper import PiperVoice
        ruta = config.leer_modelo_tts()
        log(f"cargando voz Piper ({os.path.relpath(ruta, config.BASE_DIR)})...")
        t0 = time.perf_counter()
        _voz = PiperVoice.load(ruta, include_alignments=True)
        log(f"voz Piper lista en {time.perf_counter() - t0:.2f}s "
            f"({_voz.config.sample_rate} Hz, CPU)")
    return _voz


def sintetizar(texto):
    """Texto -> (audio int16, sample_rate, timeline, con_alineacion). Bloqueante
    (CPU): desde el loop de asyncio, llamarlo con asyncio.to_thread(). El
    sample rate sale del .onnx.json del modelo (vía AudioChunk), no está fijo."""
    with _voz_lock:
        voz = _obtener_voz()
        chunks = list(voz.synthesize(texto, include_alignments=True))
    if not chunks:
        return np.zeros(0, dtype=np.int16), voz.config.sample_rate, [], True
    audio = np.concatenate([c.audio_int16_array for c in chunks])
    timeline, con_alineacion = lipsync.construir_timeline(chunks)
    return audio, chunks[0].sample_rate, timeline, con_alineacion


def precargar_tts():
    """Carga la voz y hace una síntesis de calentamiento descartada, en un
    hilo de fondo lanzado al arrancar (rem_chat.py y bench_chat.py standalone)
    — para que el primer turno no pague la carga del modelo ni la primera
    pasada de onnxruntime en frío."""
    try:
        t0 = time.perf_counter()
        sintetizar("Hola.")
        log(f"calentamiento de la voz listo en {time.perf_counter() - t0:.2f}s")
    except Exception as e:
        log(f"precarga de la voz falló, no bloqueante ({e})")


class TurnoHabla:
    """Timing de un turno con voz activada: cuánto tarda en sonar la primera
    oración frente a cuánto tarda la respuesta completa — la comparación que
    justifica sintetizar por oración en vez de esperar todo el texto."""
    def __init__(self, t_ref=None):
        self.t_inicio = time.perf_counter()
        # Referencia externa opcional (p.ej. el instante en que se soltó la
        # tecla de push-to-talk, ver rem_avatar_server._ptt_detener): el
        # tiempo que le importa al usuario cuenta desde AHÍ, no desde que
        # arrancó el turno de LLM.
        self.t_ref = t_ref
        self.t_primer_audio = None

    def marcar_primer_audio(self):
        if self.t_primer_audio is None:
            self.t_primer_audio = time.perf_counter()
            extra = f" ({self.t_primer_audio - self.t_ref:.2f}s desde la referencia externa)" if self.t_ref else ""
            log(f"primer audio enviado a los {self.t_primer_audio - self.t_inicio:.2f}s{extra}")


async def decir(texto):
    """Sintetiza una oración y la manda al avatar (enviar_audio, con fallback
    local a sounddevice si no hay cliente WS conectado). La síntesis corre en
    un hilo aparte (asyncio.to_thread): es CPU bloqueante, y en el loop
    principal frenaría también al productor (el turno de LLM consumiendo el
    siguiente chunk). Devuelve True si el audio se entregó (por WS o local),
    para que el llamador pueda medir "tiempo hasta el primer audio"."""
    log(f'hablando: "{texto}"')
    t0 = time.perf_counter()
    audio, sr, timeline, con_alineacion = await asyncio.to_thread(sintetizar, texto)
    dt = time.perf_counter() - t0
    dur = len(audio) / sr if sr else 0.0
    log(f"síntesis Piper: {dt:.3f}s para {dur:.2f}s de audio ({sr} Hz"
        f"{'' if con_alineacion else ', lipsync SIN alineación: reparto parejo'})")
    if len(audio) == 0:
        return False

    ruta = os.path.join(TMP_AUDIO_DIR, f"habla_tmp_{int(time.time() * 1000)}.wav")
    entregado = False
    try:
        sf.write(ruta, audio, sr, subtype="PCM_16")

        enviado = enviar_audio(ruta, timeline)
        if not enviado:
            log(f"esperando cliente WS conectado (máx {ESPERA_CLIENTE_S:.0f}s)...")
            t_limite = time.time() + ESPERA_CLIENTE_S
            while time.time() < t_limite and not enviado:
                await asyncio.sleep(0.3)
                enviado = enviar_audio(ruta, timeline)

        if enviado:
            log("enviado por WebSocket — el avatar reproduce por su cuenta")
            entregado = True
        else:
            log("nadie conectado al WS — reproduciendo localmente con sounddevice")
            try:
                sd.play(audio, sr)
                sd.wait()
                entregado = True
            except sd.PortAudioError as e:
                log(f"no se pudo reproducir localmente ({e}) — revisa el dispositivo de audio por defecto")
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass

    return entregado


async def worker_habla(cola):
    """Consume la cola de oraciones en orden, una por vez. Como el turno
    encola cada oración en cuanto dividir_en_oraciones() la completa (sin
    esperar el resto de la respuesta, ver chat_sesion.procesar_turno), la
    síntesis de la oración N+1 arranca apenas termina la N — mientras esa N
    ya está sonando en el frontend (enviar_audio() no espera a que termine de
    reproducirse, solo despacha). `None` en la cola es la señal de cierre.

    Cada consumidor (REPL de bench_chat.py, panel de chat de rem_chat.py vía
    rem_avatar_server.py) arma su PROPIA cola + tarea de worker_habla() — no
    comparten cola entre sí, cada turno se encola solo en la cola de quien lo
    disparó. Sí comparten la voz (_voz/_voz_lock, arriba)."""
    while True:
        item = await cola.get()
        if item is None:
            cola.task_done()
            break
        oracion, estado = item
        try:
            entregado = await decir(oracion)
            if entregado and estado is not None:
                estado.marcar_primer_audio()
        except Exception as e:
            log(f"error hablando oración: {e}")
        cola.task_done()
