"""frases_voz.py — las frases fijas dichas con la voz de Piper: las
reacciones del avatar de escritorio (al clic, al agarrarlo, al cambiar la
voz...) y los avisos del servidor en cualquier modo (micrófono, errores,
confirmación de apagar la PC).

Los textos viven en frases_escritorio.json (versionado; la página los lee de
ahí también). Cada frase se sintetiza UNA vez y se guarda en cache_frases/
(ignorado por git): <clave>.wav + <clave>.json (timeline de visemes). La clave
es un hash del texto tal como lo lee la voz (después de chat_sesion._para_voz)
y de la identidad del modelo Piper (ruta, tamaño, fecha y su .onnx.json), así
que cambiar una frase o la voz la regenera sola. precargar() las genera en un
hilo al arrancar, para que suenen al instante.

Nada de esto llama al LLM: son textos fijos de interfaz.
"""
import hashlib
import json
import os
import threading
import time

import numpy as np
import soundfile as sf

import config

FRASES_PATH = os.path.join(config.BASE_DIR, "frases_escritorio.json")
CACHE_DIR = config.ruta_datos("cache_frases")

_lock = threading.Lock()
_id_modelo = None


def _log(msg):
    print(f"[Frases] {msg}", flush=True)


def _grupos() -> dict[str, list[str]]:
    try:
        with open(FRASES_PATH, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError) as e:
        _log(f"no se pudo leer {FRASES_PATH} ({e})")
        return {}
    return {k: [t for t in v if isinstance(t, str)] for k, v in datos.items() if isinstance(v, list)}


def textos() -> set[str]:
    """Todas las frases del JSON (las que se pueden pedir con voz)."""
    return {t for lista in _grupos().values() for t in lista}


def grupo(nombre: str) -> list[str]:
    """Las frases de un grupo del JSON ([] si no existe)."""
    return _grupos().get(nombre, [])


def _texto_voz(texto: str) -> str:
    import chat_sesion
    return chat_sesion._para_voz(texto).strip()


def _identidad_modelo() -> str:
    global _id_modelo
    if _id_modelo is None:
        import config
        ruta = config.leer_modelo_tts()
        h = hashlib.sha256(os.path.abspath(ruta).encode())
        try:
            st = os.stat(ruta)
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
            with open(ruta + ".json", "rb") as f:
                h.update(f.read())
        except OSError:
            pass
        _id_modelo = h.hexdigest()[:16]
    return _id_modelo


def _clave(texto_voz: str) -> str:
    return hashlib.sha256(f"{_identidad_modelo()}|{texto_voz}".encode()).hexdigest()[:24]


def _hablable(texto_voz: str) -> bool:
    return any(c.isalpha() for c in texto_voz)


def obtener(texto: str):
    """(ruta_wav, timeline) de `texto`, de la caché o sintetizándolo ahora.
    None si el texto no tiene nada que decir ("…")."""
    voz = _texto_voz(texto)
    if not _hablable(voz):
        return None
    clave = _clave(voz)
    wav = os.path.join(CACHE_DIR, f"{clave}.wav")
    meta = os.path.join(CACHE_DIR, f"{clave}.json")
    with _lock:
        if os.path.exists(wav) and os.path.exists(meta):
            try:
                with open(meta, encoding="utf-8") as f:
                    return wav, json.load(f)["timeline"]
            except (OSError, ValueError, KeyError):
                pass
        import habla
        t0 = time.perf_counter()
        audio, sr, timeline, _alin = habla.sintetizar(voz)
        if len(audio) == 0:
            return None
        os.makedirs(CACHE_DIR, exist_ok=True)
        sf.write(wav, np.asarray(audio), sr, subtype="PCM_16")
        with open(meta + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"texto": texto, "voz": voz, "timeline": timeline}, f, ensure_ascii=False)
        os.replace(meta + ".tmp", meta)
        _log(f'generada "{texto}" en {time.perf_counter() - t0:.2f}s')
        return wav, timeline


def precargar():
    """Genera las que falten y borra de la caché las que ya no corresponden a
    ninguna frase (texto cambiado o voz cambiada). Para un hilo de fondo."""
    t0 = time.perf_counter()
    vigentes = set()
    for t in sorted(textos()):
        try:
            r = obtener(t)
        except Exception as e:
            _log(f'no se pudo generar "{t}" ({type(e).__name__}: {e})')
            continue
        if r:
            vigentes.add(os.path.splitext(os.path.basename(r[0]))[0])
    borradas = 0
    if os.path.isdir(CACHE_DIR):
        for nombre in os.listdir(CACHE_DIR):
            if os.path.splitext(nombre)[0].split(".")[0] not in vigentes:
                os.remove(os.path.join(CACHE_DIR, nombre))
                borradas += 1
    _log(f"{len(vigentes)} frases listas en {time.perf_counter() - t0:.1f}s"
         + (f" ({borradas} archivos viejos borrados)" if borradas else ""))
