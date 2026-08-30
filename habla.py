"""habla.py — síntesis de voz para un turno de conversación: TTS (edge-tts,
vía lipsync.py) -> RVC (conversión al timbre de Rem) -> enviar_audio() (al
avatar por WebSocket, con fallback local a sounddevice si no hay ningún
cliente conectado).

Extraído de bench_chat.py (donde vivía todo esto originalmente, atado al
REPL) para que rem_avatar_server.py también pueda usarlo — el panel de chat
de rem_chat.py habla las respuestas igual que el REPL, con el mismo pipeline,
sin duplicar la carga de RVC (costosa, GPU) ni el código de síntesis. Mismo
motivo que chat_sesion.py para SesionChat/procesar_turno(): un solo lugar
para lo que antes vivía nada más en el REPL.

_rvc_cache/_rvc_lock son MÓDULO-LEVEL (una sola vez por proceso) — el REPL de
bench_chat.py y el panel de chat de rem_chat.py tienen cada uno su propia
cola/worker (ver worker_habla() y CLAUDE.md, "Voz en la ventana de chat"),
pero ambos comparten esta MISMA instancia de RVC y el mismo lock: no tiene
sentido cargar el modelo dos veces, y el lock ya existía para serializar la
carga y las conversiones entre sí (ver el comentario de _rvc_lock más abajo)
— ahora también serializa entre el worker del REPL y el del panel si los dos
llegan a convertir audio al mismo tiempo.
"""
import asyncio
import os
import threading
import time

import numpy as np
import soundfile as sf
import sounddevice as sd
from scipy import signal as sps

import config
import lipsync
from rem_avatar_server import TMP_AUDIO_DIR, enviar_audio

BASE = os.path.dirname(os.path.abspath(__file__))

ESPERA_CLIENTE_S = 8.0  # tiempo máximo para que un cliente WS conecte antes del fallback local

_rvc_cache = None
# Protege tanto la carga de RVC (_obtener_rvc) como cada conversión
# (generate_from_cache): BaseLoader no es thread-safe entre llamadas
# concurrentes — self.cache_model/self.model_vc/self.model_pitch_estimator se
# leen y escriben sin lock propio, así que dos conversiones a la vez (p.ej.
# el hilo de precarga y un turno con voz llegando antes de que termine, o el
# worker del REPL y el del panel de chat al mismo tiempo) pueden verse ambas
# con el cache todavía vacío y recargar el .pth y el rmvpe por duplicado —
# visto en vivo antes de agregar este lock.
_rvc_lock = threading.Lock()


def log(msg):
    print(f"  {msg}", flush=True)


def cargar_rvc(pitch=4, index_influence=0.75):
    from infer_rvc_python import BaseLoader
    dispositivo = config.leer_dispositivo_rvc()
    rmvpe = os.path.join(BASE, "rmvpe.pt")
    rvc = BaseLoader(only_cpu=(dispositivo == "cpu"), rmvpe_path=rmvpe)
    rvc.apply_conf(
        tag="rem",
        file_model=os.path.join(BASE, "models", "Rem_600e_6600s", "Rem_600e_6600s.pth"),
        pitch_algo="rmvpe",
        pitch_lvl=pitch,
        file_index=os.path.join(BASE, "models", "Rem_600e_6600s", "Rem.index"),
        index_influence=index_influence,
        respiration_median_filtering=3,
        envelope_ratio=0.25,
        consonant_breath_protection=0.33,
        resample_sr=0,
    )
    return rvc, dispositivo


def _obtener_rvc():
    """Carga RVC si hace falta y devuelve la instancia cacheada. Con lock
    porque hay varios llamadores concurrentes posibles: el hilo de precarga
    (precargar_rvc(), lanzado al arrancar) y cualquier worker_habla() (REPL o
    panel de chat) si el usuario llega a pedir voz antes de que la precarga
    termine — sin el lock, más de uno podría ver _rvc_cache en None a la vez
    y cargar el modelo por duplicado."""
    global _rvc_cache
    with _rvc_lock:
        if _rvc_cache is None:
            log("cargando RVC...")
            t0 = time.perf_counter()
            _rvc_cache = cargar_rvc()
            rvc, dispositivo = _rvc_cache
            log(f"RVC listo en {time.perf_counter() - t0:.1f}s ({dispositivo})")
        return _rvc_cache


def _convertir_rvc(rvc, tmp_wav):
    """generate_from_cache() bajo el mismo lock que _obtener_rvc() — ver el
    comentario de _rvc_lock más arriba sobre por qué hace falta serializar
    también las conversiones, no solo la carga inicial."""
    with _rvc_lock:
        return rvc.generate_from_cache(audio_data=tmp_wav, tag="rem")


def _preparar_wav_16k(audio_mp3, tmp_mp3, tmp_wav):
    """mp3 de edge-tts -> wav mono 16kHz, el formato que espera RVC. Comparte
    esta conversión decir() (una oración real) y precargar_rvc() (la oración
    de calentamiento) para no duplicarla."""
    with open(tmp_mp3, "wb") as f:
        f.write(audio_mp3)
    audio, sr_ = sf.read(tmp_mp3)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr_ != 16000:
        audio = sps.resample(audio, int(round(len(audio) * 16000 / sr_)))
        sr_ = 16000
    sf.write(tmp_wav, audio.astype(np.float32), sr_)


def precargar_rvc():
    """Carga RVC y lo deja "caliente" con una conversión de calentamiento
    descartada, en un hilo de fondo lanzado al arrancar (ver bench_chat.py y
    rem_chat.py main()) — para que el primer turno con voz no pague ni la
    carga del modelo (~4-6s) ni el costo extra de la primera conversión en
    frío (kernels CUDA sin compilar/cachear todavía). Todo lo que toca
    (log/print, nada de estado compartido con el llamador) es seguro de
    llamar desde un hilo aparte."""
    tmp_mp3 = os.path.join(TMP_AUDIO_DIR, "_precarga_rvc.mp3")
    tmp_wav = os.path.join(TMP_AUDIO_DIR, "_precarga_rvc.wav")
    try:
        rvc, dispositivo = _obtener_rvc()
        t0 = time.perf_counter()
        audio_mp3, _ = asyncio.run(lipsync.sintetizar_con_timings("Hola."))
        _preparar_wav_16k(audio_mp3, tmp_mp3, tmp_wav)
        _convertir_rvc(rvc, tmp_wav)
        log(f"calentamiento RVC listo en {time.perf_counter() - t0:.2f}s ({dispositivo}) — RVC caliente para el primer turno")
    except Exception as e:
        log(f"precarga de RVC falló, no bloqueante ({e})")
    finally:
        for tmp in (tmp_mp3, tmp_wav):
            try:
                os.remove(tmp)
            except OSError:
                pass


class TurnoHabla:
    """Timing de un turno con voz activada: cuánto tarda en sonar la primera
    oración frente a cuánto tarda la respuesta completa — la comparación que
    justifica solapar TTS+RVC con la generación en vez de esperar todo el
    texto antes de hablar."""
    def __init__(self):
        self.t_inicio = time.perf_counter()
        self.t_primer_audio = None

    def marcar_primer_audio(self):
        if self.t_primer_audio is None:
            self.t_primer_audio = time.perf_counter()
            log(f"primer audio enviado a los {self.t_primer_audio - self.t_inicio:.2f}s")


async def decir(texto, usar_rvc):
    """Sintetiza una oración y la manda al avatar (lipsync -> RVC opcional ->
    enviar_audio, con fallback local a sounddevice si no hay cliente WS
    conectado). La conversión RVC corre en un hilo aparte (asyncio.to_thread):
    es una llamada bloqueante, y si corriera en el loop principal frenaría
    también al productor (el turno de LLM consumiendo el siguiente chunk) —
    justo lo que se quiere solapar. Devuelve True si el audio se entregó (por
    WS o local), para que el llamador pueda medir "tiempo hasta el primer
    audio"."""
    log(f'hablando: "{texto}"')
    audio_mp3, palabras = await lipsync.sintetizar_con_timings(texto)
    timeline = lipsync.construir_timeline(palabras)

    uid = int(time.time() * 1000)
    tmp_mp3 = os.path.join(TMP_AUDIO_DIR, f"habla_tmp_{uid}.mp3")
    tmp_wav = os.path.join(TMP_AUDIO_DIR, f"habla_tmp_{uid}.wav")
    tmp_wav_rvc = os.path.join(TMP_AUDIO_DIR, f"habla_tmp_{uid}_rvc.wav")
    ruta_final = tmp_wav
    entregado = False

    try:
        _preparar_wav_16k(audio_mp3, tmp_mp3, tmp_wav)

        if usar_rvc:
            rvc, dispositivo = _obtener_rvc()
            t_rvc = time.perf_counter()
            try:
                # generate_from_cache() reusa net_g/index/pipe ya cargados en
                # la instancia (self.model_vc) en vez de releer el .pth y el
                # .index de disco en cada llamada, como sí hace __call__ (ver
                # CLAUDE.md, "Precarga de RVC y fin de la recarga del .pth en cada frase"). Además corre
                # infer() en el hilo actual (el de asyncio.to_thread), no en
                # un hilo interno que __call__ solo joinea sin propagar sus
                # excepciones — así que un fallo real de RVC (p.ej. un OOM de
                # CUDA) llega acá como excepción, en vez de volver una lista
                # vacía en silencio.
                audio_opt, sr_rvc = await asyncio.to_thread(_convertir_rvc, rvc, tmp_wav)
                sf.write(tmp_wav_rvc, audio_opt, sr_rvc)
                ruta_final = tmp_wav_rvc
                log(f"conversión RVC ({dispositivo}): {time.perf_counter() - t_rvc:.2f}s")
            except Exception as e:
                log(f"RVC falló ({e}) — hablando sin convertir (voz cruda de edge-tts)")

        enviado = enviar_audio(ruta_final, timeline)
        if not enviado:
            log(f"esperando cliente WS conectado (máx {ESPERA_CLIENTE_S:.0f}s)...")
            t_limite = time.time() + ESPERA_CLIENTE_S
            while time.time() < t_limite and not enviado:
                await asyncio.sleep(0.3)
                enviado = enviar_audio(ruta_final, timeline)

        if enviado:
            log("enviado por WebSocket — el avatar reproduce por su cuenta")
            entregado = True
        else:
            log("nadie conectado al WS — reproduciendo localmente con sounddevice")
            data, sr2 = sf.read(ruta_final)
            try:
                sd.play(data, sr2)
                sd.wait()
                entregado = True
            except sd.PortAudioError as e:
                log(f"no se pudo reproducir localmente ({e}) — revisa el dispositivo de audio por defecto")
    finally:
        for tmp in {tmp_mp3, tmp_wav, tmp_wav_rvc}:
            try:
                os.remove(tmp)
            except OSError:
                pass

    return entregado


async def worker_habla(cola, usar_rvc):
    """Consume la cola de oraciones en orden, una por vez. Como el turno
    encola cada oración en cuanto dividir_en_oraciones() la completa (sin
    esperar el resto de la respuesta, ver chat_sesion.procesar_turno), la
    conversión de la oración N+1 arranca apenas termina la N — mientras esa N
    ya está sonando en el frontend (enviar_audio() no espera a que termine de
    reproducirse, solo despacha). `None` en la cola es la señal de cierre.

    Cada consumidor (REPL de bench_chat.py, panel de chat de rem_chat.py vía
    rem_avatar_server.py) arma su PROPIA cola + tarea de worker_habla() — no
    comparten cola entre sí, cada turno se encola solo en la cola de quien lo
    disparó. Sí comparten el RVC de abajo (_rvc_cache/_rvc_lock, arriba)."""
    while True:
        item = await cola.get()
        if item is None:
            cola.task_done()
            break
        oracion, estado = item
        try:
            entregado = await decir(oracion, usar_rvc)
            if entregado and estado is not None:
                estado.marcar_primer_audio()
        except Exception as e:
            log(f"error hablando oración: {e}")
        cola.task_done()
