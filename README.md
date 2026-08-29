# 🌸 Rem — Asistente virtual con avatar VRM

Asistente de escritorio con la personalidad de **Rem (Re:Zero)**: avatar 3D VRM flotando sobre el escritorio, voz clonada con RVC, lipsync sincronizado y capacidad de ejecutar tareas en la PC.

Corre **100% local y sin coste** con un modelo Qwen3.5-4B en Ollama, o contra la API de Claude / Groq si se prefiere.

> **Estado:** funcional de punta a punta desde el 25 ago 2026 (LLM → personalidad → TTS → RVC → lipsync → avatar). El frontend web de chat está en construcción; el chat viejo de Tkinter está en vías de eliminación.

---

## 🖥️ Plataforma

Este proyecto **ya no es Windows**. Nació como asistente de Windows y se portó a Linux (pycaw → `pactl`, VBCABLE → PipeWire).

| | |
|---|---|
| SO | Arch Linux |
| Compositor | Hyprland (Wayland) — el overlay usa `gtk-layer-shell` |
| Audio | PipeWire |
| GPU | NVIDIA con CUDA (desarrollado sobre una RTX 3050 de 4 GB) |
| Python | **3.10** (venv propio del proyecto) |

Ubicación del proyecto: `/mnt/extra/rem/Rem/` (partición aparte por espacio; `/home` iba justo).

---

## 📦 Dependencias del sistema

```bash
sudo pacman -S webkit2gtk-4.1 gtk-layer-shell \
               gst-plugins-base gst-plugins-good gst-libav \
               grim ollama-cuda
```

- `webkit2gtk-4.1` y `gtk-layer-shell` → sin ellos el overlay del avatar **no arranca** (falla en `gi.require_version('WebKit2', '4.1')` y el error se traga en silencio).
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
python apply_shim.py   # reaplica el shim de fairseq sobre el paquete instalado
```

Versiones que funcionan (fijadas por RVC, son sensibles):

| Paquete | Versión |
|---|---|
| numpy | 1.26.4 |
| torch / torchaudio | 2.3.1+cu121 |
| fairseq | 0.12.2 |
| infer-rvc-python | — |
| edge-tts | 7.2.8 |
| PyAudio, httpx, sounddevice, soundfile | — |

> ⚠️ Si mueves el proyecto de carpeta, `venv/bin/pip` se rompe (ruta absoluta en el shebang). `venv/bin/python` sigue funcionando; recrea el venv o arregla el shebang.

> ⚠️ **Limitación conocida:** el intérprete `/usr/local/bin/python3.10` se compiló **sin `_tkinter`**, así que `import tkinter` falla. No afecta al avatar, la voz ni los benchmarks — solo al chat viejo de Tkinter, que va a desaparecer de todos modos.

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

Cadena: **edge-tts** (voz base) → **RVC** (conversión al timbre de Rem) → reproducción + timeline de visemes.

Configuración ganadora tras muchas pruebas:

| Parámetro | Valor |
|---|---|
| Voz base | `es-VE-PaolaNeural` |
| Rate | `-8%` |
| `pitch_lvl` | `4` |
| `index_influence` | `0.75` |
| Salida RVC | 40000 Hz |

Finalistas descartadas: `es-MX-DaliaNeural --rate=-10%` y `es-CO-SalomeNeural --rate=-8%`. (`es-MX-RenataNeural` no existe en edge-tts.)

> Artefacto conocido: la **R** suena rara tras la conversión RVC. Bajar `index_influence` a 0.5 / 0.3 / 0 no compensa la pérdida de parecido; se asume el artefacto.

### Modelos necesarios

```
models/Rem_600e_6600s/Rem_600e_6600s.pth
models/Rem_600e_6600s/Rem.index
hubert_base.pt
rmvpe.pt
```

### Precarga de RVC

`_precargar_rvc()` carga el modelo y hace una conversión de calentamiento en un hilo daemon durante el arranque. Antes, cada frase releía el `.pth` (11–16 s); ahora la primera conversión real tarda **0,88 s**.

La causa era que `BaseLoader.__call__()` guarda el tag cargado en `cache_params`, una variable **local**. Se usa `BaseLoader.generate_from_cache()`, que cachea en atributos de instancia. Bonus: llama a `infer()` directo, así que los fallos de RVC ahora lanzan excepción en vez de devolver una lista vacía en silencio. `BaseLoader` no es thread-safe → hay un `threading.Lock()` serializando cada llamada.

---

## 👤 Avatar

`rem.vrm` (23,9 MB, **VRM 0.x**) renderizado con Three.js dentro de un WebView WebKit2GTK, montado como layer-shell transparente y click-through sobre Hyprland.

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
Rem.py                    # asistente principal y acciones sobre la PC
rem_overlay.py            # ventana GTK layer-shell + WebView (modo ?modo=overlay)
rem_chat.py               # ventana GTK normal, decorada y con foco (modo ?modo=ventana)
rem_avatar_server.py      # HTTP (sirve el WAV) + WebSocket (eventos)
rem_avatar.html           # Three.js, carga del VRM, lipsync, cola de audio — un motor, dos modos
lipsync.py                # timings de edge-tts → grafema-fonema → timeline
personalidad.py           # system prompt y contexto dinámico
config.py                 # dotenv + config.toml (compartido)
config.toml
apply_shim.py             # shim de fairseq
llm/
  base.py                 # ABC LLMProvider + Message / ToolSpec / Chunk / ToolCall
  local.py                # Ollama
  claude.py               # API de Anthropic
  groq.py
  echo.py                 # EchoProvider — sin modelo, repite el último mensaje (modo eco)
  sentence_splitter.py    # empuja cada oración al TTS en cuanto se completa
  _retry.py
bench_chat.py             # REPL: LLM + personalidad + voz/lipsync/avatar (modo ia/eco)
models/Rem_600e_6600s/
tmp_audio/
```

---

## ▶️ Ejecución

```bash
source venv/bin/activate

python bench_chat.py   # REPL — 'modo eco' para voz/lipsync/avatar sin LLM, 'modo ia' para el LLM real
python Rem.py          # todo (bloqueado por _tkinter hasta migrar el chat a web)
```

---

## ⚡ Rendimiento y presupuesto de VRAM

Los 4 GB de la RTX 3050 son el cuello de botella real: el modelo (~2,9 GB) y RVC **no caben cómodos a la vez**.

Calibración de `num_gpu` (el modelo tiene 32 capas):

| `num_gpu` | VRAM | Generación | RVC |
|---|---|---|---|
| 32 | ~2994 MiB | ~40,7 tok/s | ❌ OOM siempre |
| **28** | ~2714 MiB | ~25,8 tok/s | ✅ fiable |
| ≤24 | menos | hasta 4,7 tok/s | ✅ |

Se fijó **28** como el valor más alto que funciona.

Coste de tener RVC residente en la GPU:

| Escenario | tok/s |
|---|---|
| `ollama run --verbose`, nada más corriendo | 24,7 |
| RVC residente **en reposo** | 9,0 |
| RVC convirtiendo en paralelo | ~4 |

O sea: la mera presencia de RVC en la VRAM degrada la generación un ~65%. Es una compensación abierta — la precarga de RVC bajó el tiempo hasta el primer audio pero empeoró el tiempo total de respuesta.

Alternativas descartadas por medición:
- **RVC en CPU**: ~13,6 s por frase corta (~4,5× tiempo real). La cola del `SentenceSplitter` no sigue el ritmo.
- **Bajar `num_ctx` a 4096**: no libera casi nada; la caché KV de Qwen3.5 ya es pequeña por su atención híbrida.
- **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`**: llega más lejos (falla en RMVPE en vez de HuBERT) pero le faltan 12 MiB.

Cuando RVC falla por OOM, el pipeline cae al audio crudo de edge-tts: se oye, pero sin la voz de Rem.

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
- **Caché de WebKit** en `~/.cache/rem_overlay.py/WebKitCache` (o `~/.cache/rem_chat.py/WebKitCache` para la ventana) enmascara ediciones del frontend entre lanzamientos. Límpiala al depurar.
- **`_tkinter` ausente** en el intérprete → `Rem.py` no arranca. Se resuelve al migrar el chat a web.
- **Hyprland tiling ignora `set_default_size()`** en `rem_chat.py`: sin una `windowrulev2 = float, class:^(rem_chat.py)$` en tu config, la ventana se tiling-ea igual que cualquier otra en vez de abrir en 1100×620. La escena se adapta sola (escucha `resize`), pero el tamaño pedido no se respeta sin esa regla.

### Depuración del overlay / la ventana

```bash
# Consola del frontend volcada a rem_overlay.log / rem_chat.log
# (set_enable_write_console_messages_to_stdout(True))

WEBKIT_INSPECTOR_SERVER=127.0.0.1:9222 python rem_overlay.py   # overlay
venv/bin/python rem_chat.py                                    # ventana — inspector ya fijo en :9223
# DevTools desde el navegador en 127.0.0.1:9222 o :9223 según cuál
```

---

## 🗺️ Pendiente

1. **Ventana GTK separada (`rem_chat.py`) — hecha.** Falta cablear el chat en sí: React (u otra UI) dentro de esa ventana, hablando con `rem_avatar_server.py` vía eventos `chat_message`/`audio_ready`/`viseme_timeline` sobre el mismo HTTP/WebSocket.
2. Eliminar Tkinter del todo (chat viejo y su fondo).
3. Conectar el `SentenceSplitter` a `Rem.py` (hecho y testeado, aún sin cablear).
4. Migrar `extraer_memoria_importante()` — ya pasa por el provider, verificar que no queden restos del cliente Groq síncrono.

### Dirección de la personalidad

Sin cariño ni romance. Natural, con la tecnología como su fuerte, y que **contradiga cuando haga falta** en vez de dar siempre la razón.

---

## 📜 Créditos

- Modelo de voz RVC: Rem (Re:Zero)
- RVC: [infer-rvc-python](https://github.com/R3gm/infer_rvc_python)
- TTS: [edge-tts](https://github.com/rany2/edge-tts)
- LLM local: [Ollama](https://ollama.com) + Qwen3.5-4B
- Avatar: [three-vrm](https://github.com/pixiv/three-vrm)