"""Errores por palabra de varios initial_prompt de [stt.local] sobre frases de
Piper con ruido (blanco 20 dB y marrón 10 dB). Mismo camino que la app:
LocalSTTProvider.transcribir (VAD, beam 1, reintentos). Ver CLAUDE.md, pendiente
2 de la nota de traspaso (2026-11-07: técnico 7,4 %, conversación sin
«sirviente» 9,1 %; no decide).

Uso: venv/bin/python tests/banco_wer.py SALIDA [OYEYORU.wav PAUSA.wav]
  SALIDA   carpeta FUERA del repo (WAV de Piper + resultado.json).
  OYEYORU.wav, PAUSA.wav  opcionales: «Oye Yoru, ¿cómo estás?» y «Ayer estuve
           jugando videojuegos, [pausa] ¿y tú?» tal como los oyó la app
           (limpios y con los dos ruidos). Los audios nunca van al repo."""
import sys, os, re, unicodedata, json, time
import numpy as np, soundfile as sf
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); os.chdir(RAIZ)
OUT = os.path.abspath(sys.argv[1])
if OUT == RAIZ or OUT.startswith(RAIZ + os.sep):
    raise SystemExit(f"{OUT} está dentro del repo: los audios tienen que quedar fuera")
os.makedirs(OUT, exist_ok=True)
import habla, stt
from faster_whisper import decode_audio
FRASES = [
    "Oye Yoru, ¿cómo estás?",
    "Ayer estuve jugando videojuegos, ¿y tú?",
    "Ayer estuve jugando videojuegos toda la tarde con mis amigos.",
    "¿Me puedes abrir el navegador, por favor?",
    "Hoy no tengo ganas de hacer nada.",
    "¿Qué opinas de las películas de terror?",
    "El servidor se cayó otra vez esta mañana.",
    "No sé si mi micro se escucha bien.",
    "Mi PC está muy lenta últimamente.",
    "Yoru, ¿qué hora es?",
    "Mañana tengo un examen de matemáticas y no he estudiado.",
    "Estoy aprendiendo Python para un proyecto de la universidad.",
    "Gracias por ayudarme con eso.",
    "¿Cuál es tu anime favorito?",
    "Me compré un teclado nuevo y suena horrible.",
    "Ollama tarda mucho en responder cuando la batería está baja.",
]
TECNICO = "Conversación con Yoru, una asistente virtual. Vocabulario: Yoru, Rem, Esteban, Ollama, Claude, Anthropic, Hyprland, Arch Linux, Python, PipeWire, GTK, WebKit, Whisper, Piper, VRM."
CONV = "Conversación con Yoru, una asistente virtual. Vocabulario: Yoru, {s}videojuegos, por favor, estuve, servidor, micro, PC."
VARIANTES = {
    "actual (técnico)": TECNICO,
    "conversación con sirviente": CONV.format(s="sirviente, "),
    "conversación sin sirviente": CONV.format(s=""),
    "sin sirviente + Ollama, Python": CONV.format(s="").rstrip(".") + ", Ollama, Python.",
    "mínimo, sin lista": "Conversación con Yoru, una asistente virtual.",
}
APP = list(zip(["Oye Yoru, ¿cómo estás?", "Ayer estuve jugando videojuegos, ¿y tú?"], sys.argv[2:4]))
REFS = FRASES + [t for t, _ in APP]
COLABLES = {"ollama", "claude", "anthropic", "hyprland", "arch", "linux", "python", "pipewire", "gtk",
            "webkit", "whisper", "piper", "vrm", "rem", "esteban", "sirviente"}
def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z0-9ñ]+", t)
def edicion(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (x != y))
    return d[-1]
# Audios: 2 síntesis por frase (Piper varía entre llamadas) x 2 ruidos, a 16 kHz.
rng = np.random.default_rng(7)
audios = []
for k, f in enumerate(FRASES + [t for t, _ in APP]):
    NSINT = 3 if k < len(FRASES) else 1
    for sint in range(NSINT):
        if k < len(FRASES):
            a, sr, _, _ = habla.sintetizar(f)
            z = np.zeros(int(0.3 * sr), np.int16)
            ruta = f"{OUT}/f{k:02d}_{sint}.wav"; sf.write(ruta, np.concatenate([z, a, z]), sr)
        else:
            ruta = APP[k - len(FRASES)][1]
        x = decode_audio(ruta, sampling_rate=16000)
        rms = np.sqrt(np.mean(x[np.abs(x) > 1e-4] ** 2))
        blanco = rng.standard_normal(len(x)).astype(np.float32)
        marron = np.cumsum(rng.standard_normal(len(x))).astype(np.float32); marron -= np.convolve(marron, np.ones(400) / 400, "same")
        if k >= len(FRASES): audios.append((k, sint, "limpio", x))
        for nombre, ruido, snr in (("blanco 20 dB", blanco, 20), ("marrón 10 dB", marron, 10)):
            r = ruido / np.sqrt(np.mean(ruido ** 2)) * rms / 10 ** (snr / 20)
            audios.append((k, sint, nombre, np.clip(x + r, -1, 1).astype(np.float32)))
p = stt.obtener_stt(); p.precargar()
res = {}
for nv, prompt in VARIANTES.items():
    p.initial_prompt = prompt
    errs = palabras = coladas = 0; salidas = []
    t0 = time.perf_counter()
    for k, sint, nr, x in audios:
        h = p.transcribir(x)
        ref, hyp = norm(REFS[k]), norm(h)
        errs += edicion(ref, hyp); palabras += len(ref)
        col = [w for w in hyp if w in COLABLES and w not in ref]; coladas += len(col)
        salidas.append({"frase": k, "sint": sint, "ruido": nr, "texto": h, "err": edicion(ref, hyp), "coladas": col})
    res[nv] = {"wer": errs / palabras, "errores": errs, "palabras": palabras, "coladas": coladas,
               "seg": time.perf_counter() - t0, "salidas": salidas}
    print(f"{nv:32s} WER {100*errs/palabras:5.1f} % ({errs}/{palabras}) | coladas {coladas} | "
          f"app «Oye Yoru»: {[s['texto'] for s in salidas if s['frase']==len(FRASES)]} | app «¿y tú?»: {[s['texto'][-16:] for s in salidas if s['frase']==len(FRASES)+1]}", flush=True)
json.dump({"frases": REFS, "variantes": VARIANTES, "res": res}, open(f"{OUT}/resultado.json", "w"), ensure_ascii=False, indent=1)
