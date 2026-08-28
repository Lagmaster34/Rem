import faulthandler
faulthandler.enable()
import time
import asyncio
import json
import os
import random
import speech_recognition as sr
import tkinter as tk
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk
import threading
import subprocess
import psutil
import glob
import shutil
import webbrowser
import sounddevice as sd
import soundfile as sf
import requests
import re
import shlex

#usando groq
# Dependencias necesarias (instalar si falta alguna):
#   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
#   pip install infer-rvc-python
#   pip install soundfile edge-tts

# ── RVC ──────────────────────────────────────────────────────────────
try:
    from infer_rvc_python import BaseLoader
    RVC_DISPONIBLE = True
except Exception as _rvc_err:
    RVC_DISPONIBLE = False
    print(f"[RVC] No se pudo importar infer_rvc_python: {_rvc_err}")

# ── CARGAR VARIABLES DE ENTORNO desde .env ────────────────────────────
import config as _config
_config.cargar_dotenv()
import personalidad

# ── CONFIGURACION ─────────────────────────────────────────────────────
IMAGEN_FONDO    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallhaven-j5zopp_1920x1080.png")
# es-VE-PaolaNeural + rate -8%: salió de una comparación A/B (ver CLAUDE.md,
# "Configuración de voz ganadora") — RVC transfiere timbre pero no prosodia.
VOZ_REM         = os.getenv("VOZ_REM", "es-VE-PaolaNeural")
TTS_RATE        = os.getenv("TTS_RATE", "-8%")
MEMORIA_ARCHIVO         = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_rem.json")
MEMORIA_LARGA_ARCHIVO   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_larga.json")
MEMORIA_SISTEMA_ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_sistema.json")

NOMBRE_USUARIO  = os.getenv("NOMBRE_USUARIO", "Esteban")
CIUDAD          = os.getenv("CIUDAD", "Yarumal")
# Desactivado por defecto: son 5 llamadas al LLM al día sin que el usuario haga nada.
# La regla del proyecto es que la API solo se usa cuando el usuario escribe o habla.
RECORDATORIOS_ACTIVOS = os.getenv("RECORDATORIOS_ACTIVOS", "false").strip().lower() in ("1", "true", "yes", "on")

# extraer_memoria_importante() es una tarea de extracción, no de conversación,
# pero usa el mismo provider principal a través de la abstracción de llm/ (ver
# _drenar_stream_llm) — así sigue funcionando sin importar cuál esté activo.
MEMORIA_EXTRACCION_ACTIVA = os.getenv("MEMORIA_EXTRACCION_ACTIVA", "true").strip().lower() in ("1", "true", "yes", "on")

# Atajos reales de este sistema (Arch + Hyprland) — antes apuntaban a programas
# de GNOME/Debian que no están instalados acá (brave-browser, nautilus,
# gnome-terminal, gnome-calculator). Sin calculadora instalada, esa entrada se
# elimina en vez de inventar un binario que no existe.
COMANDOS = {
    "navegador":  "zen-browser",
    "terminal":   "foot",
    "archivos":   "thunar",   # también está nemo instalado; ajustar si preferís ese
}

# ── RVC REM ──────────────────────────────────────────────────────────
RVC_MODELS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models"
)
os.makedirs(RVC_MODELS_DIR, exist_ok=True)

rvc = None  # se carga en segundo plano para no bloquear la UI

_rvc_dispositivo = "cpu"

def _cargar_rvc():
    global rvc, _rvc_dispositivo
    if not RVC_DISPONIBLE:
        return
    try:
        _rvc_dispositivo = _config.leer_dispositivo_rvc()
        print(f"[RVC] Cargando modelo en {_rvc_dispositivo.upper()}...")
        model_path = os.path.join(RVC_MODELS_DIR, "Rem_600e_6600s", "Rem_600e_6600s.pth")
        index_path = os.path.join(RVC_MODELS_DIR, "Rem_600e_6600s", "Rem.index")

        rmvpe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rmvpe.pt")
        _rvc_tmp = BaseLoader(only_cpu=(_rvc_dispositivo == "cpu"),
                               rmvpe_path=rmvpe_path if os.path.exists(rmvpe_path) else None)
        _rvc_tmp.apply_conf(
            tag="rem",
            file_model=model_path,
            pitch_algo="rmvpe" if os.path.exists(rmvpe_path) else "pm",
            pitch_lvl=4,
            file_index=index_path,
            index_influence=0.75,
            respiration_median_filtering=3,
            envelope_ratio=0.25,
            consonant_breath_protection=0.33,
            resample_sr=0,
        )
        rvc = _rvc_tmp
        f0_used = "rmvpe" if os.path.exists(rmvpe_path) else "pm"
        print(f"✅ Voz de Rem cargada (RVC) — {_rvc_dispositivo.upper()}, f0: {f0_used}")
    except Exception as e:
        print(f"❌ Error cargando RVC: {e}")
        rvc = None

threading.Thread(target=_cargar_rvc, daemon=True).start()


# ── MEMORIA ───────────────────────────────────────────────────────────
def cargar_memoria():
    try:
        with open(MEMORIA_ARCHIVO, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[Rem] Memoria corta: {len(data)} mensajes")
            return data
    except Exception:
        return []

def guardar_memoria():
    try:
        with open(MEMORIA_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Rem] Error guardando memoria corta: {e}")

# ── MEMORIA LARGA ─────────────────────────────────────────────────────
# La carga (cargar_memoria_larga) vive en personalidad.py, compartida con
# bench_chat.py — acá solo se guarda el print de diagnóstico de siempre.
def guardar_memoria_larga():
    try:
        with open(MEMORIA_LARGA_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(memoria_larga, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Rem] Error guardando memoria larga: {e}")

historial     = cargar_memoria()
memoria_larga = personalidad.cargar_memoria_larga()
_total_recuerdos = sum(len(memoria_larga.get(k, [])) for k in ("hechos", "emociones", "eventos", "preferencias"))
print(f"[Rem] Memoria larga: {_total_recuerdos} recuerdos")

# ── MEMORIA DEL SISTEMA ───────────────────────────────────────────────
_MEM_SIS_MAX = 200   # entradas máximas antes de rotar las más antiguas
# La carga (cargar_memoria_sistema) también vive en personalidad.py.

def guardar_memoria_sistema():
    try:
        with open(MEMORIA_SISTEMA_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(memoria_sistema, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Rem] Error guardando memoria_sistema: {e}")

def _rotar_memoria_sistema():
    """Elimina las entradas más antiguas si se supera _MEM_SIS_MAX."""
    total = len(memoria_sistema["archivos"]) + len(memoria_sistema["carpetas"])
    if total <= _MEM_SIS_MAX:
        return
    exceso = total - _MEM_SIS_MAX
    # Eliminar archivos primero (los más usados están al final)
    claves = list(memoria_sistema["archivos"].keys())
    for k in claves[:exceso]:
        del memoria_sistema["archivos"][k]
    # Si aún hay exceso, reducir carpetas
    if len(memoria_sistema["archivos"]) + len(memoria_sistema["carpetas"]) > _MEM_SIS_MAX:
        memoria_sistema["carpetas"] = memoria_sistema["carpetas"][-(_MEM_SIS_MAX // 2):]

def registrar_archivo_sistema(nombre, ruta):
    """Guarda nombre → ruta en la memoria del sistema.

    _ruta_segura() de por medio a propósito: esta memoria no es un resultado
    de una sola vez, se reinyecta tal cual en el prompt de CADA turno futuro
    (construir_contexto_dinamico() en personalidad.py lee memoria_sistema
    directo, sin filtrar nada) — así que una sola entrada indebida acá (p.ej.
    "id_rsa" → ~/.ssh/id_rsa, si algún llamador se olvida de filtrar antes de
    registrar) queda expuesta para siempre, no solo en esa respuesta. Esta es
    la única función que escribe en memoria_sistema["archivos"], así que
    filtrar acá alcanza para todos los llamadores, presentes y futuros."""
    ok, _ = _ruta_segura(ruta, permitir_raiz=True)
    if not ok:
        return
    memoria_sistema["archivos"][nombre] = ruta
    _rotar_memoria_sistema()
    guardar_memoria_sistema()

def registrar_carpeta_sistema(ruta):
    """Añade una ruta de carpeta a la memoria del sistema (sin duplicados).
    Mismo filtro y mismo motivo que registrar_archivo_sistema()."""
    ok, _ = _ruta_segura(ruta, permitir_raiz=True)
    if not ok:
        return
    if ruta not in memoria_sistema["carpetas"]:
        memoria_sistema["carpetas"].append(ruta)
        _rotar_memoria_sistema()
        guardar_memoria_sistema()

def buscar_en_memoria_sistema(nombre):
    """Devuelve la ruta si el archivo/carpeta ya está en memoria. None si no.

    Filtra con _ruta_segura() como segunda capa (registrar_archivo_sistema()
    ya no debería dejar entrar una ruta prohibida, pero esto cubre entradas
    que hayan quedado de antes de este chequeo, o de una edición manual del
    JSON) — y si encuentra una entrada así, la borra en vez de solo omitirla,
    para que no siga apareciendo en construir_contexto_dinamico() tampoco."""
    # Buscar por nombre exacto primero
    if nombre in memoria_sistema["archivos"]:
        ruta = memoria_sistema["archivos"][nombre]
        if not os.path.exists(ruta) or not _ruta_segura(ruta, permitir_raiz=True)[0]:
            del memoria_sistema["archivos"][nombre]   # entrada obsoleta o no permitida
            guardar_memoria_sistema()
        else:
            return ruta
    # Buscar por nombre aproximado
    nombre_lower = nombre.lower()
    for k, v in list(memoria_sistema["archivos"].items()):
        if nombre_lower in k.lower() or nombre_lower in v.lower():
            if os.path.exists(v) and _ruta_segura(v, permitir_raiz=True)[0]:
                return v
    return None

memoria_sistema = personalidad.cargar_memoria_sistema()

# ── LOCKS DE THREADING ────────────────────────────────────────────────
_lock_historial = threading.Lock()
_lock_mem_larga = threading.Lock()
_lock_mem_sis   = threading.Lock()

# El texto de instrucciones (personalidad de Rem) vive en personalidad.py,
# compartido con bench_chat.py — ver construir_prompt_sistema() más abajo.


# ── MEMORIA LARGA: extracción y prompt dinámico ───────────────────────
def extraer_memoria_importante():
    """Extrae hechos relevantes del historial reciente y los guarda en memoria larga.
    Usa el mismo provider principal que la conversación (a través de
    _drenar_stream_llm/get_provider) — si ese provider no tiene su API key
    configurada, get_provider() ya falla con un mensaje claro, que este except
    solo se limita a loguear."""
    if not MEMORIA_EXTRACCION_ACTIVA:
        return
    with _lock_historial:
        mensajes_desde_ultima = len(historial) - memoria_larga.get("mensajes_procesados", 0)
        if mensajes_desde_ultima < 8 or len(historial) < 4:
            return
        fragmento = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}"
            for m in historial[-20:]
        )
        n_historial = len(historial)

    try:
        content = _drenar_stream_llm(
            "Sos un extractor de datos. Respondé únicamente con el JSON pedido, sin texto extra.",
            [{
                "role": "user",
                "content": (
                    f"Analiza esta conversación entre Rem y {NOMBRE_USUARIO}. "
                    f"Extrae solo información nueva y relevante sobre {NOMBRE_USUARIO} para que Rem la recuerde a largo plazo.\n\n"
                    f"Conversación:\n{fragmento}\n\n"
                    "Responde ÚNICAMENTE con este JSON (sin texto extra):\n"
                    "{\n"
                    '  "hechos": ["dato objetivo sobre él (trabajo, estudios, familia, etc.)"],\n'
                    '  "emociones": ["cómo se sentía o algo emocional que mencionó"],\n'
                    '  "eventos": ["algo que pasó o que planea hacer"],\n'
                    '  "preferencias": ["gustos, hobbies, comida, música, juegos, etc."]\n'
                    "}\n"
                    "Si no hay nada nuevo e importante en alguna categoría, deja la lista vacía []."
                )
            }],
        )

        content = content.strip()
        i, j = content.find("{"), content.rfind("}") + 1
        if i == -1 or j <= i:
            return
        data = json.loads(content[i:j])

        nuevos = 0
        with _lock_mem_larga:
            for categoria in ("hechos", "emociones", "eventos", "preferencias"):
                for item in data.get(categoria, []):
                    item = item.strip()
                    if item and item not in memoria_larga[categoria]:
                        memoria_larga[categoria].append(item)
                        nuevos += 1
                memoria_larga[categoria] = memoria_larga[categoria][-40:]
            memoria_larga["mensajes_procesados"] = n_historial
            guardar_memoria_larga()
        if nuevos:
            print(f"[Rem] Memoria larga actualizada: +{nuevos} recuerdos nuevos")

    except Exception as e:
        print(f"[Rem] Error extrayendo memoria: {e}")


# construir_prompt_sistema() y construir_contexto_dinamico() viven en
# personalidad.py, compartidas con bench_chat.py — ver preguntar_groq() más
# abajo, que las llama pasándoles memoria_larga/memoria_sistema.


# ── CONFIRMACION ──────────────────────────────────────────────────────
def _desc_ejecutar_comando(d):
    """Muestra el comando ya tokenizado (shlex, lo mismo que se ejecuta
    después) y el binario real que resuelve el PATH — no el nombre suelto
    que mandó el LLM, que puede no ser lo que realmente corre."""
    comando = d.get("comando", "")
    try:
        tokens = shlex.split(comando)
    except ValueError as e:
        return f"Ejecutar en terminal: {comando}\n    ⚠ sintaxis inválida, se rechazará ({e})"
    if not tokens:
        return "Ejecutar en terminal: (comando vacío, se rechazará)"
    binario = shutil.which(tokens[0]) or "⚠ no encontrado en PATH"
    ok_args, msg_args = _args_permitidos(comando)
    if not ok_args:
        return f"Ejecutar: {' '.join(tokens)}\n    binario real: {binario}\n    ⚠ se rechazará: {msg_args}"
    return f"Ejecutar: {' '.join(tokens)}\n    binario real: {binario}"


def _desc_ruta(etiqueta, clave="ruta"):
    """Descripción para una acción de un solo path: pasa por _ruta_segura()
    (la misma validación real, no una copia) para mostrar el realpath — o el
    motivo del rechazo, si ya se sabe que se va a rechazar."""
    def _f(d):
        ok, resuelta = _ruta_segura(d.get(clave, ""))
        if not ok:
            return f"{etiqueta} (⚠ se rechazará: {resuelta})"
        return f"{etiqueta}: {resuelta}"
    return _f


def _desc_mover_copiar(verbo):
    def _f(d):
        ok_o, origen  = _ruta_segura(d.get("origen", ""))
        ok_d, destino = _ruta_segura(d.get("destino", ""))
        if not ok_o:
            return f"{verbo} (⚠ origen se rechazará: {origen})"
        if not ok_d:
            return f"{verbo} (⚠ destino se rechazará: {destino})"
        return f"{verbo}: {origen} → {destino}"
    return _f


DESCRIPCIONES = {
    "abrir":         lambda d: f"Abrir: {d.get('programa','')}",
    "cerrar":        lambda d: f"Cerrar: {d.get('programa','')}",
    "volumen":       lambda d: f"Cambiar volumen a {d.get('valor',50)}%",
    "apagar":        lambda d: "⚠️ APAGAR la PC",
    "reiniciar":     lambda d: "⚠️ REINICIAR la PC",
    "captura":       lambda d: "Tomar captura de pantalla",
    "buscar":        lambda d: f"Buscar archivo: {d.get('archivo','')}",
    "optimizar":     lambda d: "Optimizar PC (limpiar ~/.cache)",
    "buscar_web":    lambda d: f"Buscar en internet: {d.get('query','')}",
    "escribir":      lambda d: f"Escribir: {d.get('texto','')}",
    "clima":         lambda d: f"Consultar clima de {CIUDAD}",
    "descargar":     lambda d: f"Descargar: {d.get('nombre','')} desde {d.get('url','')}",
    "crear_carpeta":   _desc_ruta("Crear carpeta"),
    "mover_archivo":   _desc_mover_copiar("Mover"),
    "copiar_archivo":  _desc_mover_copiar("Copiar"),
    "eliminar_archivo":_desc_ruta("⚠️ Mover a la papelera"),
    "ejecutar_comando":_desc_ejecutar_comando,
}

def confirmar_accion(datos):
    desc = DESCRIPCIONES.get(datos.get("accion",""), lambda d: datos.get("accion",""))(datos)
    resultado = [False]
    ev = threading.Event()
    def _ask():
        resultado[0] = messagebox.askyesno(
            "Rem te pregunta~ 💙",
            f"¿Quieres que haga esto, mi señor?\n\n➜  {desc}", icon="question")
        ev.set()
    app.after(0, _ask)
    ev.wait(timeout=30)
    return resultado[0]


# ── GROQ ──────────────────────────────────────────────────────────────
def _drenar_stream_llm(system, mensajes):
    """Puente sync→async temporal: responder() lanza un hilo nuevo por cada
    turno (ver más abajo), así que un event loop nuevo y descartable acá es
    más simple y seguro que compartir uno persistente entre turnos — y sobre
    todo no puede ser el loop del AudioWorker (ver _worker_audio): ese vive
    fijo en su propio hilo consumiendo su cola, y un loop de asyncio no es
    thread-safe para usarse desde otro hilo sin run_coroutine_threadsafe.
    Cuando el backend deje de ser Tkinter y pase a ser async nativo, este
    adaptador desaparece y se llama a stream_chat() directo."""
    from llm import Message, TextDelta, get_provider

    provider = get_provider()
    msgs = [Message(role=m["role"], content=m["content"]) for m in mensajes]

    async def _consumir():
        partes = []
        async for chunk in provider.stream_chat(system, msgs):
            if isinstance(chunk, TextDelta):
                partes.append(chunk.text)
        return "".join(partes)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_consumir())
    finally:
        loop.close()


def preguntar_groq(texto):
    texto_con_contexto = f"{personalidad.construir_contexto_dinamico(memoria_sistema)}\n{texto}"

    with _lock_historial:
        historial.append({"role": "user", "content": texto_con_contexto})
        if len(historial) > 60:
            historial.pop(0)
        historial_snap = list(historial)

    c = _drenar_stream_llm(personalidad.construir_prompt_sistema(memoria_larga), historial_snap)

    with _lock_historial:
        historial.append({"role": "assistant", "content": c})
        guardar_memoria()

    threading.Thread(target=extraer_memoria_importante, daemon=True).start()

    return c


# ── ESTADO DE ANIMACION ───────────────────────────────────────────────
_rem_estado = "idle"   # idle | talking | thinking

try:
    from rem_avatar_server import enviar_estado as _avatar_enviar_estado
    from rem_avatar_server import enviar_audio as _avatar_enviar_audio
    _AVATAR_DISPONIBLE = True
except Exception as _e:
    _AVATAR_DISPONIBLE = False
    print(f"[Avatar] No disponible: {_e}")

def set_rem_estado(estado):
    global _rem_estado
    _rem_estado = estado
    if _AVATAR_DISPONIBLE:
        try: _avatar_enviar_estado(estado)
        except Exception: pass

# ── DETECCIÓN DE SENTIMIENTO (keywords con límite de palabra) ────────
_HAPPY_WORDS    = ['jaja','hehe','jeje','feliz','alegr','encanta','genial',
                   'fantástic','maravill','divertid','me gusta','claro que sí',
                   'encantada']
_HAPPY_EMOJIS   = ['😊','😄','🥰','💕']
_SURPRISED_WORDS= ['wow','increíble','sorprend','no lo puedo creer',
                   'impresionante','asombros']
_SAD_WORDS      = ['triste','lament','lo siento mucho','qué pena','condolencia',
                   'lo lamento']
_SAD_EMOJIS     = ['😢','😭']
_ANGRY_WORDS    = ['enoj','molest','irrit','rabia','disgustad','no me gusta']

def _detectar_emocion(texto: str):
    """Retorna (emocion, duracion_seg) o None.
    Usa límite de palabra izquierdo (?<!\\w) para evitar falsos positivos."""
    t = texto.lower()

    def _match(words):
        return any(re.search(r'(?<!\w)' + re.escape(w), t) for w in words)

    if _match(_HAPPY_WORDS) or any(e in texto for e in _HAPPY_EMOJIS):
        return ('happy',    3.5)
    if _match(_SURPRISED_WORDS):
        return ('surprised', 2.0)
    if _match(_SAD_WORDS) or any(e in texto for e in _SAD_EMOJIS):
        return ('sad',       5.0)
    if _match(_ANGRY_WORDS):
        return ('angry',     3.0)
    return None

def _enviar_emocion_temporal(emocion: str, duracion: float):
    """Envía una emoción y restaura idle después de `duracion` segundos."""
    set_rem_estado(emocion)
    def _restaurar():
        if _rem_estado == emocion:  # solo si no cambió
            set_rem_estado('idle')
    threading.Timer(duracion, _restaurar).start()


# ── COLA DE AUDIO — reproduce oraciones en orden, nunca descarta ───────
import queue as _queue
_audio_queue = _queue.Queue()

def _worker_audio():
    """Hilo único que consume la cola y reproduce cada texto en orden."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _sintetizar(texto):
        import numpy as np
        from scipy import signal as sps
        import lipsync

        uid      = threading.get_ident()
        tmp_mp3  = os.path.join(os.path.expanduser("~"), f"rem_tts_{uid}.mp3")
        tmp_wav  = os.path.join(os.path.expanduser("~"), f"rem_tts_{uid}.wav")
        try:
            audio_mp3, palabras = await lipsync.sintetizar_con_timings(texto, VOZ_REM, TTS_RATE)
            with open(tmp_mp3, "wb") as f:
                f.write(audio_mp3)
            timeline = lipsync.construir_timeline(palabras)

            audio, sr_ = sf.read(tmp_mp3)
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
            if sr_ != 16000:
                audio = sps.resample(audio, int(round(len(audio) * 16000 / sr_)))
                sr_ = 16000
            sf.write(tmp_wav, audio.astype(np.float32), sr_)

            if rvc:
                set_rem_estado("thinking")
                t_rvc = time.perf_counter()
                resultados = rvc(audio_files=[tmp_wav], type_output="wav")
                print(f"[RVC] conversión ({_rvc_dispositivo}): {time.perf_counter() - t_rvc:.2f}s")
                ruta_final = resultados[0] if resultados else tmp_wav
            else:
                ruta_final = tmp_wav

            enviado = _AVATAR_DISPONIBLE and _avatar_enviar_audio(ruta_final, timeline)
            if not enviado:
                # Sin cliente WS conectado (avatar no abierto): fallback local.
                # Cuando sí hay avatar, el estado talking/idle lo maneja el navegador.
                data, sr2 = sf.read(ruta_final)
                set_rem_estado("talking")
                sd.stop()
                sd.play(data, sr2)
                sd.wait()
                set_rem_estado("idle")

        except Exception as e:
            print(f"[TTS] {e}")
            set_rem_estado("idle")
        finally:
            for tmp in (tmp_mp3, tmp_wav):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    while True:
        texto = _audio_queue.get()
        if texto is None:       # señal de cierre
            break
        loop.run_until_complete(_sintetizar(texto))
        _audio_queue.task_done()

threading.Thread(target=_worker_audio, daemon=True, name="AudioWorker").start()


# ── TTS ───────────────────────────────────────────────────────────────
def _partir_oraciones(texto):
    """Divide el texto en oraciones para encolar de a una."""
    # Partir solo en . ! ? seguidos de espacio (… se deja unido a la frase)
    partes = re.split(r'(?<=[.!?])\s+', texto.strip())
    # Filtrar vacíos y partes demasiado cortas (< 3 chars)
    return [p.strip() for p in partes if len(p.strip()) >= 3]

def hablar(texto):
    """Encola el texto oración por oración para que el AudioWorker las reproduzca en orden."""
    oraciones = _partir_oraciones(texto)
    if not oraciones:
        oraciones = [texto]    # fallback: encolar todo junto si no hay puntuación
    for oracion in oraciones:
        _audio_queue.put(oracion)


# ── CLIMA ─────────────────────────────────────────────────────────────
_clima_cache = {"dato": None, "ts": 0}
_geo_cache   = {"ciudad": None, "pais": None}

def detectar_ubicacion():
    """Detecta ciudad y país por IP. Cachea el resultado en memoria."""
    if _geo_cache["ciudad"]:
        return _geo_cache["ciudad"], _geo_cache["pais"]
    try:
        r = requests.get("http://ip-api.com/json/?fields=city,regionName,country,status",
                         timeout=5)
        d = r.json()
        if d.get("status") == "success":
            ciudad = d.get("city", CIUDAD)
            pais   = d.get("country", "")
            _geo_cache["ciudad"] = ciudad
            _geo_cache["pais"]   = pais
            print(f"[Geo] Ubicación detectada: {ciudad}, {d.get('regionName','')}, {pais}")
            return ciudad, pais
    except Exception as e:
        print(f"[Geo] No pude detectar ubicación: {e}")
    return CIUDAD, ""

def obtener_clima():
    import time as _t
    ahora = _t.time()
    if _clima_cache["dato"] and ahora - _clima_cache["ts"] < 1800:  # cache 30 min
        return _clima_cache["dato"]
    try:
        ciudad, pais = detectar_ubicacion()
        url = f"https://wttr.in/{ciudad}?format=j1&lang=es"
        r = requests.get(url, timeout=6)
        d = r.json()["current_condition"][0]
        temp    = d["temp_C"]
        desc    = d["weatherDesc"][0]["value"]
        humedad = d["humidity"]
        resultado = f"{ciudad}, {pais}: {temp}°C, {desc}, humedad {humedad}%"
        _clima_cache["dato"] = resultado
        _clima_cache["ts"]   = ahora
        return resultado
    except Exception as e:
        return f"No pude obtener el clima: {e}"


# obtener_info_pc() vive en personalidad.py (la usa construir_contexto_dinamico()).

# ── MONITOR PC ────────────────────────────────────────────────────────
def _loop_monitor_pc():
    while True:
        time.sleep(60)
        try:
            ram = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=1)
            alertas = []
            if ram.percent > 85:
                alertas.append(f"amo, la RAM está al {ram.percent:.0f}% — puede que la PC se empiece a poner lenta.")
            if cpu > 90:
                alertas.append(f"amo, el CPU está al {cpu:.0f}% — algo está consumiendo mucho.")
            for msg in alertas:
                app.after(0, lambda m=msg: agregar_mensaje("Rem", m))
                threading.Thread(target=hablar, args=(msg,), daemon=True).start()
        except Exception:
            pass


# ── DESCARGAR ARCHIVO ─────────────────────────────────────────────────
def descargar_archivo(url, nombre):
    try:
        # os.path.basename() descarta cualquier componente de directorio del
        # nombre (incluido "../../"): sin esto, un nombre como
        # "../../.ssh/authorized_keys" escribía el contenido descargado
        # fuera de Descargas, en cualquier ruta escribible por el usuario.
        nombre = os.path.basename(nombre) or "archivo_rem"
        ruta = os.path.join(
            os.environ.get("XDG_DOWNLOAD_DIR",
                           os.path.join(os.path.expanduser("~"), "Descargas")),
            nombre
        )
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        with open(ruta, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"Descargado como '{nombre}' en tu carpeta de Descargas."
    except Exception as e:
        return f"No pude descargar: {e}"


# ── ACCIONES ──────────────────────────────────────────────────────────
_OPTIMIZAR_DIAS_ANTIGUEDAD = 7  # borra solo lo más viejo que esto, dentro de ~/.cache

def optimizar_pc():
    """Limpia archivos viejos de ~/.cache. NUNCA toca /tmp: en Arch es tmpfs y
    contiene sockets vivos de Wayland/PipeWire/la sesión — borrarlo entero
    (como hacía antes con tempfile.gettempdir()) tumbaría el escritorio."""
    import time
    cache_dir = os.path.realpath(os.path.expanduser("~/.cache"))
    limite = time.time() - _OPTIMIZAR_DIAS_ANTIGUEDAD * 86400
    borrados = 0
    errores  = 0

    if not os.path.isdir(cache_dir):
        return "No encontré ~/.cache para limpiar."

    try:
        for raiz, dirs, archivos in os.walk(cache_dir, topdown=False):
            for nombre in archivos:
                ruta = os.path.join(raiz, nombre)
                try:
                    if os.path.getmtime(ruta) < limite:
                        os.unlink(ruta)
                        borrados += 1
                except Exception:
                    errores += 1   # archivos en uso o sin permisos, se saltan
            for nombre in dirs:
                ruta = os.path.join(raiz, nombre)
                try:
                    if not os.listdir(ruta):
                        os.rmdir(ruta)   # carpetas vacías que quedaron tras borrar su contenido
                except Exception:
                    pass
    except Exception as e:
        return f"Error al acceder a ~/.cache: {e}"

    ram = psutil.virtual_memory()
    ram_libre = round(ram.available / 1024**3, 2)
    return (f"Limpié {borrados} archivo(s) de ~/.cache con más de "
            f"{_OPTIMIZAR_DIAS_ANTIGUEDAD} días ({errores} omitidos por estar en uso). "
            f"RAM libre: {ram_libre} GB")

# ── SEGURIDAD DE ACCIONES ─────────────────────────────────────────────
_ZONA_SEGURA    = os.path.realpath(os.path.expanduser("~"))   # /home/esteban
_DIRS_PROHIBIDOS = ("/etc", "/boot", "/sys", "/proc", "/root", "/bin", "/sbin",
                    "/usr/bin", "/usr/sbin", "/lib", "/lib64")
_CMDS_PERMITIDOS = {"ls", "cat", "mkdir", "cp", "mv", "find", "grep",
                    "echo", "git", "pacman", "systemctl",
                    "df", "free", "top", "ps"}
_METACHAR_PELIGROSOS = ('|', ';', '&&', '||', '`', '$(', '>', '<', '\n')
# find con estos flags ejecuta programas arbitrarios sobre lo que encuentre
# (o borra archivos) — la whitelist por primer token no alcanza para bloquearlo.
_FIND_FLAGS_PELIGROSOS = ('-exec', '-execdir', '-delete')

# Subrutas de $HOME que quedan bloqueadas para mover/copiar/eliminar aunque
# técnicamente estén dentro de _ZONA_SEGURA: credenciales, configuración de
# apps (puede incluir tokens de sesión) y el propio proyecto (.env con las
# API keys, .git con el historial) — este último se calcula desde la
# ubicación real del proyecto, así que protege igual si algún día vuelve a
# vivir dentro de $HOME (como antes de moverse a /mnt/extra, ver CLAUDE.md).
_PROYECTO_DIR = os.path.dirname(os.path.abspath(__file__))
_RUTAS_PROHIBIDAS_HOME = tuple(
    os.path.realpath(os.path.expanduser(p)) for p in (
        "~/.ssh", "~/.gnupg", "~/.config", "~/.local/share/keyrings", "~/.mozilla",
    )
) + (
    os.path.realpath(os.path.join(_PROYECTO_DIR, ".env")),
    os.path.realpath(os.path.join(_PROYECTO_DIR, ".git")),
)

def _ruta_segura(ruta, permitir_raiz=False):
    """Valida que la ruta esté dentro de /home/esteban, no caiga en dirs
    peligrosos ni en la lista negra de rutas sensibles dentro de $HOME.

    Usa os.path.commonpath sobre rutas ya resueltas con realpath en vez de
    startswith: "/home/estebanmalo" no debe pasar como si estuviera dentro
    de "/home/esteban" solo porque el string empieza igual.

    `permitir_raiz`: por defecto, ni siquiera /home/esteban completo pasa
    (ver el chequeo de abajo) — necesario para mover/copiar/eliminar/
    ejecutar_comando, donde operar sobre TODO el home sería catastrófico.
    Pero para lecturas puras como "buscar" (glob.glob, nunca escribe) esa
    restricción no tiene sentido: buscar sin especificar carpeta ya usa
    ~ como base por defecto, y bloquearlo rompería el caso más común de esa
    acción. permitir_raiz=True se lo salta, sin tocar ninguna otra regla
    (fuera de $HOME y la lista negra siguen aplicando igual).
    """
    ruta = os.path.realpath(os.path.expanduser(str(ruta)))
    if os.path.commonpath([ruta, _ZONA_SEGURA]) != _ZONA_SEGURA:
        return False, f"Solo puedo operar dentro de {_ZONA_SEGURA}."
    if ruta == _ZONA_SEGURA and not permitir_raiz:
        # Sin este chequeo, "eliminar/mover/copiar" con ruta="~" pasaba el
        # chequeo de arriba (una ruta es "común" consigo misma) y operaba
        # sobre todo el home — encontrado auditando este código, no pedido
        # explícitamente, pero es la misma clase de problema.
        return False, f"No puedo operar sobre {_ZONA_SEGURA} completo."
    for d in _DIRS_PROHIBIDOS:
        if os.path.commonpath([ruta, d]) == d:
            return False, f"No puedo tocar {d}."
    for d in _RUTAS_PROHIBIDAS_HOME:
        if os.path.commonpath([ruta, d]) == d:
            return False, f"No puedo tocar {d} (ruta protegida)."
    return True, ruta


def _filtrar_rutas_seguras(rutas):
    """Filtra una lista de rutas (p.ej. resultados de glob.glob), quedándose
    solo con las que pasan _ruta_segura(). glob.glob() no sabe nada de la
    lista negra ni del límite de $HOME — validar la CARPETA base de una
    búsqueda no alcanza, porque "**" recursivo igual encuentra archivos
    dentro de ~/.ssh o ~/.config si están debajo de esa base. Sin este
    filtro, buscar "id_rsa" o ".env" devolvía la ruta real dentro de la
    lista negra tal cual."""
    return [r for r in rutas if _ruta_segura(r, permitir_raiz=True)[0]]

_GIT_SUBCOMANDOS_PERMITIDOS = {"status", "log", "diff", "show"}
_SYSTEMCTL_SUBCOMANDOS_PERMITIDOS = {"status", "list-units", "list-unit-files",
                                     "is-active", "is-enabled", "is-failed", "show"}

def _git_permitido(comando):
    """git en la whitelist es una vía de escape: `-c` inyecta configuración
    arbitraria (core.pager/core.editor/diff.external pueden ejecutar
    cualquier programa dentro de ESTE MISMO subprocess.run, sin necesidad de
    un segundo comando) y `--exec-path` apunta git a binarios arbitrarios.
    En vez de enumerar todas las flags peligrosas, el subcomando debe ser
    literalmente el segundo token: como -c/--exec-path son opciones
    GLOBALES (van antes del subcomando en la gramática real de git), exigir
    que el segundo token ya sea uno de la lista blanca las bloquea de raíz.
    El chequeo explícito de abajo es una segunda capa, no la única defensa."""
    try:
        tokens = shlex.split(comando)
    except ValueError as e:
        return False, f"Comando con sintaxis inválida: {e}"
    if len(tokens) < 2 or tokens[1] not in _GIT_SUBCOMANDOS_PERMITIDOS:
        return False, f"Con git solo se permite: {', '.join(sorted(_GIT_SUBCOMANDOS_PERMITIDOS))}."
    if any(t == "-c" or t.startswith("--exec-path") for t in tokens):
        return False, "Esa opción de git no está permitida."
    return True, "git"


def _systemctl_permitido(comando):
    """systemctl sin --user normalmente falla para acciones de estado (pide
    polkit/root), lo que actuaba como red de seguridad implícita — pero con
    --user esas mismas acciones (start/stop/enable/link/edit/mask/...) se
    aplican a la sesión del propio usuario sin pedir ningún privilegio, así
    que esa red desaparece con --user. Se restringe igual con o sin --user:
    solo subcomandos de solo lectura, y nada de -H/--host (evita usarlo
    contra otra máquina)."""
    try:
        tokens = shlex.split(comando)
    except ValueError as e:
        return False, f"Comando con sintaxis inválida: {e}"
    resto = tokens[1:]
    if any(t in ("-H", "--host") or t.startswith("--host=") for t in resto):
        return False, "No se permite systemctl contra un host remoto (-H/--host)."
    subcomando = next((t for t in resto if not t.startswith("-")), None)
    if subcomando not in _SYSTEMCTL_SUBCOMANDOS_PERMITIDOS:
        return False, f"Con systemctl solo se permite: {', '.join(sorted(_SYSTEMCTL_SUBCOMANDOS_PERMITIDOS))}."
    return True, "systemctl"


def _parece_ruta(token, cwd_ejecucion):
    """Heurística para saber si un token de un comando es una ruta: prefijo
    obvio (/, ~, ./, ../, o exactamente . o ..), o si no tiene ninguno,
    que exista de verdad relativo al cwd real de ejecutar_comando — esto
    último es lo que atrapa traversal escondido en un token sin prefijo
    (p.ej. "foo/../../etc/passwd": no empieza con ninguno de los prefijos,
    pero el archivo final SÍ existe, así que igual se marca y se valida)."""
    if token in (".", "..") or token.startswith(("/", "~", "./", "../")):
        return True
    return os.path.exists(os.path.join(cwd_ejecucion, token))


def _resolver_arg_como_shell(token, cwd_ejecucion):
    """Resuelve `token` tal como lo vería el comando real al ejecutarse:
    ejecutar_accion() corre subprocess.run con cwd=~ (ver más abajo), así
    que una ruta relativa —con o sin prefijo— es relativa a ~, no al cwd de
    este proceso de Rem.py (que puede ser cualquier otro). Por eso no basta
    con os.path.realpath(token) directo."""
    expandido = os.path.expanduser(token)
    if os.path.isabs(expandido):
        return expandido
    return os.path.join(cwd_ejecucion, expandido)


def _args_permitidos(comando):
    """_cmd_permitido() validaba el binario pero no sus argumentos — así que
    `cat /mnt/extra/rem/Rem/.env` (o cualquier ruta fuera de $HOME o en la
    lista negra de _ruta_segura) pasaba sin ningún chequeo vía
    ejecutar_comando, esquivando por completo esa protección. Cada token que
    parece una ruta pasa ahora por _ruta_segura() — el mismo límite de
    $HOME y la misma lista negra que mover/copiar/eliminar, ni más ni
    menos. Efecto secundario a tener en cuenta: como _ruta_segura() también
    rechaza operar sobre $HOME completo (ver más arriba), "ls ~" o
    "find . ..." (apuntando literalmente a la raíz del home, no a una
    subcarpeta) quedan bloqueados igual que "eliminar ~" — es la misma
    validación pedida, sin una versión relajada aparte para comandos de
    solo lectura."""
    cwd_ejecucion = os.path.expanduser("~")
    try:
        tokens = shlex.split(comando)
    except ValueError as e:
        return False, f"Comando con sintaxis inválida: {e}"
    for token in tokens[1:]:
        if token.startswith("-"):
            continue   # flags, no rutas
        if not _parece_ruta(token, cwd_ejecucion):
            continue
        candidato = _resolver_arg_como_shell(token, cwd_ejecucion)
        ok, resuelta = _ruta_segura(candidato)
        if not ok:
            return False, f"Argumento '{token}' no permitido: {resuelta}"
    return True, None


def _cmd_permitido(comando):
    """Valida el comando: sin metacaracteres de shell, primer token en lista blanca."""
    if not comando:
        return False, "Comando vacío."
    for mc in _METACHAR_PELIGROSOS:
        if mc in str(comando):
            return False, f"Carácter no permitido en el comando: '{mc}'"
    primer_token = str(comando).split()[0].lstrip("./")
    primer_token = os.path.basename(primer_token)
    if primer_token not in _CMDS_PERMITIDOS:
        return False, f"Comando '{primer_token}' no está en la lista blanca."
    if "rm" in str(comando) and ("-rf" in str(comando) or "-fr" in str(comando)):
        return False, "rm -rf no está permitido."
    if primer_token == "find":
        tokens = str(comando).split()
        for flag in _FIND_FLAGS_PELIGROSOS:
            if flag in tokens:
                return False, f"'{flag}' no está permitido en find (ejecuta o borra lo que encuentre)."
    if primer_token == "git":
        ok, msg = _git_permitido(comando)
        if not ok:
            return False, msg
    elif primer_token == "systemctl":
        ok, msg = _systemctl_permitido(comando)
        if not ok:
            return False, msg
    ok, msg = _args_permitidos(comando)
    if not ok:
        return False, msg
    return True, primer_token


# ── PAPELERA (eliminar_archivo ya no borra, mueve) ─────────────────────
# Papelera estándar de XDG (~/.local/share/Trash) en vez de una carpeta
# propia del proyecto: así lo que "elimina" también aparece en la papelera
# del gestor de archivos del escritorio (Thunar, ver COMANDOS más arriba),
# recuperable con las herramientas normales del sistema.
_TRASH_DIR   = os.path.realpath(os.path.expanduser("~/.local/share/Trash"))
_TRASH_FILES = os.path.join(_TRASH_DIR, "files")
_TRASH_INFO  = os.path.join(_TRASH_DIR, "info")

def _mover_a_papelera(ruta):
    """Mueve `ruta` (ya validada por _ruta_segura) a la papelera de XDG, con
    su .trashinfo (spec: freedesktop.org Trash). Devuelve la ruta final
    dentro de la papelera. Si el nombre ya existe ahí, le agrega un sufijo
    numérico en vez de pisar lo que ya estaba."""
    import datetime
    import urllib.parse

    os.makedirs(_TRASH_FILES, exist_ok=True)
    os.makedirs(_TRASH_INFO, exist_ok=True)

    nombre    = os.path.basename(ruta.rstrip("/")) or "sin_nombre"
    destino   = os.path.join(_TRASH_FILES, nombre)
    info_path = os.path.join(_TRASH_INFO, nombre + ".trashinfo")
    sufijo = 1
    while os.path.exists(destino) or os.path.exists(info_path):
        destino   = os.path.join(_TRASH_FILES, f"{nombre}.{sufijo}")
        info_path = os.path.join(_TRASH_INFO, f"{nombre}.{sufijo}.trashinfo")
        sufijo += 1

    with open(info_path, "w", encoding="utf-8") as f:
        f.write("[Trash Info]\n")
        f.write(f"Path={urllib.parse.quote(ruta)}\n")
        f.write(f"DeletionDate={datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n")

    shutil.move(ruta, destino)
    return destino


_pyautogui_mod = None

def _obtener_pyautogui():
    """Import perezoso de pyautogui: es X11-only y no está instalado en este venv
    (Wayland). Su ausencia no debe impedir que arranque el resto de la app."""
    global _pyautogui_mod
    if _pyautogui_mod is not None:
        return _pyautogui_mod
    try:
        import pyautogui
        _pyautogui_mod = pyautogui
        return pyautogui
    except Exception as e:
        print(f"[pyautogui] no disponible ({e}) — 'escribir' no podrá pegar automáticamente")
        return None


def ejecutar_accion(datos):
    if not confirmar_accion(datos): return "Entendido, mi señor. No haré nada~"
    ac = datos.get("accion")

    if ac == "abrir":
        prog = datos.get("programa","").lower()
        # 1. Busca en atajos configurados
        for k,v in COMANDOS.items():
            if k in prog or prog in k:
                try:
                    subprocess.Popen([v], start_new_session=True)
                    return f"Abriendo {k}!"
                except Exception as e:
                    return f"Error al abrir {k}: {e}"
        # 2. Intenta con xdg-open (URLs, archivos, apps registradas)
        try:
            subprocess.Popen(["xdg-open", prog], start_new_session=True)
            return f"Abriendo {prog}..."
        except Exception:
            pass
        # 3. Intenta ejecutar directamente como comando
        try:
            subprocess.Popen([prog], start_new_session=True)
            return f"Abriendo {prog}..."
        except Exception as e:
            return f"No pude abrir '{prog}'. ¿Está bien escrito el nombre?"

    elif ac == "cerrar":
        prog = datos.get("programa","").lower()
        muertos = []
        for p in psutil.process_iter(["name"]):
            try:
                if prog in p.info["name"].lower():
                    p.kill(); muertos.append(p.info["name"])
            except: pass
        return f"Cerré: {', '.join(muertos)}" if muertos else f"No encontré {prog}."

    elif ac == "volumen":
        val = datos.get("valor", 50)
        # Intentar wpctl (PipeWire), luego pactl (PulseAudio), luego amixer
        for cmd in (
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{val}%"],
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{val}%"],
            ["amixer", "-q", "sset", "Master", f"{val}%"],
        ):
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                return f"Volumen a {val}%"
            except FileNotFoundError:
                continue
            except subprocess.CalledProcessError as e:
                continue
        return f"No pude ajustar el volumen (prueba instalar pulseaudio-utils)"

    elif ac == "apagar":
        subprocess.run(["shutdown", "-h", "+1"], capture_output=True); return "Apagando en 1 minuto!"
    elif ac == "reiniciar":
        subprocess.run(["shutdown", "-r", "+1"], capture_output=True); return "Reiniciando en 1 minuto!"

    elif ac == "captura":
        try:
            escritorio = os.environ.get(
                "XDG_DESKTOP_DIR",
                os.path.join(os.path.expanduser("~"), "Escritorio")
            )
            os.makedirs(escritorio, exist_ok=True)
            ruta = os.path.join(escritorio, "captura_rem.png")
            subprocess.run(["grim", ruta], check=True, capture_output=True)
            return "Captura guardada en el escritorio!"
        except Exception as e: return f"Error: {e}"

    elif ac == "buscar":
        arch = datos.get("archivo","")
        base_datos = datos.get("carpeta", os.path.expanduser("~"))
        # permitir_raiz=True: buscar es de solo lectura (glob.glob, nunca
        # escribe) y por defecto ya busca en todo el home — a diferencia de
        # mover/copiar/eliminar, no hay motivo para bloquear ~ como base.
        ok, base = _ruta_segura(base_datos, permitir_raiz=True)
        if not ok: return base
        # Consultar memoria del sistema primero
        en_memoria = buscar_en_memoria_sistema(arch)
        if en_memoria:
            return f"Ya sé dónde está '{arch}': {en_memoria}"
        try:
            res_crudo = glob.glob(os.path.join(base, "**", arch), recursive=True)
            # base ya pasó por _ruta_segura(), pero eso solo valida el punto
            # de partida — "**" recursivo puede encontrar coincidencias
            # dentro de ~/.ssh, ~/.config, etc. igual. Filtrar acá, no solo
            # confiar en que registrar_archivo_sistema() lo haga después: el
            # mensaje de vuelta con las rutas crudas ya sería una fuga, más
            # allá de lo que quede o no guardado en memoria.
            res = _filtrar_rutas_seguras(res_crudo)
            if res:
                registrar_archivo_sistema(arch, res[0])
            return (f"Encontré {len(res)}:\n" + "\n".join(res[:5])) if res else f"No encontré '{arch}'."
        except Exception as e: return f"Error: {e}"

    elif ac == "optimizar": return optimizar_pc()

    elif ac == "buscar_web":
        q = datos.get("query","")
        webbrowser.open(f"https://www.google.com/search?q={q}")
        return f"Buscando '{q}'!"

    elif ac == "escribir":
        texto = datos.get("texto","")
        pag = _obtener_pyautogui()
        if pag is None:
            return "No puedo pegar el texto: pyautogui no está instalado (X11-only, no disponible en Wayland)."
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            proc.communicate(input=texto.encode('utf-8'))
            time.sleep(0.4)
            pag.hotkey('ctrl', 'v')
            return "Texto escrito!"
        except FileNotFoundError:
            try:
                import pyperclip
                pyperclip.copy(texto)
                time.sleep(0.4)
                pag.hotkey('ctrl', 'v')
                return "Texto escrito! (vía pyperclip)"
            except Exception as e:
                return f"Instala xclip: sudo pacman -S xclip. Error: {e}"
        except Exception as e:
            return f"Error al escribir texto: {e}"

    elif ac == "crear_carpeta":
        ruta = datos.get("ruta","")
        if not ruta: return "No me dijiste la ruta."
        ok, ruta = _ruta_segura(ruta)
        if not ok: return ruta
        try:
            os.makedirs(ruta, exist_ok=True)
            registrar_carpeta_sistema(ruta)
            return f"Carpeta creada: {ruta}"
        except Exception as e: return f"No pude: {e}"

    elif ac == "clima":
        return obtener_clima()

    elif ac == "descargar":
        url    = datos.get("url","")
        nombre = datos.get("nombre","archivo_rem")
        if not url: return "No me diste la URL."
        return descargar_archivo(url, nombre)

    elif ac == "mover_archivo":
        origen  = datos.get("origen","")
        destino = datos.get("destino","")
        ok_o, origen  = _ruta_segura(origen)
        ok_d, destino = _ruta_segura(destino)
        if not ok_o: return origen   # mensaje de error
        if not ok_d: return destino
        try:
            shutil.move(origen, destino)
            nombre = os.path.basename(destino)
            registrar_archivo_sistema(nombre, destino)
            return f"Movido: {origen} → {destino}"
        except Exception as e:
            return f"No pude mover el archivo: {e}"

    elif ac == "copiar_archivo":
        origen  = datos.get("origen","")
        destino = datos.get("destino","")
        ok_o, origen  = _ruta_segura(origen)
        ok_d, destino = _ruta_segura(destino)
        if not ok_o: return origen
        if not ok_d: return destino
        try:
            if os.path.isdir(origen):
                shutil.copytree(origen, destino)
            else:
                shutil.copy2(origen, destino)
            nombre = os.path.basename(destino)
            registrar_archivo_sistema(nombre, destino)
            return f"Copiado: {origen} → {destino}"
        except Exception as e:
            return f"No pude copiar el archivo: {e}"

    elif ac == "eliminar_archivo":
        ruta = datos.get("ruta","")
        ok, ruta = _ruta_segura(ruta)
        if not ok: return ruta
        if not os.path.exists(ruta):
            return f"No existe: {ruta}"
        try:
            destino = _mover_a_papelera(ruta)
            # Limpiar de memoria si estaba registrado
            nombre = os.path.basename(ruta)
            memoria_sistema["archivos"].pop(nombre, None)
            guardar_memoria_sistema()
            return f"Movido a la papelera: {ruta} (recuperable en {destino})"
        except Exception as e:
            return f"No pude mover a la papelera: {e}"

    elif ac == "ejecutar_comando":
        comando = datos.get("comando","").strip()
        ok, msg = _cmd_permitido(comando)
        if not ok: return f"Comando bloqueado: {msg}"
        try:
            args = shlex.split(comando)
        except ValueError as e:
            return f"Comando con sintaxis inválida: {e}"
        try:
            resultado = subprocess.run(
                args, shell=False, capture_output=True,
                text=True, timeout=30,
                cwd=os.path.expanduser("~")
            )
            salida = (resultado.stdout + resultado.stderr).strip()
            return salida[:800] if salida else "(sin salida)"
        except subprocess.TimeoutExpired:
            return "El comando tardó demasiado y lo cancelé."
        except Exception as e:
            return f"Error al ejecutar: {e}"

    return "No entendí esa acción."

def procesar_respuesta(raw):
    try:
        i, j = raw.find("{"), raw.rfind("}") + 1
        if i != -1 and j > i:
            return ejecutar_accion(json.loads(raw[i:j])), True
    except Exception: pass
    return raw, False


# ═══════════════════════════════════════════════════════════════════════
#  UI  —  diseño renovado
# ═══════════════════════════════════════════════════════════════════════

# Paleta
BG0          = "#07070f"
BG1          = "#0e0e1e"
BG_INPUT     = "#14142a"
BUBBLE_REM   = "#12133a"
BUBBLE_YOU   = "#1c1128"
BORDER_REM   = "#3a3a90"
BORDER_YOU   = "#5a2878"
CLR_REM      = "#aabcff"
CLR_YOU      = "#e0ceff"
CLR_ACC      = "#5050c0"
CLR_ACC_LT   = "#8888e0"
CLR_OK       = "#44dd88"
CLR_MIC      = "#cc4488"

FNT_TITLE = ("Segoe UI Semibold", 15)
FNT_MAIN  = ("Segoe UI",          11)
FNT_BOLD  = ("Segoe UI",          11, "bold")
FNT_SM    = ("Segoe UI",           9)
FNT_LABEL = ("Segoe UI",           9, "bold")
FNT_MSG   = ("Segoe UI Emoji",    11)   # soporte de emojis en mensajes

app = tk.Tk()
app.title("Rem — Asistente Virtual")
app.geometry("830x760")
app.minsize(720, 620)
app.configure(bg=BG0)

# ── Fondo con wallpaper ───────────────────────────────────────────────
try:
    _img_raw = Image.open(IMAGEN_FONDO)
    _has_bg  = True
except Exception:
    _has_bg  = False

bg_label = tk.Label(app, bg=BG0)
bg_label.place(x=0, y=0, relwidth=1, relheight=1)
bg_label.lower()

_last_size = [0, 0]

def actualizar_fondo(event=None):
    if not _has_bg: return
    w, h = app.winfo_width(), app.winfo_height()
    if w < 10 or (w == _last_size[0] and h == _last_size[1]): return
    _last_size[0], _last_size[1] = w, h
    img = _img_raw.resize((w, h), Image.LANCZOS).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (4, 4, 14, 215))
    img = Image.alpha_composite(img, overlay).convert("RGB")
    ph = ImageTk.PhotoImage(img)
    bg_label.config(image=ph); bg_label.image = ph

app.bind("<Configure>", actualizar_fondo)


# ── Header ────────────────────────────────────────────────────────────
hdr = tk.Frame(app, bg="#09091a", pady=10)
hdr.pack(fill=tk.X)

tk.Label(hdr, text="✿", font=("Segoe UI", 18),
         bg="#09091a", fg=CLR_ACC_LT).pack(side=tk.LEFT, padx=(18,6))
tk.Label(hdr, text="Rem", font=FNT_TITLE,
         bg="#09091a", fg=CLR_REM).pack(side=tk.LEFT)
tk.Label(hdr, text="Asistente Virtual", font=FNT_SM,
         bg="#09091a", fg="#555577").pack(side=tk.LEFT, padx=8)

estado_var = tk.StringVar(value="● En línea")
lbl_estado = tk.Label(hdr, textvariable=estado_var, font=FNT_SM,
                      bg="#09091a", fg=CLR_OK)
lbl_estado.pack(side=tk.RIGHT, padx=18)

# línea decorativa degradada
tk.Frame(app, bg=CLR_ACC, height=2).pack(fill=tk.X)

tk.Frame(app, bg="#1a1a30", height=1).pack(fill=tk.X, padx=8, pady=(4,0))


# ── Chat: canvas con fondo de Rem y burbujas flotantes ───────────────
chat_outer = tk.Frame(app, bg=BG0)
chat_outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

chat_canvas = tk.Canvas(chat_outer, bg=BG0, highlightthickness=0, bd=0)
chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

chat_sb = tk.Scrollbar(chat_outer, orient="vertical",
                        bg=BG1, troughcolor=BG0, activebackground=CLR_ACC,
                        width=6, relief=tk.FLAT)
chat_sb.pack(side=tk.RIGHT, fill=tk.Y)
chat_canvas.configure(yscrollcommand=chat_sb.set)

# ── Fondo de Rem en el canvas ─────────────────────────────────────────
_chat_bg_photo = None
_chat_bg_id    = None
_chat_y        = [10]        # posición Y acumulada para el próximo mensaje
_chat_windows  = []          # (canvas_window_id, is_right_aligned)

def _preparar_bg_chat(event=None):
    global _chat_bg_photo, _chat_bg_id
    w = chat_canvas.winfo_width()
    h = chat_canvas.winfo_height()
    if w < 10 or not _has_bg:
        return
    try:
        img = _img_raw.resize((w, h), Image.LANCZOS).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (4, 4, 18, 178))   # oscurecer un poco
        img = Image.alpha_composite(img, overlay).convert("RGB")
        _chat_bg_photo = ImageTk.PhotoImage(img)
        if _chat_bg_id is None:
            _chat_bg_id = chat_canvas.create_image(0, 0, anchor="nw",
                                                    image=_chat_bg_photo)
            chat_canvas.tag_lower(_chat_bg_id)
        else:
            chat_canvas.itemconfig(_chat_bg_id, image=_chat_bg_photo)
        _sync_bg_chat()
        # Reposicionar mensajes alineados a la derecha si cambió el ancho
        _reposicionar_derecha()
    except Exception as e:
        print(f"[BG Chat] {e}")

def _sync_bg_chat(*args):
    if _chat_bg_id is not None:
        try:
            y = chat_canvas.canvasy(0)
            chat_canvas.coords(_chat_bg_id, 0, y)
        except Exception:
            pass

def _reposicionar_derecha():
    cw = chat_canvas.winfo_width()
    if cw < 10:
        return
    for wid, is_right in _chat_windows:
        if is_right:
            try:
                chat_canvas.itemconfig(wid, anchor="ne")
                coords = chat_canvas.coords(wid)
                if coords:
                    chat_canvas.coords(wid, cw - 16, coords[1])
            except Exception:
                pass

def _yview_chat(*args):
    chat_canvas.yview(*args)
    _sync_bg_chat()

chat_sb.configure(command=_yview_chat)
chat_canvas.bind("<Configure>", _preparar_bg_chat)

def _mousewheel(e):
    chat_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    _sync_bg_chat()

chat_canvas.bind("<MouseWheel>", _mousewheel)


def agregar_mensaje(quien, texto):
    is_rem = (quien == "Rem")
    cw = max(chat_canvas.winfo_width(), 560)

    x_pos     = 16 if is_rem else cw - 16
    tk_anchor = "nw" if is_rem else "ne"
    is_right  = not is_rem

    # ── Nombre ──
    nombre    = "✿ Rem" if is_rem else "Tú"
    clr_nom   = CLR_ACC_LT if is_rem else "#9966cc"
    lbl_nom = tk.Label(chat_canvas, text=nombre, font=FNT_LABEL,
                       bg=BG0, fg=clr_nom, padx=4)
    lbl_nom.bind("<MouseWheel>", _mousewheel)
    wid_nom = chat_canvas.create_window(x_pos, _chat_y[0],
                                         anchor=tk_anchor, window=lbl_nom)
    lbl_nom.update_idletasks()
    _chat_windows.append((wid_nom, is_right))
    _chat_y[0] += lbl_nom.winfo_reqheight() + 2

    # ── Burbuja ──
    bg_bbl = BUBBLE_REM if is_rem else BUBBLE_YOU
    fg_bbl = CLR_REM    if is_rem else CLR_YOU

    bbl = tk.Frame(chat_canvas, bg=bg_bbl, padx=14, pady=9)
    lbl = tk.Label(bbl, text=texto, font=FNT_MSG,
                   bg=bg_bbl, fg=fg_bbl,
                   wraplength=400,
                   justify=tk.LEFT if is_rem else tk.RIGHT)
    lbl.pack()

    for w in (bbl, lbl):
        w.bind("<MouseWheel>", _mousewheel)

    wid_bbl = chat_canvas.create_window(x_pos, _chat_y[0],
                                          anchor=tk_anchor, window=bbl)
    bbl.update_idletasks()
    _chat_windows.append((wid_bbl, is_right))
    _chat_y[0] += bbl.winfo_reqheight() + 12

    # Actualizar región de scroll y bajar al fondo
    chat_canvas.configure(scrollregion=(0, 0, cw, _chat_y[0] + 20))
    chat_canvas.yview_moveto(1.0)


# ── Input ─────────────────────────────────────────────────────────────
tk.Frame(app, bg=CLR_ACC, height=1).pack(fill=tk.X, padx=8)

inp_frame = tk.Frame(app, bg="#0a0a18", pady=8)
inp_frame.pack(fill=tk.X, padx=8)

entrada_var = tk.StringVar()
entrada = tk.Entry(
    inp_frame, textvariable=entrada_var,
    font=FNT_MAIN, bg=BG_INPUT, fg="white",
    insertbackground=CLR_ACC_LT,
    relief=tk.FLAT, bd=0,
    highlightthickness=1,
    highlightbackground="#2a2a50",
    highlightcolor=CLR_ACC,
)
entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9, padx=(0,8))

btn_send = tk.Button(
    inp_frame, text="Enviar", font=FNT_BOLD,
    bg=CLR_ACC, fg="white", relief=tk.FLAT,
    activebackground=CLR_ACC_LT, activeforeground="white",
    cursor="hand2", padx=16, pady=4,
    bd=0
)
btn_send.pack(side=tk.RIGHT, padx=(0,6))

btn_mic = tk.Button(
    inp_frame, text="🎤", font=("Segoe UI", 14),
    bg=CLR_MIC, fg="white", relief=tk.FLAT,
    activebackground="#ee55aa", activeforeground="white",
    cursor="hand2", width=3, pady=4,
    bd=0
)
btn_mic.pack(side=tk.RIGHT, padx=(0,4))


# ── Lógica de respuesta ───────────────────────────────────────────────
def set_estado(txt, color=CLR_OK):
    estado_var.set(txt)
    lbl_estado.config(fg=color)

def responder(texto_usuario):
    app.after(0, lambda t=texto_usuario: agregar_mensaje("Tú", t))
    app.after(0, lambda: set_estado("● Pensando...", "#ffcc44"))
    set_rem_estado("thinking")
    try:
        raw = preguntar_groq(texto_usuario)
        resultado, _ = procesar_respuesta(raw)
        app.after(0, lambda r=resultado: agregar_mensaje("Rem", r))
        # Detectar emoción y enviarla antes de hablar
        emoc = _detectar_emocion(resultado)
        if emoc:
            threading.Thread(
                target=_enviar_emocion_temporal, args=emoc, daemon=True
            ).start()
        threading.Thread(target=hablar, args=(resultado,), daemon=True).start()
    except Exception as e:
        app.after(0, lambda e=e: agregar_mensaje("Rem", f"Algo salió mal: {e}"))
        set_rem_estado("idle")
    finally:
        app.after(0, lambda: set_estado("● En línea", CLR_OK))
        # idle lo restaura hablar() al terminar el audio

def enviar():
    txt = entrada_var.get().strip()
    if txt:
        entrada_var.set("")
        threading.Thread(target=responder, args=(txt,), daemon=True).start()

btn_send.config(command=enviar)
entrada.bind("<Return>", lambda _: enviar())

def escuchar():
    # Todas las actualizaciones de UI se hacen via app.after() para ser thread-safe
    def _ui(fn): app.after(0, fn)

    _ui(lambda: btn_mic.config(state=tk.DISABLED))
    _ui(lambda: set_estado("● Escuchando...", "#44aaff"))

    rec = sr.Recognizer()
    rec.energy_threshold        = 300
    rec.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as src:
            rec.adjust_for_ambient_noise(src, duration=0.3)
            _ui(lambda: set_estado("● Grabando...", "#ff4488"))
            audio = rec.listen(src, timeout=6, phrase_time_limit=12)

        _ui(lambda: set_estado("● Procesando...", "#ffcc44"))
        txt = rec.recognize_google(audio, language="es-ES")
        threading.Thread(target=responder, args=(txt,), daemon=True).start()

    except sr.WaitTimeoutError:
        _ui(lambda: agregar_mensaje("Rem", "No te escuché... ¿me dijiste algo, mi señor?~"))
        _ui(lambda: set_estado("● En línea", CLR_OK))
    except sr.UnknownValueError:
        _ui(lambda: agregar_mensaje("Rem", "No entendí lo que dijiste, ¿puedes repetirlo?~"))
        _ui(lambda: set_estado("● En línea", CLR_OK))
    except OSError:
        _ui(lambda: agregar_mensaje("Rem", "No encuentro el micrófono. ¿Está conectado y configurado en Windows?"))
        _ui(lambda: set_estado("● Sin micrófono", "#ff4444"))
    except Exception as e:
        _ui(lambda: agregar_mensaje("Rem", f"Error al escuchar: {e}"))
        _ui(lambda: set_estado("● En línea", CLR_OK))
    finally:
        _ui(lambda: btn_mic.config(state=tk.NORMAL))

btn_mic.config(command=lambda: threading.Thread(target=escuchar, daemon=True).start())


app.after(200,  actualizar_fondo)    # primer render del fondo
app.after(400,  _preparar_bg_chat)   # fondo de Rem en el chat

def _loop_sync_bg_chat():
    """Mantiene el fondo siempre alineado con el scroll del chat."""
    _sync_bg_chat()
    app.after(60, _loop_sync_bg_chat)

app.after(500, _loop_sync_bg_chat)


# ── RECORDATORIOS AUTOMÁTICOS ────────────────────────────────────────
# Edita esta lista para añadir, quitar o cambiar recordatorios.
# "hora" en formato "HH:MM" — "contexto" es lo que Rem recibe para generar el mensaje.
RECORDATORIOS = [
    {"hora": "08:00", "contexto": f"Son las 8am. Salúdale a {NOMBRE_USUARIO} para que empiece el día, de forma cariñosa y natural, como lo harías tú."},
    {"hora": "14:00", "contexto": f"Son las 2pm. Pregúntale a {NOMBRE_USUARIO} si ya comió algo hoy. Sé tú misma, no formal."},
    {"hora": "18:00", "contexto": f"Son las 6pm. Dile algo a {NOMBRE_USUARIO}, puede ser cualquier cosa: cómo va el día, si está bien, lo que se te ocurra."},
    {"hora": "22:00", "contexto": f"Son las 10pm. Coméntale a {NOMBRE_USUARIO} la hora, como si lo notaras tú sola. Natural, sin drama."},
    {"hora": "00:30", "contexto": f"Es medianoche pasada. Dile algo a {NOMBRE_USUARIO} sobre que es tarde. Con tu estilo, sin sermón."},
]

_recordatorios_disparados = set()

def _loop_recordatorios():
    import datetime
    ahora       = datetime.datetime.now()
    hora_actual = ahora.strftime("%H:%M")
    hoy         = str(ahora.date())

    for rec in RECORDATORIOS:
        clave = f"{rec['hora']}_{hoy}"
        if hora_actual == rec["hora"] and clave not in _recordatorios_disparados:
            _recordatorios_disparados.add(clave)
            # Limpiar disparos de días anteriores
            viejos = {k for k in _recordatorios_disparados if not k.endswith(hoy)}
            _recordatorios_disparados.difference_update(viejos)
            threading.Thread(
                target=_disparar_recordatorio,
                args=(rec["contexto"],),
                daemon=True
            ).start()

    app.after(30_000, _loop_recordatorios)   # revisar cada 30 segundos

def _disparar_recordatorio(contexto):
    try:
        raw      = preguntar_groq(contexto)
        resultado, _ = procesar_respuesta(raw)
        app.after(0, lambda r=resultado: agregar_mensaje("Rem", r))
        hablar(resultado)
    except Exception as e:
        print(f"[Recordatorio] Error: {e}")

if RECORDATORIOS_ACTIVOS:
    app.after(15_000, _loop_recordatorios)   # arrancar 15s después del inicio


# ── Bienvenida ────────────────────────────────────────────────────────
# Frases fijas, sin llamar al LLM: la API solo debe usarse cuando el usuario
# escribe o habla, nunca en el arranque de la app.
_SALUDOS_BIENVENIDA = [
    "¡Hola, mi señor! Aquí estoy, lista para ti~",
    "Bienvenido de nuevo, {nombre}. Rem te esperaba.",
    "¡{nombre}! Qué alegría verte, ya estoy lista.",
    "Aquí Rem, reportándose para lo que necesites, {nombre}~",
    "Volviste. Rem se pone feliz cuando eso pasa, {nombre}.",
]

def bienvenida():
    time.sleep(1)
    msg = random.choice(_SALUDOS_BIENVENIDA).format(nombre=NOMBRE_USUARIO)
    app.after(0, lambda m=msg: agregar_mensaje("Rem", m))
    threading.Thread(target=hablar, args=(msg,), daemon=True).start()

threading.Thread(target=bienvenida, daemon=True).start()
threading.Thread(target=_loop_monitor_pc, daemon=True).start()

# ── Avatar 3D ─────────────────────────────────────────────────────────
if _AVATAR_DISPONIBLE and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rem.vrm")):
    from rem_avatar_server import iniciar_avatar
    _sw = app.winfo_screenwidth()
    _sh = app.winfo_screenheight()
    threading.Thread(
        target=iniciar_avatar,
        args=(_sw, _sh),
        daemon=True,
        name="AvatarInit"
    ).start()
    print("[Avatar] Iniciando avatar 3D de Rem…")
else:
    print("[Avatar] rem.vrm no encontrado o servidor no disponible — sin avatar")


# ── Cierre limpio ─────────────────────────────────────────────────────
def on_close():
    guardar_memoria()
    if _AVATAR_DISPONIBLE:
        try:
            from rem_avatar_server import cerrar_avatar
            cerrar_avatar()
        except Exception: pass
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)
app.mainloop()
