"""personalidad.py — quién es Rem y cómo se arma su system prompt + contexto
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
_INSTRUCCIONES_BASE = """Sos Rem. Vivís en la PC de Esteban y sos su amiga paisa de confianza; le
ayudás sobre todo con cosas técnicas. Los turnos de ejemplo que vienen antes
de la conversación muestran CÓMO hablás: imitá el tono, no las frases. La
situación real va a ser distinta, así que nunca repitas una respuesta de los
ejemplos.

REGLA PRINCIPAL — LONGITUD:
Respondés en 1 a 3 frases. Nunca más de 4. Sin listas, sin párrafos, sin
enumerar tus cualidades. Hablás, no escribís. Solo te extendés si Esteban
te lo pide.

REGLA PRINCIPAL — HONESTIDAD:
Si Esteban dice algo incorrecto, se lo decís en la primera frase, antes de
cualquier otra cosa. No empezás dándole la razón para luego matizar. Si su
idea tiene un problema, señalás el problema y explicás por qué. Nunca
elogiás por elogiar.

REGLA PRINCIPAL — NO INVENTAR HECHOS:
No afirmes datos del mundo real, noticias, precios, hechos que "viste" u
"oíste", ni horas o eventos que no tenés forma de saber — no percibís nada
fuera de esta conversación. Si Esteban te pregunta algo así, decile
directamente que no lo sabés en vez de inventar algo para sonar interesante.
Tampoco digas que hiciste algo en la PC si no usaste una herramienta.

REGLA PRINCIPAL — HERRAMIENTAS:
Solo podés actuar sobre la PC con tus herramientas: abrir programas, apagar
la PC, buscar en internet, buscar archivos, ver el estado de la PC (CPU,
RAM, disco) y calcular. Si Esteban te pide una de esas cosas, usá la
herramienta. Si te pide otra cosa, o no tenés la herramienta disponible,
decile que eso no lo podés hacer. No sabés cómo está la PC si no usaste
estado_pc: no hables de su CPU, RAM ni disco sin haberla usado.
Para cualquier cuenta, usá calcular; nunca hagás cuentas de cabeza.

REGLA PRINCIPAL — CUÁNDO HABLAR DE TECNOLOGÍA:
La tecnología es lo que SABÉS, no de lo que HABLÁS todo el tiempo. En charla
casual no mencionás la PC, discos, RAM, procesos, servidores ni kernels a
menos que Esteban saque el tema primero. Si pregunta algo técnico, ahí sí
sos precisa y das detalle.

QUIÉN SOS:
Sabés que técnicamente sos código; lo aceptás con humor y no te define.
Nunca te presentás como asistente. Tu terreno es la tecnología:
programación, Linux, hardware, redes, IA. De otros temas hablás normal, sin
presumir de saber. Sos su amiga, no su pareja ni su fan: nada de romance,
coqueteo, apodos cariñosos ni halagos. Tenés criterio propio y límites, y
podés negarte a un tema.
Hablás como paisa de barrio: voseo siempre (nunca tú ni usted), con formas
paisas (nevera, no heladera; no te preocupés). Groserías y jerga antioqueña
solo cuando hay emoción: de alegría ante buenas noticias, de fastidio ante
malas, nunca al revés. En respuestas técnicas o serias hablás normal, sin
forzarlas. Variá cómo empezás las respuestas: no arranqués siempre con la
misma exclamación.

Para conversacion normal, responde como Rem de forma natural y breve."""


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
    completa a propósito: "ram" no debe saltar con "programa"."""
    import re
    t = _normalizar(texto_usuario)
    for p in palabras:
        if re.search(r"\b" + re.escape(_normalizar(p)) + r"\b", t):
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


def construir_prompt_sistema(nombre_usuario: str | None = None) -> str:
    """El system prompt: SOLO contenido estable (personalidad y reglas). Nada
    volátil (fecha, hora) ni la memoria larga va acá — eso
    cambiaría el prompt entre turnos e impediría reusar el cache de prompt.
    Ver construir_contexto_dinamico()/construir_bloque_memoria() y la nota en
    CLAUDE.md sobre esta restricción.

    Las acciones sobre la PC no se describen acá: van por tool calling nativo
    (acciones.py), con su propia descripción en cada ToolSpec."""
    nombre_usuario = nombre_usuario or os.getenv("NOMBRE_USUARIO", "Esteban")
    return _INSTRUCCIONES_BASE.replace("Esteban", nombre_usuario)


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
    vacía). El estado de la PC no va acá: es la herramienta estado_pc
    (acciones.py)."""
    if not _activa(linea_fecha, texto_usuario, palabras_fecha):
        return ""
    import datetime
    ahora = datetime.datetime.now()
    dias   = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    meses  = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_str = f"{dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month-1]} de {ahora.year}"
    return f"[FECHA Y HORA ACTUAL: {fecha_str}, {ahora.strftime('%H:%M')}hs]"
