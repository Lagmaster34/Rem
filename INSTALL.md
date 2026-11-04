
# Rem — Guía de instalación completa (Arch Linux)

## Archivos NO incluidos en el repo

| Archivo | Tamaño | Dónde conseguirlo |
|---|---|---|
| Modelo de voz Piper (`.onnx` + `.onnx.json`) | — | Pon tu propio modelo Piper en la ruta de `[tts].modelo` de `config.toml` |

Sin el modelo de voz, Rem funciona pero no habla.

Los clips de animación del avatar (`Animaciones/VRMA_MotionPack/*.vrma`) tampoco van al repo —
ver `Animaciones/README.md` para las fuentes y dónde colocarlos. Sin ellos el avatar cae a la
animación procedural (funciona, con un aviso en consola).

three.js y three-vrm **sí** van en el repo (`vendor/`, MIT): el avatar carga sin internet.

---

## 1. Dependencias del sistema (pacman)

```bash
sudo pacman -S --needed \
    python python-gobject webkit2gtk-4.1 gtk3 \
    gst-plugins-base gst-plugins-good gst-libav \
    portaudio base-devel git \
    ollama-cuda
```

> Sin GPU NVIDIA, usa `ollama` en vez de `ollama-cuda` (el LLM irá en CPU, más lento). La voz
> (Piper) y el oído (faster-whisper) corren en CPU de todos modos.
> `python-gobject`/`webkit2gtk-4.1`/`gtk3` son las libs y headers del **sistema** contra los que se
> compilan `pygobject`/`pycairo` en el paso 4 — la ventana del avatar (`rem_chat.py`) corre con
> `venv/bin/python`, no necesita un Python del sistema aparte.

---

## 2. Python 3.10 para el venv

El venv del proyecto usa Python **3.10** (es con el que está probado todo `requirements.txt`).

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
venv/bin/python -m pip install -r requirements.txt
```

Incluye `piper-tts` (voz) + `onnx` (para exponer la duración de cada fonema, de donde sale el
lipsync), `faster-whisper` (push-to-talk) y `pygobject`/`pycairo` (los bindings de GTK3/WebKit2 que
usa `rem_chat.py`, compilados contra las libs del paso 1). No hace falta torch ni CUDA en Python.

---

## 5. Modelos locales

```bash
# LLM (el de config.toml -> [llm.ollama].model)
ollama pull hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M
```

El modelo de faster-whisper (`small`) se descarga solo la **primera vez** que arranca Rem (unos
460 MB, a `~/.cache/huggingface`); desde ahí carga de la caché sin tocar la red.

La voz: pon tu propio modelo Piper (`.onnx` + `.onnx.json`, con el mismo nombre más `.json`) en la
ruta de `[tts].modelo` de `config.toml`. Del `.onnx.json` salen el sample rate y los parámetros de
síntesis.

---

## 6. Configurar el archivo `.env` (opcional)

Solo hace falta si usas un LLM por API en vez de Ollama:

```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=tu_clave_aqui
GROQ_API_KEY=tu_clave_aqui
EOF
```

La voz de salida no va en `.env`: es el modelo de `config.toml` → `[tts]`.

---

## 7. Permisos de audio y micrófono

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

## 8. Ejecutar Rem

```bash
cd "/ruta/al/proyecto Rem"
venv/bin/python rem_chat.py                  # ventana con panel de chat
venv/bin/python rem_chat.py --modo overlay   # overlay sobre el escritorio + push-to-talk
```

Usá siempre `venv/bin/python`, no el `python` del sistema.

---

## Resumen de archivos que NO están en git

| Archivo | Razón |
|---|---|
| `.env` | Contiene la API key — nunca subir |
| Modelos de voz Piper (`*.onnx`, `*.onnx.json`) | No se versionan nunca |
| `memoria_larga.json` | Memoria de conversaciones (datos personales) |
| `venv/` | Entorno virtual — recrear con esta guía |

---

## Arquitectura del sistema

```
rem_chat.py             ← LA APLICACIÓN: levanta el servidor y abre la ventana
  ├── Piper (habla.py)  ← voz de Yoru, local en CPU, + timeline de visemes (lipsync.py)
  ├── faster-whisper    ← push-to-talk (stt/), local en CPU
  ├── llm/ (Ollama/Claude/Groq) ← lenguaje
  └── rem_avatar_server.py
        ├── HTTP :18765 → sirve rem_avatar.html + vendor/ + VRM + Animaciones/*.vrma + WAV
        ├── WS   :18766 → bidireccional: estado/audio/chat  <->  chat_message/estado/modo/voz
        └── GTK3 + WebKit2 4.1 (ventana decorada opaca, inspector en :9222)
              └── Three.js + @pixiv/three-vrm + @pixiv/three-vrm-animation (VRM + clips VRMA)

bench_chat.py           ← REPL de depuración: cliente del servidor, o standalone si no hay ninguno
```

---

## Solución de problemas frecuentes

### El avatar 3D no aparece
- Verifica que `webkit2gtk-4.1` esté instalado: `pacman -Qi webkit2gtk-4.1`
- Corré `venv/bin/python rem_chat.py` en una terminal y mirá `rem_chat.log` (consola del frontend)
- Inspector remoto de WebKit: abrí `http://127.0.0.1:9222` en un navegador normal

### Rem no habla
- Confirma que `models/yoru_piper/model.onnx` y `model.onnx.json` existen (o la ruta de `[tts].modelo`)
- Prueba la voz sola: `venv/bin/python lipsync.py "hola"`

### La boca no se mueve al hablar (`lipsync SIN alineación` en el log)
- Falta el paquete `onnx`: `venv/bin/python -m pip install "piper-tts[alignment]==1.8.0"`

### Error de audio / PortAudio crash
- Instala PipeWire (paso 7) en lugar de PulseAudio clásico
- Verifica que `sounddevice` use el dispositivo correcto: `venv/bin/python -c "import sounddevice; print(sounddevice.query_devices())"`
