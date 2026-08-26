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
| LLM | Claude (Anthropic) — `claude-sonnet-5` por defecto. Groq queda como fallback (`llm/groq.py`) |
| TTS | `edge-tts` (Microsoft Neural, voz `es-VE-PaolaNeural`, rate `-8%`) |
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
| `llm/` | Capa de abstracción de LLM (contrato + providers). Ver "Capa de abstracción de LLM" más abajo |
| `config.py` | Módulo compartido: carga `.env` y lee `config.toml`. Lo usan `Rem.py`, `bench.py` y `bench_chat.py` — ninguno de los otros dos puede importar `Rem.py` (ver más abajo), así que sin esto no verían las variables de entorno |
| `config.toml` | Config no sensible versionada en git (a diferencia de `.env`, que tiene los secretos) — hoy solo `[llm]` / `[llm.claude]` |
| `bench_chat.py` | REPL async nativo para probar la capa `llm/` sin Tkinter. Ver "Capa de abstracción de LLM" más abajo |

## Capa de abstracción de LLM (`llm/`)
Contrato común para poder cambiar de backend (Claude, Groq, un modelo local a futuro) sin tocar
`Rem.py` más allá del punto de llamada. Proveedor activo: **Claude** (`llm/claude.py`), con **Groq
como fallback** (`llm/groq.py`) — ver `get_provider()` más abajo.

- `llm/base.py`: tipos normalizados (`Message`, `ToolSpec`, `ToolCall`, `Chunk` = `TextDelta` |
  `ToolCallChunk` | `Done`) y el ABC `LLMProvider` con `stream_chat(system, messages, tools=None)
  -> AsyncIterator[Chunk]`. **El system prompt es un parámetro explícito, no un `Message` más en la
  lista**: Claude lo lleva como campo de nivel superior y los endpoints OpenAI-compatible como un
  mensaje del array — si se metiera en `messages`, cada provider tendría que extraerlo de ahí para
  dárselo a su API en el formato que le corresponde, y ese paso de ida y vuelta es justo donde se
  rompe el prompt caching (ver "Nada volátil en el system prompt" más arriba).
- `llm/_retry.py`: `reintentar_con_backoff()` — retry con backoff exponencial compartido por
  `groq.py`, `claude.py` y `local.py`. Solo cubre conectar y obtener el stream (si la conexión se
  corta a mitad de la respuesta ya no reintenta: reintentar ahí rehace la respuesta desde cero y
  duplicaría texto que el consumidor ya recibió). Loguea tipo + `__cause__` de cada intento (no solo
  `str(e)`), y al agotar los reintentos lanza `RuntimeError(...) from ultimo_error` — la excepción
  original queda encadenada, no se pierde detrás de un mensaje genérico.
- `llm/groq.py`: `GroqProvider`, streaming real vía `AsyncGroq`. Reensambla tool_calls fragmentadas
  por índice de red antes de emitirlas.
- `llm/local.py`: `OllamaProvider`, sobre la API **nativa** de Ollama (`/api/chat` vía `httpx`
  crudo, streaming NDJSON) — no la compatible con OpenAI (`/v1/chat/completions`), que no acepta
  `think` ni `keep_alive`. Sin API key: corre local. Modelo por defecto
  `hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M`, configurable en `config.toml` →
  `[llm.ollama]` junto con `base_url`, `keep_alive` y el sampling (`temperature`/`top_p`/`top_k`/
  `min_p`/`num_ctx`).
  - **VRAM medida en esta máquina** (RTX 3050, 4 GB): el modelo ocupa ~2893 MiB cargado y RVC
    ~790 MiB — suman ~3683 de 4096 MiB, **entran juntos** sin problema (la estimación inicial de
    1-1,5 GB para RVC estaba sobreestimada; no hace falta serializarlos). Por eso `keep_alive`
    default es `"10m"` en vez de `0`: mantiene el modelo cargado entre turnos.
  - **`think=false` no es configurable a propósito**: con el thinking activo el modelo genera
    cientos de tokens de razonamiento antes de responder — verificado en vivo como inviable para un
    asistente hablado (demasiada latencia antes del primer `TextDelta`).
  - `message.tool_calls` en esta API llega **completo** (argumentos ya como dict, sin fragmentar
    entre chunks) — más simple que Claude, no hace falta acumular ni parsear JSON parcial. La API
    tampoco manda un `id` por tool call, así que `OllamaProvider` genera uno (`uuid4().hex`) para
    cumplir el contrato normalizado.
  - Cada `Done.usage` trae `prompt_eval_count`/`eval_count` y las duraciones de Ollama en ms
    (`load_duration_ms`, `prompt_eval_duration_ms`, `eval_duration_ms`, `total_duration_ms`); cada
    turno también lo loguea por consola, con la carga del modelo separada de la generación. Medido
    en esta máquina: con `keep_alive=0` (valor viejo) la carga rondaba ~4-4,5s en cada turno, sin
    bajar con turnos repetidos ni con la caché de páginas tibia — confirmado con `keep_alive="10m"`
    (valor actual) que el modelo sí queda cargado entre turnos: primer turno en frío ~4,2s de
    carga, turnos siguientes ~0,2-0,3s. Verificado tanto con `curl` directo a `/api/chat` +
    `/api/ps` como con `OllamaProvider` real end-to-end (incluyendo a través de
    `get_provider()`/`config.toml`, no solo con el valor pasado a mano).
  - **Bug encontrado y corregido durante la implementación**: el primer intento cortaba la
    iteración de `resp.aiter_lines()` con `break` apenas llegaba la línea con `done: true`, en vez
    de dejarla agotarse sola (el servidor cierra el body ahí mismo de todos modos). Un generador
    async abandonado a mitad de iteración (en vez de agotado) necesita un `athrow(GeneratorExit)`
    de limpieza que asyncio programa como Task aparte — si el loop del turno ya cerró para cuando el
    GC lo recolecta (el patrón exacto de `_drenar_stream_llm()`: loop nuevo y descartable por
    turno), esa Task se destruye a mitad de camino (`Task was destroyed but it is pending!`).
    Reproducido, diagnosticado y arreglado sacando el `break`.
- `llm/claude.py`: `ClaudeProvider`, streaming real vía `AsyncAnthropic`. Modelo por defecto
  `claude-sonnet-5` (familia intermedia, no el tope Opus 5/Fable 5 — para un asistente conversacional
  de escritorio la latencia importa más que la capacidad máxima, y cada turno reenvía el system
  prompt completo aunque esté cacheado; Haiku 4.5 es la alternativa más barata/rápida si hace falta
  apretar más, a costa de fidelidad de personaje). Configurable en `config.toml` → `[llm.claude]`
  (`model`, `max_tokens`). Detalles de la traducción de eventos:
  - System prompt como lista de bloques (`[{"type": "text", "text": system, "cache_control":
    {"type": "ephemeral"}}]`), no string plano — así es como Anthropic cachea el prefijo.
  - `max_tokens` es obligatorio en esta API (Rem usa 1024 por defecto: respuesta conversacional
    corta, no una tarea agéntica).
  - Traducción de eventos nativos → `Chunk`: `content_block_delta` con `text_delta` → `TextDelta`;
    `message_stop` (con el `stop_reason` de `message_delta` y el `usage` acumulado) → `Done`.
  - Tool calling: los argumentos llegan fragmentados como `input_json_delta` (`partial_json` por
    índice de bloque) — se concatenan y se parsean recién en `content_block_stop`, nunca delta por
    delta (el JSON parcial no es válido hasta estar completo).
  - Cada `Done` loguea `cache_creation_input_tokens`/`cache_read_input_tokens` por turno, para
    poder verificar a simple vista que el cache realmente pega.
- `llm/__init__.py`: `get_provider()` — decide el provider por `REM_LLM_PROVIDER` (env) >
  `[llm].provider` en `config.toml` > `"groq"` por defecto (hoy `config.toml` fija `"claude"`;
  `"ollama"` corre 100% local, sin API key). Lee `config.toml` a través de
  `config.leer_config_toml()` (ver más abajo). Si falta la API key del provider elegido
  (`ANTHROPIC_API_KEY`/`GROQ_API_KEY`), **falla acá mismo con un `RuntimeError` explícito** en vez
  de dejar que reviente recién en la primera petición con un error de conexión genérico — mismo
  criterio que `GroqProvider`/`ClaudeProvider` rechazando una `api_key` vacía en su propio
  `__init__` (`OllamaProvider` no tiene ese chequeo, no necesita key). Falla con `ValueError` claro
  si se pide un provider que no existe.
- `llm/sentence_splitter.py`: `dividir_en_oraciones()` consume un `AsyncIterator[Chunk]` y emite
  oraciones completas apenas se detecta su final (reutiliza la regla de corte de
  `_partir_oraciones()` en Rem.py: `. ! ?` seguido de espacio, descarta fragmentos < 3 chars).
  Maneja el caso de que una oración llegue partida entre dos chunks de red. **Construido pero
  todavía no conectado a `Rem.py`** — conectarlo requeriría tocar `responder()`/`hablar()`, más
  allá del único punto de llamada (`preguntar_groq()`) que se tocó en esta migración. Queda listo
  para cuando el backend deje de ser Tkinter y `hablar()` pueda ir hablando oración por oración a
  medida que llegan, en vez de esperar la respuesta completa.

**Cliente perezoso por event loop (Groq y Claude)**: ni `GroqProvider` ni `ClaudeProvider` crean su
cliente HTTP (`AsyncGroq`/`AsyncAnthropic`, ambos httpx por debajo) en `__init__` — lo arman recién
en el primer uso real, y lo recrean si el event loop actual cambió respecto al de la última llamada
(`_obtener_cliente()`). Motivo: un cliente httpx async que llega a abrir una conexión real queda con
su pool interno atado al loop que estaba corriendo en ese momento; si el provider se usara como
singleton y se lo llamara desde un loop nuevo — el patrón exacto de `_drenar_stream_llm()` más abajo,
un loop descartable por turno — reusar ese cliente revienta con `RuntimeError: Event loop is closed`.
Reproducido con `httpx.AsyncClient` puro (sin mocks): un request exitoso en un loop + el mismo
cliente reusado en otro loop distinto falla así — pero **solo si el primer request llegó a completarse
con éxito** (una conexión que nunca se estableció, p.ej. por un 401, no deja pool que reusar, así que
un test con una API key inválida no alcanza para reproducirlo).

**Integración en `Rem.py`**: `preguntar_groq()` llama a `_drenar_stream_llm()`, que hace de puente
sync→async: crea un event loop de asyncio nuevo y descartable (uno por turno, ya que `responder()`
corre en un hilo nuevo por cada mensaje del usuario), junta todos los `TextDelta` del stream en un
solo string, y lo devuelve — mismo contrato de entrada/salida que antes,
`responder()`/`procesar_respuesta()`/`hablar()` no se tocaron. Ese loop **no puede ser el del
`AudioWorker`** (`_worker_audio`): ese vive fijo en su propio hilo consumiendo su cola de audio, y un
loop de asyncio no es seguro de usar desde otro hilo sin `run_coroutine_threadsafe`. Es un puente
temporal: cuando Tkinter deje de ser el backend, este adaptador desaparece y se llama a
`stream_chat()`/`dividir_en_oraciones()` directo desde el loop async nativo del backend nuevo.
`extraer_memoria_importante()` (cada 8 mensajes) también pasa por `_drenar_stream_llm()` — usa el
mismo provider principal que la conversación, en vez de un cliente Groq síncrono aparte; si ese
provider no tiene su API key configurada, el `RuntimeError` explícito de `get_provider()` llega tal
cual al `except` de `extraer_memoria_importante()` y se loguea, sin tumbar el hilo.

**`config.py`** (módulo compartido, en la raíz, no en `llm/`): `cargar_dotenv()` (carga `.env` al
entorno vía `os.environ.setdefault`, tolera valores con `=` dentro gracias a `split("=", 1)` — las
API keys pueden llevarlo) y `leer_config_toml()` (parsea `config.toml` con `tomlkit`). Existe porque
`bench.py` y `bench_chat.py` no pueden importar `Rem.py` (ver "Banco de pruebas" más abajo) y antes
no veían ninguna variable de `.env` — `llm/__init__.py` también lo usa para leer `config.toml`, en
vez de tener su propia lectura duplicada.

**Banco de pruebas sin Tkinter (`bench_chat.py`)**: el Python 3.10.14 del venv se compiló sin
`_tkinter`, así que `Rem.py` no arranca ni se puede importar en este entorno (y Tkinter va a
desaparecer del proyecto de todos modos). `bench_chat.py` es el REPL async nativo para probar
`llm/` en aislamiento — en la línea de `bench.py` (que prueba lipsync/RVC/avatar sin el chat), pero
para el LLM: `chat <texto>` llama a `stream_chat()` directo con `async for` (sin el puente
sync→async, no hace falta: todo el REPL vive en un único `asyncio.run()`), `voz on|off` encadena la
respuesta al pipeline de voz existente (`lipsync.py` + RVC + `enviar_audio` de
`rem_avatar_server.py`, reusados tal cual), `reset` limpia el historial y `quit` cierra. Arranca el
avatar exactamente igual que `bench.py` (`config.cargar_dotenv()` → `iniciar_avatar()`).

## Configuración (.env en la raíz del proyecto)
```
ANTHROPIC_API_KEY=tu_api_key_de_anthropic
GROQ_API_KEY=tu_api_key_de_groq
NOMBRE_USUARIO=Esteban
CIUDAD=Yarumal
VOZ_REM=es-VE-PaolaNeural
TTS_RATE=-8%
REM_LAYER=top
REM_OVERLAY_W=520
REM_OVERLAY_H=860
RECORDATORIOS_ACTIVOS=false
MEMORIA_EXTRACCION_ACTIVA=true
```
`ANTHROPIC_API_KEY` es la que usa el provider activo (`claude`, ver `config.toml`); `GROQ_API_KEY`
solo hace falta si `[llm].provider`/`REM_LLM_PROVIDER` se cambia a `"groq"`. `get_provider()` falla
al arrancar con un mensaje explícito si falta la key del provider elegido — ver "Capa de
abstracción de LLM" más arriba.
`REM_LAYER` (`top`|`overlay`) y `REM_OVERLAY_W`/`REM_OVERLAY_H` los lee `rem_overlay.py`, no
`Rem.py` — controlan la capa del compositor y el tamaño fijo de la layer surface (ver
"Layer surface acotada" más abajo).
`RECORDATORIOS_ACTIVOS` (default `false`): dispara 5 llamadas al LLM al día (08:00, 14:00, 18:00,
22:00, 00:30) sin que el usuario haga nada — apagado por defecto porque la regla del proyecto es
que la API solo se usa cuando el usuario escribe o habla (ver "Nada volátil en el system prompt /
sin llamadas al LLM sin intervención del usuario" más abajo).
`MEMORIA_EXTRACCION_ACTIVA` (default `true`): `extraer_memoria_importante()` es una tarea de
extracción (no de conversación) que corre cada 8 mensajes, a través del mismo provider principal
que la conversación (ver "Capa de abstracción de LLM") — `false` la desactiva del todo.
Todas las variables tienen valores por defecto en el código. Solo la API key del provider activo
(`ANTHROPIC_API_KEY` por defecto) es obligatoria.

## Nada volátil en el system prompt (para que el prompt caching funcione)
El caching de prompts en los proveedores de inferencia (Groq incluido) exige que el prefijo sea
idéntico byte a byte entre llamadas para reusar el cache — cualquier cambio en el system prompt
(fecha, hora, estado de la PC, etc.) rompe el cache en cada turno y obliga a pagar el prompt
completo siempre. Por eso:
- `construir_prompt_sistema()` (usado como mensaje `system`) contiene **solo** contenido estable:
  personalidad, reglas y catálogo de acciones, con la memoria larga (`memoria_larga`) al final del
  bloque — así un cambio en la memoria no invalida la parte de arriba, que es la que más vale la
  pena mantener idéntica entre llamadas.
- Todo lo volátil (fecha/hora, estado de la PC vía `obtener_info_pc()`, memoria del sistema de
  archivos/carpetas conocidas) va en `construir_contexto_dinamico()`, que se antepone al **mensaje
  del usuario** en cada turno (dentro de `preguntar_groq()`), nunca al system prompt.
- Regla para futuros cambios: si algo cambia en cada turno (timestamps, métricas en vivo, conteos),
  no va en `construir_prompt_sistema()`.

## Ninguna llamada al LLM sin intervención del usuario
Requisito firme del proyecto: la API (Claude, o el provider que esté activo) solo se usa cuando el
usuario escribe o habla.
- `bienvenida()` (saludo al arrancar la app) usa una frase estática elegida al azar de
  `_SALUDOS_BIENVENIDA`, no llama al LLM.
- `RECORDATORIOS` (recordatorios automáticos por hora) está detrás de `RECORDATORIOS_ACTIVOS`,
  desactivado por defecto — ver más arriba.
- `extraer_memoria_importante()` sí llama al LLM sin intervención directa en ese instante, pero solo
  se dispara como consecuencia de turnos de conversación ya iniciados por el usuario (cada 8
  mensajes), nunca por un timer independiente — y es configurable vía `MEMORIA_EXTRACCION_ACTIVA`.

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
│   └── _drenar_stream_llm()            — event loop asyncio propio y descartable por turno
├── extraer_memoria_importante()        — daemon thread, cada 8 msgs
├── _loop_monitor_pc (daemon thread)    — alerta CPU/RAM cada 60s
└── _loop_recordatorios (app.after)     — recordatorios cada 30s, si RECORDATORIOS_ACTIVOS

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

## Configuración de voz ganadora (comparación A/B)
`VOZ_REM=es-VE-PaolaNeural`, `TTS_RATE=-8%`, `pitch_lvl=4`, `index_influence=0.75` — probado con
`test_voz.py --voz ... --rate ...` contra varias voces de edge-tts y comparado el resultado tras
pasar por RVC.

**Por qué esta combinación**: RVC transfiere el timbre del modelo (`Rem_600e_6600s`) pero no la
prosodia — el ritmo y la entonación de la voz de origen sobreviven la conversión casi intactos. Por
eso la voz de origen se elige por su **ritmo**, no por lo bien que suene cruda (`es-MX-DaliaNeural`
sonaba bien sin convertir, pero su cadencia no encajaba tan bien después de RVC). El `rate=-8%`
(más lenta que el default) mejora la fidelidad de la conversión: RVC tiene más margen por fonema
para trackear el pitch (`rmvpe`) correctamente cuando el audio de entrada no está acelerado.

## Limitación conocida: la `rr` vibrante suena imperfecta
El modelo RVC (`Rem_600e_6600s`) se entrenó con audio en japonés, un idioma sin el fonema vibrante
múltiple `/r/` (rr) del español — el modelo nunca aprendió a reproducirlo con fidelidad, así que en
palabras como "perro" o "corre" la conversión suena forzada/distorsionada.

Se intentó compensar bajando `index_influence` a 0.5, 0.3 y 0 (menos guiado por el index, más
libertad para el propio modelo) y no mejoró — a esos niveles se pierde timbre de Rem sin ganar
fidelidad en la `rr`, porque el problema no es de mezcla index/modelo sino que el modelo mismo no
tiene ese fonema en su espacio de entrenamiento. La solución real sería reentrenar el modelo con
audio de doblaje latino (que sí tiene `rr` vibrante), no ajustar parámetros de inferencia.

## Rendimiento medido (agosto 2026)
Medido en esta máquina (RTX 3050 Laptop, torch 2.3.1+cu121) con `test_voz.py`:
- `edge-tts`: ~1,5s por frase larga
- conversión RVC: ~3,3s para 12,2s de audio (factor 0,27× tiempo real, con GPU)
- salida de RVC: 40000 Hz
- configuración usada: `pitch_lvl=4`, `index_influence=0.75`

## RVC vuelve a GPU: calibración de num_gpu para hacerle sitio
Se probó primero mover RVC a CPU cuando el LLM local (`ollama`) satura la VRAM (ver historial más
abajo), pero medido en vivo con el `SentenceSplitter` ya conectado (ver más abajo) CPU no alcanza:
una frase corta tardó **~13,6s** en convertir en CPU frente a ~3-5s en GPU — casi 4,5× tiempo real,
así que la cola de conversión no le sigue el ritmo a la generación y la latencia termina peor que
sin el splitter. La solución real no era mover RVC a CPU, sino bajarle capas al LLM en GPU
(`num_gpu` de Ollama) para hacerle sitio a RVC en la misma tarjeta.

**Calibración empírica** (RTX 3050, 4 GB VRAM; modelo Qwen3.5-4B Q4_K_M, 32 capas —
`qwen35.block_count` vía `/api/show`). Para cada `num_gpu` candidato: se descargó el modelo
(`keep_alive: 0`), se recargó con ese `num_gpu` + una generación de 100 tokens (`num_predict: 100`,
`num_ctx: 4096`), se midió VRAM con `nvidia-smi` y tokens/s (`eval_count`/`eval_duration`), y se
intentó una conversión RVC real en CUDA:

| num_gpu | VRAM modelo | tok/s | RVC (cuda) |
|---------|-------------|-------|------------|
| 32 (default de Ollama, todas las capas) | ~2994 MiB | ~40,7 | **FALLA siempre** — CUDA out of memory |
| 28 | ~2714 MiB | ~25,8 | OK |
| 24 | ~2430 MiB | ~20,7 | OK |
| 20 | ~2156 MiB | ~16,9 | OK |
| 16 | ~1872 MiB | ~12,9 | OK |
| 12 | ~1596 MiB | ~12,3 | OK |
| 8  | ~1312 MiB | ~10,3 | OK |
| 4  | ~1061 MiB | ~8,3  | OK |
| 0 (CPU puro) | ~153 MiB | ~4,7 | OK |

En `num_gpu=32` el resultado de `rvc(...)` vuelve vacío, no una excepción visible — mismo mecanismo
de `infer_rvc_python` que traga excepciones de su hilo interno (ver más abajo). Se confirmó que es
un **OOM real, no la carrera intermitente**: repetido 4 veces seguidas con el modelo ya cargado en
`num_gpu=32`, las 4 veces salió vacío y las 4 veces el subproceso mostraba `CUDA out of memory` en
stderr — pese a que la VRAM libre en reposo (~1100 MiB) parecía alcanzarle a los ~790 MiB que RVC
necesita, el pico real durante la conversión (fragmentación + el propio LLM sin liberar su
allocator) lo excede.

`num_gpu=28` se verificó robusto (no "la primera que pasó"): conversión repetida varias veces, con
una frase corta y con una de ~13s de audio, sin fallar ninguna — con VRAM libre de sobra
(~1300+ MiB) a diferencia del filo de 32. Es el valor más alto que cumple el objetivo ("no bajes más
de lo necesario"): bajar a 24 ya cuesta ~20% de tok/s sin ganar nada, la VRAM libre en 28 ya sobra.
Configurado en `config.toml` → `[llm.ollama].num_gpu = 28`, pasado en cada petición vía
`get_provider()` → `OllamaProvider._options["num_gpu"]` (se reenvía tal cual en el payload, sin
lista blanca de claves).

La velocidad de generación no se degrada de forma inviable ni siquiera en el otro extremo (CPU
puro, `num_gpu=0`, ~4,7 tok/s) — no hizo falta evaluar la cuantización Q3_K_M para este objetivo, ya
que `num_gpu=28` deja tok/s (~25,8) muy por encima del piso aceptable sin sacrificar VRAM de sobra.

`device` en `config.toml` → `[rvc]` vuelve a `"cuda"` por defecto (`"cpu"` sigue disponible: sirve
si el provider activo no es `ollama`, o para liberar toda la GPU por algún otro motivo) — vía
`config.leer_dispositivo_rvc()`, aplicado en `bench.py`, `bench_chat.py`, `test_voz.py` y `Rem.py`
(los cuatro construyen su `BaseLoader` con `only_cpu=(dispositivo == "cpu")`). Verificado en vivo
end-to-end tras el cambio: LLM (`num_gpu=28`) → `SentenceSplitter` → RVC en CUDA, dos oraciones de
una respuesta real, ambas convertidas sin OOM.

## SentenceSplitter conectado en bench_chat.py
`llm/sentence_splitter.py` estaba construido y testeado pero sin ningún consumidor real. Ahora
`bench_chat.py._chat()` lo usa así: consume `provider.stream_chat()` con un pequeño tee
(`_pasar_por()`, ya que un async generator es de un solo consumidor) que por un lado imprime el
texto y registra `Done`/tool_calls tal como antes, y por otro alimenta `dividir_en_oraciones()` —
cada oración completa se encola (`asyncio.Queue`) apenas está lista, sin esperar el resto de la
respuesta. Un único worker (`_worker_habla()`, una tarea de fondo creada al arrancar el REPL)
consume esa cola en orden y llama a `_decir()` por oración.

- La conversión RVC dentro de `_decir()` corre en `asyncio.to_thread()`: es una llamada
  bloqueante, y si corriera en el loop principal frenaría también al productor (`_chat()` leyendo
  el siguiente chunk del LLM) — exactamente lo que se quiere solapar. `enviar_audio()` no espera a
  que termine de reproducirse, solo despacha — por eso alcanza con un worker secuencial (no hace
  falta paralelismo real entre oraciones) para lograr el solape: mientras la oración N sí ya está
  sonando en el frontend, el worker sigue de largo con la N+1.
- Medido en vivo (modelo Ollama a ~13 tok/s, RVC en CPU): una respuesta de 3 oraciones/67 tokens
  tardó ~24s en generarse completa, pero el primer audio salió a los ~43s en un caso (RVC en CPU es
  más lento que la generación) — la métrica que importa acá es la comparación entre "tiempo hasta
  el primer audio" y "tiempo total", ambas logueadas por turno (`_TurnoHabla`), para poder decidir
  después si el solape compensa según qué tan lento esté RVC ese día.
- **Bug real encontrado en vivo, no de este código**: `infer_rvc_python`'s `BaseLoader.__call__`
  spawnea un hilo interno (`threading.Thread(target=self.infer)`) por archivo y lo joinea
  (`run_threads`) antes de devolver — pero si esa excepción ocurre en el frame de la excepción no
  se re-lanza, así que el error queda parcialmente silenciado: se vio consistentemente en pruebas
  aisladas mínimas que replican exactamente el patrón de `_decir()` (con y sin `asyncio.to_thread`)
  **sin** reproducirlo, y de forma intermitente en el flujo real de `bench_chat.py` con RVC llamado
  varias veces por turno (una vez por oración) — no se identificó la causa exacta de la carrera,
  solo que existe y es intermitente. Cuando pasa, `__call__` devuelve una lista vacía en vez de
  lanzar, así que `_decir()` ya lo tolera (cae a la voz cruda de edge-tts sin convertir para esa
  oración en particular, no se cae ni se traba el pipeline) — se agregó un log explícito
  (`"RVC no devolvió resultado — hablando sin convertir"`) para que ese fallback silencioso se note.
  **Confirmado después, durante la calibración de `num_gpu`** (ver "RVC vuelve a GPU" más arriba):
  un resultado vacío no implica necesariamente esta carrera intermitente — un CUDA out of memory
  real pasa por el mismo camino silencioso (el hilo interno lo traga igual), y solo se distingue
  mirando `stderr` del proceso. Con `num_gpu=28` ya calibrado esto no debería dispararse por falta
  de VRAM, pero si vuelve a aparecer el log de fallback, no asumir que es "la carrera de siempre"
  sin antes descartar OOM.

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

## Cómo three.js construye morphTargetDictionary (importante para el lipsync)
Investigado leyendo el bundle real de `three@0.169.0` y su `GLTFLoader`, porque el diagnóstico
inicial de "0 mallas con visemes" tenía una hipótesis que resultó **incorrecta**:

- **`PropertyBinding.sanitizeNodeName()` NO interviene en `morphTargetDictionary`.** Esa función
  (`t.replace(/\s/g,"_").replace(/[\[\].:\/]/g,"")`) se usa para nombres de *tracks* de animación,
  no para construir el diccionario de morph targets. De hecho, si interviniera, el punto de
  `vrc.v_aa` se **eliminaría** (`"vrcv_aa"`), no se reemplazaría por `_` (`"vrc_v_aa"`) — el propio
  regex es `[\[\].:\/]`, que quita el carácter en vez de sustituirlo.
- **`GLTFLoader` usa los nombres crudos de `extras.targetNames` tal cual**, sin sanitizar:
  `mesh.morphTargetDictionary[targetNames[i]] = i`. Si el modelo trae `"vrc.v_aa"` en el glTF, la
  clave en el diccionario es literalmente `"vrc.v_aa"`.
- **La causa real y más probable de que el diccionario no aparezca**: `GLTFLoader` solo construye
  `morphTargetDictionary` si `mesh.morphTargetInfluences.length === extras.targetNames.length`
  *para ese primitive específico*. Si algún primitive de la malla tiene una cantidad de morph
  attributes distinta a los 59 de `targetNames` (común cuando el exportador reparte los morphs de
  forma desigual entre primitives de un mismo mesh con varios materiales), el diccionario **no se
  crea en absoluto** para ese primitive — sin importar los nombres — y GLTFLoader tira
  `console.warn("THREE.GLTFLoader: Invalid extras.targetNames length. Ignoring names.")`, que hasta
  ahora nadie estaba mirando.
- `VRMUtils.removeUnnecessaryJoints` (el único util de VRMUtils que se llama en `rem_avatar.html`)
  solo rebindea el `Skeleton` de los `SkinnedMesh` — no toca geometría ni `morphTargetDictionary`.
  Se descartó como causa.

`localizarMallaFacial()` en `rem_avatar.html` ahora hace dos cosas para que esto no se vuelva a
redescubrir a ciegas: (1) loguea el nombre de cada malla y todas sus claves de
`morphTargetDictionary` tal como llegan, sin asumir formato; (2) para mallas SIN diccionario pero
con `geometry.morphAttributes.position` no vacío, loguea explícitamente el mismatch de longitud
como sospechoso. La comparación contra `VISEME_NAMES` es normalizada (minúsculas + solo
alfanumérico) como defensa adicional, pero según lo de arriba probablemente no haga falta —
`vrc.v_aa` debería llegar tal cual.

**Confirmado en vivo — ninguna de las dos hipótesis de arriba era la causa.** El navegador real
reporta 72 mallas con `morphTargetDictionary` construido y 0 con mismatch de longitud, pero ninguna
con claves `vrc.*`: los nombres reales son genéricos tipo `Bodybaked_NN` (numéricos). El mecanismo
exacto por el que three-vrm termina asignando esos nombres en vez de los de `extras.targetNames`
sigue sin confirmarse (no es `GLTFLoader`, que ya probamos que usa los nombres crudos tal cual) —
pero para el lipsync no importa, porque hay un camino mejor que no depende del nombre en absoluto:

- El archivo tiene **un solo mesh** (`Body.baked`, índice 0) con **72 primitives**, uno por grupo de
  material. Confirmado con Python directo sobre el JSON crudo del glTF (sin depender del navegador):
  las 72 primitives comparten **exactamente la misma lista de 59 `targetNames`, en el mismo orden**.
  Eso significa que un **índice** de morph target es válido universalmente en las 72 — no hace falta
  el nombre para nada, ni siquiera el que asigna three-vrm en runtime.
- Los `binds` de `blendShapeMaster.blendShapeGroups` en VRM 0.x apuntan a `{mesh: <índice en
  gltf.meshes[]>, index: <índice de morph target>}` directo — por eso `expressionManager` resuelve
  bien sin pasar por el nombre. `bind.mesh` **no** es un índice de `gltf.nodes[]` (fue el primer error
  al investigar esto): con un solo mesh en el archivo, `bind.mesh` es siempre `0`.
- Tabla de índices de los 15 visemes VRChat/Oculus, extraída de `extras.targetNames` de la
  primitive 0 (representativa de las 72): `vrc.v_aa`=4, `v_ch`=5, `v_dd`=6, `v_e`=7, `v_ff`=8,
  `v_ih`=9, `v_kk`=10, `v_nn`=11, `v_oh`=12, `v_ou`=13, `v_pp`=14, `v_rr`=15, `v_sil`=16, `v_ss`=17,
  `v_th`=18. También `vrc.blink_left`=0, `vrc.blink_right`=1.
- **Hallazgo colateral, afecta al último fallback (`expressionManager`, 5 visemes VRM)**: los
  `blendShapeGroups` A/I/U/E/O del modelo **no** corresponden 1:1 a `aa/ih/ou/ee/oh`. Confirmado con
  los binds crudos: `A`→`vrc.v_aa` (bien), `E`→`vrc.v_e` (bien), `O`→`vrc.v_oh` (bien), pero
  **`I`→`vrc.v_ff`** (el bind apunta a la fricativa F, no a una forma de "i") y **`U` no tiene ningún
  bind** (lista vacía — seleccionar el preset "ou" no mueve nada). Esto es una imperfección de cómo
  se exportó/riggeó el modelo original, no un bug de este proyecto — pero significa que si algún día
  `_viaLipsync` cae hasta ese último fallback (`FONEMA_A_VISEME_VRM` en `lipsync.py`, vía
  `expressionManager`), reproduce mal los fonemas "i" y "u" en este modelo específico. Con la vía por
  índice implementada más abajo, ese fallback ya no se usa para `rem.vrm`.
- **Implementado**: `rem_avatar.html` aplica `mesh.morphTargetInfluences[índice]` directo con la
  tabla de arriba (`VISEME_INDEX`), en vez de `morphTargetDictionary[nombre]` — evita tanto el
  problema del nombre como el de los binds A/I/U/E/O incompletos del modelo. `localizarMallaFacial()`
  registra en `_visemeMeshesPorIndice` **todas** las mallas con `morphTargetInfluences.length > 18`
  (las 72 primitives de `Body.baked` en este modelo) y `setViseme()` escribe en todas ellas a la vez
  — escribir en una sola movería la cara a trozos, porque three.js las carga como 72 `Mesh`
  independientes que comparten geometría pero no el array de influences.
  - Tres vías con prioridad `indice > nombre > expressionManager` (`_viaLipsync`), decidida una vez
    al cargar el modelo. La vía "nombre" (`morphTargetDictionary`) y la de `expressionManager` (5
    visemes estándar de VRM) quedan como fallback para si algún día se carga un modelo distinto sin
    estos morphs vrc.\* por índice.
  - Orden crítico igual que antes: la vía por índice/nombre escribe **después** de `vrm.update(dt)`
    (expressionManager no las toca, así que no hay pisado); la vía `expressionManager` escribe
    **antes**, porque `vrm.update()` es lo que consume `setValue()` y aplica los morphs reales.
  - `updateExpressions()` suprime el peso de la expresión `surprised` mientras hay audio de lipsync
    activo (`_audioSource` truthy): sus binds incluyen los morphs **25, 38 y 41** (fuera del rango
    4-18 de los visemes, pero igual gestos de boca) que si no competirían visualmente con el viseme
    activo. `Talk` bindea el morph **19** (también boca) pero nunca se llama desde ningún lado del
    código — no hizo falta suprimirla aparte.
- **`lookUp`/`lookDown`/`lookLeft`/`lookRight` tampoco tienen binds** (mismo problema que la
  expresión `ou`/`U` de arriba: listas vacías, seleccionar esos presets no mueve nada) — la mirada
  por expresiones (`expressionManager`) no funciona en este modelo, para ninguna dirección. La forma
  real de implementar mirada acá es `vrm.lookAt` operando sobre los huesos `leftEye`/`rightEye` (ver
  "Huesos humanoides" arriba, sí existen y están mapeados), no sobre blend shapes.

## Reproducción de audio: `<audio>` de HTML, no Web Audio API
Se intentó primero con `AudioContext` (Web Audio API), con `resume()` en gestos de usuario
(`click`/`keydown`/`touchstart`) para desbloquear el autoplay. **No funcionaba en el overlay**: es
**click-through por diseño** (`_aplicar_click_through` en `rem_overlay.py`) — nunca va a recibir un
gesto real, así que el `AudioContext` quedaba `'suspended'` para siempre ahí adentro.
`WebKitSettings.set_media_playback_requires_user_gesture(False)` (probado en `rem_overlay.py`) **no
resolvía esto**: esa política de WebKit2 solo aplica a elementos de medios (`<audio>`/`<video>`), no a
la Web Audio API — por eso `AudioContext` seguía bloqueado pese a desactivarla.

La solución fue eliminar el problema de raíz: `rem_avatar.html` reproduce con un `HTMLAudioElement`
(`new Audio()`) en vez de `AudioContext`/`AudioBufferSourceNode`. Se creó **una sola vez** y se
reutiliza para toda la cola (no una instancia por frase): a cada turno de la cola se le asigna
`.src` y se llama `.play()` de nuevo. **Corrección sobre la afirmación original de este bloque**:
en su momento se creyó que `HTMLMediaElement.play()` no tenía ninguna restricción de gesto de
usuario en este WebView y que por eso no hacía falta ningún workaround — resultó ser incompleto,
ver "Regresión repetida de la política de autoplay" más abajo: sí hay una restricción, solo que la
controla un mecanismo distinto de `media-playback-requires-user-gesture`.

- El lipsync ya no necesita `audioContext.currentTime - startTime`: `audio.currentTime` ya es la
  posición dentro del archivo actual, leída directo en cada frame — sobra de precisión a 60fps.
- `estado = 'talking'` se activa en el evento `playing` y se desactiva en `ended` (que también
  encadena la siguiente reproducción de la cola, igual que antes con `source.onended`).
- Si `play()` devuelve una promesa rechazada, se loguea el motivo (`console.error`) para poder
  diagnosticar si alguna otra política de autoplay llegara a bloquear en el futuro.
- Se eliminó el mensaje `{"tipo": "audio_bloqueado"}` que el frontend mandaba de vuelta por
  WebSocket y el fallback a `sounddevice` en `rem_avatar_server.py` que dependía de él — ya no hace
  falta, `_ws_handler` volvió a descartar todo lo que llega del cliente (solo le importa el cierre
  de conexión, para el log breve en vez de traceback).

## Regresión repetida de la política de autoplay
`play()` volvió a rechazarse con `NotAllowedError` una segunda vez, con el mismo síntoma que la
sección anterior. El patrón de código en `rem_overlay.py` era `webview = WebKit2.WebView();
settings = webview.get_settings()` y recién ahí se llamaba a `settings.set_media_playback_requires_
user_gesture(False)` junto a los demás `set_*` — agregar `set_enable_write_console_messages_to_
stdout(True)`/`set_enable_developer_extras(True)` (para el volcado de consola, ver más arriba) puso
código nuevo por delante en el bloque y volvió a romperlo, la MISMA clase de fragilidad que ya había
pasado una vez antes.

**La causa real no era el orden del bloque — el diagnóstico original quedó incompleto.**
Investigando en vivo (Hyprland real, probando `say` con `bench.py` y leyendo el log del overlay)
con el orden ya arreglado (`WebKit2.Settings()` armado aparte, completo, antes de crear el WebView
vía `WebKit2.WebView.new_with_settings(settings)` — así el orden interno de los `set_*` deja de
importar) **el `NotAllowedError` seguía pasando igual**. `WebKitSettings:media-playback-requires-
user-gesture` no es lo único que controla esto en WebKitGTK 2.52: hay un mecanismo separado y más
nuevo, `WebKitWebsitePolicies` con la propiedad `autoplay` (`WebKitAutoplayPolicy`: `ALLOW` /
`ALLOW_WITHOUT_SOUND` / `DENY`) — confirmado con `list_properties()` que el nombre real de la
propiedad es `"autoplay"`, no `"autoplay-policy"`. Es el que de verdad decide si
`HTMLMediaElement.play()` se rechaza.

`WebsitePolicies` es una propiedad de **construcción** del `WebView` (`website-policies`, junto a
`settings`), no algo que se pueda mutar después sobre un WebView ya creado — por eso el fix final
construye los tres objetos (`Settings`, `WebsitePolicies`, `WebView`) en ese orden estricto, con
`WebView(settings=settings, website_policies=policies)`:

```python
policies = WebKit2.WebsitePolicies(autoplay=WebKit2.AutoplayPolicy.ALLOW)
webview = WebKit2.WebView(settings=settings, website_policies=policies)
```

Verificado en vivo: sin `WebsitePolicies`, el log mostraba `[Lipsync] play() rechazado ... name:
NotAllowedError`; con `WebsitePolicies(autoplay=ALLOW)`, `[Lipsync] play() resuelto (promesa)`. Se
mantiene también `media-playback-requires-user-gesture(False)` en `Settings` (por si algún otro
camino de reproducción lo consulta), pero **no alcanza solo** — los dos mecanismos son
independientes y hace falta el segundo.

## Encuadre del avatar: anclas normalizadas, no world units fijas
`recalcularEncuadre()` deriva `camera.position.z` para que el modelo ocupe `CONFIG.pet.alturaPantalla`
del alto de pantalla, y `vrm.scene.position.y` para que su centro caiga en `CONFIG.pet.anchorY`
(fracción 0=arriba..1=abajo). La cámara mira siempre a `(0,0,0)`; todo el trabajo de encuadre lo hace
la posición del modelo, no la cámara. `CONFIG.pet.anchorX`/`walkLeft`/`walkRight` son fracciones de
pantalla (0=izq..1=der) — `worldX(n)` las convierte a coordenadas de mundo recién al escribir
`vrm.scene.position.x`, así que sobreviven a un resize sin que Rem salte de lugar. Se llama en la
carga del VRM y en cada `resize`.

**La altura del modelo se mide con huesos, no con `Box3`.** El primer intento usaba
`new THREE.Box3().setFromObject(vrm.scene)`, que para un VRM con `SkinnedMesh` da la caja de la
geometría **sin aplicar el skinning** — el shader deforma los vértices en la GPU, no en los datos de
`geometry.attributes.position` en CPU, así que `Box3` mide aproximadamente la mitad de la altura real
(medido en este modelo, cifras exactas confirmadas en vivo: Box3 = 0,801u vs. huesos = 1,623u — el
diagnóstico original con cifras aproximadas, 0,80u/1,55u, quedó confirmado por una medición real
posterior). La fórmula de encuadre en sí es correcta
para *cualquier* altura que se le pase (normaliza a `alturaPantalla`/`anchorY` por construcción) — el
bug no estaba ahí, sino en que `Box3` alimentaba un dato de altura equivocado: la cámara terminaba
demasiado cerca para el tamaño *real* renderizado (más grande que el medido), así que la cabeza se
salía del cuadro aunque los números de `recalcularEncuadre()` parecieran consistentes.

La medición real: `vrm.humanoid.getRawBoneNode('head'|'leftFoot'|'rightFoot')` +
`getWorldPosition()`, altura = `head.y - min(leftFoot.y, rightFoot.y)`, con **+18%** extra arriba
para cubrir pelo/adornos que no tienen hueso propio. Se hace con `getRawBoneNode` (huesos reales ya
posados), no el proxy normalizado. Y se hace **un frame después** de la carga (flag
`_medirHuesosPendiente`, consumido en `animate()` tras el primer `vrm.update(dt)`), no en el mismo
frame del `gltf.load()` callback, porque recién ahí el esqueleto refleja la pose real (antes puede
seguir en un estado intermedio del importador). La medición inicial por `Box3` se conserva como
placeholder para el primer frame o dos, y ambas cifras (Box3 y huesos) quedan logueadas para comparar.

## Layer surface acotada (rendimiento del overlay)
`rem_overlay.py` ancla la layer surface solo a `RIGHT`+`BOTTOM` con tamaño fijo
(`win.set_size_request`, default 520×860, configurable por `.env` con `REM_OVERLAY_W`/`REM_OVERLAY_H`)
en vez de a los 4 bordes. Anclar a los 4 bordes hacía que el compositor estirara un canvas WebGL
transparente del tamaño del monitor entero, renderizado a 60fps de forma permanente sobre todo el
escritorio — con las ~103 cadenas de spring bones de este modelo, costo constante innecesario.
`set_exclusive_zone(-1)` y el click-through se mantienen igual.

**Dos regresiones que introdujo ese cambio, ya arregladas:**

- **Click-through roto**: `_aplicar_click_through()` (input region vacía vía
  `input_shape_combine_region`) solo se aplicaba en `realize`. Con anclaje a los 4 bordes eso
  alcanzaba porque la superficie no se reasignaba después; con `RIGHT+BOTTOM` + tamaño fijo, el
  compositor puede reasignar/redimensionar la superficie después de `realize`, y la input region
  vacía no sobrevive a eso — el overlay volvía a capturar clics en su esquina. Se refuerza también
  tras `show_all()` y en cada señal `size-allocate`.
- **Rem no se veía en el overlay** (pero sí en un navegador normal, con lipsync funcionando — o sea
  no era un bug de JS): la superficie de 520×860 tiene aspect ~0,60 (vertical), no 16:9 como un
  monitor. `CONFIG.pet.anchorX=0.82` está pensado para un monitor ancho donde Rem camina por un
  tercio de pantalla; en una superficie angosta dedicada solo al avatar, ese offset cae fuera (o casi
  fuera) del recuadro visible, porque `anchoVisible` en `recalcularEncuadre()` es mucho más chico en
  vertical. `_ajustarAnclasPorAspect()` en `rem_avatar.html` colapsa `anchorX`/`walkLeft`/`walkRight`
  a `0.5` (centrado, sin caminata lateral) cuando `camera.aspect < 1`, reevaluado en cada
  `recalcularEncuadre()` (carga + resize) — así que si algún día la superficie vuelve a ser ancha,
  vuelve a las anclas originales solo. `BORDE_IZQ`/`BORDE_DER` en `tickPet()` pasaron de `const`
  cacheadas a leer `CONFIG.pet.walkLeft`/`walkRight` en vivo, si no el ajuste no tenía efecto ahí.

## Arranque del overlay: sin divergencia entre bench.py y bench_chat.py, pero riesgo de conflicto de puertos
Investigado tras un reporte de que `bench.py` había dejado de lanzar el overlay mientras
`bench_chat.py` sí lo hacía. Probado en vivo (Hyprland real, no headless) corriendo cada script por
separado con stdin cerrado tras ~10s: **ambos cargan el overlay de forma idéntica y exitosa** —
mismo `rem_overlay.log` (VRM cargado, WS conectado, expresiones resueltas), sin ningún error. La
secuencia de arranque del avatar es byte-a-byte la misma en los dos (`config.cargar_dotenv()` →
`iniciar_avatar()` → `_abrir_navegador()` opcional) desde que `bench.py` también empezó a llamar a
`config.cargar_dotenv()`, así que ese cambio no es la causa — no se pudo reproducir el reporte
original en este entorno.

**Riesgo real encontrado en el camino** (no confirmado como la causa de aquel reporte, pero sí un
bug latente): `rem_avatar_server.py._iniciar_ws()` llama a `_ws_ready.set()` **antes** de intentar
`websockets.serve(...)`. Si el puerto `:18766` ya está ocupado (p.ej. porque `bench.py`,
`bench_chat.py` o `Rem.py` ya está corriendo en otra terminal), `websockets.serve()` lanza una
excepción dentro del hilo daemon `AvatarWS` — que muere en silencio (una excepción no capturada en
un `threading.Thread` no se propaga al hilo principal) — pero `_ws_ready` ya quedó en `True` desde
antes de ese fallo. `iniciar_avatar()` nunca se entera: `_lanzar_overlay()` se llama igual, y el
overlay termina intentando hablarle a un WebSocket que en ESTE proceso nunca llegó a levantar (aunque
sí puede haber uno ajeno, del otro proceso, sirviendo ese mismo puerto). Si dos instancias de
Rem/bench/bench_chat corren en simultáneo, la segunda puede terminar así — con un overlay que se ve
"no funcionar" sin ningún error visible. No se tocó porque no se confirmó que sea la causa real del
reporte; si vuelve a pasar, revisar primero si hay más de un proceso corriendo a la vez.

## Segunda regresión del overlay: no es el bug de _ws_ready, es un crash interno de WebKit
Investigado tras un nuevo reporte de que el overlay volvió a no aparecer. Revisando
`rem_overlay.log` de una corrida real (proceso único, sin nada más corriendo — descartado el bug de
`_ws_ready` de arriba: no había puerto ocupado ni segunda instancia) aparece esto:

```
CONSOLE NETWORK ERROR WebSocket connection to 'ws://localhost:18766/' failed: WebSocket network error: Network process crashed.
ERROR: WebKit encountered an internal error. This is a WebKit bug.
.../WebKit/WebProcess/Network/WebLoaderStrategy.cpp(640) : void WebKit::WebLoaderStrategy::internallyFailedLoadTimerFired()
[native code]: CONSOLE WARN [WS] Error de conexión: error
.../GLTFLoader.mjs:2:3766: CONSOLE ERROR [VRM] error: TypeError: Load failed
```

El **proceso de red de WebKit2GTK 2.52.5 se cae** (el propio mensaje de WebKit dice "this is a
WebKit bug", no algo que dispare el código de Rem) justo mientras la página tiene dos fetches en
vuelo: el WebSocket y el `fetch()` del glTF/VRM. El WebSocket se reconecta solo un instante después
(se ve `[WS] conectado` de nuevo en la misma corrida, y el audio sigue funcionando bien el resto de
la sesión) — pero la carga del VRM **no tiene ningún reintento**, así que si el crash pega justo en
esa ventana, el avatar queda invisible por el resto de la sesión aunque el resto del pipeline
(audio, lipsync, WS) siga andando con normalidad. Esto explica el síntoma reportado sin ser el
mismo bug que la sección anterior.

**Reproducido de forma consistente** en este entorno (dos corridas limpias seguidas, sin procesos
previos, mismo resultado) — no fue un evento aislado. Se revisó lo obvio (procesos WebKit
colgados, espacio en disco, RAM, `journalctl`/`dmesg`) sin encontrar una causa de recursos: nada
lo explica desde ese lado. Sí aparecen mensajes de `xdg-desktop-portal`/`wireplumber` sin relación
aparente alrededor de la misma hora en el journal del usuario, que podrían apuntar a la sesión de
Hyprland en un estado degradado tras uso intensivo prolongado (muchos lanzamientos de overlay en
esta sesión de trabajo) — no confirmado como causa, solo una correlación observada.
No se implementó ningún arreglo en su momento (por ejemplo, reintentar la carga del VRM igual que ya
se reintenta `load-failed` del WebView) porque la causa raíz es un bug interno de WebKit, no algo en
este código — si vuelve a pasar, lo primero a probar es reiniciar la sesión de Hyprland.

### Arreglo: reintento con espera exponencial en la carga del VRM
La causa raíz sigue sin arreglarse (sigue siendo un bug de WebKit), pero que el avatar quede
invisible el resto de la sesión por un crash transitorio sí era evitable — igual que el WebSocket ya
se reconecta solo. `_cargarVRM(intento)` en `rem_avatar.html` envuelve el `loader.load()` original:
si el callback de error dispara, loguea `[VRM] error (intento N/5): ...` y, si quedan intentos,
reintenta con `setTimeout` tras `min(500 * 2**intento, 5000)` ms (mismo patrón — base, exponente,
tope — que el retry de `load-failed` en `rem_overlay.py`); al agotar los 5 intentos loguea
`"no se pudo cargar tras 5 intentos"` y se rinde, en vez de reintentar para siempre.

**Verificado en vivo, tres escenarios** (con `bench.py`, cache de WebKit limpiada entre corridas en
`~/.cache/rem_overlay.py/WebKitCache` para no servir una copia vieja de `rem_avatar.html` — la
cache en disco de WebKit2GTK persiste entre lanzamientos del proceso y puede enmascarar cambios
recién hechos al archivo si no se limpia):
1. Carga normal (sin fallas): sin regresión, el avatar carga igual que antes.
2. Falla transitoria real (se renombró `rem.vrm` para forzar un 404, y se restauró a los ~5s,
   a mitad de la secuencia de reintentos): intento 1 falla y loguea "reintentando en 1000ms...";
   para cuando dispara el reintento el archivo ya está de vuelta, y la carga siguiente
   **se completa con éxito** (`[VRM] OK | expressions: ...`) — el escenario real que motivó el
   pedido.
3. Falla persistente (archivo ausente durante toda la ventana de prueba): se ven los 5 intentos
   con backoff creciente (1000, 2000, 4000, 5000, y el quinto ya sin más espera) y el mensaje final
   de rendición — confirma que no reintenta indefinidamente.


    # IMPORTANTE: 
    AL MOMENTO DE HACER COMMIT NO PONGAS TU AUDITORIA Claude/Anthropic DETRO DEL COMMIT
