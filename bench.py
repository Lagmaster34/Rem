#!/usr/bin/env python3
"""bench.py — Prueba del lipsync real (fonemas -> visemes) sin Groq ni el chat.

Lanza el servidor del avatar (HTTP :18765, WS :18766, overlay GTK) y reproduce
una frase fija por el pipeline completo: edge-tts con timings -> RVC -> enviar_audio().
No importa Rem.py (arranca la GUI Tkinter, el cliente Groq y app.mainloop() a nivel
de módulo) — es autocontenido, reusa solo lipsync.py y rem_avatar_server.py.

    venv/bin/python bench.py
    venv/bin/python bench.py --texto "otra frase para probar"
    venv/bin/python bench.py --no-rvc          # más rápido, sin conversión de voz
"""

import argparse
import asyncio
import os
import sys
import time

import numpy as np
import soundfile as sf
import sounddevice as sd
from scipy import signal as sps

import lipsync
from rem_avatar_server import iniciar_avatar, cerrar_avatar, enviar_audio

BASE = os.path.dirname(os.path.abspath(__file__))

TEXTO_DEFAULT = "Hola, amo. Bienvenido de nuevo. ¿En qué puedo ayudarte hoy?"
VOZ = "es-MX-DaliaNeural"

ESPERA_CLIENTE_S = 8.0  # tiempo máximo para que el overlay conecte por WS


def log(msg):
    print(f"  {msg}", flush=True)


def titulo(t):
    print()
    print("=" * 62)
    print(t)
    print("=" * 62)


def cargar_rvc(pitch=4, index_influence=0.75):
    from infer_rvc_python import BaseLoader
    rmvpe = os.path.join(BASE, "rmvpe.pt")
    rvc = BaseLoader(only_cpu=False, rmvpe_path=rmvpe)
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
    return rvc


async def main_async(args):
    titulo("PASO 1 — TTS + timings (lipsync.sintetizar_con_timings)")
    log(f'texto: "{args.texto}"')
    audio_mp3, palabras = await lipsync.sintetizar_con_timings(args.texto, VOZ)
    timeline = lipsync.construir_timeline(palabras)
    log(f"{len(palabras)} palabras, {len(timeline)} eventos de viseme")

    tmp_mp3 = os.path.join(BASE, "bench_tmp.mp3")
    tmp_wav = os.path.join(BASE, "bench_tmp.wav")
    with open(tmp_mp3, "wb") as f:
        f.write(audio_mp3)

    audio, sr_ = sf.read(tmp_mp3)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr_ != 16000:
        audio = sps.resample(audio, int(round(len(audio) * 16000 / sr_)))
        sr_ = 16000
    sf.write(tmp_wav, audio.astype(np.float32), sr_)

    ruta_final = tmp_wav
    if not args.no_rvc:
        titulo("PASO 2 — CONVERSIÓN RVC")
        t0 = time.perf_counter()
        rvc = cargar_rvc()
        log(f"RVC cargado en {time.perf_counter() - t0:.1f}s")
        resultados = rvc(audio_files=[tmp_wav], type_output="wav")
        if resultados:
            ruta_final = resultados[0]
        log(f"convertido -> {ruta_final}")
    else:
        titulo("PASO 2 — CONVERSIÓN RVC (saltada, --no-rvc)")

    titulo("PASO 3 — ENVÍO AL AVATAR")
    log(f"esperando cliente WS conectado (máx {ESPERA_CLIENTE_S:.0f}s)...")
    enviado = False
    t_limite = time.time() + ESPERA_CLIENTE_S
    while time.time() < t_limite:
        if enviar_audio(ruta_final, timeline):
            enviado = True
            break
        time.sleep(0.3)

    if enviado:
        log("audio + timeline enviados por WebSocket — mirá el overlay")
        dur = timeline[-1]["t"] if timeline else 0
        time.sleep(dur + 1.0)
    else:
        log("nadie conectado al WS — reproduciendo localmente con sounddevice")
        data, sr2 = sf.read(ruta_final)
        try:
            sd.play(data, sr2)
            sd.wait()
        except sd.PortAudioError as e:
            log(f"no se pudo reproducir localmente ({e}) — revisa el dispositivo de audio por defecto")

    for tmp in (tmp_mp3, tmp_wav):
        try:
            os.remove(tmp)
        except OSError:
            pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--texto", type=str, default=TEXTO_DEFAULT)
    p.add_argument("--no-rvc", action="store_true", help="saltar la conversión RVC (más rápido)")
    args = p.parse_args()

    if not sys.executable.replace("\\", "/").endswith("venv/bin/python"):
        log("ADVERTENCIA: ejecuta con venv/bin/python bench.py")

    titulo("INICIANDO AVATAR (HTTP :18765, WS :18766, overlay GTK)")
    iniciar_avatar()

    try:
        asyncio.run(main_async(args))
    finally:
        titulo("CERRANDO")
        cerrar_avatar()


if __name__ == "__main__":
    main()
