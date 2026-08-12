# Rem — Asistente Virtual IA

## Qué es este proyecto
Asistente personal de IA con personalidad de Rem de Re:Zero. Corre en **Linux (Arch)**.  
Habla, escucha, recuerda, ejecuta acciones en el sistema y muestra un avatar 3D animado en el escritorio.

## Ruta del proyecto
El proyecto vive en `/mnt/extra/rem/Rem` (movido desde `/home/esteban/Proyectos/Rem de re zero/Rem`,
cruzando sistemas de archivos). El `venv/` se recreó desde cero tras el traslado porque los venvs de
Python guardan rutas absolutas hardcodeadas (en el shebang de `venv/bin/pip`, `activate`, etc.) que
apuntaban a la ruta vieja y quedaban rotas al moverse. Si el proyecto se vuelve a mover, **hay que
recrear el venv** (`/usr/local/bin/python3.10 -m venv venv` + reinstalar desde `requirements.txt`),
no basta con copiar la carpeta.

## Stack técnico
| Capa | Tecnología |
|------|-----------|
| LLM | Groq API — `llama-3.3-70b-versatile` |
| TTS | `edge-tts` (Microsoft Neural, voz `es-MX-DaliaNeural`) |
| Voice conversion | `infer-rvc-python` + modelo `Rem_600e_6600s` |
| STT | `speech_recognition` + Google |
| GUI | Tkinter (Python 3.10 en venv) |
| Avatar 3D | Three.js + `@pixiv/three-vrm` en WebGL |
| Overlay | GTK3 + WebKit2 (Python **system** 3.12, NO el venv) |
| fairseq | v0.12.2 con shim de compatibilidad (`fairseq_shim/`) |

## Archivos principales
| Archivo | Qué hace |
|---------|----------|
| `Rem.py` | App principal: GUI Tkinter, chat, TTS/RVC, acciones, memoria |
| `rem_avatar_server.py` | Servidor HTTP `:18765` + WebSocket `:18766` para el avatar |
| `rem_overlay.py` | Overlay GTK transparente (usa `python3` del sistema, NO el venv) |
| `rem_avatar.html` | Frontend Three.js/VRM del avatar — animación procedural |
| `fairseq_shim/__init__.py` | Shim que reemplaza el `__init__.py` de fairseq para compatibilidad PyTorch |
| `fairseq_shim/checkpoint_utils.py` | Fork de fairseq con `torch.load(weights_only=False)` |
| `apply_shim.py` | Copia `fairseq_shim/` sobre el fairseq instalado en `venv/`. Ejecutar tras cualquier reinstalación de fairseq |
| `cortar_sprites.py` | Script one-off para extraer sprites de un collage PNG |

## Configuración (.env en la raíz del proyecto)
```
GROQ_API_KEY=tu_api_key_de_groq
NOMBRE_USUARIO=Esteban
CIUDAD=Yarumal
MODELO_VISION=meta-llama/llama-4-scout-17b-16e-instruct
```
Todas las variables tienen valores por defecto en el código. Solo `GROQ_API_KEY` es obligatoria.

## Archivos de datos (creados en runtime, ignorados por git)
| Archivo | Contenido |
|---------|-----------|
| `memoria_rem.json` | Historial de chat (últimos 60 mensajes) |
| `memoria_larga.json` | Recuerdos a largo plazo (hechos, emociones, eventos, preferencias) |
| `memoria_sistema.json` | Archivos y carpetas conocidas del sistema |

## Archivos pesados (ignorados por git, descargar manualmente)
| Archivo | Tamaño | Fuente |
|---------|--------|--------|
| `rmvpe.pt` | ~173 MB | HuggingFace |
| `hubert_base.pt` | ~181 MB | HuggingFace |
| `models/Rem_600e_6600s/Rem_600e_6600s.pth` | — | Google Drive (ver README) |
| `models/Rem_600e_6600s/Rem.index` | — | Google Drive (ver README) |
| `rem.vrm` | — | Incluido en el repo |

## Arquitectura de concurrencia

```
Rem.py — hilo principal (Tkinter mainloop)
├── AudioWorker (daemon thread)         — cola TTS → RVC → sounddevice
├── _cargar_rvc (daemon thread, inicio) — carga modelo RVC en background
├── escuchar() (daemon thread)          — micrófono → speech recognition
├── responder() (daemon thread)         — LLM → respuesta → hablar()
├── extraer_memoria_importante()        — daemon thread, cada 8 msgs
├── _loop_monitor_pc (daemon thread)    — alerta CPU/RAM cada 60s
├── _loop_vision_pantalla (app.after)   — análisis pantalla cada 45s
└── _loop_recordatorios (app.after)     — recordatorios cada 30s

rem_avatar_server.py (daemon thread desde Rem.py)
├── AvatarHTTP (daemon thread)          — sirve archivos en :18765
├── AvatarWS (daemon thread)            — WebSocket en :18766
└── rem_overlay.py (subprocess hijo)    — Python system, GTK3 + WebKit2
```

## Locks de threading (en Rem.py)
| Lock | Protege |
|------|---------|
| `_lock_historial` | `historial` (lista de mensajes del chat) |
| `_lock_mem_larga` | `memoria_larga` y sus escrituras a disco |
| `_lock_mem_sis` | `memoria_sistema` y sus escrituras a disco |

## Seguridad de acciones del sistema
- `ejecutar_comando`: whitelist de binarios, bloquea metacaracteres de shell, usa `shlex.split()` sin `shell=True`
- `_ruta_segura()`: valida que las rutas estén dentro de `/home/$NOMBRE_USUARIO`
- Toda acción pasa por `confirmar_accion()` (diálogo de confirmación)
- CORS restringido a `localhost` en `rem_avatar_server.py`

## Arrancar el proyecto
```bash
# Activar venv Python 3.10 primero
source venv/bin/activate
python Rem.py
```
Equivalente sin activar el venv: `venv/bin/python Rem.py`.

**El intérprete correcto es siempre `venv/bin/python` (Python 3.10.14, con torch/fairseq/RVC
instalados) — nunca el `python`/`python3` del sistema.** El `python3` del sistema (≥3.12) es solo
para `rem_overlay.py` (GTK3 + WebKit2, ver más abajo) y no tiene ninguna de las dependencias del
proyecto instaladas.

El overlay (`rem_overlay.py`) lo lanza Rem.py automáticamente usando `python3` del sistema.

## Problemas conocidos
- **fairseq + PyTorch moderno**: los archivos en `fairseq_shim/` solucionan la incompatibilidad. Ver `INSTALL.md`.
  Después de cualquier `pip install fairseq` (reinstalación, venv nuevo, etc.) hay que volver a aplicar
  el shim con `venv/bin/python apply_shim.py` — si no, `torch.load()` fallará al cargar checkpoints
  porque le falta `weights_only=False`.
- **RVC tarda en cargar**: los 30-60s solo aplican si cae a CPU (`only_cpu=True` o sin CUDA disponible). Con GPU (CUDA disponible) la carga es prácticamente instantánea, ~0,7s medidos en esta máquina. El TTS funciona sin RVC (sin conversión de voz).
- **Avatar overlay no aparece**: verificar `webkit2gtk-4.1` instalado y compositor con soporte RGBA.
- **Error de audio**: verificar que PipeWire esté corriendo (`systemctl --user status pipewire`).
- **Python dual**: `rem_overlay.py` DEBE usar el `python3` del sistema (≥3.12 con GTK), NO el venv 3.10.

## Rendimiento medido (agosto 2026)
Medido en esta máquina (RTX 3050 Laptop, torch 2.3.1+cu121) con `test_voz.py`:
- `edge-tts`: ~1,5s por frase larga
- conversión RVC: ~3,3s para 12,2s de audio (factor 0,27× tiempo real, con GPU)
- salida de RVC: 40000 Hz
- configuración usada: `pitch_lvl=4`, `index_influence=0.75`

## Datos del modelo rem.vrm
Extraído con `dump_vrm.py`. `rem.vrm` es **VRM 0.x** (usa `extensions.VRM`, no `VRMC_vrm`).

- **Blend shapes** (`blendShapeMaster.blendShapeGroups`): 18 en total — vocales A/I/U/E/O, `Blink`
  (+ `Blink_L`/`Blink_R` por separado), expresiones `Joy`/`Angry`/`Sorrow`/`Fun`, direcciones de
  mirada `LookUp`/`LookDown`/`LookLeft`/`LookRight`, y `Talk`/`Surprised` con `presetName='unknown'`
  — como no tienen preset estándar, three-vrm los expone por su nombre literal (`Talk`, `Surprised`
  con mayúscula), no por preset.
- **Morph targets** (`meshes[].primitives[].extras.targetNames`): 59 únicos, incluyen el set
  completo de los 15 visemes de VRChat/Oculus (`vrc.v_aa`, `v_ch`, `v_dd`, `v_e`, `v_ff`, `v_ih`,
  `v_kk`, `v_nn`, `v_oh`, `v_ou`, `v_pp`, `v_rr`, `v_sil`, `v_ss`, `v_th`) más
  `vrc.blink_left`/`blink_right` y `vrc.lowerlid_left`/`lowerlid_right`.
- **Huesos humanoides** (`humanoid.humanBones`): 52 mapeados, incluye `leftEye`/`rightEye`, `jaw` y
  los dedos completos de ambas manos. **No incluye `upperChest` ni dedos de los pies.**
- **Spring bones** (`secondaryAnimation`): 7 `boneGroups` (`Robe`, `Skirt`, `FrontHair`, `Hair`,
  `Sidehair`, `Breasts`, y uno sin `comment` con 0 huesos raíz en `bones`) con ~103 cadenas de huesos
  en total (suma de `bones` de los 6 grupos reales), `stiffiness` entre 1,16 y 1,8, `dragForce` entre
  0,22 y 0,27.
  - **`colliderGroups` = 0**: no hay colisionadores configurados. El pelo y la falda van a
    atravesar el cuerpo en vez de rebotar contra él — para arreglarlo hay que añadir
    `colliderGroups` en VRoid Studio o UniVRM antes de exportar.
  - **`gravityPower` = 0 en los 7 grupos**: las cadenas no caen por gravedad, solo reaccionan al
    movimiento del hueso padre (drag/stiffness). Si se quiere que el pelo/ropa cuelgue con peso
    real, hay que subir `gravityPower` en el mismo editor.
