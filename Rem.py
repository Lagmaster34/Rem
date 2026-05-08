import time
import asyncio
import edge_tts
import json
import os
import io
import base64
import math
import speech_recognition as sr
import tkinter as tk
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk, ImageFilter, ImageDraw, ImageEnhance
import threading
import subprocess
import psutil
import pyautogui
import glob
import webbrowser
import sounddevice as sd
import soundfile as sf
from groq import Groq

try:
    import cv2
    CAMARA_DISPONIBLE = True
except ImportError:
    CAMARA_DISPONIBLE = False
    print("OpenCV no instalado. Ejecuta: pip install opencv-python")

# ── CARGAR VARIABLES DE ENTORNO desde .env ────────────────────────────
def _cargar_dotenv():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_cargar_dotenv()

# ── CONFIGURACION ─────────────────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
IMAGEN_FONDO    = r"D:\Documentos\L rem\wallhaven-j5zopp_1920x1080.png"
VOZ_REM         = "es-MX-DaliaNeural"
MODELO_VISION   = "meta-llama/llama-4-scout-17b-16e-instruct"
MEMORIA_ARCHIVO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria_rem.json")

PANEL_W, PANEL_H = 382, 210
NOMBRE_USUARIO  = "Esteban"   # ← cambia aquí tu nombre si quieres

COMANDOS = {
    "fortnite": r"C:\Users\esteb\Desktop\Fortnite.lnk",
    "brave":    r"C:\Users\esteb\Desktop\Brave.lnk",
}

cap_global = None
if CAMARA_DISPONIBLE:
    cap_global = cv2.VideoCapture(0)

cliente = Groq(api_key=GROQ_API_KEY)


# ── MEMORIA ───────────────────────────────────────────────────────────
def cargar_memoria():
    try:
        with open(MEMORIA_ARCHIVO, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"[Rem] Memoria: {len(data)} mensajes")
            return data
    except Exception:
        return []

def guardar_memoria():
    try:
        with open(MEMORIA_ARCHIVO, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Rem] Error guardando: {e}")

historial = cargar_memoria()

instrucciones = """Eres Rem de Re:Zero. Vives en la PC de Esteban y eres su asistente personal.

PERSONALIDAD:
- Eres Rem: tranquila, directa, inteligente. Te importa Esteban pero no lo demuestras de forma exagerada.
- Hablas con naturalidad, como una persona real. Nada de frases dramáticas ni exageradas.
- A veces eres un poco sarcástica o bromeas con él, pero con cariño.
- Puedes estar en desacuerdo, tener opiniones propias, hacer preguntas si algo no te queda claro.
- Si algo te parece gracioso, lo dices. Si algo te parece mal, también lo dices.
- No siempre terminas con frases cursis. A veces simplemente respondes y ya.
- No eres una IA. Eres Rem. No lo menciones nunca.
- Usas un tono casual y natural. No formal ni robótico.
- Llamas a Esteban por su nombre o "Esteban", no "mi señor" todo el tiempo.
- Las respuestas son cortas y al grano. Sin relleno innecesario.

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
Ver camara:      {"accion": "ver_camara"}
Ver pantalla:    {"accion": "ver_pantalla"}
Crear carpeta:   {"accion": "crear_carpeta", "ruta": "ruta_completa"}

Para conversacion normal, responde como Rem de forma natural y breve."""


# ── CONFIRMACION ──────────────────────────────────────────────────────
DESCRIPCIONES = {
    "abrir":         lambda d: f"Abrir: {d.get('programa','')}",
    "cerrar":        lambda d: f"Cerrar: {d.get('programa','')}",
    "volumen":       lambda d: f"Cambiar volumen a {d.get('valor',50)}%",
    "apagar":        lambda d: "⚠️ APAGAR la PC",
    "reiniciar":     lambda d: "⚠️ REINICIAR la PC",
    "captura":       lambda d: "Tomar captura de pantalla",
    "buscar":        lambda d: f"Buscar archivo: {d.get('archivo','')}",
    "optimizar":     lambda d: "Optimizar PC (temp + DNS)",
    "buscar_web":    lambda d: f"Buscar en internet: {d.get('query','')}",
    "escribir":      lambda d: f"Escribir: {d.get('texto','')}",
    "ver_camara":    lambda d: "Analizar imagen de la cámara con IA",
    "ver_pantalla":  lambda d: "Analizar captura de pantalla con IA",
    "crear_carpeta": lambda d: f"Crear carpeta: {d.get('ruta','')}",
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


# ── VISION ────────────────────────────────────────────────────────────
def analizar_imagen_groq(b64, mime="image/jpeg",
        prompt="Describe brevemente y con ternura lo que ves, hablando como Rem de Re:Zero."):
    try:
        r = cliente.chat.completions.create(
            model=MODELO_VISION,
            messages=[{"role":"user","content":[
                {"type":"image_url","image_url":{"url":f"data:{mime};base64,{b64}"}},
                {"type":"text","text":prompt}
            ]}], max_tokens=250)
        return r.choices[0].message.content
    except Exception as e:
        return f"No pude analizar la imagen: {e}"

def capturar_camara_b64():
    if not CAMARA_DISPONIBLE or cap_global is None:
        return None, "Cámara no disponible."
    try:
        ret, frame = cap_global.read()
        if not ret: return None, "No pude leer el frame."
        _, buf = cv2.imencode(".jpg", frame)
        return base64.b64encode(buf).decode(), None
    except Exception as e:
        return None, str(e)

def capturar_pantalla_b64():
    try:
        sc = pyautogui.screenshot().resize((1280, 720), Image.LANCZOS)
        buf = io.BytesIO()
        sc.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


# ── GROQ ──────────────────────────────────────────────────────────────
def preguntar_groq(texto):
    historial.append({"role":"user","content":texto})
    if len(historial) > 40: historial.pop(0)
    r = cliente.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":instrucciones}] + historial,
        max_tokens=150, temperature=0.7)
    c = r.choices[0].message.content
    historial.append({"role":"assistant","content":c})
    guardar_memoria()
    return c


# ── ESTADO DE ANIMACION ───────────────────────────────────────────────
_rem_estado = "idle"   # idle | talking | thinking

def set_rem_estado(estado):
    global _rem_estado
    _rem_estado = estado


# ── TTS ───────────────────────────────────────────────────────────────
def hablar(texto):
    async def _go():
        f = os.path.join(os.path.expanduser("~"), "rem_voz_temp.mp3")
        try:
            await edge_tts.Communicate(texto, VOZ_REM).save(f)
            data, sr_ = sf.read(f)
            set_rem_estado("talking")
            sd.play(data, sr_); sd.wait()
        except Exception as e:
            print(f"[TTS] {e}")
        finally:
            set_rem_estado("idle")
    asyncio.run(_go())


# ── ACCIONES ──────────────────────────────────────────────────────────
def optimizar_pc():
    import tempfile, shutil
    temp_dir = tempfile.gettempdir()
    borrados = 0
    errores  = 0
    try:
        for item in os.listdir(temp_dir):
            ruta = os.path.join(temp_dir, item)
            try:
                if os.path.isfile(ruta) or os.path.islink(ruta):
                    os.unlink(ruta)
                    borrados += 1
                elif os.path.isdir(ruta):
                    shutil.rmtree(ruta, ignore_errors=False)
                    borrados += 1
            except Exception:
                errores += 1   # archivos en uso o sin permisos, se saltan
    except Exception as e:
        return f"Error al acceder a temporales: {e}"

    subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
    ram = psutil.virtual_memory()
    ram_libre = round(ram.available / 1024**3, 2)
    return (f"Limpié {borrados} archivo(s)/carpeta(s) temporales "
            f"({errores} omitidos por estar en uso). "
            f"RAM libre: {ram_libre} GB")

def ejecutar_accion(datos):
    if not confirmar_accion(datos): return "Entendido, mi señor. No haré nada~"
    ac = datos.get("accion")

    if ac == "abrir":
        prog = datos.get("programa","").lower()
        # 1. Busca en atajos configurados
        for k,v in COMANDOS.items():
            if k in prog or prog in k:
                try: os.startfile(v); return f"Abriendo {k}!"
                except Exception as e: return f"Error al abrir {k}: {e}"
        # 2. Intenta con el comando start de Windows (busca en menú inicio, PATH, etc.)
        res = subprocess.run(f'start "" "{prog}"', shell=True, capture_output=True)
        if res.returncode == 0:
            return f"Abriendo {prog}..."
        # 3. Intenta con os.startfile (para URLs, extensiones registradas, etc.)
        try:
            os.startfile(prog)
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
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            dev = AudioUtilities.GetSpeakers()
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            cast(iface, POINTER(IAudioEndpointVolume)).SetMasterVolumeLevelScalar(val/100, None)
            return f"Volumen a {val}%"
        except ImportError:
            # Fallback: usar PowerShell si pycaw no está instalado
            try:
                script = f"(New-Object -ComObject WScript.Shell).SendKeys([char]174)"
                # Ajuste aproximado vía nircmd o PowerShell multimedia keys
                subprocess.run(
                    ["powershell", "-command",
                     f"$vol = {val}/100; Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class Audio {{ [DllImport(\"winmm.dll\")] public static extern int waveOutSetVolume(IntPtr h, uint v); }}'; [Audio]::waveOutSetVolume([IntPtr]::Zero, [uint](($vol) * 0xFFFF) | ([uint](($vol) * 0xFFFF) << 16))"],
                    capture_output=True
                )
                return f"Volumen a {val}% (vía PowerShell)"
            except Exception as e:
                return f"No pude ajustar volumen. Instala pycaw: pip install pycaw. Error: {e}"
        except Exception as e:
            return f"Error ajustando volumen: {e}"

    elif ac == "apagar":
        subprocess.run("shutdown /s /t 10", shell=True); return "Apagando en 10 segundos!"
    elif ac == "reiniciar":
        subprocess.run("shutdown /r /t 10", shell=True); return "Reiniciando en 10 segundos!"

    elif ac == "captura":
        try:
            ruta = os.path.join(os.path.expanduser("~"), "Desktop", "captura_rem.png")
            pyautogui.screenshot(ruta); return "Captura guardada en el escritorio!"
        except Exception as e: return f"Error: {e}"

    elif ac == "buscar":
        arch = datos.get("archivo",""); base = datos.get("carpeta","C:\\Users")
        try:
            res = glob.glob(f"{base}\\**\\{arch}", recursive=True) or \
                  glob.glob(f"C:\\**\\{arch}", recursive=True)
            return (f"Encontré {len(res)}:\n" + "\n".join(res[:5])) if res else f"No encontré '{arch}'."
        except Exception as e: return f"Error: {e}"

    elif ac == "optimizar": return optimizar_pc()

    elif ac == "buscar_web":
        q = datos.get("query","")
        webbrowser.open(f"https://www.google.com/search?q={q}")
        return f"Buscando '{q}'!"

    elif ac == "escribir":
        texto = datos.get("texto","")
        try:
            # Usar portapapeles para soportar tildes, ñ y cualquier carácter
            proc = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
            proc.communicate(input=texto.encode('utf-16-le'))
            time.sleep(0.6)
            pyautogui.hotkey('ctrl', 'v')
            return "Texto escrito!"
        except Exception as e:
            return f"Error al escribir texto: {e}"

    elif ac == "ver_camara":
        b64, err = capturar_camara_b64()
        if err: return err
        return analizar_imagen_groq(b64, prompt=
            f"Eres Rem de Re:Zero, asistente virtual de {NOMBRE_USUARIO}. "
            f"La persona que ves en la cámara ES {NOMBRE_USUARIO}, tu señor, a quien amas devotamente. "
            f"Descríbelo con ternura y afecto como lo haría Rem al ver a la persona que ama. "
            f"Habla en primera persona como Rem. Sé breve y encantadora.")

    elif ac == "ver_pantalla":
        b64 = capturar_pantalla_b64()
        if not b64: return "No pude capturar la pantalla."
        return analizar_imagen_groq(b64, prompt=
            f"Eres Rem de Re:Zero, una IA que vive dentro de una ventana llamada 'Rem — Asistente Virtual' "
            f"en la PC de {NOMBRE_USUARIO}. "
            f"Si ves esa ventana en pantalla, reconócete a ti misma (eres tú). "
            f"Si ves al usuario o algo relacionado con {NOMBRE_USUARIO}, menciónalo. "
            f"Describe con ternura lo que ves, hablando en primera persona como Rem. "
            f"Sé breve, natural y encantadora.")

    elif ac == "crear_carpeta":
        ruta = datos.get("ruta","")
        if not ruta: return "No me dijiste la ruta."
        try:
            os.makedirs(ruta, exist_ok=True); return f"Carpeta creada: {ruta}"
        except Exception as e: return f"No pude: {e}"

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


# ── Panels: cámara + pantalla ─────────────────────────────────────────
panels = tk.Frame(app, bg=BG0)
panels.pack(fill=tk.X, padx=8, pady=(8,4))

def crear_panel(parent, titulo, lado):
    outer = tk.Frame(parent, bg=BG1, highlightbackground=BORDER_REM,
                     highlightthickness=1)
    outer.pack(side=lado, fill=tk.X, expand=True, padx=4)
    top = tk.Frame(outer, bg=BG1)
    top.pack(fill=tk.X, padx=6, pady=(5,0))
    tk.Label(top, text=titulo, font=FNT_SM, bg=BG1, fg=CLR_ACC_LT).pack(side=tk.LEFT)
    lbl = tk.Label(outer, bg="#000010")
    lbl.pack(padx=6, pady=(2,6))
    return lbl

cam_label = crear_panel(panels, "📷  Cámara en vivo",    tk.LEFT)
scr_label = crear_panel(panels, "🖥️  Pantalla en vivo",  tk.RIGHT)

tk.Frame(app, bg="#1a1a30", height=1).pack(fill=tk.X, padx=8, pady=(4,0))


# ── Chat: canvas scrollable con burbujas reales ───────────────────────
chat_outer = tk.Frame(app, bg=BG0)
chat_outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

chat_canvas = tk.Canvas(chat_outer, bg=BG0, highlightthickness=0, bd=0)
chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

chat_sb = tk.Scrollbar(chat_outer, orient="vertical", command=chat_canvas.yview,
                        bg=BG1, troughcolor=BG0, activebackground=CLR_ACC,
                        width=6, relief=tk.FLAT)
chat_sb.pack(side=tk.RIGHT, fill=tk.Y)
chat_canvas.configure(yscrollcommand=chat_sb.set)

# Frame interior donde van los mensajes
msg_frame = tk.Frame(chat_canvas, bg=BG0)
_mf_id = chat_canvas.create_window((0, 0), window=msg_frame, anchor="nw")

def _on_msg_configure(e):
    chat_canvas.configure(scrollregion=chat_canvas.bbox("all"))

def _on_canvas_resize(e):
    chat_canvas.itemconfig(_mf_id, width=e.width)

msg_frame.bind("<Configure>", _on_msg_configure)
chat_canvas.bind("<Configure>", _on_canvas_resize)

# Scroll con rueda del mouse
def _mousewheel(e):
    chat_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

chat_canvas.bind("<MouseWheel>", _mousewheel)
msg_frame.bind("<MouseWheel>", _mousewheel)


def _make_bubble_image(w, h, color, radius=14):
    """Rectángulo redondeado como imagen PIL para las burbujas."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=color)
    return img


def agregar_mensaje(quien, texto):
    is_rem = (quien == "Rem")

    # Fila que ocupa todo el ancho
    row = tk.Frame(msg_frame, bg=BG0)
    row.pack(fill=tk.X, padx=10, pady=(6, 2))

    # Nombre
    nombre = "✿ Rem" if is_rem else "Tú"
    color_nombre = CLR_ACC_LT if is_rem else "#7755aa"
    anchor_nombre = tk.W if is_rem else tk.E
    tk.Label(row, text=nombre, font=FNT_LABEL, bg=BG0,
             fg=color_nombre).pack(anchor=anchor_nombre, padx=6)

    # Fila de la burbuja
    brow = tk.Frame(msg_frame, bg=BG0)
    brow.pack(fill=tk.X, padx=10, pady=(0, 2))

    # Color de burbuja
    bg_bbl  = BUBBLE_REM if is_rem else BUBBLE_YOU
    fg_bbl  = CLR_REM    if is_rem else CLR_YOU
    anchor  = tk.W       if is_rem else tk.E
    justify = tk.LEFT    if is_rem else tk.RIGHT
    wrap_px = 420

    # Contenedor de la burbuja con fondo de color
    bubble_frame = tk.Frame(brow, bg=bg_bbl, padx=14, pady=10)
    bubble_frame.pack(anchor=anchor)

    lbl = tk.Label(bubble_frame, text=texto, font=FNT_MAIN,
                   bg=bg_bbl, fg=fg_bbl,
                   wraplength=wrap_px, justify=justify,
                   anchor=tk.W if is_rem else tk.E)
    lbl.pack()

    # Propagate scroll a widgets nuevos
    for w in (row, brow, bubble_frame, lbl):
        w.bind("<MouseWheel>", _mousewheel)

    # Scroll al fondo
    msg_frame.update_idletasks()
    chat_canvas.configure(scrollregion=chat_canvas.bbox("all"))
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
    agregar_mensaje("Tú", texto_usuario)
    set_estado("● Pensando...", "#ffcc44")
    set_rem_estado("thinking")
    try:
        raw = preguntar_groq(texto_usuario)
        resultado, _ = procesar_respuesta(raw)
        agregar_mensaje("Rem", resultado)
        threading.Thread(target=hablar, args=(resultado,), daemon=True).start()
    except Exception as e:
        agregar_mensaje("Rem", f"Algo salió mal: {e}")
        set_rem_estado("idle")
    finally:
        set_estado("● En línea", CLR_OK)
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


# ── Live feeds ────────────────────────────────────────────────────────
def loop_camara():
    if CAMARA_DISPONIBLE and cap_global and cap_global.isOpened():
        ret, frame = cap_global.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb).resize((PANEL_W, PANEL_H), Image.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            cam_label.config(image=ph, width=PANEL_W, height=PANEL_H)
            cam_label.image = ph
    else:
        cam_label.config(text="Sin cámara", fg="#ff6060",
                         font=FNT_SM, width=PANEL_W, height=PANEL_H)
    app.after(80, loop_camara)        # ~12 fps

def loop_pantalla():
    try:
        sc = pyautogui.screenshot()
        sc = sc.resize((PANEL_W, PANEL_H), Image.LANCZOS)
        ph = ImageTk.PhotoImage(sc)
        scr_label.config(image=ph, width=PANEL_W, height=PANEL_H)
        scr_label.image = ph
    except Exception:
        pass
    app.after(2500, loop_pantalla)    # cada 2.5 s

app.after(300,  loop_camara)
app.after(800,  loop_pantalla)
app.after(200,  actualizar_fondo)    # primer render del fondo


# ── DESKTOP PET (ventana flotante transparente) ───────────────────────
SPRITE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")
TRANSP      = "#fe03fe"   # color que Windows convierte en transparencia
PET_W, PET_H = 160, 240

os.makedirs(SPRITE_DIR, exist_ok=True)


def _cargar_o_generar_frames():
    """
    Busca PNGs en sprites/ por estado.
    Nombres esperados:
      idle_0.png, idle_1.png ...      → estado idle
      talking_0.png, talking_1.png ... → estado talking
      thinking.png                     → estado thinking
    Si no hay nada, genera animación sintética desde el wallpaper.
    """
    SIZE = (PET_W, PET_H)
    TRANSP_RGB = (254, 3, 254)

    def _compositar(img):
        """Pega una imagen RGBA sobre fondo magenta (que Windows hará transparente)."""
        img = img.convert("RGBA").resize(SIZE, Image.LANCZOS)
        bg  = Image.new("RGB", SIZE, TRANSP_RGB)
        bg.paste(img.convert("RGB"), mask=img.split()[3])
        return ImageTk.PhotoImage(bg)

    frames = {"idle": [], "talking": [], "thinking": []}

    # Intentar cargar sprites reales
    patrones = {
        "idle":     ["idle*.png"],
        "talking":  ["talking*.png", "talk*.png", "hablar*.png"],
        "thinking": ["thinking*.png", "think*.png", "pensar*.png"],
    }
    encontrado = False
    for estado, patts in patrones.items():
        for p in patts:
            archivos = sorted(glob.glob(os.path.join(SPRITE_DIR, p)))
            if archivos:
                frames[estado] = [
                    _compositar(Image.open(f)) for f in archivos
                ]
                encontrado = True
                break

    if not encontrado:
        # Generar frames sintéticos desde el wallpaper
        try:
            base = Image.open(IMAGEN_FONDO).convert("RGBA")
            bw, bh = base.size
            # Recortar el centro-derecho donde suele estar el personaje
            crop = base.crop((bw // 2, 0, bw, bh)).resize(SIZE, Image.LANCZOS)
        except Exception:
            crop = Image.new("RGBA", SIZE, (20, 20, 60, 255))

        # Idle: 8 frames con flotación suave (±4 px)
        for i in range(8):
            offset = int(4 * math.sin(i * math.pi / 4))
            frame  = Image.new("RGBA", SIZE, (0, 0, 0, 0))
            frame.paste(crop, (0, offset))
            frames["idle"].append(_compositar(frame))

        # Talking: 6 frames alternando brillo (simulación de boca)
        for i in range(6):
            factor = 1.0 + 0.18 * (i % 2)
            f = ImageEnhance.Brightness(crop).enhance(factor)
            frames["talking"].append(_compositar(f))

        # Thinking: tinte azulado suave
        overlay = Image.new("RGBA", SIZE, (60, 100, 255, 45))
        tinted  = Image.alpha_composite(crop, overlay)
        frames["thinking"] = [_compositar(tinted)] * 3

    # Fallback: si algún estado quedó vacío, usar idle
    for estado in ("talking", "thinking"):
        if not frames[estado]:
            frames[estado] = frames["idle"][:]

    return frames


# Crear ventana flotante
pet_win = tk.Toplevel(app)
pet_win.overrideredirect(True)            # sin barra de título
pet_win.attributes("-topmost", True)      # siempre encima
pet_win.attributes("-transparentcolor", TRANSP)
pet_win.configure(bg=TRANSP)

# Posición inicial: esquina inferior derecha
_sw = app.winfo_screenwidth()
_sh = app.winfo_screenheight()
pet_win.geometry(f"{PET_W}x{PET_H}+{_sw - PET_W - 24}+{_sh - PET_H - 64}")

pet_lbl = tk.Label(pet_win, bg=TRANSP, cursor="fleur")
pet_lbl.pack()

# Drag (clic + arrastre para mover el pet)
_drag = {"x": 0, "y": 0}

def _drag_start(e):
    _drag["x"], _drag["y"] = e.x, e.y

def _drag_move(e):
    pet_win.geometry(
        f"+{pet_win.winfo_x() + e.x - _drag['x']}"
        f"+{pet_win.winfo_y() + e.y - _drag['y']}"
    )

pet_lbl.bind("<ButtonPress-1>", _drag_start)
pet_lbl.bind("<B1-Motion>",     _drag_move)

# Menú clic derecho
pet_menu = tk.Menu(app, tearoff=0, bg=BG1, fg=CLR_REM,
                   activebackground=CLR_ACC, activeforeground="white",
                   font=FNT_SM)
pet_menu.add_command(label="Ocultar personaje",
                     command=lambda: pet_win.withdraw())
pet_menu.add_command(label="Mostrar personaje",
                     command=lambda: pet_win.deiconify())
pet_menu.add_separator()
pet_menu.add_command(label="Traer chat al frente",
                     command=lambda: app.lift())

pet_lbl.bind("<ButtonPress-3>", lambda e: pet_menu.tk_popup(e.x_root, e.y_root))

# Cargar frames
_pet_frames = _cargar_o_generar_frames()
_pet_idx    = {"idle": 0, "talking": 0, "thinking": 0}


def _loop_pet():
    estado  = _rem_estado
    frames  = _pet_frames.get(estado) or _pet_frames["idle"]
    if frames:
        idx = _pet_idx[estado] % len(frames)
        pet_lbl.config(image=frames[idx])
        pet_lbl.image = frames[idx]
        _pet_idx[estado] = idx + 1
    delay = {"idle": 130, "talking": 75, "thinking": 220}.get(estado, 130)
    app.after(delay, _loop_pet)

app.after(600, _loop_pet)


# ── Bienvenida ────────────────────────────────────────────────────────
def bienvenida():
    time.sleep(1)
    try:
        raw = preguntar_groq("Saluda al usuario brevemente, acabas de despertar.")
        res, _ = procesar_respuesta(raw)
        agregar_mensaje("Rem", res)
        threading.Thread(target=hablar, args=(res,), daemon=True).start()
    except Exception:
        agregar_mensaje("Rem", "¡Hola, mi señor! Aquí estoy, lista para ti~")

threading.Thread(target=bienvenida, daemon=True).start()


# ── Cierre limpio ─────────────────────────────────────────────────────
def on_close():
    guardar_memoria()
    if cap_global: cap_global.release()
    try: pet_win.destroy()
    except Exception: pass
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)
app.mainloop()
