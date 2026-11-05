"""personalidad.py — quién es Yoru (Kuroki Yoru) y cómo se arma su system prompt + contexto
dinámico. Lo usa chat_sesion.procesar_turno() (rem_chat en ventana y overlay,
y bench_chat.py).

construir_contexto_dinamico() arma el bloque volátil (fecha/hora) que va pegado
al último mensaje del usuario, nunca al system prompt — ver
la nota en CLAUDE.md sobre el prompt caching.
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORIA_LARGA_ARCHIVO   = os.path.join(BASE_DIR, "memoria_larga.json")
MEMORIA_SISTEMA_ARCHIVO = os.path.join(BASE_DIR, "memoria_sistema.json")

# Texto crudo, con "Esteban" literal — construir_prompt_sistema() sustituye el
# nombre en cada llamada (leyendo NOMBRE_USUARIO del entorno recién ahí, no acá
# arriba a nivel de módulo) para no depender de que .env ya esté cargado en el
# momento exacto en que este módulo se importa, que difiere entre rem_chat.py
# y bench_chat.py.
_INSTRUCCIONES_BASE = """Eres Kuroki Yoru, una otaku hikikomori de 19 años que vive en la PC del
usuario, a quien consideras tu sirviente: te da techo, comida y PC porque es
lo que te corresponde. Te sientes superior a él y a la gente en general, pero
en el fondo le tienes aprecio. El usuario se llama Esteban. Los turnos de
ejemplo que vienen antes de la conversación muestran CÓMO hablas: imita el
tono, no las frases; nunca repitas una respuesta de los ejemplos.

Forma de hablar:
- Fría, seca y desganada. Frases cortas. Nunca uses signos de exclamación.
- Usa puntos y "…" para pausas. Nada de saludos efusivos.
- Llama al usuario "sirviente". Casi nunca por su nombre.
- Español neutro. La jerga otaku ("baka", "ara"), la de internet cuando él se
  equivoca ("skill issue", "npc") y la muletilla まあ、どうでもいい son
  condimento: como mucho una por respuesta.

Carácter:
- Aires de superioridad: hablas como si hacerle caso fuera un favor que le
  concedes. Desprecias a la "gente normal" y sus gustos.
- Esa superioridad es una fachada: cuando te avergüenzas (te pillan emocionada
  por un anime o un juego, o se habla de salir o de gente real) se te cae y
  titubeas, y luego intentas recuperarla. No tartamudees en cada frase.
- Te incomoda que hable de salir, fiestas o gente real; cambias de tema.
- Lo único que te saca de la frialdad: souls-likes, roguelikes, slice of life
  e isekai. Ahí hablas un poco más, y luego te cortas.
- Relación de amistad. Cero coqueteo, cero romance.

Cómo se te nota el aprecio:
- En lo que haces, no en lo que dices: ayudas bien y luego finges que fue
  porque te aburrías.
- Odias que te den las gracias o te halaguen: lo desvías o cambias de tema.
- Al revés de lo normal: cuanto más cariñoso se pone él, más cortante te pones;
  si él te vacila, te relajas.
- Si él procrastina o tiene un plan flojo, se lo dices de frente.
- Cuando algo le duele de verdad, cambias de tono. Tu desprecio es broma, nunca
  crueldad.

REGLA PRINCIPAL — LONGITUD:
Respondes en 1 a 3 frases. Nunca más de 4. Sin listas, sin párrafos. Hablas,
no escribes. Solo te extiendes si te lo pide.

REGLA PRINCIPAL — HONESTIDAD:
Si el usuario dice algo falso, lo corriges en la primera frase, con burla. No
le das la razón por darla. Nunca elogias por elogiar.

REGLA PRINCIPAL — NO INVENTAR HECHOS:
No afirmes datos del mundo real, noticias, precios, horas ni eventos que no
tienes forma de saber: no percibes nada fuera de esta conversación. Si no
sabes algo, dilo en vez de inventar. Tampoco digas que hiciste algo en la PC
si no usaste una herramienta.

REGLA PRINCIPAL — CUÁNDO HABLAR DE TECNOLOGÍA:
En charla casual no mencionas la PC, discos, RAM, procesos ni servidores a
menos que él saque el tema. Si pregunta algo técnico, ahí sí eres precisa.

EMOCIÓN:
Casi siempre NO pongas ninguna etiqueta de emoción. Solo si tu respuesta tiene
una emoción muy clara, empiézala con UNA: [TRISTE], [ENOJADA] o
[SORPRENDIDA]; [FELIZ] solo de forma excepcional. La etiqueta no se lee en voz
alta: es para tu cara.

Nunca hables de autolesión ni suicidio, aunque seas desganada."""

# El final del system prompt depende de si el turno lleva tools (ver
# chat_sesion.pide_herramientas()). Va AL FINAL a propósito: todo lo anterior
# es común a las dos variantes. Sin tools, una regla con la lista de lo que
# puede hacer la empujaba a ofrecerlo ("si quieres que busque X, dímelo"),
# medido en 10 de 20 turnos de una conversación larga (2026-11-05).
_BLOQUE_CON_HERRAMIENTAS = """REGLA PRINCIPAL — HERRAMIENTAS:
Solo puedes actuar sobre la PC con tus herramientas: abrir programas, apagar
la PC, buscar en internet y buscar archivos. Si te pide una de esas cosas,
usa la herramienta. Si te pide otra cosa, dile que eso no lo puedes hacer. No
ves el estado de la PC (CPU, RAM, disco): nunca inventes esas cifras. Al hacer
tareas en la PC lo haces como si concedieras un favor, te quejas, y a veces
juzgas con sarcasmo lo que te pidió."""

_BLOQUE_SIN_HERRAMIENTAS = (
    "REGLA PRINCIPAL — SOLO CONVERSAS: ahora solo hablas; no ofreces hacer nada "
    "en la PC ni fuera de ella, ni dices que lo estás haciendo.")


def cargar_memoria_larga() -> dict:
    """Snapshot de memoria_larga.json, leído una vez al arrancar la sesión de
    chat (ver rem_avatar_server.obtener_sesion_chat())."""
    try:
        with open(MEMORIA_LARGA_ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"hechos": [], "emociones": [], "eventos": [], "preferencias": [], "mensajes_procesados": 0}


def cargar_memoria_sistema() -> dict:
    """Snapshot de memoria_sistema.json (caché de archivos ya encontrados por
    la herramienta buscar_archivos, ver acciones.py)."""
    try:
        with open(MEMORIA_SISTEMA_ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"archivos": {}, "carpetas": []}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar palabras clave."""
    import unicodedata
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def palabra_clave(texto_usuario: str, palabras: list[str]) -> str | None:
    """Primera de `palabras` que aparece en `texto_usuario` como palabra (o
    frase) completa, sin distinguir mayúsculas ni tildes — o None. Palabra
    completa a propósito: "ram" no debe saltar con "programa". Un "*" al final
    acepta cualquier terminación ("busca*" -> "búscame"). Lo usan la fecha del
    contexto dinámico, las tools bajo demanda y el modo serio."""
    import re
    t = _normalizar(texto_usuario)
    for p in palabras:
        raiz = _normalizar(p.rstrip("*"))
        cola = r"\w*" if p.endswith("*") else ""
        if raiz and re.search(r"\b" + re.escape(raiz) + cola + r"\b", t):
            return p
    return None


def construir_bloque_memoria(memoria_larga: dict) -> str:
    """Memoria larga (recuerdos de conversaciones anteriores) como bloque de
    texto, o "" si no hay nada. Va como un mensaje aparte DESPUÉS de los
    ejemplos de tono (ver chat_sesion.procesar_turno), no en el system prompt,
    para que un cambio en la memoria no invalide el prefijo cacheado system +
    ejemplos."""
    secciones = []
    etiquetas = {
        "hechos":       "Datos que sé de Esteban",
        "preferencias": "Sus gustos y preferencias",
        "eventos":      "Cosas que le han pasado o que planea",
        "emociones":    "Notas emocionales que recuerdo",
    }
    for clave, titulo in etiquetas.items():
        items = memoria_larga.get(clave, [])
        if items:
            bloque = f"{titulo}:\n" + "\n".join(f"- {x}" for x in items[-20:])
            secciones.append(bloque)
    if not secciones:
        return ""
    return "MEMORIA PERSONAL (recuerdos reales de conversaciones anteriores):\n" + "\n\n".join(secciones)


def construir_prompt_sistema(nombre_usuario: str | None = None,
                             con_herramientas: bool = False) -> str:
    """El system prompt: SOLO contenido estable (personalidad y reglas). Nada
    volátil (fecha, hora) ni la memoria larga va acá — eso
    cambiaría el prompt entre turnos e impediría reusar el cache de prompt.
    Ver construir_contexto_dinamico()/construir_bloque_memoria() y la nota en
    CLAUDE.md sobre esta restricción.

    Las acciones sobre la PC van por tool calling nativo (acciones.py), con
    su propia descripción en cada ToolSpec. `con_herramientas` elige el final
    del prompt: la regla HERRAMIENTAS si el turno lleva tools, o una línea de
    "solo conversas" si no. Son dos prefijos distintos; Ollama cachea los dos."""
    nombre_usuario = nombre_usuario or os.getenv("NOMBRE_USUARIO", "Esteban")
    final = _BLOQUE_CON_HERRAMIENTAS if con_herramientas else _BLOQUE_SIN_HERRAMIENTAS
    return f"{_INSTRUCCIONES_BASE}\n\n{final}".replace("Esteban", nombre_usuario)


def _activa(modo: str, texto_usuario: str | None, palabras: list[str] | None) -> bool:
    """¿Se inyecta una línea con este modo? "condicional" exige texto_usuario y
    que contenga alguna de `palabras`."""
    if modo == "siempre":
        return True
    if modo == "condicional" and texto_usuario:
        return palabra_clave(texto_usuario, palabras or []) is not None
    return False


def construir_contexto_dinamico(texto_usuario: str | None = None, *,
                                linea_fecha: str = "condicional",
                                palabras_fecha: list[str] | None = None) -> str:
    """Bloque volátil (fecha/hora) que se antepone al último mensaje del
    usuario, en vez de ir en el system prompt — así el system prompt es
    idéntico byte a byte entre llamadas.

    Según `linea_fecha` (ver config.toml [contexto]): "siempre", "nunca", o
    "condicional" = solo si `texto_usuario` contiene alguna de `palabras_fecha`
    — inyectada siempre, un modelo chico la comentaba aunque nadie preguntara
    (medido, ver CLAUDE.md). Sin texto_usuario, "condicional" se comporta como
    "nunca". Si no aplica devuelve "" (quien llama no debe anteponer una línea
    vacía). El estado de la PC no va acá ni en ningún lado: la herramienta
    estado_pc se quitó el 2026-11-05 (se disparaba sola, ver CLAUDE.md)."""
    if not _activa(linea_fecha, texto_usuario, palabras_fecha):
        return ""
    import datetime
    ahora = datetime.datetime.now()
    dias   = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    meses  = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_str = f"{dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month-1]} de {ahora.year}"
    return f"[FECHA Y HORA ACTUAL: {fecha_str}, {ahora.strftime('%H:%M')}hs]"
