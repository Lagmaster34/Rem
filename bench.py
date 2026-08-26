#!/usr/bin/env python3
"""bench.py — REPL para probar el lipsync real (fonemas -> visemes) sin Groq ni el chat.

Lanza el servidor del avatar (HTTP :18765, WS :18766, overlay GTK) UNA vez y lo
mantiene vivo mientras escribís comandos. No importa Rem.py (arranca la GUI
Tkinter y app.mainloop() a nivel de módulo, y en este venv ni siquiera podría:
el Python 3.10.14 se compiló sin _tkinter) — es autocontenido, reusa solo
config.py, lipsync.py y rem_avatar_server.py.

    venv/bin/python bench.py
    venv/bin/python bench.py --no-rvc      # 'say' más rápido, sin conversión de voz
    venv/bin/python bench.py --open        # abre el navegador automáticamente al arrancar

Comandos dentro del REPL:
    say <texto>       — sintetiza, convierte con RVC y envía al avatar
    state <estado>    — manda ese estado (idle/talking/thinking/happy/sad/angry/surprised)
    open               — abre http://localhost:18765/rem_avatar.html en el navegador por defecto
    quit               — cierra limpiamente (o Ctrl+D / Ctrl+C)
"""

import argparse
import asyncio
import os
import sys
import time
import urllib.error
import urllib.request
import webbrowser

import numpy as np
import soundfile as sf
import sounddevice as sd
from scipy import signal as sps

import config
import lipsync
from rem_avatar_server import (
    HTTP_PORT, TMP_AUDIO_DIR, iniciar_avatar, cerrar_avatar, enviar_audio,
    enviar_estado, ESTADOS_VALIDOS,
)

BASE = os.path.dirname(os.path.abspath(__file__))
URL_AVATAR = f"http://localhost:{HTTP_PORT}/rem_avatar.html"

ESPERA_CLIENTE_S = 8.0  # tiempo máximo para que un cliente WS conecte antes del fallback local
ESPERA_HTTP_S = 5.0     # tiempo máximo para que el servidor HTTP responda antes de --open

_rvc_cache = None  # se carga una sola vez, en el primer 'say' que la necesite


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
    global _rvc_cache
    if _rvc_cache is None:
        log("cargando RVC (una sola vez, se reusa en los siguientes 'say')...")
        t0 = time.perf_counter()
        _rvc_cache = cargar_rvc()
        rvc, dispositivo = _rvc_cache
        log(f"RVC listo en {time.perf_counter() - t0:.1f}s ({dispositivo})")
    return _rvc_cache


async def _decir(texto, usar_rvc):
    log(f'texto: "{texto}"')
    audio_mp3, palabras = await lipsync.sintetizar_con_timings(texto)
    timeline = lipsync.construir_timeline(palabras)
    log(f"{len(palabras)} palabras, {len(timeline)} eventos de viseme")

    # Temporales en tmp_audio/ (no en la raíz del proyecto) — RVC escribe su
    # salida "<tmp_wav>_edited.wav" junto a la entrada, así que también cae ahí.
    uid = int(time.time() * 1000)
    tmp_mp3 = os.path.join(TMP_AUDIO_DIR, f"bench_tmp_{uid}.mp3")
    tmp_wav = os.path.join(TMP_AUDIO_DIR, f"bench_tmp_{uid}.wav")
    ruta_final = tmp_wav

    try:
        with open(tmp_mp3, "wb") as f:
            f.write(audio_mp3)

        audio, sr_ = sf.read(tmp_mp3)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr_ != 16000:
            audio = sps.resample(audio, int(round(len(audio) * 16000 / sr_)))
            sr_ = 16000
        sf.write(tmp_wav, audio.astype(np.float32), sr_)

        if usar_rvc:
            rvc, dispositivo = _obtener_rvc()
            t_rvc = time.perf_counter()
            resultados = await asyncio.to_thread(rvc, audio_files=[tmp_wav], type_output="wav")
            log(f"conversión RVC ({dispositivo}): {time.perf_counter() - t_rvc:.2f}s")
            if resultados:
                ruta_final = resultados[0]

        enviado = enviar_audio(ruta_final, timeline)
        if not enviado:
            log(f"esperando cliente WS conectado (máx {ESPERA_CLIENTE_S:.0f}s)...")
            t_limite = time.time() + ESPERA_CLIENTE_S
            while time.time() < t_limite and not enviado:
                time.sleep(0.3)
                enviado = enviar_audio(ruta_final, timeline)

        if enviado:
            log("enviado por WebSocket — el avatar reproduce por su cuenta, seguí escribiendo")
        else:
            log("nadie conectado al WS — reproduciendo localmente con sounddevice")
            data, sr2 = sf.read(ruta_final)
            try:
                sd.play(data, sr2)
                sd.wait()
            except sd.PortAudioError as e:
                log(f"no se pudo reproducir localmente ({e}) — revisa el dispositivo de audio por defecto")
    finally:
        for tmp in {tmp_mp3, tmp_wav, ruta_final}:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _esperar_http(timeout=ESPERA_HTTP_S):
    """Sondea el servidor HTTP hasta que responda o se acabe el tiempo. Devuelve
    True si respondió."""
    t_limite = time.time() + timeout
    while time.time() < t_limite:
        try:
            urllib.request.urlopen(URL_AVATAR, timeout=1.0)
            return True
        except urllib.error.URLError:
            time.sleep(0.2)
    return False


def _abrir_navegador():
    if not _esperar_http():
        log(f"el servidor HTTP no respondió a tiempo — igual intento abrir {URL_AVATAR}")
    webbrowser.open(URL_AVATAR)
    log(f"abriendo {URL_AVATAR} en el navegador por defecto")


def _imprimir_ayuda():
    print()
    print(f"  Abrí {URL_AVATAR} en un navegador normal")
    print("  para ver el avatar sin depender del overlay GTK (o usá el comando 'open').")
    print()
    print("  Comandos:")
    print("    say <texto>       — sintetiza, convierte con RVC y envía al avatar")
    print(f"    state <estado>    — manda ese estado ({'/'.join(sorted(ESTADOS_VALIDOS))})")
    print("    open               — abre el avatar en el navegador por defecto")
    print("    quit               — cierra limpiamente (o Ctrl+D / Ctrl+C)")
    print()


def repl(args):
    _imprimir_ayuda()
    while True:
        try:
            linea = input("bench> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not linea:
            continue

        comando, _, resto = linea.partition(" ")
        comando = comando.lower()
        resto = resto.strip()

        if comando == "quit":
            break

        elif comando == "say":
            if not resto:
                log("uso: say <texto>")
                continue
            try:
                asyncio.run(_decir(resto, usar_rvc=not args.no_rvc))
            except Exception as e:
                log(f"error: {e}")

        elif comando == "state":
            estado = resto.lower()
            if estado not in ESTADOS_VALIDOS:
                log(f"estado inválido. usar uno de: {', '.join(sorted(ESTADOS_VALIDOS))}")
                continue
            enviar_estado(estado)
            log(f"estado -> {estado}")

        elif comando == "open":
            _abrir_navegador()

        else:
            log(f"comando desconocido: {comando!r} (usa say / state / quit)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-rvc", action="store_true", help="'say' salta la conversión RVC (más rápido)")
    p.add_argument("--open", action="store_true", help="abre el navegador automáticamente al arrancar")
    args = p.parse_args()

    if not sys.executable.replace("\\", "/").endswith("venv/bin/python"):
        log("ADVERTENCIA: ejecuta con venv/bin/python bench.py")

    config.cargar_dotenv()

    print("Iniciando avatar (HTTP :18765, WS :18766, overlay GTK)...")
    iniciar_avatar()

    if args.open:
        _abrir_navegador()

    try:
        repl(args)
    finally:
        print()
        print("Cerrando...")
        cerrar_avatar()


if __name__ == "__main__":
    main()
