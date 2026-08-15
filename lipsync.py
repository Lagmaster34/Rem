"""Lipsync real basado en fonemas para el avatar de Rem.

Pipeline: texto → edge-tts (audio + WordBoundary por palabra) → fonemas por
reglas (grafema→fonema español) → timeline de visemes VRChat/Oculus con
apertura de mandíbula, listo para mandar al frontend por WebSocket.

Sin dependencias externas: solo stdlib + edge_tts (ya usado por el proyecto).
"""

import edge_tts

# edge-tts reporta offset/duration en "ticks" de 100 nanosegundos
# (mismo formato que .NET TimeSpan): 10_000_000 ticks = 1 segundo.
TICKS_POR_SEGUNDO = 10_000_000

# es-VE-PaolaNeural + rate -8%: configuración ganadora de una comparación A/B
# (ver CLAUDE.md, "Configuración de voz ganadora").
VOZ_DEFAULT = "es-VE-PaolaNeural"
RATE_DEFAULT = "-8%"


async def sintetizar_con_timings(texto, voz=VOZ_DEFAULT, rate=RATE_DEFAULT):
    """Sintetiza `texto` con edge-tts y devuelve (bytes_mp3, palabras_con_timings).

    palabras_con_timings: [{"palabra": str, "inicio": float, "fin": float}, ...]
    inicio/fin en segundos, relativos al comienzo del audio.
    """
    communicate = edge_tts.Communicate(texto, voz, rate=rate, boundary="WordBoundary")

    audio_chunks = []
    palabras = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            inicio = chunk["offset"] / TICKS_POR_SEGUNDO
            duracion = chunk["duration"] / TICKS_POR_SEGUNDO
            palabras.append({
                "palabra": chunk["text"],
                "inicio": inicio,
                "fin": inicio + duracion,
            })

    return b"".join(audio_chunks), palabras


# ── Grafema → fonema (español, por reglas) ──────────────────────────────
_VOCALES_ACENTUADAS = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}


def _normalizar(c):
    return _VOCALES_ACENTUADAS.get(c, c)


def texto_a_fonemas(palabra):
    """Convierte una palabra en español a una lista de fonemas, por reglas.

    Maneja los dígrafos (ch, ll, rr, qu, gu ante e/i) antes que las letras
    sueltas para que no se procesen letra por letra por error.
    """
    p = palabra.lower()
    n = len(p)
    fonemas = []
    i = 0

    while i < n:
        c2 = p[i:i + 2]
        sig = _normalizar(p[i + 2]) if i + 2 < n else ""

        # Dígrafos primero
        if c2 == "ch":
            fonemas.append("ch"); i += 2; continue
        if c2 == "ll":
            fonemas.append("y"); i += 2; continue
        if c2 == "rr":
            fonemas.append("r"); i += 2; continue
        if c2 == "qu" and sig in "ei":
            fonemas.append("k"); i += 2; continue
        if c2 == "gu" and sig in "ei":
            fonemas.append("g"); i += 2; continue

        c = _normalizar(p[i])
        sig1 = _normalizar(p[i + 1]) if i + 1 < n else ""

        if c in "aeiou":
            fonemas.append(c)
        elif c == "c":
            fonemas.append("s" if sig1 in "ei" else "k")
        elif c == "g":
            fonemas.append("x" if sig1 in "ei" else "g")
        elif c == "j":
            fonemas.append("x")
        elif c == "v":
            fonemas.append("b")
        elif c == "z":
            fonemas.append("s")
        elif c == "h":
            pass  # muda, no genera fonema
        elif c == "y":
            es_final = (i == n - 1)
            fonemas.append("i" if es_final else "y")
        elif c == "ñ":
            fonemas.append("n")
        elif c.isalpha():
            fonemas.append(c)  # consonantes regulares: b,d,f,k,l,m,n,p,r,s,t...
        # no alfabético (puntuación, espacios, dígitos) → se ignora

        i += 1

    return fonemas


# ── Fonema → viseme (morph targets VRChat/Oculus presentes en rem.vrm) ──
FONEMA_A_VISEME = {
    "a": "vrc.v_aa",
    "e": "vrc.v_e",
    "i": "vrc.v_ih",
    "o": "vrc.v_oh",
    "u": "vrc.v_ou",
    "p": "vrc.v_pp", "b": "vrc.v_pp", "m": "vrc.v_pp",
    "f": "vrc.v_ff",
    "s": "vrc.v_ss",
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
    "f": ("ih", 0.3), "s": ("ih", 0.3), "z": ("ih", 0.3),
    "n": ("ih", 0.2), "l": ("ih", 0.2), "t": ("ih", 0.2), "d": ("ih", 0.2),
    "k": ("aa", 0.3), "g": ("aa", 0.3), "x": ("aa", 0.3),
    "r": ("ih", 0.25),
    "ch": ("ih", 0.4), "y": ("ih", 0.4),
    "silencio": (None, 0.0),
}
_VISEME_VRM_DEFAULT = (None, 0.0)


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


def construir_timeline(palabras_con_timings):
    """Reparte los fonemas de cada palabra uniformemente en su intervalo de tiempo
    e inserta silencios en los huecos entre palabras.

    Cada evento trae dos mapeos en paralelo, para que el frontend elija cuál usar
    según lo que exponga el modelo cargado:
      - "viseme"/"apertura": morph targets vrc.* (VRChat/Oculus, 15 visemes) + jaw.
      - "viseme_vrm"/"peso_vrm": preset estándar de VRM (aa/ee/ih/oh/ou vía
        expressionManager), con peso parcial para consonantes sin viseme propio.

    Devuelve una lista ordenada por "t".
    """
    timeline = []
    t_cursor = 0.0

    for palabra_info in palabras_con_timings:
        inicio = palabra_info["inicio"]
        fin = palabra_info["fin"]

        if inicio > t_cursor:
            timeline.append(_construir_evento(t_cursor, "silencio"))

        fonemas = texto_a_fonemas(palabra_info["palabra"])
        if fonemas:
            duracion = (fin - inicio) / len(fonemas)
            for idx, fonema in enumerate(fonemas):
                timeline.append(_construir_evento(inicio + idx * duracion, fonema))

        t_cursor = fin

    timeline.append(_construir_evento(t_cursor, "silencio"))
    return timeline


if __name__ == "__main__":
    import asyncio

    FRASE = "Hola, amo. ¿Cómo estás hoy?"

    async def _prueba():
        print(f'Sintetizando: "{FRASE}"')
        audio, palabras = await sintetizar_con_timings(FRASE)
        print(f"audio: {len(audio)} bytes")
        print()
        print("-- palabras con timing --")
        for p in palabras:
            print(f'  {p["inicio"]:.3f}s - {p["fin"]:.3f}s : {p["palabra"]!r}')

        timeline = construir_timeline(palabras)
        print()
        print(f"-- timeline de visemes ({len(timeline)} eventos) --")
        for ev in timeline:
            print(f'  t={ev["t"]:.3f}s  viseme={ev["viseme"]:<12}  apertura={ev["apertura"]:.2f}'
                  f'  | vrm={str(ev["viseme_vrm"]):<5} peso_vrm={ev["peso_vrm"]:.2f}')

    asyncio.run(_prueba())
