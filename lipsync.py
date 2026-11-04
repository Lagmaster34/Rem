"""Lipsync real basado en fonemas para el avatar de Rem.

Pipeline: texto → Piper (audio + alineación fonema→muestras de audio) →
fonemas IPA de espeak-ng → timeline de visemes VRChat/Oculus con apertura de
mandíbula, listo para mandar al frontend por WebSocket.

Las duraciones salen del PROPIO modelo (la salida de duraciones por fonema de
VITS que Piper 1.8 expone con `include_alignments`, ver habla.py), no de un
reparto estimado: la suma de muestras de un chunk coincide exacta con la
longitud de su audio. Este módulo no carga Piper: recibe los AudioChunk ya
sintetizados.
"""

# ── Fonema → viseme (vocabulario canónico "vrc.v_*" del frontend) ───────
FONEMA_A_VISEME = {
    "a": "vrc.v_aa",
    "e": "vrc.v_e",
    "i": "vrc.v_ih",
    "o": "vrc.v_oh",
    "u": "vrc.v_ou",
    "p": "vrc.v_pp", "b": "vrc.v_pp", "m": "vrc.v_pp",
    "f": "vrc.v_ff",
    "s": "vrc.v_ss",
    "th": "vrc.v_th",
    "t": "vrc.v_dd", "d": "vrc.v_dd",
    "k": "vrc.v_kk", "g": "vrc.v_kk", "x": "vrc.v_kk",
    "n": "vrc.v_nn", "l": "vrc.v_nn",
    "r": "vrc.v_rr",
    "ch": "vrc.v_ch", "y": "vrc.v_ch",
    "silencio": "vrc.v_sil",
}
_VISEME_DEFAULT = "vrc.v_nn"  # fallback para fonemas no mapeados (consonante genérica)

# Apertura de mandíbula por fonema: vocales abiertas > medias > cerradas > consonantes > silencio
_APERTURA_VOCALES = {"a": 1.0, "e": 0.7, "o": 0.7, "i": 0.4, "u": 0.4}
_APERTURA_CONSONANTE = 0.15
_APERTURA_SILENCIO = 0.0

# ── Fonema → viseme estándar de VRM (fallback: 5 visemes aa/ee/ih/oh/ou vía
# expressionManager, para cuando el modelo no expone morph targets vrc.* ──
# Las consonantes sin viseme propio se aproximan con un peso parcial sobre el
# viseme más cercano en vez de dejar la boca completamente inerte.
FONEMA_A_VISEME_VRM = {
    "a": ("aa", 1.0), "e": ("ee", 1.0), "i": ("ih", 1.0), "o": ("oh", 1.0), "u": ("ou", 1.0),
    "p": (None, 0.0), "b": (None, 0.0), "m": (None, 0.0),
    "f": ("ih", 0.3), "s": ("ih", 0.3), "th": ("ih", 0.3),
    "n": ("ih", 0.2), "l": ("ih", 0.2), "t": ("ih", 0.2), "d": ("ih", 0.2),
    "k": ("aa", 0.3), "g": ("aa", 0.3), "x": ("aa", 0.3),
    "r": ("ih", 0.25),
    "ch": ("ih", 0.4), "y": ("ih", 0.4),
    "silencio": (None, 0.0),
}
_VISEME_VRM_DEFAULT = (None, 0.0)

# ── IPA de espeak-ng (español) → fonema interno ─────────────────────────
# espeak-ng parte las africadas en dos símbolos (tʃ → "t", "ʃ"), así que no
# hacen falta entradas de dos caracteres.
_IPA_A_FONEMA = {
    "a": "a", "ɐ": "a", "æ": "a", "ɑ": "a",
    "e": "e", "ɛ": "e", "ə": "e",
    "i": "i", "ɪ": "i", "j": "i",   # j = semivocal ("funθjon"): boca de i
    "o": "o", "ɔ": "o",
    "u": "u", "ʊ": "u", "w": "u",   # w = semivocal: boca de u
    "p": "p", "b": "b", "β": "b", "m": "m", "ɱ": "m",
    "f": "f", "v": "f",
    "θ": "th", "ð": "th",           # ð = la d suave intervocálica ("moðelo")
    "s": "s", "z": "s",
    "t": "t", "d": "d",
    "k": "k", "c": "k", "g": "g", "ɡ": "g", "ɣ": "g", "x": "x", "χ": "x", "h": "x",
    "n": "n", "ɲ": "n", "ŋ": "n", "ɴ": "n", "l": "l",
    "r": "r", "ɾ": "r", "ɹ": "r", "ʀ": "r",
    "ʃ": "ch", "ʒ": "y", "ʝ": "y", "ʎ": "y", "ɟ": "y",
}
# Marcas de acento/longitud y diacríticos: el modelo les asigna duración
# propia (es el arranque del fonema siguiente), pero no son una forma de boca.
_MODIFICADORES = set("ˈˌːˑ̪̃͡")
# Pausas: BOS/EOS de Piper y puntuación — boca cerrada.
_PAUSAS = set("^$_,.;:!?¡¿—–-…()\"'")
# Un espacio entre palabras es un silencio real solo si dura más que esto; si
# no, es habla continua y se mantiene el fonema anterior.
ESPACIO_PAUSA_S = 0.12


def _construir_evento(t, fonema):
    viseme_vrm, peso_vrm = FONEMA_A_VISEME_VRM.get(fonema, _VISEME_VRM_DEFAULT)
    apertura = _APERTURA_SILENCIO if fonema == "silencio" else _APERTURA_VOCALES.get(fonema, _APERTURA_CONSONANTE)
    return {
        "t": t,
        "viseme": FONEMA_A_VISEME.get(fonema, _VISEME_DEFAULT),
        "apertura": apertura,
        "viseme_vrm": viseme_vrm,
        "peso_vrm": peso_vrm,
    }


def _segmentos(chunk):
    """[(símbolo IPA, nº de muestras)] de un AudioChunk de Piper. Con
    alineación, las duraciones reales del modelo. Sin ella (el modelo no se
    pudo parchear, o Piper descartó la alineación de este chunk), los fonemas
    del chunk repartidos parejo en su duración real — sin modificadores, que no
    son sonidos propios."""
    if chunk.phoneme_alignments:
        return [(a.phoneme, int(a.num_samples)) for a in chunk.phoneme_alignments]
    simbolos = [p for p in chunk.phonemes if p not in _MODIFICADORES]
    if not simbolos:
        return [("_", len(chunk.audio_float_array))]
    paso = len(chunk.audio_float_array) / len(simbolos)
    return [(p, paso) for p in simbolos]


def construir_timeline(chunks):
    """Timeline de visemes de los AudioChunk de una síntesis de Piper, en el
    orden en que se concatenan en el WAV (sin silencio entre chunks).

    Cada evento trae dos mapeos en paralelo, para que el frontend elija cuál usar
    según lo que exponga el modelo cargado:
      - "viseme"/"apertura": morph targets vrc.* (VRChat/Oculus, 15 visemes) + jaw.
      - "viseme_vrm"/"peso_vrm": preset estándar de VRM (aa/ee/ih/oh/ou vía
        expressionManager), con peso parcial para consonantes sin viseme propio.

    Devuelve (timeline ordenado por "t", con_alineacion) — con_alineacion es
    False si algún chunk tuvo que caer al reparto parejo.
    """
    timeline = []
    muestras = 0.0
    con_alineacion = True
    sr = chunks[0].sample_rate if chunks else 1

    def emitir(t, fonema):
        # Silencios seguidos se colapsan en uno solo.
        if fonema == "silencio" and timeline and timeline[-1]["viseme"] == "vrc.v_sil":
            return
        timeline.append(_construir_evento(t, fonema))

    for chunk in chunks:
        if not chunk.phoneme_alignments:
            con_alineacion = False
        inicio_pendiente = None  # arranque de un fonema precedido por un acento
        for simbolo, n in _segmentos(chunk):
            t = muestras / sr
            if simbolo in _MODIFICADORES:
                if inicio_pendiente is None:
                    inicio_pendiente = t
            elif simbolo == " ":
                if n / sr > ESPACIO_PAUSA_S:
                    emitir(t, "silencio")
                inicio_pendiente = None
            elif simbolo in _PAUSAS:
                emitir(t, "silencio")
                inicio_pendiente = None
            else:
                fonema = _IPA_A_FONEMA.get(simbolo, simbolo)
                emitir(inicio_pendiente if inicio_pendiente is not None else t, fonema)
                inicio_pendiente = None
            muestras += n

    emitir(muestras / sr, "silencio")
    return timeline, con_alineacion


if __name__ == "__main__":
    import sys
    import time

    from piper import PiperVoice

    import config

    FRASE = sys.argv[1] if len(sys.argv) > 1 else "Hola, Esteban. ¿Cómo estás hoy?"
    voz = PiperVoice.load(config.leer_modelo_tts(), include_alignments=True)
    t0 = time.perf_counter()
    chunks = list(voz.synthesize(FRASE, include_alignments=True))
    dt = time.perf_counter() - t0
    total = sum(len(c.audio_float_array) for c in chunks)
    print(f'"{FRASE}": {total / chunks[0].sample_rate:.2f}s de audio a {chunks[0].sample_rate} Hz, sintetizado en {dt:.3f}s')
    for c in chunks:
        print("  fonemas:", "".join(c.phonemes), "| alineación:", "sí" if c.phoneme_alignments else "NO")

    timeline, con_alineacion = construir_timeline(chunks)
    print(f"-- timeline de visemes ({len(timeline)} eventos, alineación del modelo: {con_alineacion}) --")
    for ev in timeline:
        print(f'  t={ev["t"]:.3f}s  viseme={ev["viseme"]:<12}  apertura={ev["apertura"]:.2f}'
              f'  | vrm={str(ev["viseme_vrm"]):<5} peso_vrm={ev["peso_vrm"]:.2f}')
