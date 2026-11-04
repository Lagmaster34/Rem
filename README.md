# 🌸 Rem — Asistente virtual con avatar VRM

Asistente de escritorio con la personalidad de **Rem (Re:Zero)**: avatar 3D VRM flotando sobre el escritorio, voz de Yoru con Piper TTS local, lipsync sincronizado y capacidad de ejecutar tareas en la PC.

Corre **100% local, sin coste y sin internet** con un modelo Qwen3.5-4B en Ollama (LLM), faster-whisper (oído) y Piper (voz), o contra la API de Claude / Groq si se prefiere.

> **Estado:** funcional de punta a punta desde el 25 ago 2026 (LLM → personalidad → TTS → lipsync → avatar; desde nov 2026 la voz es Piper en vez de edge-tts + RVC). La aplicación es `rem_chat.py` (ventana con panel de chat, u overlay con push-to-talk); el viejo asistente Tkinter (`Rem.py`) se eliminó.

---

## 🖥️ Plataforma

Este proyecto **ya no es Windows**. Nació como asistente de Windows y se portó a Linux (pycaw → `pactl`, VBCABLE → PipeWire).

| | |
|---|---|
| SO | Arch Linux |
| Compositor | Hyprland (Wayland) |
| Audio | PipeWire |
| GPU | NVIDIA con CUDA (desarrollado sobre una RTX 3050 de 4 GB) |
| Python | **3.10** (venv propio del proyecto) |

Ubicación del proyecto: `/mnt/extra/rem/Rem/` (partición aparte por espacio; `/home` iba justo).

---

## 📦 Dependencias del sistema

```bash
sudo pacman -S webkit2gtk-4.1 \
               gst-plugins-base gst-plugins-good gst-libav \
               grim ollama-cuda
```

- `webkit2gtk-4.1` → sin él la ventana del avatar (`rem_chat.py`) **no arranca** (falla en `gi.require_version('WebKit2', '4.1')`).
- Los plugins de GStreamer → sin ellos el WebView no reproduce audio (`autoaudiosink not found`).
- `grim` para capturas. **`mss` no sirve en Hyprland**: usa APIs de X11 y devuelve imágenes negras.

---

## 🐍 Entorno de Python

El venv vive dentro del proyecto y usa **Python 3.10.14**.

```bash
cd /mnt/extra/rem/Rem
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Sin torch ni CUDA en Python: la voz (Piper) y el oído (faster-whisper) van en CPU sobre onnxruntime /
ctranslate2. La GPU queda para Ollama.

| Paquete | Versión |
|---|---|
| piper-tts (+ onnx, para las alineaciones del lipsync) | 1.8.0 |
| faster-whisper | 1.2.1 |
| numpy | 2.2.6 |
| httpx, sounddevice, soundfile | — |

> ⚠️ Si mueves el proyecto de carpeta, `venv/bin/pip` se rompe (ruta absoluta en el shebang). `venv/bin/python` sigue funcionando; recrea el venv o arregla el shebang.

---

## 🧠 Modelo de IA

La capa LLM está abstraída: se elige el proveedor en `config.toml`.

```toml
[llm]
provider = "local"   # local | claude | groq
```

Override por entorno: `REM_LLM_PROVIDER=claude`.

### Opción A — Local (por defecto, gratis, sin internet)

Modelo: `hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M` (~3,2 GB en disco).

```bash
# Guardar los modelos fuera de /home (drop-in de systemd)
sudo systemctl edit ollama
# [Service]
# Environment="OLLAMA_MODELS=/mnt/extra/ollama"

sudo systemctl restart ollama
ollama pull hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M
```

```toml
[llm.local]
num_gpu    = 28      # ver "Presupuesto de VRAM" abajo
keep_alive = "10m"   # imprescindible: con 0 recarga el modelo en cada turno
num_ctx    = 4096
```

El proveedor habla con `/api/chat` nativo por httpx con streaming NDJSON y fuerza `think: false` (si no, el modelo escupe cientos de tokens de razonamiento antes de contestar).

### Opción B — API de Claude

Crea `.env` en la raíz del proyecto (ya está en `.gitignore`, **el repo es público**):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Modelo `claude-sonnet-5`, con el system prompt cacheado (`cache_control` efímero). Solo se gastan tokens cuando le hablas: no hay ninguna llamada automática.

> La suscripción Pro de Claude.ai **no** incluye créditos de API. Sin saldo, la API responde 400 `credit balance is too low`.

### Opción C — Groq

Sigue soportado (`llm/groq.py`, `AsyncGroq` con streaming), pero ya no es el camino principal.

---

## 🎙️ Voz

Cadena: **Piper** (voz de Yoru, local, CPU) → WAV + timeline de visemes → reproducción en el avatar.
El avatar sigue siendo el de Rem.

- Pon tu propio modelo Piper (`.onnx` + `.onnx.json`) en la ruta de `[tts].modelo` de
  `config.toml`. Los modelos de voz no se versionan. Se usan los parámetros de síntesis del
  `.onnx.json` tal cual.
- Se carga una vez por proceso y se calienta al arrancar (~1,2 s en segundo plano). Síntesis medida:
  **~0,03-0,6 s por oración** (≈0,06× tiempo real); primer audio en modo eco en **<0,2 s**.
- **Lipsync con las duraciones reales del modelo**: Piper 1.8 expone cuánto dura cada fonema
  (`include_alignments`; el modelo se parchea en memoria con el paquete `onnx`). `lipsync.py` lo
  convierte en el timeline de visemes.
- Probar: `venv/bin/python lipsync.py "una frase"`.

Antes: edge-tts (`es-VE-PaolaNeural`) + RVC (`Rem_600e_6600s`). Se eliminó por completo (código y
dependencias, incluido torch); el historial está en git hasta `bb410ce`. Los archivos de RVC
(`models/Rem_600e_6600s/`, `hubert_base.pt`, `rmvpe.pt`, ~420 MB) ya no se usan.

---

## 👤 Avatar

`rem.vrm` (23,9 MB, **VRM 0.x**) renderizado con Three.js dentro de un WebView WebKit2GTK — una ventana de escritorio normal (`rem_chat.py`), decorada y opaca, con panel de chat a la derecha.

**Animación de cuerpo:** clips `.vrma` reales (`Animaciones/`, se descargan a mano — ver `Animaciones/README.md`) reproducidos con `THREE.AnimationMixer`; mapeo estado→clip y gestos de reposo en `CONFIG.animaciones`. Los clips solo mueven huesos de cuerpo — respiración, parpadeo, saccades, mirada a cámara y lipsync se aplican siempre encima.

**Lipsync:** los 15 visemes de VRChat/Oculus se aplican **por índice directo** sobre los morph targets, no por nombre.

<details>
<summary>Por qué (detalle técnico importante)</summary>

Los morph targets del modelo cargado no se llaman `vrc.v_aa` sino `Bodybaked_NN`, así que resolverlos por nombre daba 0/14. Pero el `.vrm` crudo tiene **un solo mesh `Body.baked` con 72 primitives**, todas con el mismo orden de 59 `targetNames`, así que un índice vale igual en las 72:

| viseme | idx | | viseme | idx |
|---|---|---|---|---|
| aa | 4 | | oh | 12 |
| ch | 5 | | ou | 13 |
| dd | 6 | | pp | 14 |
| e  | 7 | | rr | 15 |
| ff | 8 | | sil | 16 |
| ih | 9 | | ss | 17 |
| kk | 10 | | th | 18 |
| nn | 11 | | | |

(`blink_left=0`, `blink_right=1`, `lowerlid_left=2`, `lowerlid_right=3`.)

Además hay que suprimir el peso de `Surprised` mientras suena el lipsync, porque bindea un morph de boca. El `expressionManager` sí expone 18 expresiones y sirve como fallback de 5 visemes, pero los binds del modelo original están mal: `I` apunta a `vrc.v_ff` y `U` no tiene bind.
</details>

**Encuadre:** medido sobre huesos (head → leftFoot + 18%), no con `Box3` — `Box3` medía 0.801u frente a los 1.623u reales y cortaba a Rem por la mitad.

**Físicas:** el modelo trae 7 grupos de spring bones (Robe, Skirt, FrontHair, Hair, Sidehair, Breasts), pero sin colisionadores y con `gravityPower = 0`.

**Rig:** 52 huesos humanoides, incluidos `leftEye`, `rightEye` y `jaw`. No tiene `upperChest` ni `toes`.

---

## 🗂️ Estructura

```
rem_chat.py               # LA APLICACIÓN: levanta el servidor y abre la ventana GTK + WebView
rem_avatar_server.py      # HTTP (sirve HTML/VRM/clips/WAV) + WebSocket bidireccional (estado/audio/chat)
rem_avatar.html           # Three.js, carga del VRM, clips VRMA, lipsync, panel de chat, cola de audio
Animaciones/              # clips .vrma del avatar (no van al repo — ver Animaciones/README.md)
lipsync.py                # alineaciones fonema→audio de Piper → timeline de visemes
personalidad.py           # system prompt y contexto dinámico
config.py                 # dotenv + config.toml (compartido)
config.toml
vendor/                   # three.js / three-vrm en local (el avatar carga sin internet)
chat_sesion.py            # SesionChat + procesar_turno() (compartido rem_chat.py / bench_chat.py)
habla.py                  # pipeline de voz de un turno (Piper → enviar_audio)
llm/
  base.py                 # ABC LLMProvider + Message / ToolSpec / Chunk / ToolCall
  local.py                # Ollama
  claude.py               # API de Anthropic
  groq.py
  echo.py                 # EchoProvider — sin modelo, repite el último mensaje (modo eco)
  sentence_splitter.py    # empuja cada oración al TTS en cuanto se completa
  _retry.py
bench_chat.py             # REPL de depuración: cliente del servidor, o standalone si no hay ninguno
models/yoru_piper/        # voz de Yoru (Piper) — no se versiona
tmp_audio/
```

---

## ▶️ Ejecución

```bash
venv/bin/python rem_chat.py     # LA APLICACIÓN — abre la ventana del avatar con panel de chat
venv/bin/python rem_chat.py --modo overlay   # avatar sobre el escritorio + caja de texto
venv/bin/python bench_chat.py   # REPL de depuración — se conecta a rem_chat.py si está corriendo,
                                # o levanta el servidor él mismo. 'modo eco' = voz sin LLM
```

### Lanzadores (sin escribir comandos)

La carpeta `lanzadores/` abre cada modo con doble clic o desde el lanzador de apps:

| Script | Entrada en el lanzador | Qué abre |
|---|---|---|
| `lanzadores/rem-ventana.sh` | **Rem Ventana** | `rem_chat.py --modo ventana` |
| `lanzadores/rem-overlay.sh` | **Rem Overlay** | `rem_chat.py --modo overlay` (avatar sobre el escritorio + caja de texto) |
| `lanzadores/rem-debug.sh` | **Rem Debug** | `bench_chat.py` en una terminal (`$TERMINAL`, o foot/kitty/alacritty) |
| `lanzadores/rem-panel.sh` | **Rem Panel** | `rem_panel.py`: panel de control (necesita Rem abierto; no lo cierra ni lo reinicia) |
| `lanzadores/rem-cerrar.sh` | **Rem Cerrar** | Cierra cualquier `rem_chat.py` abierto, ventana u overlay (SIGTERM, y SIGKILL a los 5 s) |

Para que aparezcan en el lanzador de apps (Hyprland, rofi, wofi, etc.):

```bash
lanzadores/instalar.sh    # escribe los .desktop en ~/.local/share/applications/
```

- **Dos instancias nunca compiten por el puerto.** `rem-ventana.sh` y `rem-overlay.sh` cierran
  cualquier `rem_chat.py` que ya esté corriendo, en el modo que sea, antes de abrir el nuevo. Así
  nunca quedan la ventana y el overlay abiertos a la vez. Primero piden un cierre limpio (SIGTERM) y solo
  fuerzan (SIGKILL) si no se cerró en 5 s. `rem-debug.sh` **no** lo cierra, porque `bench_chat.py`
  no ocupa el puerto: si hay una ventana abierta se conecta a ella como cliente, y si no, levanta
  su propio servidor.
- **Logs** en `lanzadores/logs/<script>.log`: cada arranque se agrega con fecha y hora, sin borrar
  los anteriores. La consola de WebKit sigue yendo a `rem_chat.log`, en la raíz. El log de debug
  guarda la sesión completa del REPL.
- **Si movés el proyecto**, los `.sh` siguen funcionando porque calculan la raíz desde su propia
  ubicación. Hay que volver a correr `instalar.sh`: un `.desktop` necesita la ruta absoluta en
  `Exec=`, así que se instala como copia con la ruta real y no como symlink.
- **Ícono**: el proyecto no trae uno propio, así que se usa `avatar-default` del tema. Si dejás un
  `lanzadores/rem.png` o `rem.svg` y volvés a correr `instalar.sh`, se usa ese.
- **Cerrar con una tecla** (útil en el overlay, que no tiene botón de cerrar): agregar a
  `hyprland.conf`
  ```
  bind = SUPER SHIFT, H, exec, /mnt/extra/rem/Rem/lanzadores/rem-cerrar.sh
  ```
- Para el push-to-talk del overlay hacen falta además los binds de Hyprland (ver CLAUDE.md,
  "Líneas de Hyprland para push-to-talk").

---

## ⚡ Rendimiento y presupuesto de VRAM

Los 4 GB de la RTX 3050 son solo para Ollama: Piper, faster-whisper y el WebGL del avatar (que
WebKit rasteriza por software) no usan la NVIDIA.

Medido sin red (nov 2026, con corriente), `num_gpu = 24`: **2322 MiB** de VRAM en uso (2312 de
Ollama) y **15-18 tok/s** con prompts de ~2600-3000 tokens. Calibración de `num_gpu` (32 capas):

| `num_gpu` | VRAM modelo | Generación |
|---|---|---|
| 32 | ~2994 MiB | ~40,7 tok/s |
| 28 | ~2714 MiB | ~25,8 tok/s |
| **24** (actual) | ~2430 MiB | ~20,7 tok/s |
| 0 | ~153 MiB | ~4,7 tok/s |

24 se eligió para dejarle sitio a RVC, que ya no existe: hay margen para subirlo, pero no se tocó
todavía (medir antes con `nvidia-smi`).

- **Bajar `num_ctx` a 4096** no libera casi nada: la caché KV de Qwen3.5 ya es pequeña por su
  atención híbrida.
- En batería la GPU cae a P5 y la generación baja a ~6,6 tok/s (ver CLAUDE.md).

---

## 🔐 Seguridad

El asistente puede ejecutar comandos, así que hubo una auditoría con hallazgos serios. Estado actual:

- **Whitelist de binarios** sin `python3`, `pip` ni `apt`. `find` bloquea `-exec`, `-execdir` y `-delete`. `git` y `systemctl` limitados a subcomandos de solo lectura, con bloqueo de `-c` / `--exec-path` / `-H`.
- **`_ruta_segura`** usa `os.path.commonpath` sobre `realpath` (antes `startswith`). `~` a secas ya no pasa el chequeo — antes sí, y habría hecho `rmtree` de todo `/home/esteban`.
- **`_args_permitidos()`** valida cada token que parezca ruta en `ejecutar_comando`, incluido traversal escondido (`carpeta_real/../../etc/passwd`). Antes solo se validaba el binario, así que `cat .env` por el chat exponía las API keys.
- **Lista negra**: `~/.ssh`, `~/.gnupg`, `~/.config`, keyrings, `~/.mozilla`, `.env` y `.git` del proyecto.
- **`eliminar_archivo`** manda a la papelera XDG con su `.trashinfo` en vez de borrar.
- **`optimizar_pc()`** ya no toca `/tmp`; solo `~/.cache` con filtro de 7 días.
- **Confirmación** con el comando tokenizado y las rutas ya resueltas a la vista.
- No queda ningún `subprocess` con `sudo` (se eliminó `instalar_paquete`: sin TTY y con `sudo` pidiendo contraseña, no podía funcionar).
- `memoria_sistema.json` salió de git con `git rm --cached` — estaba trackeado en un repo público.

**Sin visión de pantalla ni cámara**: eliminadas deliberadamente del proyecto.

---

## 🐛 Problemas conocidos

- **Autoplay en WebKitGTK 2.52**: `set_media_playback_requires_user_gesture(False)` **no basta**. Hay que pasar `WebsitePolicies(autoplay=ALLOW)` al constructor del WebView. Verificado en vivo: sin eso, `play()` se rechaza con `NotAllowedError`.
- **Crash del proceso de red de WebKit 2.52.5** al cargar el WebSocket y el VRM ("this is a WebKit bug"). El WS reconecta solo; `_cargarVRM()` reintenta hasta 5 veces con espera exponencial.
- **Caché de WebKit** en `~/.cache/rem_chat.py/WebKitCache` enmascara ediciones del frontend entre lanzamientos. Límpiala al depurar.
- **Hyprland tiling ignora `set_default_size()`** en `rem_chat.py`: sin una `windowrulev2 = float, class:^(rem_chat.py)$` en tu config, la ventana se tiling-ea igual que cualquier otra en vez de abrir en 1100×620. La escena se adapta sola (escucha `resize`), pero el tamaño pedido no se respeta sin esa regla.

### Depuración de la ventana

```bash
venv/bin/python rem_chat.py   # consola del frontend volcada a rem_chat.log; inspector en :9222
# DevTools remoto desde un navegador normal en http://127.0.0.1:9222
```

---

## 🗺️ Pendiente

1. **Ventana GTK (`rem_chat.py`) con panel de chat — hecha.** El overlay transparente (`rem_overlay.py`) se eliminó: `rem_chat.py` lo sustituye por completo.
2. **`Rem.py` / Tkinter — eliminado.** Lo que no se portó (extracción automática de memoria larga, el resto del catálogo de acciones) queda en el historial de git (`58abc8e`).
3. Extracción de memoria larga en `rem_chat.py`: hoy la memoria larga se lee pero nada la actualiza (antes lo hacía `extraer_memoria_importante()` en `Rem.py`).

### Dirección de la personalidad

Sin cariño ni romance. Natural, con la tecnología como su fuerte, y que **contradiga cuando haga falta** en vez de dar siempre la razón.

---

## 📜 Créditos

- TTS: [Piper](https://github.com/OHF-voice/piper1-gpl) (GPL-3.0)
- Avatar: [three.js](https://threejs.org) y [three-vrm](https://github.com/pixiv/three-vrm) (MIT), vendorizados en `vendor/`
- LLM local: [Ollama](https://ollama.com) + Qwen3.5-4B
- Avatar: [three-vrm](https://github.com/pixiv/three-vrm)