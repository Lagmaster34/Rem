# Rem — Asistente Virtual IA

## Qué es este proyecto
Asistente personal de IA con personalidad de Rem de Re:Zero. Corre en **Linux (Arch)**.  
Habla, escucha, recuerda, ejecuta acciones en el sistema y muestra un avatar 3D animado en el escritorio.

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
El overlay (`rem_overlay.py`) lo lanza Rem.py automáticamente usando `python3` del sistema.

## Problemas conocidos
- **fairseq + PyTorch moderno**: los archivos en `fairseq_shim/` solucionan la incompatibilidad. Ver `INSTALL.md`.
- **RVC tarda en cargar**: se carga en daemon thread al inicio, puede tardar 30-60s. El TTS funciona sin RVC (sin conversión de voz).
- **Avatar overlay no aparece**: verificar `webkit2gtk-4.1` instalado y compositor con soporte RGBA.
- **Error de audio**: verificar que PipeWire esté corriendo (`systemctl --user status pipewire`).
- **Python dual**: `rem_overlay.py` DEBE usar el `python3` del sistema (≥3.12 con GTK), NO el venv 3.10.
