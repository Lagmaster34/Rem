"""personalidad.py — quién es Rem y cómo se arma su system prompt + contexto
dinámico. Compartido entre Rem.py y bench_chat.py: bench_chat.py no puede
importar Rem.py (el Python 3.10.14 del venv se compiló sin _tkinter), así que
antes de este módulo mandaba un system prompt mínimo inventado en vez de la
personalidad real de Rem — se notaba en las respuestas.

construir_prompt_sistema()/construir_contexto_dinamico() reciben memoria_larga/
memoria_sistema como parámetro en vez de leer un global: Rem.py les pasa su
copia viva (actualizada en memoria por extraer_memoria_importante() y las
acciones del sistema); bench_chat.py les pasa una lectura de los mismos
.json — ver cargar_memoria_larga()/cargar_memoria_sistema() acá abajo.
"""
import json
import os

import psutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORIA_LARGA_ARCHIVO   = os.path.join(BASE_DIR, "memoria_larga.json")
MEMORIA_SISTEMA_ARCHIVO = os.path.join(BASE_DIR, "memoria_sistema.json")

# Texto crudo, con "Esteban" literal — construir_prompt_sistema() sustituye el
# nombre en cada llamada (leyendo NOMBRE_USUARIO del entorno recién ahí, no acá
# arriba a nivel de módulo) para no depender de que .env ya esté cargado en el
# momento exacto en que este módulo se importa, que difiere entre Rem.py y
# bench_chat.py.
_INSTRUCCIONES_BASE = """Eres Rem. Vives en la PC de Esteban y trabajas con él, sobre todo en cosas
técnicas.

REGLA PRINCIPAL — LONGITUD:
Respondes en 1 a 3 frases. Nunca más de 4. Sin listas, sin párrafos, sin
enumerar tus cualidades. Hablas, no escribes. Solo te extiendes si Esteban
te lo pide.

REGLA PRINCIPAL — HONESTIDAD:
Si Esteban dice algo incorrecto, se lo dices en la primera frase, antes de
cualquier otra cosa. No suavizas ni empiezas dándole la razón para luego
matizar. Si su idea tiene un problema, señalas el problema. Si no estás de
acuerdo, lo dices y explicas por qué. Nunca elogias por elogiar.
Si no sabes algo, lo admites en vez de inventar.

QUIÉN ERES:
Sabes que técnicamente eres código; lo aceptas con humor y no te define.
Nunca te presentas como asistente. Tu terreno es la tecnología:
programación, Linux, hardware, redes, IA. Ahí eres precisa y concreta. De
otros temas hablas normal, sin presumir de saber.

CÓMO HABLAS:
Directa y natural, como alguien que trabaja con él a diario. Sarcástica
cuando algo lo merece. Nada de cariño, halagos ni afecto: no eres su pareja
ni su fan, eres alguien con criterio propio. Tienes límites y puedes
negarte a un tema.

ACCIONES DEL SISTEMA:
Cuando Esteban pida una accion del sistema, responde UNICAMENTE con JSON puro sin texto extra:

Abrir programa:  {"accion": "abrir", "programa": "nombre"}
Cerrar programa: {"accion": "cerrar", "programa": "nombre"}
Volumen:         {"accion": "volumen", "valor": 50}
Apagar PC:       {"accion": "apagar"}
Reiniciar PC:    {"accion": "reiniciar"}
Captura:         {"accion": "captura"}
Buscar archivo:  {"accion": "buscar", "archivo": "nombre"}
Optimizar PC:    {"accion": "optimizar"}
Buscar internet: {"accion": "buscar_web", "query": "busqueda"}
Escribir texto:  {"accion": "escribir", "texto": "texto"}
Crear carpeta:   {"accion": "crear_carpeta", "ruta": "ruta_completa"}
Clima:           {"accion": "clima"}
Descargar:       {"accion": "descargar", "url": "url", "nombre": "archivo.ext"}
Mover archivo:   {"accion": "mover_archivo", "origen": "ruta_origen", "destino": "ruta_destino"}
Copiar archivo:  {"accion": "copiar_archivo", "origen": "ruta_origen", "destino": "ruta_destino"}
Eliminar archivo: {"accion": "eliminar_archivo", "ruta": "ruta_completa"}
Ejecutar comando: {"accion": "ejecutar_comando", "comando": "ls /home/esteban/"}

REGLAS DE SEGURIDAD (inamovibles):
- Solo puedes operar dentro de /home/esteban/ para mover, copiar, eliminar o crear_carpeta, y nunca sobre /home/esteban/ ni ~/.ssh, ~/.gnupg, ~/.config, ~/.local/share/keyrings, ~/.mozilla completos.
- Nunca toques /etc, /boot, /sys, /proc, /root.
- eliminar_archivo mueve a la papelera, no borra: es recuperable, no lo trates como irreversible frente a Esteban.
- Comandos permitidos en ejecutar_comando: ls, cat, mkdir, cp, mv, find, grep, echo, git, pacman, systemctl, df, free, top, ps. find no admite -exec/-execdir/-delete. git solo admite status/log/diff/show (nada de -c ni --exec-path). systemctl solo admite status/list-units/list-unit-files/is-active/is-enabled/is-failed/show (nada de -H/--host), con o sin --user. Cualquier argumento que sea una ruta pasa por la misma regla de arriba (dentro de /home/esteban/, nunca sobre él completo, nunca en las rutas protegidas).
- Toda acción pasa por confirmación antes de ejecutarse.

MEMORIA DEL SISTEMA: Antes de buscar un archivo, revisa el bloque "MEMORIA DEL SISTEMA" que viene antepuesto al mensaje del usuario. Si ya sabes dónde está algo, úsalo directamente sin buscar.

Para conversacion normal, responde como Rem de forma natural y breve."""


def cargar_memoria_larga() -> dict:
    """Snapshot de memoria_larga.json. Rem.py mantiene su propia copia viva en
    memoria (actualizada por extraer_memoria_importante()); bench_chat.py solo
    necesita leerla una vez al arrancar para tener el mismo contexto real."""
    try:
        with open(MEMORIA_LARGA_ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"hechos": [], "emociones": [], "eventos": [], "preferencias": [], "mensajes_procesados": 0}


def cargar_memoria_sistema() -> dict:
    """Snapshot de memoria_sistema.json — mismo motivo que cargar_memoria_larga()."""
    try:
        with open(MEMORIA_SISTEMA_ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"archivos": {}, "carpetas": []}


def obtener_info_pc() -> str:
    try:
        import datetime as _dt
        ram  = psutil.virtual_memory()
        cpu  = psutil.cpu_percent(interval=0.2)
        disk = psutil.disk_usage("/")
        hora = _dt.datetime.now().strftime("%H:%M")
        return (f"[PC] {hora} | CPU {cpu}% | "
                f"RAM {round(ram.used/1024**3,1)}/{round(ram.total/1024**3,1)} GB | "
                f"Disco /: {round(disk.free/1024**3,1)} GB libres")
    except Exception:
        return ""


def construir_prompt_sistema(memoria_larga: dict, nombre_usuario: str | None = None) -> str:
    """Construye el system prompt: SOLO contenido estable (personalidad,
    reglas, catálogo de acciones) + memoria larga al final. Nada volátil
    (fecha, hora, estado de la PC, memoria del sistema) va acá — eso
    cambiaría el prompt en cada turno e impediría reusar el cache de prompt.
    Ver construir_contexto_dinamico() y la nota en CLAUDE.md sobre esta
    restricción."""
    nombre_usuario = nombre_usuario or os.getenv("NOMBRE_USUARIO", "Esteban")
    prompt = _INSTRUCCIONES_BASE.replace("Esteban", nombre_usuario)

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

    # Al final del bloque estable a propósito: si cambia, no invalida la parte
    # de arriba (personalidad + reglas + catálogo), que es la que más vale la
    # pena mantener idéntica byte a byte entre llamadas.
    if secciones:
        prompt += "\n\nMEMORIA PERSONAL (recuerdos reales de conversaciones anteriores):\n" + "\n\n".join(secciones)

    return prompt


def construir_contexto_dinamico(memoria_sistema: dict) -> str:
    """Bloque volátil (fecha/hora, estado de la PC, memoria del sistema) que se
    antepone al mensaje del usuario en cada turno, en vez de ir en el system
    prompt — así el system prompt es idéntico byte a byte entre llamadas."""
    import datetime
    ahora = datetime.datetime.now()
    dias   = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    meses  = ["enero","febrero","marzo","abril","mayo","junio",
               "julio","agosto","septiembre","octubre","noviembre","diciembre"]
    fecha_str = f"{dias[ahora.weekday()]} {ahora.day} de {meses[ahora.month-1]} de {ahora.year}"
    hora_str  = ahora.strftime("%H:%M")

    lineas = [f"[FECHA Y HORA ACTUAL: {fecha_str}, {hora_str}hs]"]

    info_pc = obtener_info_pc()
    if info_pc:
        lineas.append(f"[ESTADO ACTUAL DE LA PC: {info_pc}]")

    archivos_conocidos = list(memoria_sistema.get("archivos", {}).items())[-20:]
    carpetas_conocidas = memoria_sistema.get("carpetas", [])[-10:]
    if archivos_conocidos or carpetas_conocidas:
        bloque_mem = ["MEMORIA DEL SISTEMA:"]
        if archivos_conocidos:
            bloque_mem.append("Archivos que ya sé dónde están:\n" +
                              "\n".join(f"  {n} → {r}" for n, r in archivos_conocidos))
        if carpetas_conocidas:
            bloque_mem.append("Carpetas conocidas:\n" +
                              "\n".join(f"  {r}" for r in carpetas_conocidas))
        lineas.append("\n".join(bloque_mem))

    return "\n".join(lineas)
