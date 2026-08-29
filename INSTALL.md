# Rem — Guía de instalación completa (Arch Linux)

## Archivos grandes NO incluidos en el repo (descargar manualmente)

| Archivo | Tamaño | Dónde conseguirlo |
|---|---|---|
| `rmvpe.pt` | 173 MB | [HuggingFace — lj1995/VoiceConversionWebUI](https://huggingface.co/lj1995/VoiceConversionWebUI/blob/main/rmvpe.pt) |
| `hubert_base.pt` | 181 MB | [HuggingFace — lj1995/VoiceConversionWebUI](https://huggingface.co/lj1995/VoiceConversionWebUI/blob/main/hubert_base.pt) |

Descarga ambos y colócalos en la **raíz** del proyecto (mismo nivel que `Rem.py`).

---

## 1. Dependencias del sistema (pacman)

```bash
sudo pacman -S --needed \
    python python-gobject webkit2gtk-4.1 gtk3 \
    ffmpeg portaudio \
    base-devel git \
    cuda cudnn \
    nvidia nvidia-utils
```

> Si no tienes GPU NVIDIA, omite `cuda cudnn nvidia nvidia-utils`.
> `python-gobject`/`webkit2gtk-4.1`/`gtk3` son las libs y headers del **sistema** contra los que se
> compilan `pygobject`/`pycairo` en el paso 4 — el overlay (`rem_overlay.py`) y la ventana
> (`rem_chat.py`) corren igual con `venv/bin/python`, no necesitan un Python del sistema aparte.

---

## 2. Python 3.10 para el venv

Arch usa Python 3.12+. RVC e `infer_rvc_python` necesitan Python **3.10**.

```bash
# Instalar pyenv
sudo pacman -S pyenv

# En tu ~/.bashrc o ~/.zshrc añade:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Reinicia la terminal, luego:
pyenv install 3.10.14
```

O desde AUR con `yay`:

```bash
yay -S python310
```

---

## 3. Crear el entorno virtual

```bash
cd "/ruta/al/proyecto Rem"

# Con pyenv:
pyenv local 3.10.14
python -m venv venv

# O con python310 de AUR:
python3.10 -m venv venv
```

---

## 4. Instalar dependencias Python en el venv

```bash
source venv/bin/activate

# PyTorch con CUDA 12.4 (ajusta cu124 a tu versión de CUDA)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# RVC y conversión de voz
pip install infer-rvc-python

# Sin GPU — versión CPU:
# pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Resto de dependencias
pip install \
    edge-tts \
    SpeechRecognition \
    Pillow \
    psutil \
    pyautogui \
    sounddevice \
    soundfile \
    requests \
    groq \
    opencv-python \
    mss \
    websockets \
    librosa \
    scipy \
    numpy \
    numba \
    faiss-cpu \
    praat-parselmouth \
    pyworld \
    torchcrepe \
    transformers \
    safetensors \
    huggingface_hub \
    ffmpeg-python \
    pyxdg \
    rich \
    pygobject \
    pycairo
```

`pygobject`/`pycairo` son los bindings de Python a GTK3/WebKit2 que usan `rem_overlay.py` y
`rem_chat.py` — compilan contra las libs de sistema instaladas en el paso 1
(`python-gobject`/`webkit2gtk-4.1`/`gtk3`), sin depender de un intérprete de Python aparte.

---

## 5. Instalar fairseq (shim parcheado para RVC)

`infer_rvc_python` necesita fairseq pero la versión de PyPI falla con PyTorch moderno.
Hay que instalar fairseq y luego aplicar el shim incluido en el repo:

```bash
# Estando dentro del venv activado:
pip install fairseq==0.12.2

# Aplicar el shim (sobreescribe __init__.py y checkpoint_utils.py del fairseq instalado):
python apply_shim.py
```

> **Nota:** `apply_shim.py` copia `fairseq_shim/__init__.py` y `fairseq_shim/checkpoint_utils.py`
> del repo sobre el paquete fairseq instalado en `venv/`, validando que el destino exista antes de
> sobreescribir. Hay que volver a ejecutarlo cada vez que se reinstale fairseq (venv nuevo,
> `pip install fairseq` de nuevo, etc.) — ver `CLAUDE.md`.
>
> Si `pip install fairseq==0.12.2` no instala nada, clona el repo original y copia manualmente
> antes de correr `apply_shim.py`:
> ```bash
> FAIRSEQ_DIR="venv/lib/python3.10/site-packages/fairseq"
> git clone --depth 1 https://github.com/facebookresearch/fairseq /tmp/fairseq
> cp -r /tmp/fairseq/fairseq/* "$FAIRSEQ_DIR/"
> python apply_shim.py
> ```

---

## 6. Configurar el archivo `.env`

Crea un archivo `.env` en la raíz del proyecto:

```bash
cat > .env << 'EOF'
GROQ_API_KEY=tu_clave_aqui
VOZ_REM=es-VE-PaolaNeural
TTS_RATE=-8%
REM_LAYER=top
REM_OVERLAY_W=520
REM_OVERLAY_H=860
EOF
```

Obtén tu clave gratis en [console.groq.com](https://console.groq.com).

`VOZ_REM` y `TTS_RATE` son opcionales (tienen los mismos valores por defecto en el código) — salieron
de una comparación A/B de voces de edge-tts pasadas por RVC. RVC transfiere el timbre del modelo pero
no la prosodia, así que la voz de origen se elige por su ritmo, no por cómo suena cruda; `-8%` (más
lenta que el default) le da a RVC más margen por fonema para trackear el pitch con `rmvpe` y mejora
la fidelidad de la conversión. Ver `CLAUDE.md` → "Configuración de voz ganadora" para más detalle,
incluida la limitación conocida con la `rr` vibrante.

`REM_LAYER`/`REM_OVERLAY_W`/`REM_OVERLAY_H` también son opcionales, los lee `rem_overlay.py`: capa
del compositor (`top`|`overlay`) y tamaño fijo en píxeles de la layer surface (esquina
inferior-derecha). Ver `CLAUDE.md` → "Layer surface acotada".

---

## 7. Colocar los modelos RVC

La estructura debe ser:

```
Proyecto Rem/
├── models/
│   └── Rem_600e_6600s/
│       ├── Rem_600e_6600s.pth   ← modelo de voz RVC
│       └── Rem.index            ← índice FAISS
├── rmvpe.pt                     ← descargar de HuggingFace
├── hubert_base.pt               ← descargar de HuggingFace
└── rem.vrm                      ← modelo 3D del avatar
```

---

## 8. Imagen de fondo

El archivo `wallhaven-j5zopp_1920x1080.png` debe estar en la raíz del proyecto.
Está incluido en el repo. Si quieres usar otra imagen, cambia la variable en `Rem.py`:

```python
IMAGEN_FONDO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tu_imagen.png")
```

---

## 9. Permisos de audio y micrófono

En Arch con PipeWire (recomendado):

```bash
sudo pacman -S pipewire pipewire-pulse pipewire-alsa wireplumber
systemctl --user enable --now pipewire pipewire-pulse wireplumber
```

Para que `sounddevice` funcione correctamente, el usuario debe estar en el grupo `audio`:

```bash
sudo usermod -aG audio $USER
```

---

## 10. Ejecutar Rem

```bash
cd "/ruta/al/proyecto Rem"
venv/bin/python Rem.py
```

O activando el venv primero:

```bash
source venv/bin/activate
python Rem.py
```

---

## Resumen de archivos que NO están en git

| Archivo | Razón |
|---|---|
| `.env` | Contiene la API key — nunca subir |
| `rmvpe.pt` | 173 MB — descargar de HuggingFace |
| `hubert_base.pt` | 181 MB — descargar de HuggingFace |
| `memoria_rem.json` | Memoria de conversaciones (datos personales) |
| `memoria_larga.json` | Memoria de conversaciones (datos personales) |
| `venv/` | Entorno virtual — recrear con esta guía |

---

## Arquitectura del sistema

```
Rem.py                  ← App principal (Tkinter UI, IA, voz, acciones)
  ├── Groq API          ← llama-3.3-70b-versatile (lenguaje)
  ├── EdgeTTS           ← síntesis de voz (es-VE-PaolaNeural, rate -8%)
  ├── RVC               ← conversión de voz al timbre de Rem
  ├── SpeechRecognition ← micrófono → texto
  └── rem_avatar_server.py
        ├── HTTP :18765 → sirve rem_avatar.html + rem.vrm
        ├── WS   :18766 → envía estados (idle/talking/thinking/happy/sad...)
        └── rem_overlay.py (venv/bin/python, vía sys.executable)
              └── GTK3 + WebKit2 4.1 (overlay transparente)
                    └── Three.js + @pixiv/three-vrm (renderiza rem.vrm)
```

---

## Solución de problemas frecuentes

### El avatar 3D no aparece
- Verifica que `webkit2gtk-4.1` esté instalado: `pacman -Qi webkit2gtk-4.1`
- Lanza el overlay manualmente para ver errores: `venv/bin/python rem_overlay.py`
- El compositor (KWin/Mutter) debe soportar RGBA — en KDE activa "Efectos de escritorio"

### Error de audio / PortAudio crash
- Instala PipeWire (paso 9) en lugar de PulseAudio clásico
- Verifica que `sounddevice` use el dispositivo correcto: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### fairseq ImportError
- Verifica que el `__init__.py` del shim esté en `venv/lib/python3.10/site-packages/fairseq/`
- Comprueba que `checkpoint_utils.py` tenga `weights_only=False` en el `torch.load()`

### RVC no carga el modelo
- Confirma que `models/Rem_600e_6600s/Rem_600e_6600s.pth` existe
- Confirma que `rmvpe.pt` está en la raíz del proyecto
- Si no hay GPU: el modelo carga en CPU (tarda ~30 segundos la primera vez)
