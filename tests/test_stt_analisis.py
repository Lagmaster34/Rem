"""Pruebas de stt/analisis.py con señales sintéticas (sin micrófono ni Whisper).

    venv/bin/python tests/test_stt_analisis.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stt.analisis import ConfigVoz, FinDeFrase, es_inventada, veredicto  # noqa: E402

SR = 16000
RNG = np.random.default_rng(7)
CFG = ConfigVoz(frases_inventadas=["Gracias.", "Subtítulos realizados por la comunidad de Amara.org"])


def ruido(s, dbfs):
    return (RNG.standard_normal(int(s * SR)) * 10 ** (dbfs / 20)).astype(np.float32)


def voz(s, dbfs, pausas=()):
    """Algo con forma de habla: tono con armónicos y sílabas a ~4 Hz (la
    envolvente no baja de 0,35, como la voz real entre sílabas). `pausas` =
    [(desde, hasta)] en s con silencio dentro."""
    t = np.arange(int(s * SR)) / SR
    tono = sum(np.sin(2 * np.pi * f * t) / k for k, f in enumerate((180, 360, 540, 720), 1))
    env = 0.35 + 0.65 * np.abs(np.sin(2 * np.pi * 2 * t))
    x = tono * env
    x *= 10 ** (dbfs / 20) / np.sqrt(np.mean(x * x))
    for a, b in pausas:
        x[int(a * SR):int(b * SR)] = 0
    return x.astype(np.float32)


def detectar(audio, espera=None, bloque_s=0.05):
    d = FinDeFrase(SR, CFG, espera_voz_s=espera)
    n = int(bloque_s * SR)
    for i in range(0, len(audio), n):
        r = d.alimentar(audio[i:i + n])
        if r:
            return r, d.t, d
    return None, d.t, d


fallos = 0


def comprobar(nombre, ok, detalle=""):
    global fallos
    print(f"{'ok ' if ok else 'MAL'} {nombre}{f' — {detalle}' if detalle else ''}")
    if not ok:
        fallos += 1


# Veredictos
v = veredicto(np.zeros(int(1.0 * SR), np.float32), SR, CFG)
comprobar("silencio digital corto -> silencio", v.tipo == "silencio", v.resumen())
v = veredicto(np.zeros(int(2.0 * SR), np.float32), SR, CFG)
comprobar("silencio digital largo -> muerto", v.tipo == "muerto", v.resumen())
v = veredicto(ruido(3, -55), SR, CFG)
comprobar("solo ruido de fondo -> sin_voz", v.tipo == "sin_voz", v.resumen())
v = veredicto(np.concatenate([ruido(0.8, -55), voz(1.5, -25) + ruido(1.5, -55), ruido(1, -55)]), SR, CFG)
comprobar("ruido + voz + ruido -> enviar", v.tipo == "enviar" and v.voz_ms > 1000, v.resumen())

# Fin de frase en vivo
audio = np.concatenate([ruido(0.8, -55), voz(1.5, -25) + ruido(1.5, -55), ruido(2, -55)])
r, t, d = detectar(audio)
comprobar("fin tras 1 s de silencio", r == "fin" and abs(t - (0.8 + 1.5 + 1.0)) <= 0.08, f"{r} a {t:.2f}s")

audio = np.concatenate([voz(1.2, -25) + ruido(1.2, -55), ruido(2, -55)])
r, t, _ = detectar(audio)
comprobar("hablando desde el primer instante", r == "fin" and abs(t - 2.2) <= 0.08, f"{r} a {t:.2f}s")

audio = np.concatenate([ruido(0.5, -55), voz(3, -25, pausas=[(1.0, 1.4), (2.0, 2.5)]) + ruido(3, -55), ruido(2, -55)])
r, t, _ = detectar(audio)
comprobar("pausas de 0,4-0,5 s no cortan la frase", r == "fin" and abs(t - 4.5) <= 0.08, f"{r} a {t:.2f}s")

# Cuarto ruidoso: el ruido (-28 dBFS) ya pasa del viejo umbral fijo de 0,028 RMS
# (-31 dBFS), que nunca daría la frase por terminada. Con el piso adaptativo sí.
audio = np.concatenate([ruido(0.8, -28), voz(1.5, -10) + ruido(1.5, -28), ruido(2, -28)])
r, t, _ = detectar(audio)
comprobar("cuarto ruidoso (-28 dBFS) con umbral adaptativo", r == "fin" and abs(t - 3.3) <= 0.08, f"{r} a {t:.2f}s")
fijo = 20 * np.log10(0.028)
comprobar("…donde el umbral fijo 0,028 RMS no serviría", -28 > fijo, f"ruido -28 dBFS > {fijo:.1f} dBFS")

r, t, _ = detectar(np.zeros(int(6 * SR), np.float32))
comprobar("micrófono muerto en vivo a los 4 s", r == "muerto" and abs(t - 4.0) <= 0.06, f"{r} a {t:.2f}s")

r, t, _ = detectar(ruido(5, -55), espera=3.0)
comprobar("modo conversación: nadie habla en 3 s -> espera", r == "espera" and abs(t - 3.0) <= 0.06, f"{r} a {t:.2f}s")

r, t, _ = detectar(np.concatenate([ruido(0.5, -55), voz(17, -25) + ruido(17, -55)]))
comprobar("tope a los 15 s de voz", r == "tope" and abs(t - 15.5) <= 0.08, f"{r} a {t:.2f}s")

# Frases inventadas
comprobar("«Gracias.» con 60 ms de voz es inventada", es_inventada("Gracias.", 60, CFG))
comprobar("«gracias» con 500 ms de voz se respeta", not es_inventada("gracias", 500, CFG))
comprobar("«Subtítulos… Amara.org» sin tildes ni signos", es_inventada("subtitulos realizados por la comunidad de amara org", 0, CFG))
comprobar("«hola» nunca es inventada", not es_inventada("hola", 0, CFG))

print(f"\n{'TODO BIEN' if not fallos else f'{fallos} FALLO(S)'}")
sys.exit(1 if fallos else 0)
