"""Pruebas de los filtros de texto de chat_sesion: etiqueta de emoción,
marcas (corchetes, llamadas escritas como texto), límite de oraciones y
detección del modo serio.

Sin dependencias: `venv/bin/python tests/test_filtros_texto.py` (sale con 1
si algo falla). También corre con pytest si algún día se instala.

Cada caso de stream se prueba con 300 particiones aleatorias del texto en
fragmentos de 1-5 caracteres, como llegan de Ollama: el resultado tiene que
ser idéntico en todas.
"""
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from chat_sesion import (_extraer_emocion, _limitar_oraciones, _para_voz,  # noqa: E402
                         _quitar_marcas, detectar_modo_serio)
from llm import Done, TextDelta  # noqa: E402

PARTICIONES = 300


def _trozos(texto, semilla):
    rnd = random.Random(semilla)
    i, out = 0, []
    while i < len(texto):
        n = rnd.randint(1, 5)
        out.append(texto[i:i + n])
        i += n
    return out


def _pipeline(texto, semilla, max_oraciones=None):
    """Mismo orden que procesar_turno(): emoción -> marcas -> límite."""
    etiquetas, quitados, cortes = [], [], []

    async def gen():
        for t in _trozos(texto, semilla):
            yield TextDelta(t)
        yield Done(reason="stop")

    async def correr():
        s = _quitar_marcas(_extraer_emocion(gen(), etiquetas.append), quitados.append)
        if max_oraciones:
            s = _limitar_oraciones(s, max_oraciones, cortes.append)
        out = ""
        async for c in s:
            if isinstance(c, TextDelta):
                out += c.text
        return out
    return asyncio.run(correr()), etiquetas, quitados, cortes


def _unico(texto, **kw):
    resultados = {(o, tuple(e), tuple(q), len(c))
                  for o, e, q, c in (_pipeline(texto, s, **kw) for s in range(PARTICIONES))}
    assert len(resultados) == 1, f"{texto!r}: depende de cómo se parta: {resultados}"
    return resultados.pop()


def test_etiqueta_emocion_al_inicio():
    # La etiqueta del principio es para la cara: sale por on_etiqueta y no
    # llega al texto (ni a _quitar_marcas, que no la ve).
    out, etiquetas, quitados, _ = _unico("[TRISTE] …Es un golpe duro.")
    assert out == "…Es un golpe duro.", out
    assert etiquetas == ("TRISTE",) and quitados == ()


def test_etiqueta_a_mitad_de_texto():
    out, etiquetas, quitados, _ = _unico("…Eso duele. [TRISTE] Aquí estoy.")
    assert out == "…Eso duele. Aquí estoy.", out
    assert etiquetas == () and quitados == ("[TRISTE]",)


def test_marcas():
    casos = {
        "[ENJOYED abrir_programa('steam')]": "",
        "…Malenia es dura. [ENJOYED abrir_programa('steam')] Ve a entrenar.": "…Malenia es dura. Ve a entrenar.",
        "Ya está. abrir_programa('steam') Disfrútalo, sirviente.": "Ya está. Disfrútalo, sirviente.",
        "Dark Souls (el primero) es mejor.": "Dark Souls (el primero) es mejor.",
        "Un corchete [sin cerrar al final": "Un corchete [sin cerrar al final",
    }
    for entrada, esperado in casos.items():
        out = _unico(entrada)[0]
        assert out == esperado, f"{entrada!r} -> {out!r}"


def test_limite_oraciones():
    texto = "…Uno. Dos, con coma. ¿Tres? Cuatro. Cinco."
    out, _, _, cortes = _unico(texto, max_oraciones=3)
    assert out == "…Uno. Dos, con coma. ¿Tres?", out
    assert cortes == 1
    # Los "…" del principio o a mitad de frase no cuentan como final.
    out, _, _, cortes = _unico("…ah. Sí… pero no. Vale. Otra.", max_oraciones=3)
    assert out == "…ah. Sí… pero no. Vale.", out
    # Con menos oraciones que el límite no se corta nada.
    out, _, _, cortes = _unico("Una. Dos.", max_oraciones=3)
    assert out == "Una. Dos." and cortes == 0


def test_para_voz():
    assert _para_voz("Hola [FELIZ] sirviente, abrir_programa('x').") == "Hola sirviente."
    assert _para_voz("¡Skill issue! Ve con los npc.") == "skil íshiu. Ve con los enpisí."
    assert _para_voz("まあ、どうでもいい.") == "maa, dou demo íi."


def test_modo_serio():
    cfg = config.leer_config_modo_serio()
    serias = ["lo dejamos con mi pareja", "me siento muy aislado", "perdí el trabajo",
              "se nos murió mi tío", "estoy agobiado con todo", "ya no aguanto la u",
              "mi novia me dejó", "me echaron hoy", "falleció mi abuela", "estoy deprimido"]
    no_serias = ["se murió mi personaje en Elden Ring", "terminé el juego",
                 "me echaron de la partida", "hola", "solo quería saber la hora",
                 "el jefe final me mató otra vez", "¿qué anime me recomiendas?"]
    for t in serias:
        assert detectar_modo_serio(t, cfg), f"debería ser serio: {t!r}"
    for t in no_serias:
        assert not detectar_modo_serio(t, cfg), f"no debería ser serio: {t!r}"


if __name__ == "__main__":
    fallos = 0
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_") and callable(f):
            try:
                f()
                print(f"ok    {nombre}")
            except AssertionError as e:
                fallos += 1
                print(f"FALLA {nombre}: {e}")
    sys.exit(1 if fallos else 0)
