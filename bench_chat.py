#!/usr/bin/env python3
"""bench_chat.py — REPL async nativo para la capa LLM (llm/), sin Tkinter ni GUI.

En la línea de bench.py (banco de pruebas del lipsync/RVC/avatar sin el chat),
pero para el otro extremo: probar stream_chat() de verdad, sin Rem.py. No lo
importa (no se puede: el Python 3.10.14 del venv se compiló sin _tkinter, y
Tkinter va a desaparecer del proyecto de todos modos) — es autocontenido,
reusa lipsync.py y rem_avatar_server.py igual que bench.py.

Es el precursor del backend que va a reemplazar a Tkinter: consume
provider.stream_chat() directo con `async for`, sin el puente sync->async de
_drenar_stream_llm() en Rem.py (ese puente existe solo porque responder() hoy
corre en un hilo nuevo por turno — acá no hace falta, todo el REPL vive en un
único asyncio.run()).

    venv/bin/python bench_chat.py
    venv/bin/python bench_chat.py --no-rvc      # 'voz' sin conversión RVC
    venv/bin/python bench_chat.py --open        # abre el navegador al arrancar

Comandos dentro del REPL:
    chat <texto>       — manda <texto> al LLM, imprime la respuesta en streaming
    voz on|off          — activa/desactiva hablar la respuesta (lipsync+RVC+avatar)
    reset                — limpia el historial de la conversación
    quit                 — cierra limpiamente (o Ctrl+D / Ctrl+C)
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

import lipsync
from llm import Done, Message, TextDelta, ToolCallChunk, get_provider
from rem_avatar_server import (
    HTTP_PORT, TMP_AUDIO_DIR, iniciar_avatar, cerrar_avatar, enviar_audio,
)

BASE = os.path.dirname(os.path.abspath(__file__))
URL_AVATAR = f"http://localhost:{HTTP_PORT}/rem_avatar.html"

ESPERA_CLIENTE_S = 8.0  # tiempo máximo para que un cliente WS conecte antes del fallback local
ESPERA_HTTP_S = 5.0     # tiempo máximo para que el servidor HTTP responda antes de --open

# Prompt mínimo de prueba: NO es el system prompt de Rem.py (personalidad +
# reglas + catálogo de acciones + memoria) — reproducir eso acá está fuera de
# alcance, este script solo prueba la capa LLM en sí.
SYSTEM_PROMPT = (
    "Sos Rem, una asistente de IA con la personalidad de Rem de Re:Zero: cálida, "
    "leal y un poco tímida. Respondé de forma natural y breve, en español."
)

_rvc_cache = None


def log(msg):
    print(f"  {msg}", flush=True)


def _cargar_dotenv():
    """Copia mínima de la de Rem.py: bench_chat.py es autocontenido y no pasa
    por Rem.py, así que GROQ_API_KEY no llega al entorno solo por tener el
    .env en la carpeta si no se cargó a mano antes."""
    ruta = os.path.join(BASE, ".env")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


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


def _obtener_rvc():
    global _rvc_cache
    if _rvc_cache is None:
        log("cargando RVC (una sola vez, se reusa en las siguientes respuestas)...")
        t0 = time.perf_counter()
        _rvc_cache = cargar_rvc()
        log(f"RVC listo en {time.perf_counter() - t0:.1f}s")
    return _rvc_cache


async def _decir(texto, usar_rvc):
    """Sintetiza la respuesta del LLM y la manda al avatar — mismo pipeline que
    bench.py (lipsync -> RVC opcional -> enviar_audio, con fallback local a
    sounddevice si no hay cliente WS conectado), reusado tal cual."""
    log(f'hablando: "{texto}"')
    audio_mp3, palabras = await lipsync.sintetizar_con_timings(texto)
    timeline = lipsync.construir_timeline(palabras)

    uid = int(time.time() * 1000)
    tmp_mp3 = os.path.join(TMP_AUDIO_DIR, f"bench_chat_tmp_{uid}.mp3")
    tmp_wav = os.path.join(TMP_AUDIO_DIR, f"bench_chat_tmp_{uid}.wav")
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
            rvc = _obtener_rvc()
            resultados = rvc(audio_files=[tmp_wav], type_output="wav")
            if resultados:
                ruta_final = resultados[0]

        enviado = enviar_audio(ruta_final, timeline)
        if not enviado:
            log(f"esperando cliente WS conectado (máx {ESPERA_CLIENTE_S:.0f}s)...")
            t_limite = time.time() + ESPERA_CLIENTE_S
            while time.time() < t_limite and not enviado:
                await asyncio.sleep(0.3)
                enviado = enviar_audio(ruta_final, timeline)

        if enviado:
            log("enviado por WebSocket — el avatar reproduce por su cuenta")
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


async def _chat(historial, texto, provider):
    """Manda `texto` al LLM vía stream_chat() y lo consume directo con
    `async for` — sin puente sync->async, ese es justo el punto de este
    script. Imprime TextDelta a medida que llegan, muestra las ToolCall que
    aparezcan y el Done final con el uso de tokens."""
    historial.append(Message(role="user", content=texto))

    print("Rem> ", end="", flush=True)
    partes = []
    async for chunk in provider.stream_chat(SYSTEM_PROMPT, historial):
        if isinstance(chunk, TextDelta):
            print(chunk.text, end="", flush=True)
            partes.append(chunk.text)
        elif isinstance(chunk, ToolCallChunk):
            print(f"\n  [tool_call] {chunk.call.name}({chunk.call.arguments}) id={chunk.call.id}")
        elif isinstance(chunk, Done):
            print()
            print(f"  [done] reason={chunk.reason} usage={chunk.usage}")

    texto_completo = "".join(partes)
    historial.append(Message(role="assistant", content=texto_completo))
    return texto_completo


def _imprimir_ayuda():
    print()
    print(f"  Abrí {URL_AVATAR} en un navegador normal para ver el avatar (o usá 'open' si lo agregás).")
    print()
    print("  Comandos:")
    print("    chat <texto>       — manda <texto> al LLM, respuesta en streaming")
    print("    voz on|off          — activa/desactiva hablar la respuesta (lipsync+RVC+avatar)")
    print("    reset                — limpia el historial de la conversación")
    print("    quit                 — cierra limpiamente (o Ctrl+D / Ctrl+C)")
    print()


async def repl(args):
    _imprimir_ayuda()
    provider = get_provider()
    historial: list[Message] = []
    voz_activa = False
    loop = asyncio.get_running_loop()

    while True:
        try:
            linea = (await loop.run_in_executor(None, input, "bench_chat> ")).strip()
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

        elif comando == "chat":
            if not resto:
                log("uso: chat <texto>")
                continue
            try:
                respuesta = await _chat(historial, resto, provider)
                if voz_activa and respuesta.strip():
                    await _decir(respuesta, usar_rvc=not args.no_rvc)
            except Exception as e:
                log(f"error: {e}")

        elif comando == "voz":
            estado = resto.lower()
            if estado not in ("on", "off"):
                log("uso: voz on|off")
                continue
            voz_activa = (estado == "on")
            log(f"voz -> {'activada' if voz_activa else 'desactivada'}")

        elif comando == "reset":
            historial.clear()
            log("historial limpiado")

        else:
            log(f"comando desconocido: {comando!r} (usa chat / voz / reset / quit)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-rvc", action="store_true", help="'voz' salta la conversión RVC (más rápido)")
    p.add_argument("--open", action="store_true", help="abre el navegador automáticamente al arrancar")
    args = p.parse_args()

    if not sys.executable.replace("\\", "/").endswith("venv/bin/python"):
        log("ADVERTENCIA: ejecuta con venv/bin/python bench_chat.py")

    _cargar_dotenv()

    print("Iniciando avatar (HTTP :18765, WS :18766, overlay GTK)...")
    iniciar_avatar()

    if args.open:
        _abrir_navegador()

    try:
        asyncio.run(repl(args))
    finally:
        print()
        print("Cerrando...")
        cerrar_avatar()


if __name__ == "__main__":
    main()
