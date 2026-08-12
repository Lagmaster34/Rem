#!/usr/bin/env python3
"""
test_voz.py — Linea base de voz: edge-tts CRUDO vs edge-tts + RVC

Genera la misma frase por los dos caminos, guarda ambos WAV y los
reproduce uno detras de otro para que puedas compararlos de verdad.

IMPORTANTE: ejecutar SIEMPRE con el interprete del venv.

    venv/bin/python test_voz.py

Parametros opcionales para experimentar:

    venv/bin/python test_voz.py --pitch 0
    venv/bin/python test_voz.py --pitch 2 --index 0.5
    venv/bin/python test_voz.py --texto "otra frase distinta"
    venv/bin/python test_voz.py --voz es-ES-XimenaNeural
    venv/bin/python test_voz.py --rate "+15%"
    venv/bin/python test_voz.py --no-play        # solo genera los WAV
"""

import argparse
import asyncio
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "pruebas_voz")

# Frase disenada para estresar los fonemas del espanol que NO existen
# en japones. Si el modelo RVC se entreno con audio japones, aqui es
# donde va a chirriar:
#   - rr vibrante : perro, corre, jarra
#   - jota        : Jorge, jardin
#   - s final     : buenos, dias, gracias
#   - entonacion  : la pregunta del final
TEXTO_DEFAULT = (
    "Buenos dias, amo. El perro de Jorge corre rapido por el jardin. "
    "Gracias por todo. Y dime, mi senor, "
    "¿ya desayunaste algo esta manana?"
)

VOZ = "es-MX-DaliaNeural"


def log(msg):
    print(f"  {msg}", flush=True)


def titulo(t):
    print()
    print("=" * 62)
    print(t)
    print("=" * 62)


def comprobar_entorno():
    """Aborta pronto y con un mensaje claro si algo falta."""
    titulo("COMPROBACION DE ENTORNO")
    log(f"Python    : {sys.version.split()[0]}  ({sys.executable})")

    if not sys.executable.replace("\\", "/").endswith("venv/bin/python"):
        log("")
        log("!! ADVERTENCIA: no parece el Python del venv.")
        log("!! Ejecuta:  venv/bin/python test_voz.py")
        log("")

    try:
        import numpy
        log(f"numpy     : {numpy.__version__}"
            + ("  <-- OJO, deberia ser 1.x" if numpy.__version__.startswith("2") else ""))
    except ImportError:
        log("numpy     : NO INSTALADO"); sys.exit(1)

    try:
        import torch
        log(f"torch     : {torch.__version__}   cuda={torch.cuda.is_available()}")
        if torch.cuda.is_available():
            log(f"gpu       : {torch.cuda.get_device_name(0)}")
    except ImportError:
        log("torch     : NO INSTALADO"); sys.exit(1)

    faltan = []
    for nombre, ruta in (
        ("hubert_base.pt", os.path.join(BASE, "hubert_base.pt")),
        ("rmvpe.pt",       os.path.join(BASE, "rmvpe.pt")),
        ("modelo .pth",    os.path.join(BASE, "models", "Rem_600e_6600s", "Rem_600e_6600s.pth")),
        ("Rem.index",      os.path.join(BASE, "models", "Rem_600e_6600s", "Rem.index")),
    ):
        if os.path.exists(ruta):
            mb = os.path.getsize(ruta) / 1024 / 1024
            log(f"{nombre:<14}: OK  ({mb:,.1f} MB)")
        else:
            log(f"{nombre:<14}: FALTA  -> {ruta}")
            faltan.append(nombre)

    if faltan:
        log("")
        log("Faltan archivos necesarios. Abortando.")
        sys.exit(1)


async def sintetizar_tts(texto, destino_mp3, voz, rate):
    import edge_tts
    await edge_tts.Communicate(texto, voz, rate=rate).save(destino_mp3)


def mp3_a_wav16k(origen_mp3, destino_wav):
    """Convierte a mono 16 kHz, que es lo que espera RVC."""
    import numpy as np
    import soundfile as sf

    audio, sr = sf.read(origen_mp3)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    if sr != 16000:
        try:
            import soxr
            audio = soxr.resample(audio, sr, 16000)
        except ImportError:
            from scipy import signal as sps
            audio = sps.resample(audio, int(round(len(audio) * 16000 / sr)))
        sr = 16000

    sf.write(destino_wav, audio.astype(np.float32), sr)
    return sr


def cargar_rvc(pitch, index_influence):
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


def reproducir(ruta, etiqueta):
    import soundfile as sf
    import sounddevice as sd

    data, sr = sf.read(ruta)
    dur = len(data) / sr
    log(f"[{etiqueta}]  {dur:.1f}s @ {sr} Hz  -> reproduciendo...")
    sd.play(data, sr)
    sd.wait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pitch", type=int, default=4,
                   help="semitonos de transposicion (Rem.py usa 4)")
    p.add_argument("--index", type=float, default=0.75,
                   help="index_influence, 0.0-1.0 (Rem.py usa 0.75)")
    p.add_argument("--texto", type=str, default=TEXTO_DEFAULT)
    p.add_argument("--voz", type=str, default=VOZ,
                   help="voz de edge-tts (default: es-MX-DaliaNeural)")
    p.add_argument("--rate", type=str, default="+0%",
                   help="ajuste de velocidad de edge-tts, ej. +15%%, -10%%")
    p.add_argument("--no-play", action="store_true")
    args = p.parse_args()

    comprobar_entorno()
    os.makedirs(OUT, exist_ok=True)

    voz_rate = f"{args.voz}_{args.rate}"
    sufijo = f"p{args.pitch}_i{args.index}_{voz_rate}"
    mp3       = os.path.join(OUT, f"01_crudo_{voz_rate}.mp3")
    wav_crudo = os.path.join(OUT, f"01_crudo_{voz_rate}.wav")
    wav_rvc   = os.path.join(OUT, f"02_rvc_{sufijo}.wav")

    titulo("PASO 1 — TTS (edge-tts, sin conversion)")
    log(f'texto: "{args.texto}"')
    log(f"voz={args.voz}   rate={args.rate}")
    t0 = time.perf_counter()
    asyncio.run(sintetizar_tts(args.texto, mp3, args.voz, args.rate))
    t_tts = time.perf_counter() - t0
    mp3_a_wav16k(mp3, wav_crudo)
    log(f"listo en {t_tts:.2f}s  -> {wav_crudo}")

    titulo("PASO 2 — CARGA DEL MODELO RVC")
    log(f"pitch_lvl={args.pitch}   index_influence={args.index}")
    t0 = time.perf_counter()
    try:
        rvc = cargar_rvc(args.pitch, args.index)
    except Exception as e:
        log(f"FALLO al cargar RVC: {type(e).__name__}: {e}")
        log("")
        log("El TTS crudo si se genero. Reproduciendo solo ese.")
        if not args.no_play:
            reproducir(wav_crudo, "CRUDO")
        sys.exit(1)
    log(f"modelo cargado en {time.perf_counter() - t0:.1f}s")

    titulo("PASO 3 — CONVERSION RVC")
    t0 = time.perf_counter()
    try:
        res = rvc(audio_files=[wav_crudo], type_output="wav")
    except Exception as e:
        log(f"FALLO en la conversion: {type(e).__name__}: {e}")
        sys.exit(1)
    t_rvc = time.perf_counter() - t0

    if not res:
        log("RVC no devolvio nada."); sys.exit(1)

    import shutil
    shutil.copy(res[0], wav_rvc)
    log(f"convertido en {t_rvc:.2f}s  -> {wav_rvc}")

    titulo("RESULTADOS")
    log(f"TTS        : {t_tts:.2f}s")
    log(f"RVC        : {t_rvc:.2f}s")
    log(f"TOTAL      : {t_tts + t_rvc:.2f}s")
    log("")
    log(f"WAV crudo  : {wav_crudo}")
    log(f"WAV con RVC: {wav_rvc}")

    if args.no_play:
        return

    titulo("ESCUCHA COMPARATIVA")
    log("Primero el crudo, luego el convertido. Presta atencion a:")
    log("  - 'perro' y 'corre'   (rr vibrante)")
    log("  - 'Jorge' y 'jardin'  (jota)")
    log("  - 'buenos', 'gracias' (s final)")
    log("  - la pregunta final   (entonacion)")
    print()
    reproducir(wav_crudo, "1/2 CRUDO")
    time.sleep(0.8)
    reproducir(wav_rvc, "2/2 CON RVC")
    print()


if __name__ == "__main__":
    main()
