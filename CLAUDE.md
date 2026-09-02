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
| Overlay / ventana | GTK3 + WebKit2, `venv/bin/python` (PyGObject/pycairo instalados ahí, ver "El venv sí puede tener GTK" más abajo) |
| fairseq | v0.12.2 con shim de compatibilidad (`fairseq_shim/`) |

## Archivos principales
| Archivo | Qué hace |
|---------|----------|
| `Rem.py` | App principal: GUI Tkinter, chat, TTS/RVC, acciones, memoria |
| `rem_avatar_server.py` | Servidor HTTP `:18765` + WebSocket `:18766` para el avatar |
| `rem_overlay.py` | Overlay GTK transparente click-through (`?modo=overlay`) |
| `rem_chat.py` | Ventana GTK decorada y con foco (`?modo=ventana`) — ver "Ventana de escritorio" más abajo |
| `rem_avatar.html` | Frontend Three.js/VRM del avatar — animación (clips VRMA para el cuerpo + procedural para respiración/mirada/gestos) + panel de chat HTML/CSS/JS (solo modo ventana), un motor para los dos modos |
| `Animaciones/` | Clips `.vrma` del avatar — no van al repo, se descargan a mano. Ver `Animaciones/README.md` y "Animación de cuerpo con clips VRMA" más abajo |
| `chat_sesion.py` | `SesionChat` + `procesar_turno()` — estado de una conversación y el turno "en crudo" contra el LLM, compartido entre `bench_chat.py` y el panel de chat de `rem_chat.py`. Ver "Panel de chat" más abajo |
| `habla.py` | Pipeline de voz de un turno (TTS -> RVC -> `enviar_audio()`), compartido entre `bench_chat.py` y el panel de chat. Ver "Voz en la ventana de chat" más abajo |
| `fairseq_shim/__init__.py` | Shim que reemplaza el `__init__.py` de fairseq para compatibilidad PyTorch |
| `fairseq_shim/checkpoint_utils.py` | Fork de fairseq con `torch.load(weights_only=False)` |
| `apply_shim.py` | Copia `fairseq_shim/` sobre el fairseq instalado en `venv/`. Ejecutar tras cualquier reinstalación de fairseq |
| `llm/` | Capa de abstracción de LLM (contrato + providers). Ver "Capa de abstracción de LLM" más abajo |
| `config.py` | Módulo compartido: carga `.env` y lee `config.toml`. Lo usa `Rem.py` y `bench_chat.py` — `bench_chat.py` no puede importar `Rem.py` (ver más abajo), así que sin esto no vería las variables de entorno |
| `config.toml` | Config no sensible versionada en git (a diferencia de `.env`, que tiene los secretos) — hoy solo `[llm]` / `[llm.claude]` |
| `bench_chat.py` | REPL async nativo: prueba la capa `llm/` (modo ia) y voz/lipsync/avatar (modo eco), sin Tkinter. Ver "Capa de abstracción de LLM" más abajo y "bench.py eliminado" más abajo |

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
`bench_chat.py` no puede importar `Rem.py` (ver "Banco de pruebas" más abajo) y antes no veía
ninguna variable de `.env` — `llm/__init__.py` también lo usa para leer `config.toml`, en vez de
tener su propia lectura duplicada.

**Banco de pruebas sin Tkinter (`bench_chat.py`)**: el Python 3.10.14 del venv se compiló sin
`_tkinter`, así que `Rem.py` no arranca ni se puede importar en este entorno (y Tkinter va a
desaparecer del proyecto de todos modos). `bench_chat.py` es el REPL async nativo que cubre tanto
`llm/` como voz/lipsync/avatar, con dos modos alternables en caliente (`SesionChat.cambiar_modo()`,
ver "bench.py eliminado" más abajo): `chat <texto>` llama a `stream_chat()` directo con `async for`
(sin el puente sync→async, no hace falta: todo el REPL vive en un único `asyncio.run()`), `voz
on|off` encadena la respuesta al pipeline de voz existente (`lipsync.py` + RVC + `enviar_audio` de
`rem_avatar_server.py`, reusados tal cual), `state <estado>` / `open` controlan el avatar
directamente, `reset` limpia el historial y `quit` cierra. Arranca el avatar con
`config.cargar_dotenv()` → `iniciar_avatar()`.

## Modo eco (`llm/echo.py`) y `bench.py` eliminado
`EchoProvider` implementa el contrato de `LLMProvider` sin llamar a ningún modelo: busca el último
`Message` con `role="user"` en la lista (no asume que sea el último elemento, aunque en el uso normal
lo es) y lo emite tal cual como un único `TextDelta`, ignorando `system` y `tools` por completo, y
cierra con `Done(reason="stop")`. Sin estado, sin cliente HTTP, sin API key — nada que inicializar.
Registrado en el factory (`llm/__init__.py`) como provider `"echo"`, sin requerir configuración.
Sirve para que Rem repita con su voz lo que se escriba, sin IA de por medio: prueba TTS/RVC/lipsync/
avatar de punta a punta sin gastar tokens ni depender de que haya red o API key.

**`SesionChat` (en `bench_chat.py`)** agrupa `modo`/`provider`/`historial` y expone
`cambiar_modo(modo) -> bool` (`True` si hubo un cambio real, `False` si ya estaba en ese modo — el
REPL usa el valor de vuelta para no decir "historial limpiado" cuando no limpió nada) como una
función limpia, sin nada de `input()`/`print()` — el mismo mecanismo que va a usar el botón de la
futura ventana de chat en React para alternar entre la IA de verdad y el eco de prueba, no lógica
pegada a este REPL en particular. El historial no se mezcla entre modos: se limpia al cambiar (más
simple que mantener dos historiales en paralelo). Atomicidad: el provider nuevo se arma (`EchoProvider()`
o `get_provider()`, que puede lanzar si falta una API key) **antes** de tocar `self.modo`/
`self.historial` — si falla, la sesión queda exactamente como estaba, no a mitad de cambio.

**El contexto dinámico no se antepone en modo eco**: `_chat()` normalmente antepone
`construir_contexto_dinamico()` (fecha/hora/estado de la PC) al mensaje del usuario antes de
guardarlo en el historial, porque ese bloque existe para informarle al LLM — pero en modo eco no hay
LLM, así que incluirlo igual solo lograba que Rem leyera en voz alta el porcentaje de CPU, en contra
del propósito del modo (repetir tal cual lo que se escribió). `_chat()` ahora recibe
`incluir_contexto: bool` (default `True`, sin cambios para modo ia); `repl()` calcula
`sesion.modo != "eco"` para decidirlo. `--depurar-contexto-eco` (apagado por defecto) lo fuerza de
vuelta si hace falta ver ese bloque específicamente sin gastar tokens de un LLM real.

**`bench.py` eliminado**: existía para probar voz/lipsync/avatar con una frase suelta, sin pasar por
ningún LLM — exactamente lo que cubre el modo eco de `bench_chat.py`, y más (además tiene modo ia,
`voz on/off`, `SentenceSplitter`, etc.). Antes de borrarlo se comparó comando por comando contra
`bench_chat.py`: tenía dos que no existían del otro lado, `state <estado>` (dispara manualmente un
estado emocional del avatar) y `open` (abre el navegador en cualquier momento de la sesión, no solo
al arrancar) — los dos se portaron a `bench_chat.py` antes de borrar `bench.py`. Diferencia menor de
comportamiento que no se portó: `bench.py`'s `say` sintetizaba el texto completo como una sola unidad
TTS/RVC; `bench_chat.py` siempre pasa por `dividir_en_oraciones()`, así que un texto con varias
oraciones se parte en llamadas `_decir()` separadas — sin efecto perceptible con texto normal, solo
importa para probar la síntesis de una frase larga sin cortes.

## Personalidad de Rem (`personalidad.py`)
`_INSTRUCCIONES_BASE` prioriza dos reglas por encima de todo (longitud y honestidad, en ese orden,
al principio del prompt) en vez de enterrar "respondé corto" como el punto 7 de 8 entre rasgos de
personalidad — con un modelo chico (Ollama, 4B, ver "Capa de abstracción de LLM" más arriba) esa
regla se perdía entre el resto y las respuestas salían de 100-180 tokens en vez de 1-3 frases. El
personaje ya no tiene cariño/afecto ni rasgos de pareja — es una colega de trabajo con foco en lo
técnico (programación, Linux, hardware, redes, IA), que contradice a Esteban cuando hace falta en
vez de darle la razón primero y matizar después. Los bloques ACCIONES DEL SISTEMA/REGLAS DE
SEGURIDAD/MEMORIA DEL SISTEMA se mantienen intactos entre reescrituras de personalidad — son
funcionales, no de tono, y cualquier cambio a los permisos reales (ver "Seguridad de acciones del
sistema" más abajo) tiene que reflejarse ahí también, o el modelo va a intentar acciones que el
código ya rechaza sin saber por qué.

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
| `Animaciones/VRMA_MotionPack/*.vrma` | — | `tk256ailab/vrm-viewer` (MIT) + pack VRoid Project — ver `Animaciones/README.md` |

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
└── rem_overlay.py (subprocess hijo)    — sys.executable (venv/bin/python), GTK3 + WebKit2
```

## Locks de threading (en Rem.py)
| Lock | Protege |
|------|---------|
| `_lock_historial` | `historial` (lista de mensajes del chat) |
| `_lock_mem_larga` | `memoria_larga` y sus escrituras a disco |
| `_lock_mem_sis` | `memoria_sistema` y sus escrituras a disco |

## Seguridad de acciones del sistema
- `ejecutar_comando`: whitelist de binarios, bloquea metacaracteres de shell, usa `shlex.split()` sin `shell=True`.
  `git` y `systemctl`, aunque están en la whitelist, se restringen además a un conjunto cerrado de
  subcomandos de solo lectura (`_git_permitido()`/`_systemctl_permitido()`) — `git -c
  core.pager=...`/`--exec-path` pueden ejecutar programas arbitrarios dentro del mismo
  `subprocess.run`, y `systemctl --user start/stop/enable/...` aplica sin pedir ningún privilegio
  (a diferencia de sin `--user`, que suele fallar por polkit — esa falla actuaba como red de
  seguridad implícita que `--user` esquiva).
- `_ruta_segura(ruta, permitir_raiz=False)`: valida que la ruta esté dentro de `/home/$NOMBRE_USUARIO`,
  que no sea `/home/$NOMBRE_USUARIO` completo (por defecto — sin este chequeo, "eliminar ~" hacía
  `shutil.rmtree()` sobre todo el home), que no caiga en dirs del sistema (`/etc`, `/root`, ...) ni en
  la lista negra de subrutas sensibles dentro de `$HOME` (`_RUTAS_PROHIBIDAS_HOME`: `~/.ssh`,
  `~/.gnupg`, `~/.config`, `~/.local/share/keyrings`, `~/.mozilla`, y el `.env`/`.git` del propio
  proyecto, calculados desde su ubicación real — protegen igual si el proyecto vuelve a vivir dentro
  de `$HOME`). La usan `mover_archivo`/`copiar_archivo`/`eliminar_archivo`/`crear_carpeta`, y `buscar`
  con `permitir_raiz=True` (es de solo lectura — `glob.glob`, nunca escribe — y por defecto ya busca
  en todo el home; bloquear la raíz ahí rompería el caso más común).
- **`ejecutar_comando` valida también sus argumentos, no solo el binario** (`_args_permitidos()`):
  antes, `_cmd_permitido()` solo miraba el primer token — `cat /ruta/al/proyecto/.env` vía
  `ejecutar_comando` ignoraba por completo `_ruta_segura()` y la lista negra. Cada token que "parece
  una ruta" (prefijo `/`, `~`, `./`, `../`, o que exista de verdad relativo al cwd real de
  `ejecutar_comando`, lo que atrapa traversal escondido tipo `carpeta_real/../../etc/passwd`) pasa por
  `_ruta_segura()` con `permitir_raiz=False` — mismo límite que mover/copiar/eliminar. Efecto
  secundario a tener en cuenta: `ls ~`/`find .` (apuntando literalmente a la raíz del home) también
  quedan bloqueados por esto, no solo los casos destructivos.
- **`buscar` filtra también los resultados del `glob.glob()`, no solo la carpeta base**
  (`_filtrar_rutas_seguras()`): validar la carpeta de partida con `_ruta_segura()` no alcanza, porque
  `"**"` recursivo encuentra coincidencias dentro de `~/.ssh`/`~/.config`/etc. igual si están debajo
  de esa base — antes, buscar `"id_rsa"` o `".env"` devolvía la ruta real dentro de la lista negra tal
  cual, tanto en la respuesta como cacheada en `memoria_sistema.json`. Como defensa en profundidad,
  `registrar_archivo_sistema()`/`registrar_carpeta_sistema()` (los únicos dos lugares que escriben en
  `memoria_sistema`) también rechazan una ruta que no pase `_ruta_segura()`, y
  `buscar_en_memoria_sistema()` filtra (y borra) cualquier entrada que ya esté adentro y no pase el
  chequeo — importante porque `construir_contexto_dinamico()` en `personalidad.py` reinyecta
  `memoria_sistema` completo en el prompt de cada turno futuro sin filtrar nada: una entrada indebida
  ahí no es una fuga de una sola vez, queda expuesta en todas las respuestas siguientes hasta que se
  borre a mano.
- `descargar_archivo()`: sanea `nombre` con `os.path.basename()` — sin esto, un `nombre` con `../../`
  escribía el contenido descargado fuera de `~/Descargas`.
- `eliminar_archivo` mueve a la papelera de XDG (`~/.local/share/Trash`, con su `.trashinfo`) en vez de
  borrar (`_mover_a_papelera()`) — recuperable con las herramientas normales del escritorio (Thunar).
- Diálogo de confirmación (`DESCRIPCIONES`): para rutas, muestra el `realpath` ya validado por
  `_ruta_segura()` (o el motivo del rechazo, si ya se sabe que va a fallar) en vez del string crudo
  que mandó el LLM; para `ejecutar_comando`, muestra el comando tokenizado con `shlex` y el binario
  real que resuelve el `PATH` (`shutil.which`).
- Toda acción pasa por `confirmar_accion()` (diálogo de confirmación).
- CORS restringido a `localhost` en `rem_avatar_server.py`.

Los cuatro huecos detectados en la auditoría previa (`ejecutar_comando` sin validar argumentos,
`crear_carpeta` y `buscar` sin pasar por `_ruta_segura()`, `descargar_archivo` sin sanear `nombre`)
quedaron cerrados en esa pasada. Una revisión posterior encontró que validar la carpeta base de
`buscar` no alcanzaba (ver el bullet de `_filtrar_rutas_seguras()` más arriba) — cerrado también. Si
en el futuro se agrega una acción nueva que reciba una ruta directo del JSON del LLM, o que devuelva
una lista de rutas encontradas en vez de una sola, ese es el lugar a revisar: pasarla (o filtrarla)
por `_ruta_segura()` antes de usarla o devolverla, no asumir que el patrón ya está cubierto en todos
lados.

**`memoria_sistema.json` ya no se trackea en git** (`git rm --cached`, el `.gitignore` ya tenía
`memoria_*.json` pero no aplica retroactivamente a un archivo agregado antes de esa regla) — el
archivo local sigue existiendo y la app lo sigue leyendo/escribiendo igual, solo que sus cambios ya
no terminan en el historial del repo público. Se verificó todo el historial de git: el archivo
estuvo vacío en su único commit, así que no hizo falta reescribir historia. Se aprovechó para sacar
la clave `"programas"` del JSON, que no existe en el schema que lee `personalidad.cargar_memoria_sistema()`
(solo `archivos`/`carpetas`) — residuo de un formato viejo.

## Arrancar el proyecto
```bash
# Activar venv Python 3.10 primero
source venv/bin/activate
python Rem.py
```
Equivalente sin activar el venv: `venv/bin/python Rem.py`.

**El intérprete correcto es siempre `venv/bin/python` (Python 3.10.14, con torch/fairseq/RVC
instalados) — nunca el `python`/`python3` del sistema.** Esto ya incluye a `rem_overlay.py` y
`rem_chat.py`: el `python3` del sistema no tiene ningún rol especial en el proyecto (ver "El venv sí
puede tener GTK" más abajo) — PyGObject/pycairo están en `requirements.txt` igual que el resto.

El overlay (`rem_overlay.py`) lo lanza `Rem.py`/`bench_chat.py`/`rem_chat.py` automáticamente vía
`rem_avatar_server._lanzar_overlay()`, con `sys.executable` (el mismo intérprete del proceso que lo
llama, normalmente `venv/bin/python`) — no una ruta hardcodeada.

## Problemas conocidos
- **fairseq + PyTorch moderno**: los archivos en `fairseq_shim/` solucionan la incompatibilidad. Ver `INSTALL.md`.
  Después de cualquier `pip install fairseq` (reinstalación, venv nuevo, etc.) hay que volver a aplicar
  el shim con `venv/bin/python apply_shim.py` — si no, `torch.load()` fallará al cargar checkpoints
  porque le falta `weights_only=False`.
- **RVC tarda en cargar**: los 30-60s solo aplican si cae a CPU (`only_cpu=True` o sin CUDA disponible). Con GPU (CUDA disponible) la carga es prácticamente instantánea, ~0,7s medidos en esta máquina. El TTS funciona sin RVC (sin conversión de voz).
- **Avatar overlay no aparece**: verificar `webkit2gtk-4.1` instalado y compositor con soporte RGBA.
- **Error de audio**: verificar que PipeWire esté corriendo (`systemctl --user status pipewire`).

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
`config.leer_dispositivo_rvc()`, aplicado en `bench_chat.py`, `test_voz.py` y `Rem.py`
(los tres construyen su `BaseLoader` con `only_cpu=(dispositivo == "cpu")`). Verificado en vivo
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

## Precarga de RVC y fin de la recarga del .pth en cada frase
Dos problemas medidos en vivo con el `SentenceSplitter` ya conectado (ver arriba): el primer audio
de una sesión tardaba ~16,5s (carga de RVC + primera conversión en frío) mientras el usuario
esperaba, y el log mostraba `Loading .../Rem_600e_6600s.pth` antes de **cada** conversión — con el
splitter mandando una oración a la vez, eso es una recarga del modelo por oración, no por respuesta.

**Causa de la recarga**: `BaseLoader.__call__()` (el método que `bench_chat.py` usaba)
guarda el tag de la última conversión en `cache_params`, una **variable local** que se reinicializa
a `None` al entrar a `__call__()` — así que aunque el tag (`"rem"`) nunca cambia entre llamadas,
la condición `cache_params != id_tag` es `True` siempre, y `load_trained_model()` (con su
`torch.load()` del `.pth` y la relectura del `.index` vía faiss) se repite en cada conversión.
`BaseLoader` expone un método distinto para esto — `generate_from_cache(audio_data, tag)` — que
guarda el estado equivalente en `self.cache_model`/`self.model_vc` (atributos de instancia, no
variables locales) y compara con `!=` antes de recargar: como la config de `"rem"` nunca cambia
tras el `apply_conf()` inicial, la carga real solo ocurre una vez por instancia de `BaseLoader`.
`bench_chat.py` ahora llama a `generate_from_cache(audio_data=<ruta_wav>, tag="rem")`
en vez de `__call__(audio_files=[...], type_output="wav")` — con `type_output` fijo en `"array"`
dentro de ese método, devuelve `(audio_int16, sample_rate)` directo en vez de escribir un archivo,
así que `_decir()` lo escribe a wav con `sf.write()` antes de mandarlo a `enviar_audio()`.

**Beneficio colateral**: `__call__()` corre `self.infer()` dentro de un `threading.Thread` propio
que solo se joinea (`run_threads`) — si `infer()` lanza, esa excepción no se propaga al hilo
llamador (comportamiento estándar de `threading.Thread`), y por eso el bug de la carrera
intermitente documentado arriba ("RVC no devolvió resultado") se manifestaba como una lista vacía
en vez de una excepción visible. `generate_from_cache()` llama a `self.infer()` **directo**, sin
hilo interno — un fallo real de RVC (OOM de CUDA, lo que sea) ahora llega a `_decir()` como una
excepción de verdad, con su mensaje, en vez de desaparecer en silencio. `_decir()` sigue
tolerándolo igual que antes (`except Exception` alrededor de la conversión, cae a la voz cruda de
edge-tts sin convertir para esa oración), pero ahora el log de fallback trae el motivo real.

**Precarga en el arranque**: `_precargar_rvc()` carga RVC y hace
una conversión de calentamiento descartable (frase fija `"Hola."`) en un hilo de fondo
(`threading.Thread(daemon=True)`), lanzado en `main()` antes de `iniciar_avatar()` para solaparse
con el arranque del servidor HTTP/WS y el subproceso del overlay en vez de sumarse después. Así,
para cuando el usuario escribe su primer `chat` real, tanto la carga del modelo (`import
torch`/`faiss`, `Config()`) como el primer `generate_from_cache()` en frío (el más caro: incluye
`torch.load()` del `.pth`, cargar el estimador de pitch `RMVPE` y leer el `.index`) ya se pagaron
en background.

**Bug de concurrencia encontrado al combinar ambos cambios, y su arreglo**: `BaseLoader` no es
thread-safe entre llamadas concurrentes — ni `generate_from_cache()` ni la carga perezosa del
estimador de pitch (`self.model_pitch_estimator`) tienen lock propio. Con el hilo de precarga y una
petición real llegando casi al mismo tiempo (probado en vivo mandando un `chat` a los 2s de
arrancar, antes de que la precarga terminara), **ambos hilos vieron el cache vacío a la vez** y
recargaron el `.pth` y el `RMVPE` por duplicado (`Loading .../Rem_600e_6600s.pth` y `Loading vocal
pitch estimator model` aparecían dos veces seguidas en el log). Arreglado serializando **toda**
llamada a RVC — tanto la carga inicial (`_obtener_rvc()`) como cada conversión
(`generate_from_cache()`, ahora envuelta en `_convertir_rvc()`) — detrás de un único
`threading.Lock()` (`_rvc_lock`). No hay costo real: las dos rutas comparten la misma GPU/CPU, así
que no había paralelismo que ganar corriéndolas a la vez, solo una carrera a evitar. Verificado en
vivo tras el fix: una sola aparición de cada línea `Loading`, sin duplicados, en varias corridas
seguidas de `bench_chat.py`.

**Medido en vivo, esta máquina, GPU** (`bench_chat.py`, con la precarga corriendo de fondo mientras el
REPL ya está disponible):
- Carga del objeto `BaseLoader` (`import torch`/`faiss` + `Config()`): ~3,2-6,2s (varía entre
  corridas, primer import de estas libs en el proceso).
- Calentamiento completo (síntesis TTS de la frase de descarte + `generate_from_cache()` en frío,
  incluyendo `torch.load()` del `.pth`, carga del `RMVPE` y lectura del `.index`): ~9-13s.
- **Primera conversión real del usuario, después de que la precarga ya terminó**: **0,88s** — misma
  velocidad que las conversiones subsiguientes (antes del fix, la primera conversión de la sesión
  costaba ~11-16s, todo pagado en el momento en que el usuario ya está esperando la respuesta).
- El prompt del REPL queda disponible de inmediato, antes de que termine la precarga (corre en un
  hilo de fondo, ver más arriba) — no bloquea el arranque.

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
  de conexión, para el log breve en vez de traceback). **Ya no es así**: `_ws_handler` sí procesa
  mensajes del cliente desde que existe el panel de chat (`chat_message`/`cambiar_modo`/`reset`) —
  ver "WebSocket bidireccional y chat_sesion.py" más abajo. Este bullet queda como registro de por
  qué el WS empezó siendo de una sola vía, no como descripción del estado actual.

## Regresión repetida de la política de autoplay
`play()` volvió a rechazarse con `NotAllowedError` una segunda vez, con el mismo síntoma que la
sección anterior. El patrón de código en `rem_overlay.py` era `webview = WebKit2.WebView();
settings = webview.get_settings()` y recién ahí se llamaba a `settings.set_media_playback_requires_
user_gesture(False)` junto a los demás `set_*` — agregar `set_enable_write_console_messages_to_
stdout(True)`/`set_enable_developer_extras(True)` (para el volcado de consola, ver más arriba) puso
código nuevo por delante en el bloque y volvió a romperlo, la MISMA clase de fragilidad que ya había
pasado una vez antes.

**La causa real no era el orden del bloque — el diagnóstico original quedó incompleto.**
Investigando en vivo (Hyprland real, probando `chat` con `bench_chat.py` y leyendo el log del overlay)
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

## Riesgo de conflicto de puertos si hay más de un proceso con el overlay
Investigado tras un reporte de que el overlay había dejado de lanzarse en un lanzamiento del REPL
(en su momento con dos scripts equivalentes, `bench.py` y `bench_chat.py` — el primero ya no existe,
ver "bench.py eliminado" más abajo). Probado en vivo (Hyprland real, no headless) con stdin cerrado
tras ~10s: el overlay cargó de forma idéntica y exitosa en ambos — mismo `rem_overlay.log` (VRM
cargado, WS conectado, expresiones resueltas), sin ningún error. La secuencia de arranque del avatar
era byte-a-byte la misma en los dos (`config.cargar_dotenv()` → `iniciar_avatar()` →
`_abrir_navegador()` opcional) — no se pudo reproducir el reporte original en este entorno.

**Riesgo real encontrado en el camino** (no confirmado como la causa de aquel reporte, pero sí un
bug latente, y sigue vigente): `rem_avatar_server.py._iniciar_ws()` llama a `_ws_ready.set()`
**antes** de intentar `websockets.serve(...)`. Si el puerto `:18766` ya está ocupado (p.ej. porque
`bench_chat.py` o `Rem.py` ya está corriendo en otra terminal), `websockets.serve()` lanza una
excepción dentro del hilo daemon `AvatarWS` — que muere en silencio (una excepción no capturada en
un `threading.Thread` no se propaga al hilo principal) — pero `_ws_ready` ya quedó en `True` desde
antes de ese fallo. `iniciar_avatar()` nunca se entera: `_lanzar_overlay()` se llama igual, y el
overlay termina intentando hablarle a un WebSocket que en ESTE proceso nunca llegó a levantar (aunque
sí puede haber uno ajeno, del otro proceso, sirviendo ese mismo puerto). Si dos instancias de
Rem/bench_chat corren en simultáneo, la segunda puede terminar así — con un overlay que se ve
"no funcionar" sin ningún error visible. En su momento no se tocó porque no se había confirmado que
fuera la causa real de aquel reporte.

**Arreglado al construir `rem_chat.py`** (ver más abajo), que sí necesitaba detectar de verdad si el
servidor ya estaba arriba — no alcanzaba con seguir sin tocarlo. `_iniciar_ws()` ahora solo llama a
`_ws_ready.set()` **después** de que `websockets.serve()` tiene éxito; si falla, guarda la excepción
en `_ws_bind_error` y deja `_ws_ready` sin activar. La función nueva `iniciar_servidor_avatar()`
(HTTP+WS, sin el overlay) primero prueba con un connect a `127.0.0.1:18765` si ya hay algo
escuchando — si lo hay, ni intenta levantar un server nuevo, evitando la carrera de raíz en vez de
solo manejarla mejor. `iniciar_avatar()` (la usada por `Rem.py`) ahora llama a
`iniciar_servidor_avatar()` en vez de tener su propia copia de esa lógica.

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

**Verificado en vivo, tres escenarios** (con `bench_chat.py`, cache de WebKit limpiada entre corridas en
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

## Ventana de escritorio (`rem_chat.py`) — un motor, dos modos
Primera etapa de un frontend de chat aparte del overlay: solo la ventana y la escena 3D, sin el
chat en sí todavía (viene después). `rem_chat.py` es GTK3 + WebKit2 igual que `rem_overlay.py`, pero
lo opuesto a propósito: ventana normal decorada, opaca, con foco de teclado — sin
`gtk-layer-shell`, sin transparencia, sin click-through. Tamaño por defecto 1100×620,
redimensionable, título "Rem".

**El venv sí puede tener GTK.** La suposición previa ("`rem_overlay.py` DEBE usar el python3 del
sistema, NO el venv") seguía siendo cierta *porque nadie lo había intentado*, no porque fuera
imposible: `pip install pygobject pycairo` en el venv compiló sin problema contra las libs
GTK3/WebKit2GTK-4.1 (y `GtkLayerShell` — se probó aparte, también disponible) ya instaladas en el
sistema (Arch no separa paquetes `-dev`, así que los headers/`.pc` ya estaban ahí). Verificado en
vivo, ventana real renderizando. `pygobject`/`pycairo` quedaron agregados a `requirements.txt`.

**`rem_overlay.py` también pasó al venv** — no se quedó atrás una vez confirmado que podía moverse.
`rem_avatar_server._lanzar_overlay()` lanzaba el overlay con una ruta hardcodeada,
`"/usr/bin/python3"`; ahora usa `sys.executable` — el mismo intérprete que ya está corriendo el
proceso que llama a `_lanzar_overlay()` (normalmente `venv/bin/python`, sea `Rem.py`,
`bench_chat.py` o `rem_chat.py`), sin asumir nada sobre qué hay instalado en el `python3` del
sistema. Verificado en vivo: el overlay corre como
`/mnt/extra/rem/Rem/venv/bin/python /mnt/extra/rem/Rem/rem_overlay.py --layer top` (confirmado con
`ps aux`), carga igual que siempre (mismos números de encuadre, `[Modo] activo: overlay`, sin
ninguna línea `[Suelo]`) — cero diferencia de comportamiento, solo cambió qué intérprete lo hospeda.
La nota vieja de "Python dual" (`rem_overlay.py` DEBE usar el python3 del sistema) ya no es cierta y
se sacó de "Problemas conocidos" — los dos scripts (`rem_overlay.py` y `rem_chat.py`) corren con
`venv/bin/python` ahora. El `python3` del sistema (≥3.12) queda sin ningún rol especial en el
proyecto salvo que alguien decida usarlo a mano.

**Un solo `rem_avatar.html`, no duplicado.** `?modo=overlay|ventana` en la URL decide la escena
(`overlay` por defecto si el parámetro falta o no se reconoce): `overlay` es el comportamiento de
siempre (fondo transparente, sin suelo, `anchorX=0.5`, pensado para la superficie angosta 520×860
del overlay real); `ventana` agrega el suelo synthwave y centra a Rem en el tercio izquierdo del
ancho (`anchorX = 1/6`). `CONFIG.modos.{overlay,ventana}.anchorX` reemplaza el viejo
`anchorX`/`walkLeft`/`walkRight` fijos — sin caminata (ver más abajo) alcanza con un valor por modo.
`_ajustarAnclasPorAspect()` se mantiene para el caso general (una superficie angosta y vertical
sigue necesitando colapsar a 0,5, sea cual sea el modo) pero ya no toca nada de caminata.

**Log propio (`rem_chat.log`) — `os.dup2`, no `sys.stdout = archivo`.** Primer intento (reasignar
`sys.stdout`/`sys.stderr` a nivel de Python) no funcionó: WebKit2 escribe su volcado de consola
(`set_enable_write_console_messages_to_stdout`) directo al file descriptor 1 nativo del proceso, sin
pasar por el objeto `sys.stdout` de Python — reasignar solo ese objeto capturaba los `print()`
propios pero dejaba afuera justo el volcado de consola, que es lo que más importa poder ver.
Confirmado en vivo: con la reasignación simple, `rem_chat.log` solo tenía los `print()` de Python;
el volcado de WebKit se iba a donde estuviera apuntando el fd 1 original (la terminal, si se lanza
directo). Arreglado con `os.dup2(log_file.fileno(), sys.stdout.fileno())` (y lo mismo para stderr) —
mismo efecto que `subprocess.Popen(..., stdout=archivo)` logra para el overlay, pero hecho desde
adentro del propio proceso, porque `rem_chat.py` no se spawnea a sí mismo.

**Inspector remoto en un puerto distinto al del overlay**: `WEBKIT_INSPECTOR_SERVER=127.0.0.1:9223`
(el overlay usa `:9222`) para que las dos ventanas puedan correr juntas sin pisarse el puerto del
inspector — mismo motivo que el resto de este apartado.

**Solo servidor, sin overlay**: `rem_avatar_server.iniciar_servidor_avatar()` (nueva función, ver
"Riesgo de conflicto de puertos" más arriba) levanta HTTP+WS o detecta que ya están corriendo — a
diferencia de `iniciar_avatar()`, no lanza `rem_overlay.py` como subproceso. Así `rem_chat.py` puede
arrancar solo (levanta el servidor él mismo) o junto al overlay/`Rem.py`/`bench_chat.py` (se conecta
al servidor que ya esté arriba). Verificado en vivo: `rem_overlay.py` lanzado por separado, apuntando
al servidor que `rem_chat.py` ya había levantado, cargó y funcionó igual que siempre (mismos números
de encuadre que antes de este cambio: `z≈7.23 anchoVisible≈2.18`, sin ninguna línea `[Suelo]` en su
log — modo overlay intacto).

**Tiling de Hyprland ignora `set_default_size()`** — no es un bug de `rem_chat.py`, es la política
por defecto de un WM tiling: sin una `windowrulev2` para floatear la clase `rem_chat.py`, Hyprland
igual tiling-ea la ventana al tile que le toque en vez de respetar 1100×620. La escena ya lo tolera
bien (el listener de `resize` recalcula el encuadre solo, probado en vivo con la ventana en
~1808×1018), pero si se quiere el tamaño real pedido hace falta algo como
`windowrulev2 = float, class:^(rem_chat.py)$` en la config de Hyprland — eso es decisión/config del
usuario, no algo para forzar desde el código Python.

## Suelo de cuadrícula synthwave y fin de la caminata
`crearSueloSynthwave()` (solo si `MODO === 'ventana'`) arma un `THREE.GridHelper` (líneas cian,
`CONFIG.suelo.colorLinea`) más una `THREE.Line` de horizonte aparte, más brillante
(`colorHorizonte`) y con `fog: false` (no se apaga con la distancia — es la marca de "hasta acá se
ve", tiene que quedar siempre legible). La perspectiva hacia el horizonte la da `THREE.Fog`
(`nieblaCerca`/`nieblaLejos`), no geometría extra — nada de reflejos ni post-procesado, la GPU de
esta máquina ya anda justa (ver la calibración de `num_gpu` más arriba). `posicionarSuelo()` alinea
el suelo con los pies de Rem (`_modeloPositionY + (_modeloCentroLocal - _modeloAlturaLocal / 2)`),
llamado desde `recalcularEncuadre()` cada vez que cambia la medición.

**Bug encontrado en vivo, no obvio**: la línea de horizonte no aparecía en pantalla, sin ningún error
en consola. Causa: `camera.far` estaba en `20` (valor pensado solo para el overlay sin suelo), pero
la línea de horizonte queda a `camera.position.z + CONFIG.suelo.tamano/2` de la cámara — con los
valores por defecto, ~27 unidades — **más allá del plano de recorte lejano**, así que WebGL la
descartaba en silencio antes de llegar a rasterizar nada. Subido a `far=45`. Verificado en vivo con
captura de pantalla: sin el fix, cuadrícula visible pero sin horizonte; con el fix, línea de
horizonte cian claramente visible en el punto de fuga.

**Caminata eliminada por completo**: `tickPet()`, `updateWalking()`, `charDir`, `walkBlend`,
`walkPhase`, `petEstado`, `petTimer` y los anclajes `walkLeft`/`walkRight` — Rem queda fija en su
sitio (`CONFIG.pet.anchorX`, ya no un `charX` mutable). Esto simplificó bastante
`recalcularEncuadre()`, que ya no necesita decidir si colapsar un rango de caminata además de la
posición de reposo.

## Animación natural con ruido Perlin, en vez de sumas de senos
`getStatePose()` — las poses de brazos/cabeza/torso de cada estado emocional eran productos de
`Math.sin()` a distintas frecuencias, que técnicamente **siguen siendo periódicas** aunque no lo
parezca a simple vista, y el ojo detecta esa periodicidad en pocos segundos (se lee como robot, no
como alguien vivo). Reemplazado por ruido Perlin 1D embebido (`noise1D()`, tabla de permutación
clásica de Ken Perlin, sin dependencias externas — la misma técnica que "flow noise" para animación
idle procedural): cada canal (`hX`/`hY`/`hZ`/`bZ`/`ruZ`/`luZ`/`ruX`/`luX`) es
`noise1D(t * frecuencia + fase)`, con una fase fija propia por canal (`ruido(fase, freq, t)`) para
que no se muevan todos en sincronía. La respiración (`bX`, y ahora también pecho/hombros
directamente en `animate()`) se dejó con un seno limpio a propósito — la respiración real SÍ es
rítmica, eso no era lo que hacía ver a Rem como un robot.

- **Respiración en pecho y hombros**: `chestB.rotation.x` (ya existía) más `leftShoulder`/
  `rightShoulder.rotation.z` (nuevo), todos del mismo `Math.sin(t * 0.8)` — los hombros solo suben
  en la inhalación (`Math.max(0, ...)`), no oscilan simétricos, para que se lea como una elevación
  real. Confirmado en vivo que este modelo trae los huesos `leftShoulder`/`rightShoulder` mapeados
  (log `[VRM] lookAt... leftShoulder/rightShoulder: true true`).
- **Traslado de peso** (`updateTrasladoPeso()`): reemplaza el bob/rock que aportaba la caminata
  eliminada — sin esto, una cadera perfectamente inmóvil se ve tan artificial como una cabeza que no
  se mueve nunca. Ruido a frecuencia muy baja (`freq=0.05`, período ~20s) a propósito: un traslado de
  peso real es lento y ocasional, no un tic constante.
- **Micro-saccades** (`updateSaccades()`): distinto del drift de cabeza que ya existía
  (`updateLook()`) — los ojos saltan cada 0,5-2s a un punto nuevo dentro de un cono chico, con
  duración de salto de 20-40ms (usando el mismo `_fade()` del ruido para el suavizado del salto, no
  un tirón lineal). Vía `vrm.lookAt.yaw`/`.pitch` (grados), que `vrm.update()` aplica a los huesos
  `leftEye`/`rightEye` a través del applier que three-vrm arma solo al cargar el modelo — confirmado
  en vivo que `vrm.lookAt` existe en este VRM (mismo log de arriba). En estado `thinking` el cono de
  saccades se centra en el mismo punto arriba-a-un-lado que ya mira la cabeza, no en el centro, para
  que el ojo no se pierda del gesto.
- **Gesticulación al hablar con ruido**: el caso `talking` de `getStatePose()` ya no usa
  `Math.sin()` para los brazos — cada brazo tiene su propio canal de ruido con amplitud generosa,
  para que se lea como alguien hablando con las manos, no como un metrónomo.
- **Pose de `thinking` distinta a propósito**: mirada arriba a un lado (cabeza vía `updateLook()` Y
  ahora también los ojos vía el sesgo del cono de saccades), mano derecha elevada cerca de la cara
  (`ruZ: -1.05`), y el multiplicador de velocidad más bajo de todos los estados (`SPEEDS.thinking =
  0.5`) — ya existía en germen antes de este cambio, se conservó y se reforzó con las dos capas de
  mirada coincidiendo en el mismo punto.
- `angry` pasó de `sign(Math.sin())*Math.sin()` (brusco pero igual de periódico, con un período largo
  que lo disimulaba a corto plazo) a ruido de frecuencia alta — mismo carácter entrecortado a la
  vista, sin el patrón exacto repitiéndose.

**Verificado en vivo**: los 7 estados (`idle/talking/thinking/happy/sad/angry/surprised`) probados en
secuencia vía WebSocket, sin ningún error nuevo en `rem_chat.log` más allá de los crashes conocidos
del Network Process de WebKit (ver "Segunda regresión del overlay" más arriba, no relacionados).

## Brazos, manos y pose procedural de cuerpo
Los brazos estaban en gran parte estáticos (antebrazo con valores fijos que nunca cambiaban, brazos
pegados al cuerpo, dedos sin usar — "señal de muñeco"). Se les dio acople al cuerpo, curvatura de
dedos, gesticulación al hablar, y se agregó una animación de reposo puntual (giro de 360°). Todo en
`rem_avatar.html`, sin tocar Python.

- **Antebrazos**: pasaron de `rla.rotation.x = -0.15` fijo a una flexión base
  (`CONFIG.brazos.codoFlexionBase`) más deriva de ruido Perlin, con `spr.rlX`/`spr.llX` (nuevos
  canales de `Spring`) suavizando el objetivo. También reciben la mitad del acople al cuerpo que el
  upperArm (ver más abajo), para que el antebrazo no se quede rígido mientras el brazo entero se
  inclina.
- **Separación del cuerpo**: `ruZ`/`luZ` en reposo pasaron de ±1,28 (pegados) a
  `CONFIG.brazos.separacion` (±1,20 por defecto), con `CONFIG.brazos.balanceoDelante` sumado al
  `rotation.x` del upperArm para que cuelguen hacia delante en vez de planos contra el costado.
- **Hombros**: `leftShoulder`/`rightShoulder` (mapeados pero sin usar hasta ahora) suben/bajan con la
  fase de respiración y se inclinan con `pesoRock` (el valor de traslado de peso que ahora devuelve
  `updateTrasladoPeso()`, antes no devolvía nada).
- **Acople brazo-cuerpo**: en vez de ruido independiente, el objetivo de `rotation.x` de cada
  upperArm suma `acopleCuerpo = spr.bX.v * CONFIG.brazos.acopleRespiracion + spr.bZ.v *
  CONFIG.brazos.acopleInclinacion` — los valores ya amortiguados (`.v`, la velocidad/posición actual
  del spring del torso, no el objetivo crudo) del spring de respiración/inclinación del torso. Como
  los brazos tienen su propio spring encima, el resultado es un retardo compuesto (el spring del
  torso ya atrasa la respiración real, y el del brazo atrasa aún más ese valor) sin necesidad de un
  sistema de lag aparte — es lo que hace que, cuando el cuerpo se inclina, los brazos se lean
  "yendo detrás" en vez de moverse a la vez.
- **Dedos**: las 30 cadenas de falange (28 realmente presentes en este modelo — el pulgar solo tiene
  Proximal/Distal, sin Intermediate, confirmado en vivo: `28/30 mapeados — faltan:
  leftThumbIntermediate, rightThumbIntermediate`) tenían rotación en 0 siempre. `aplicarCurvaturaDedos()`
  aplica una curvatura de reposo decreciente hacia la punta (`CONFIG.dedos.curlProximal >
  curlIntermedio > curlDistal`) sobre `rotation.z`, con el pulgar ligeramente opuesto
  (`curlPulgar` + un `rotation.y` fijo) y una deriva de ruido muy lenta (`derivaFreq = 0.025`) para
  que no se vean congelados. **Verificado en vivo con captura ampliada de ambas manos**: la
  curvatura se ve natural (dedos plegados hacia la palma, no un abanico ni una torsión rara) — el eje
  (`rotation.z`) y el signo espejado (`signo = left?-1:1`) confirmados correctos a simple vista, no
  quedó como una suposición sin probar.
- **Gesticulación al hablar**: el caso `talking` de `getStatePose()` combina dos señales para la
  amplitud del gesto (`gestoAmp`, 0..1): un envolvente de ruido con `Math.max(0, ruido(...))` (da
  pausas reales de arranca/para, no oscilación continua) y `_hablaEnergia` (una señal nueva, suavizada
  con `lerp(..., dt*8)` hacia `_jawApertura*1.3` mientras hay audio sonando — reusa la apertura de
  mandíbula que ya alimenta el lipsync como proxy barato de "energía del habla", sin agregar ningún
  análisis de audio nuevo). Las dos se combinan (`clamp(envolvente*gestoRuidoAmp +
  _hablaEnergia*gestoHablaAmp, 0, 1)`) en vez de elegir una sola, así que el gesto tiene both un
  arranque/parada visible y responde a si Rem está realmente vocalizando fuerte en ese instante.
- **Pose de `thinking`**: reescrita para que el brazo acompañe la idea de "mano hacia la cara" — codo
  flexionado fuerte (`rlX: -0.95`), upperArm elevado (`ruX: 0.35`) y rotado hacia el centro
  (`ruZ: -0.85`, notablemente menos separado que el reposo normal).
- **Giro de bailarina — ELIMINADO**. `updateGiroBailarina()` (giro de 360° codificado a mano sobre
  `vrm.scene.rotation.y` + poses de pierna/cabeza/brazos) se quitó junto con `CONFIG.giro`,
  `easeInOutCubic`, `_sortearIntervaloGiro`, `_anguloFrontalMasCercano` y las variables `_giro*`. Lo
  reemplaza el clip `VRMA_05.vrma` (girar) dentro del repertorio de gestos de reposo — ver
  "Animación de cuerpo con clips VRMA" más abajo. Los bullets de abajo de esta sección
  (respiración en pecho/hombros, traslado de peso, saccades, dedos, brazos acoplados) **siguen
  vigentes**: son la capa procedural que corre cuando no hay clip, y las partes de respiración/
  mirada que se aplican SIEMPRE encima del mixer.

**Bug encontrado y corregido durante la implementación**: el bloque de antebrazos en `animate()`
usaba `ts` (la variable de tiempo escalada por emoción, que solo existe como local dentro de
`getStatePose(t)`) en vez de `t` (tiempo bruto, la única variable de tiempo real en el scope de
`animate()`) — `ReferenceError: Can't find variable: ts` en cada frame, capturado en `rem_chat.log`
antes de arreglarse. `t` es suficiente para una deriva sutil de codo, no hacía falta el escalado por
emoción ahí.

**Rangos de valores** (todo en `CONFIG`, sin tocar el resto del código):

| Bloque | Clave | Controla |
|---|---|---|
| `brazos` | `separacion` (1.20) | Ángulo de reposo de `ruZ`/`luZ` — más alto separa más los brazos del cuerpo |
| | `balanceoDelante` (0.14) | Inclinación hacia delante del upperArm en reposo |
| | `codoFlexionBase` (-0.30) | Flexión de codo en reposo — más negativo, brazo más doblado |
| | `codoDerivaAmp` (0.05) | Amplitud de la deriva de ruido del codo |
| | `acopleRespiracion` (0.35) | Cuánto de la respiración del torso se filtra al balanceo del brazo |
| | `acopleInclinacion` (0.25) | Cuánto del traslado de peso del torso se filtra al brazo |
| | `gestoRuidoAmp` (1.6) | Cuánto empuja el envolvente de ruido la amplitud del gesto al hablar |
| | `gestoHablaAmp` (0.5) | Cuánto empuja la energía real del habla (apertura de mandíbula) |
| `dedos` | `curlProximal` (0.55) | Curvatura de la falange proximal (la más cercana a la mano) |
| | `curlIntermedio` (0.42) | Curvatura de la falange intermedia |
| | `curlDistal` (0.28) | Curvatura de la falange distal (la punta) |
| | `curlPulgar` (0.32) | Curvatura del pulgar (solo tiene proximal/distal en este modelo) |
| | `derivaAmp` (0.05) | Amplitud de la micro-variación lenta de los dedos |
| | `derivaFreq` (0.025) | Frecuencia de esa deriva — más bajo, más lenta |

(El bloque `CONFIG.giro` ya no existe — lo reemplazó `CONFIG.animaciones`, ver "Animación de cuerpo
con clips VRMA" más abajo.)

## Panel de chat en la ventana de escritorio (solo modo "ventana")
`rem_chat.py` ya tenía la ventana y la escena 3D; faltaba el chat en sí. Se agregó como
HTML/CSS/JS vanilla dentro de `rem_avatar.html` (nada de frameworks ni dependencias externas,
como pide el proyecto) — ocupa la mitad derecha de la ventana, opaca, encima del canvas. En modo
overlay no se crea nada: `crearPanelChat()` arranca con `if (MODO !== 'ventana') return;`, mismo
patrón de guarda que ya usaba `crearSueloSynthwave()`.

**Por qué el canvas se deja a tamaño completo en vez de reducirlo a la mitad izquierda**: se
evaluaron dos diseños — (a) canvas a ancho completo con el panel como `<div>` opaco encima
(`position:fixed; right:0; width:50%`), o (b) redimensionar de verdad el renderer/cámara a la
mitad izquierda. Se eligió (a): más simple, cero riesgo de romper `_ajustarAnclasPorAspect()` (que
colapsa `anchorX` a 0,5 para superficies angostas — una mitad de ventana normal, ~550×620, cae en
ese umbral y hubiera recentrado a Rem en su propia mitad en vez de mantener la composición "tercio
izquierdo" pensada para el ancho completo) y sin cambios a `recalcularEncuadre()`/el listener de
`resize`, ya probados. El costo (renderizar píxeles que quedan tapados por el panel) es
insignificante para esta escena (una malla + una cuadrícula, sin post-procesado) — no es
comparable al problema real de rendimiento que motivó acotar la layer surface del overlay (ver
"Layer surface acotada" más arriba), que era un canvas del tamaño del MONITOR ENTERO
permanentemente, no la mitad de una ventana normal.

**Estructura**: header (selector de modo ia/eco + botón de reset) → lista de mensajes (scrolleable)
→ línea de estado (pensando/hablando) → input + botón de enviar. Burbujas diferenciadas: `.msg.user`
alineada a la derecha, fondo sólido; `.msg.rem` alineada a la izquierda, con borde y glow cian sutil
(`box-shadow`) a tono con el suelo synthwave (reusa los mismos tonos que `CONFIG.suelo.colorLinea`/
`colorFondo`, hardcodeados en el CSS del `<head>` porque el CSS no puede leer `CONFIG`, que se
define recién en el `<script type="module">`). Tipografía: pila del sistema
(`-apple-system, ..., sans-serif`) — sin cargar ninguna fuente externa.

**Streaming palabra a palabra**: cada `chat_delta` que llega por WebSocket se concatena directo al
`textContent` de la burbuja de Rem en curso (`burbujaRemActual`), sin esperar a que dividir_en_
oraciones() ni ningún otro agrupador termine — confirmado en vivo que el backend manda fragmentos
sub-palabra reales (`"Est"`, `"oy"`, `" prob"`, ...), no oraciones completas de una. La burbuja de
Rem se crea recién con el PRIMER `chat_delta` (no al mandar el mensaje), así el estado "pensando"
(sin burbuja todavía) se distingue visualmente de "hablando" (burbuja creciendo).

**Indicador de estado, en sintonía con el estado real del avatar**: el panel no inventa un estado
propio — dispara los mismos `enviar_estado()` que ya mueven el cuerpo de Rem (thinking al arrancar
el turno, talking con el primer fragmento, idle al terminar o si algo falla), así que el indicador
de texto del panel (con un punto que pulsa) y la pose/gesticulación del avatar quedan
sincronizados sin necesidad de audio real — este panel es solo texto, no pasa por TTS/RVC/lipsync
en absoluto (el pipeline de voz no se tocó).

## WebSocket bidireccional y `chat_sesion.py`
Antes el WS de `:18766` era de una sola vía (Python → browser: estado/audio). `_ws_handler()` en
`rem_avatar_server.py` ahora también procesa lo que manda el cliente, con mensajes tipados por un
campo `tipo`:

| Dirección | tipo | Payload | Qué hace |
|---|---|---|---|
| browser → Python | `chat_message` | `{texto}` | Corre un turno completo contra el LLM activo |
| browser → Python | `cambiar_modo` | `{modo: "ia"\|"eco"}` | Cambia el provider de la sesión de chat compartida |
| browser → Python | `reset` | — | Limpia el historial de la sesión de chat compartida |
| Python → browser | `chat_delta` | `{texto}` | Un fragmento de la respuesta, tal como llega del LLM |
| Python → browser | `chat_done` | — | Fin del turno |
| Python → browser | `modo_actual` | `{modo}` | El modo activo — se manda tras cualquier cambio real, venga de donde venga |
| Python → browser | `error` | `{mensaje}` | Algo falló (turno ya en curso, falta API key, excepción del provider, modo inválido) |

Los tipos ya existentes (`estado`, `{tipo: "audio", ...}`) siguen igual — el frontend solo agregó
más ramas al mismo `if/else if` de `_ws.onmessage`, no se tocó el pipeline de audio/lipsync.

**`SesionChat` se extrajo de `bench_chat.py` a `chat_sesion.py`** (junto con una función nueva,
`procesar_turno()`) para que el REPL y el panel de chat usen la misma clase en vez de dos copias.
`procesar_turno()` es una versión "en crudo" del turno: emite cada `TextDelta` tal como llega vía
un callback `on_delta`, sin agrupar por oración — a propósito distinta de `_chat()` en
`bench_chat.py`, que sigue intacta (agrupa con `dividir_en_oraciones()` para encolar hacia
TTS/RVC/avatar). No se tocó `_chat()` ni nada del pipeline de voz: el panel de chat es un consumidor
nuevo y separado, no un reemplazo.

**La sesión de chat es un singleton compartido, no uno por consumidor**: `rem_avatar_server.
obtener_sesion_chat()` construye (perezoso, recién en el primer uso real) una única `SesionChat` +
snapshot de memoria por proceso, y tanto `_ws_handler()` (panel HTML) como `repl()` en
`bench_chat.py` la usan — la MISMA instancia cuando ambos corren en el mismo proceso (que es el caso
normal: `bench_chat.py` levanta `iniciar_avatar()`, que es este mismo módulo). Por eso cambiar de
modo desde el botón del panel también lo ve el comando `modo` del REPL y viceversa: no son dos
estados sincronizados por mensajes, son el mismo objeto. `cambiar_modo_chat()` es el punto de
entrada único para cambiar de modo (lo llaman tanto `_ws_handler` como el comando `modo` del REPL) —
además de mutar la sesión, manda `modo_actual` por WebSocket, así que un cambio disparado desde el
REPL también sincroniza el selector del panel.

Perezoso a propósito: `Rem.py` también importa `rem_avatar_server` pero tiene su propio pipeline de
conversación aparte (Tkinter, `preguntar_groq()`) y no usa nada de esto — construir la sesión
recién en el primer `chat_message`/`cambiar_modo`/`reset` real evita pagar `get_provider()` (que
puede lanzar sin API key) o leer `memoria_larga.json`/`memoria_sistema.json` para quien no la pide.

**Turnos serializados con un flag, no una cola**: `_procesar_mensaje_chat()` rechaza un
`chat_message` nuevo con un `error` si ya hay un turno en curso (`_chat_turno_activo`, guardado con
un `threading.Lock` normal, nunca sostenido a través de un `await` — sostener un `threading.Lock`
mientras se espera algo en un loop de asyncio de un solo hilo puede colgar ese mismo hilo si otra
tarea del mismo loop necesita el mismo lock antes de que se libere). Suficiente para el caso real
(un usuario, un panel) y evita interlear dos streams de `chat_delta` en la misma lista de mensajes,
que sería confuso incluso sin ningún problema de concurrencia real de por medio.

**Verificado en vivo, end to end**: cliente WebSocket de prueba conectado al mismo `:18766` que usa
`rem_chat.py` — `cambiar_modo` a `eco` sincronizó el selector del panel real (con la nota de
sistema "Modo: Eco" y el historial limpio) sin tocar nada de la ventana directamente; `chat_message`
en modo `ia` (provider real, Ollama) devolvió fragmentos sub-palabra reales por `chat_delta` y
terminó en `chat_done`, con la burbuja de Rem creciendo en la ventana real a medida que llegaban;
turnos repetidos en secuencia (varios `chat_message` uno tras otro) generaron una burbuja nueva por
turno sin errores ni mezclarse. Corregido en el camino: la primera versión de
`_procesar_mensaje_chat()` no pasaba `incluir_contexto=False` en modo eco, así que el panel iba a
repetir en voz—en texto, acá—el bloque de fecha/hora/CPU en vez de lo que se escribió (mismo bug
que ya se había corregido una vez en `bench_chat.py`, reintroducido acá por no compartir esa
decisión con `procesar_turno()`; ahora `_procesar_mensaje_chat()` calcula
`incluir_contexto = sesion.modo != "eco"` igual que `repl()`).

## Voz en la ventana de chat
El panel de chat (ver arriba) arrancó siendo solo texto — `_procesar_mensaje_chat()` llamaba a
`chat_sesion.procesar_turno()` sin `cola_habla`, así que escribir en la ventana nunca producía voz,
aunque la ventana existe justamente para hablar con Rem. `_chat()` (REPL de `bench_chat.py`) y
`_procesar_mensaje_chat()` (panel) eran casi idénticas salvo el destino del texto/audio — se
unificó la parte común (armar el turno, consumir el stream, hablar por oración) en
`chat_sesion.procesar_turno()`, y el pipeline de voz en sí (antes atado al REPL) se extrajo a
`habla.py`.

**`habla.py`**: `cargar_rvc()`/`precargar_rvc()`/`decir()`/`worker_habla()`/`TurnoHabla`, todo lo
que antes vivía en `bench_chat.py` con el prefijo `_` (`_obtener_rvc`, `_decir`, `_worker_habla`,
`_TurnoHabla`, etc.) — mismos cuerpos, solo movidos y sin el guion bajo en lo que ahora es API
pública del módulo. `_rvc_cache`/`_rvc_lock` siguen siendo module-level (una sola instancia de RVC
por proceso, cargada una vez) — importante porque ahora hay DOS consumidores posibles en el mismo
proceso (la cola del REPL y la del panel, ver más abajo) que no deben cargar el modelo por
duplicado ni pisarse entre conversiones concurrentes, mismo motivo que ya tenía el lock antes de
este cambio.

**`chat_sesion.procesar_turno()` ahora cubre los dos casos** (con y sin voz) vía parámetros
opcionales: `on_delta` (cada fragmento de texto, como antes), `on_tool_call` (preservado por si
`stream_chat()` alguna vez se llama con `tools=`, hoy no aplica) y `cola_habla` (si no es `None`,
encola cada oración completa apenas `dividir_en_oraciones()` la detecta — igual que hacía `_chat()`
antes de la extracción). Devuelve `(texto_completo, done_chunk, turno_habla)` — `turno_habla` es la
instancia de `habla.TurnoHabla` si se pidió voz, o `None` si no. `_pasar_por()` (el tee que permite
consumir el stream dos veces — para deltas/tool_calls y para partir oraciones a la vez) también se
movió a este módulo.

**`bench_chat.py._chat()` quedó como envoltorio de consola**: arma los callbacks de impresión
(`on_delta` imprime, `on_tool_call` imprime `[tool_call] ...`) y llama a `procesar_turno()` —
ya no tiene lógica de turno propia. El REPL sigue con su propia cola/worker de voz
(`asyncio.Queue` + `habla.worker_habla()`, creados en `repl()`), sin cambios de comportamiento
para quien ya lo usaba.

**El panel tiene su PROPIA cola/worker de voz, separada de la del REPL** —
`rem_avatar_server._obtener_cola_habla()` crea (perezoso, en el primer turno con voz) un
`asyncio.Queue` + una tarea `habla.worker_habla()` propios del panel, corriendo en `_ws_loop` (la
llamada a `asyncio.create_task()` liga la tarea al loop que esté corriendo en ese momento — por
eso `_obtener_cola_habla()` solo puede llamarse desde dentro de una coroutine que ya corre en
`_ws_loop`, que es exactamente lo que es `_procesar_mensaje_chat()`). No comparten cola con el REPL
a propósito: cada turno se habla desde la cola de quien lo disparó, así que un mensaje escrito en
un lado nunca termina también encolado en el worker del otro — ver más abajo, "verificado en vivo",
por qué esto importa para no duplicar audio.

**Interruptor de voz del panel** (`voz_chat_activa()`/`set_voz_chat_activa()` en
`rem_avatar_server.py`, mensaje WS `{tipo: "voz", activa: bool}`): equivalente a `voz on|off` del
REPL, pero **independiente** — no hay sincronización entre los dos, cada uno controla si SUS
PROPIOS turnos hablan. Arranca en `True` (a diferencia de `voz_activa` del REPL, que arranca en
`False`): la ventana existe para hablar con Rem, así que el botón (🔊/🔇 en el header del panel) es
para silenciarla, no para tener que activarla primero. Es puramente local en el frontend — a
diferencia de `cambiar_modo`, no hay confirmación del backend ni un tipo `voz_actual` que
sincronizar (un on/off no puede fallar, y no hay ningún otro cliente cuyo estado deba reflejar).

**`rem_chat.py` ahora también precarga RVC al arrancar** (`habla.precargar_rvc()` en un hilo de
fondo, antes de `iniciar_servidor_avatar()`, mismo patrón que `bench_chat.py`) — sin flag `--no-rvc`
propio: a diferencia del REPL (donde la voz es opcional, detrás de `voz on`), en la ventana es una
capacidad de primera clase, así que siempre precarga.

**Verificado en vivo, los cuatro escenarios**:
1. Panel con voz activa, modo eco: `chat_message` por WS produjo exactamente una línea `hablando:
   "..."` en el log, conversión RVC, `enviado por WebSocket`, y el navegador real (`rem_chat.py`)
   registró `[Lipsync] mensaje de audio recibido` + `play() resuelto` — la ventana efectivamente
   habla.
2. Interruptor en `False`: el mismo `chat_message` completó `chat_delta`/`chat_done` normalmente
   (el texto se sigue viendo) pero sin ninguna línea `hablando:` nueva en el log — cero turnos de
   síntesis cuando la voz está apagada.
3. **Doble cliente, la prueba pedida explícitamente** ("con la ventana y el REPL abiertos a la
   vez"): se lanzó `bench_chat.py` primero (dueño real del servidor WS + su propio overlay como
   cliente) y `rem_chat.py` segundo (detecta el servidor existente, se conecta como otro cliente
   más — ver "Riesgo de conflicto de puertos" más arriba). Un `chat` + `voz on` desde el REPL
   produjo **una sola** línea `hablando:` para ese turno (con la cola/worker del REPL); un
   `chat_message` inyectado por WebSocket (simulando al panel) produjo **una sola** línea
   `hablando:` para ESE turno (con la cola/worker del panel, cargando su propia instancia de RVC
   perezosamente la primera vez que le tocó hablar — reutilizando el mismo `_rvc_cache` después).
   Total de la sesión: 2 líneas `hablando:` para 2 turnos — ninguno duplicado.
   - Nota sobre alcance: `enviar_audio()` igual **difunde** cada turno a todos los clientes WS
     conectados (así ya funcionaba antes de este cambio, ver "Riesgo de conflicto de puertos" y
     "Ninguna llamada al LLM sin intervención del usuario" — es una propiedad del diseño de
     broadcast, no algo que este cambio haya tocado): con el overlay del REPL y la ventana los dos
     conectados al mismo servidor, un turno con voz suena en los dos, cada uno una vez. Lo que se
     verificó (y lo que pedía el punto 1) es que el BACKEND nunca sintetiza/encola el mismo turno
     dos veces — no que un segundo cliente conectado deje de escuchar la misma reproducción
     legítima, que es un comportamiento distinto (y deseable: si alguien tiene el overlay en un
     monitor y la ventana en otro, esperaría que ambos hablen a la vez).
4. Interacción con `iniciar_servidor_avatar()`: al reusar el servidor de otro proceso, ese segundo
   proceso NUNCA corre su propio `_ws_handler` — sus propios `_ws_clients`/`_chat_sesion`/etc.
   quedan vacíos para siempre (son globals de módulo, uno por proceso). Confirmado en vivo: con
   `rem_chat.py` como segundo proceso, un `enviar_audio()` disparado DESDE ESE proceso cayó al
   fallback local de `sounddevice` ("nadie conectado al WS") pese a que la ventana real sí estaba
   conectada — porque la ventana está conectada al servidor real (el del OTRO proceso), no al
   `_ws_clients` (vacío) de la suya propia. No es un bug de esta tarea: es la razón por la que el
   escenario 3 se armó con `bench_chat.py` primero (dueño real del servidor) — así el turno del
   REPL sí llega a `_ws_clients` reales. Documentado acá para que quede claro por qué el orden de
   arranque importa en este escenario específico.

## Encuadre 3D consciente del panel de chat, y tamaño por modo
Con el panel de chat ocupando la mitad derecha de la ventana (ver arriba), Rem quedaba descentrada:
`recalcularEncuadre()` seguía calculando `anchorX` como fracción del ANCHO TOTAL de la ventana, no
del área 3D realmente visible (la mitad izquierda, la que no tapa el panel) — con `anchorX=1/6`
(pensado para el ancho completo, "tercio izquierdo" de antes de que existiera el panel) Rem
terminaba pegada al borde izquierdo de su propia mitad, no centrada en ella.

**`fraccionAreaVisible3D()`** devuelve qué fracción del CANVAS COMPLETO ocupa el área 3D visible:
`1 - CONFIG.chat.anchoFrac` en modo ventana, `1` en overlay (sin panel, sin cambios). `worldX(n)`
en sí no cambió — sigue midiendo en fracciones del canvas completo, a propósito: `camera.aspect`
tiene que seguir atado al tamaño REAL del render, o la imagen se distorsiona. Lo que cambió es qué
se le pasa: `recalcularEncuadre()` ahora hace `worldX(CONFIG.pet.anchorX * fraccionAreaVisible3D())`
en vez de `worldX(CONFIG.pet.anchorX)` — `anchorX` pasó a ser una fracción DEL ÁREA VISIBLE
(0=su borde izquierdo, 1=justo donde empieza el panel), no del canvas completo. Con eso,
`CONFIG.modos.ventana.anchorX` pasó de `1/6` a `0.5` (centrada en su área, como pide la
especificación) — `overlay.anchorX` sigue en `0.5` (sin panel, área visible = canvas completo, sin
cambio de comportamiento).

**`CONFIG.chat.anchoFrac` es la única fuente de verdad para el ancho del panel** — la lee tanto
`fraccionAreaVisible3D()` (encuadre) como `crearPanelChat()`, que fija el custom property CSS
`--chat-panel-width` (`${CONFIG.chat.anchoFrac * 100}%`) ANTES de crear el `<div>` del panel. El
CSS del `<head>` usa `width: var(--chat-panel-width, 50%)` — el `50%` es solo el valor de respaldo
por si el custom property no llegara a fijarse (no debería notarse nunca, se fija sincrónicamente
muy temprano en el mismo `<script type="module">`). Antes el 50% estaba hardcodeado en dos lugares
(el CSS y, implícitamente, en cualquier cálculo de encuadre que lo asumiera) — ahora un cambio a
`CONFIG.chat.anchoFrac` mueve los dos a la vez, no pueden desincronizarse.

**`alturaPantalla` pasó de `CONFIG.pet` (un solo valor) a `CONFIG.modos.{overlay,ventana}`** (cada
modo con el suyo) — mismo patrón que ya tenía `anchorX`, resuelto una vez al cargar
(`CONFIG.pet.alturaPantalla = CONFIG.modos[MODO].alturaPantalla`, junto a la resolución de
`anchorX` que ya existía). `overlay` se quedó en `0.45` (sin cambios); `ventana` subió a `0.65`
(pedido explícito: "empieza en 0,65") — cada modo necesita un encuadre distinto porque el overlay es
una superficie angosta dedicada solo a Rem, mientras que la ventana reparte el espacio con el panel
de chat.

**Verificado en vivo**: captura de pantalla con la ventana real mostró a Rem centrada
horizontalmente en la mitad izquierda (ya no pegada al borde) y notablemente más grande que antes
— y el log de `[Encuadre]` confirmó la aritmética exacta (`anchoVisible=1.077`, `anchorX=0.5` →
`position.x=-0.269`, que es `(0.5*0.5 - 0.5) * 1.077`, coincide byte a byte con lo calculado a
mano).

## Mirada a cámara, con saccades y "apartar la mirada" superpuestos
Antes las saccades (`updateSaccades()`) eran todo el control de los ojos: saltos aleatorios
alrededor de un centro FIJO en `(0,0)` grados (o un offset fijo en `thinking`) — nunca miraba
realmente a la cámara/usuario, solo alrededor de un punto arbitrario.

**API real de `VRMLookAt` (three-vrm), confirmada leyendo el bundle fuente** (no documentación de
memoria — se bajó `@pixiv/three-vrm@2.1.3` de esm.sh y se inspeccionó la clase minificada): el
método público `lookAt(posiciónMundo)` calcula `_yaw`/`_pitch` (grados) para mirar exactamente a esa
posición desde la orientación ACTUAL de la cabeza — es lo mismo que el auto-tracking interno usaría
si `target`/`autoUpdate` estuvieran en su modo automático (`update(dt)`: `if (target && autoUpdate)
this.lookAt(target.getWorldPosition())`). Como este proyecto ya escribía `vrm.lookAt.yaw`/`.pitch` a
mano cada frame (para las saccades), la solución fue llamar a `vrm.lookAt.lookAt(camera.
getWorldPosition())` directo, en vez de depender del auto-tracking — con `target=camera` fijado
solo como documentación viva (nadie más lo lee) y `autoUpdate=false` a propósito: si quedara en
`true` (el default), `vrm.update()` volvería a llamar a `lookAt()` por su cuenta DESPUÉS de que este
código ya escribió el valor final (saccades + apartar-la-mirada incluidos), pisándolo.

**Se recalcula cada frame, no una vez** — importante porque la orientación de la cabeza cambia todo
el tiempo (el drift de `updateLook()`, y durante un clip VRMA el mixer posa cabeza/cuerpo entero):
`vrm.lookAt.lookAt()` usa la matriz de mundo ACTUAL del hueso `head` en el momento en que se llama,
así que los ojos compensan solos cualquier movimiento de cabeza sin que este código sepa nada de
`updateLook()`/del clip activo. Se llama antes de que `headB.rotation` se escriba con el
valor de ESTE frame (mismo punto donde ya vivía `updateSaccades()`) — un frame de atraso en la base
de la mirada, igual de imperceptible que otros casos ya documentados de esta clase en el archivo
(p.ej. `_jawApertura`).

**Tres capas, de la más lenta a la más rápida**:
1. **Base**: sigue a la cámara (`vrm.lookAt.lookAt()` × `CONFIG.mirada.intensidadSeguimiento`,
   1.0 = mirada directa). En `thinking` la base es fija arriba-a-un-lado (`yaw=-10, pitch=8`, el
   mismo punto de siempre) — Rem está pensando, no mirando al usuario.
2. **Apartar la mirada** (`_miradaFase`: `'siguiendo' ↔ 'apartando'`, mismo patrón de máquina de
   estados que `updateGiroBailarina()`): cada `apartarIntervaloMinS`-`apartarIntervaloMaxS`
   segundos (nunca en `thinking`, que ya tiene su propio desvío), se suma un offset aleatorio
   (`apartarAmpYaw`/`apartarAmpPitch`) con envolvente entra-sostiene-sale (`_envolventeApartar()`,
   con `_fade()` en las rampas) — mirar fijo sin parpadear tampoco es natural.
3. **Saccades**: como antes (saltos rápidos de 20-40ms cada 0,5-2s), pero ahora RELATIVOS a la base
   de las capas 1+2 en vez de a un centro fijo — se separaron `_saccadeYaw/_saccadePitch` (el
   desvío actual) de `_saccadeYawObjetivo/_saccadePitchObjetivo` (el objetivo del salto en curso),
   y `vrm.lookAt.yaw/pitch` se escribe SIEMPRE (`base + saccade`), no solo mientras hay un salto en
   curso — a diferencia de la versión vieja (centro fijo, no hacía falta reescribir entre saltos),
   la base ahora se mueve todo el tiempo.

**`CONFIG.mirada`**: `intensidadSeguimiento` (0..1, cuánto gira hacia la cámara) y
`apartarIntervaloMinS/MaxS`/`apartarAmpYaw/Pitch`/`apartarEntradaS/SostenS/SalidaS` (frecuencia,
amplitud y timing de apartar la mirada) — pedidos explícitamente en CONFIG para poder afinarse.

**Verificado en vivo**: con `apartarIntervaloMinS/MaxS` bajados temporalmente a 2-3s (revertidos a
4/9 después) y logs de transición agregados, se vieron varios ciclos completos
(`[Mirada] apartando (yaw=..., pitch=...)` → `[Mirada] de vuelta a cámara, próximo apartado en
~Ns`) sin errores, con capturas de pantalla confirmando que el mecanismo corre sin romper nada del
resto de la animación (respiración, brazos, dedos, giro).

## Mirada a cámara, segunda pasada: la cámara no estaba alineada con Rem
La mirada a cámara (ver más arriba) seguía sin verse directa. La causa no estaba en `vrm.lookAt`
sino en el encuadre: en modo ventana Rem está desplazada del centro de la ventana (`posX`, para
dejarle sitio al panel de chat), pero `camera.position.x` se quedaba siempre en 0. El vector
cámara→Rem tenía entonces una componente en X — la cámara la veía en tres cuartos, no de frente —
y los ojos tenían que girar para compensar ESE ángulo estructural además de cualquier seguimiento
real, compitiendo con un rango de giro bastante angosto (ver el punto siguiente).

**Cámara alineada con Rem en X, más `setViewOffset()` para no perder el encuadre.**
`recalcularEncuadre()` ahora hace `camera.position.x = posX` y `camera.lookAt(posX, 0, 0)` (mismo
`posX` que ya se usa para `vrm.scene.position.x`) — el vector cámara→Rem queda puramente `-Z`,
vista frontal de verdad. Como el punto que mira la cámara siempre proyecta al centro de la imagen,
esto por sí solo centraría a Rem en el medio del CANVAS COMPLETO (en modo ventana, debajo del
panel) — se corrige con `camera.setViewOffset(window.innerWidth, window.innerHeight, offsetX, 0,
window.innerWidth, window.innerHeight)`, con `offsetX = (0.5 - fracXCanvas) * window.innerWidth`:
un corrimiento de "lente descentrado" (el mismo truco que un objetivo tilt-shift o un corrimiento
de cámara de arquitectura) que reencuadra la imagen ya renderizada sin volver a rotar la cámara
(rotar la reintroduciría el ángulo que se acaba de eliminar). En overlay, `fracXCanvas=0.5` siempre
(sin panel), así que `offsetX=0` — no-op, confirmado en vivo (`position.x=0.000 viewOffsetX=0.0px`,
sin cambios de comportamiento).

**El punto de fuga de la cuadrícula se repositiona con la cámara.** `posicionarSuelo()` ahora
también centra el grid/horizonte en `posX` (antes solo ajustaba la Y) — el punto de fuga lo
determina el eje óptico REAL de la cámara (`camera.position.x`, no dónde termina apareciendo Rem en
pantalla tras el `setViewOffset`), así que centrar el suelo en `posX` pone el punto de fuga
exactamente detrás de Rem en vez de en el `x=0` fijo de antes (que ya no significaba nada
particular). Verificado en vivo con captura: las líneas de la cuadrícula convergen justo bajo sus
pies, más coherente que antes.

**Límites reales de `lookAt` en este modelo — investigado, no solo sospechado.** Se bajó
`@pixiv/three-vrm@2.1.3` de esm.sh y se leyó el parser VRM 0.x (`_v0ImportDegreeMap`) para confirmar
qué hace exactamente con `firstPerson.lookAt{Horizontal,Vertical}{Inner,Outer,Down,Up}` de
`rem.vrm` (inspeccionado también con `dump_vrm.py` sobre el glTF crudo): las cuatro curvas son
`[0,0,0,1,1,1,1,0]` — la única curva que three-vrm soporta para VRM 0.x, que resulta ser
**exactamente lineal** (ambas tangentes de Hermite en los extremos igualan la pendiente de la
secante, así que la curva de Bezier se reduce a una recta) — con `xRange=90, yRange=10` en las
cuatro. Eso da `map(e) = 10 * clamp(e/90, 0, 1)`: el ojo real gira **exactamente 1/9 de lo que se le
pide**, hasta un tope de 10° en cualquier dirección. Confirma la sospecha del reporte: las saccades
(±14°/±8° de pedido) y el apartar-la-mirada (±26°/±14°) ya venían recortados a apenas 1-3° reales
de giro de ojo, independientemente del problema de la cámara — los dos problemas se sumaban.
`[VRM] rangos de lookAt` (nuevo log al cargar el modelo, lee `vrm.lookAt.applier.rangeMap*` en vivo
— no hace falta volver a correr `dump_vrm.py` para redescubrir esto si el modelo cambia) y
`[Mirada] pedido yaw/pitch` (nuevo log cada 2s desde `updateSaccades()`) dejan esto verificable sin
salir del navegador. No se retocaron las amplitudes de saccades/apartar — quedó reportado para que
se ajusten a mano si hace falta, mismo criterio que "mostrame los rangos para afinarlos yo después".

**La cabeza (y el cuello) ahora acompañan la mirada.** Antes solo los ojos seguían a la cámara — una
persona real también gira un poco la cabeza. `updateSaccades()` calcula `_cabezaMiradaYaw/Pitch`,
una versión CON RETARDO (`lerp` a `CONFIG.mirada.cabezaVelocidad` por segundo — más lento que la
respuesta instantánea de los ojos, que se escriben sin demora arriba en la misma función: los ojos
llegan primero, la cabeza detrás) de la mirada final (base de cámara + saccade + apartar, ya
combinadas). `animate()` sólo la aplica fuera de `'thinking'` (que ya tiene su propio desvío de
cabeza fijo vía `updateLook()`, apuntando al mismo punto que usa `_miradaBase()` para los ojos —
sumar los dos hubiera duplicado el giro) y la suma a `tHX`/`tHY`, escalada por
`CONFIG.mirada.cabezaFraccion` (empieza en 0,3, pedido explícito). **El cuello ya se repartía
automáticamente**: `neckB.rotation.{x,y,z}` ya leía una fracción (0,30-0,38) del MISMO spring
resuelto que usa `headB` — sumar la mirada a `tHX/tHY` (el objetivo del spring, antes de resolverlo)
hace que la nueva contribución se reparta entre cabeza y cuello sin código nuevo específico para
eso.

**Verificado en vivo, numéricamente, no solo a ojo**: log temporal de `headB.rotation.y`/
`neckB.rotation.y`/`_cabezaMiradaYaw` cada 0,3s durante un apartado real (con
`apartarIntervaloMinS/MaxS` bajados temporalmente a 2-3s, revertidos después). Con
`[Mirada] apartando (yaw=-25.5, ...)`, se vio `_cabezaMiradaYaw` moverse de +2,5° a -19,5° con
retardo visible frente al salto instantáneo de los ojos, `head.rotation.y` seguir la MISMA
dirección (negativa) proporcionalmente (~un tercio de `_cabezaMiradaYaw`, coincide con
`cabezaFraccion=0.3` más el retardo propio del spring), y `neck.rotation.y` seguir a `head.rotation.y`
en la proporción 0,30 ya existente — confirma signo y magnitud correctos, no una suposición sin
probar. Capturas de pantalla del encuadre completo confirmaron además que Rem sigue apareciendo en
la mitad izquierda (no debajo del panel) y con una mirada visiblemente más directa a cámara que
antes de esta pasada.

## Animación de cuerpo con clips VRMA

Las poses de cuerpo por estado (ruido Perlin) y el "giro de bailarina" a mano se reemplazaron por
clips `.vrma` reales (formato [VRM Animation](https://vrm.dev/en/vrma/)) reproducidos con
`THREE.AnimationMixer`. Motivo: las poses codificadas a mano no daban la calidad necesaria (el giro
levantaba la rodilla hacia atrás en vez de elevar el pie; `thinking` se veía mal). Todo el cambio
está en `rem_avatar.html` — no se tocó Python.

### Estructura de `Animaciones/`

```
Animaciones/
├── README.md                    (de dónde se baja cada conjunto + términos de uso)
└── VRMA_MotionPack/             (todos los .vrma acá, por nombre exacto)
    ├── Thinking.vrma Sad.vrma Angry.vrma Surprised.vrma Blush.vrma
    ├── LookAround.vrma Sleepy.vrma Goodbye.vrma Clapping.vrma   (pack tk256ailab, MIT)
    ├── Readme_VRMA_MotionPack_EN.txt
    └── VRMA_01.vrma … VRMA_07.vrma                              (pack oficial VRoid Project)
```

`Animaciones/` está en `.gitignore` (mismo criterio que `rmvpe.pt`/`rem.vrm`). Se descarga a mano
— ver `Animaciones/README.md`. Si un clip falta o no parsea, el avatar cae a la animación
procedural con un aviso (`[Anim] "<archivo>" no disponible: … — se mantiene la animación
procedural`), sin romperse.

### Librería: `@pixiv/three-vrm-animation@2.1.3` (solo el loader plugin)

- Versión emparejada con `@pixiv/three-vrm@2` (mismo `three-vrm-core`, mismo módulo `three` vía
  esm.sh). Subir todo a `@3` rompería la integración fina con internals de v2 (`expr._binds`,
  `vrm.lookAt.applier.rangeMap*`).
- Se usa **solo `VRMAnimationLoaderPlugin`** (registrado en el mismo `GLTFLoader` que carga
  `/rem.vrm` — es inerte para un `.vrm`). Hace el parseo + retargetizado real de rotaciones (rig
  origen → rig del modelo).
- **NO se usa `createVRMAnimationClip`**: ese además arma pistas de expresión/mirada y auto-crea un
  `VRMLookAtQuaternionProxy` en la escena. En su lugar `clipDeVrma(va)` arma el `THREE.AnimationClip`
  a mano (replica la parte *humanoid* de `createVRMAnimationHumanoidTracks` v2.1.3) con el `THREE`
  de la página — el mismo que el mixer, sin costura de versiones nueva.
- **Gotcha `specVersion`**: los 9 `.vrma` de `tk256ailab` no traen
  `extensions.VRMC_vrm_animation.specVersion`, y `VRMAnimationLoaderPlugin@2.1.3` aborta el parseo
  sin él (v3.1+ lo tolera). `normalizarVrma(url)` parchea una **copia en memoria** (inyecta
  `specVersion:"1.0"`, re-empaqueta el glb, devuelve un blob URL) antes de dársela a `GLTFLoader`
  — el archivo en disco no se toca, sin paso manual. El pack VRoid ya lo trae: para esos devuelve
  la URL original.

### Regla dura: los clips SOLO mueven huesos de cuerpo

- `clipDeVrma()` excluye `leftEye`/`rightEye`/`jaw` (`_EXCLUIR_HUESOS_CLIP`) y **nunca** crea pistas
  de expresión ni de mirada (usa solo `va.humanoidTracks`).
- **Respiración, parpadeo, saccades, mirada a cámara y jaw se aplican SIEMPRE encima del mixer,
  también durante un clip.** Los ojos van por `vrm.lookAt` (`updateSaccades()`, incondicional); el
  parpadeo/expresión por `expressionManager` (`updateBlink()`/`updateExpressions()`, incondicional);
  el jaw por el hueso crudo en `aplicarVisemesPostUpdate()` (después de `vrm.update()`). La
  respiración (`aplicarRespiracionEncima`) y el seguimiento de cabeza (`aplicarCabezaSigueMiradaEncima`,
  contenido, salvo en `thinking`) se suman (`+=`) tras `mixer.update()`, escalados por `_clipPeso`
  para no doblar el aporte procedural en la transición.
- **La cara es independiente del cuerpo**: `updateExpressions()` maneja la expresión facial por
  `estado`. Por eso "volver a lo procedural manteniendo la emoción" sale gratis — al terminar un
  clip `unaVez` o vencer el `duracionS` de un `bucle`, `volverAProcedural()` devuelve el cuerpo a lo
  procedural y la cara conserva la emoción sola mientras `estado` siga activo (nunca se deja el
  cuerpo plantado en el frame final).

### La mezcla (`actualizarAnimacionClips` en `animate()`)

`vrm.update(dt)` copia los huesos normalizados a los crudos. El mixer y el código procedural
escriben huesos normalizados **antes** de `vrm.update()` — el mixer es un escritor más, aguas
arriba.

- `_clipPeso` (0 = procedural puro, 1 = clip puro) rampa a `dt / crossfadeS` por frame.
- `_clipPeso === 0`: solo `aplicarCuerpoProcedural(t, dt)` (el bloque de pose por estado + springs,
  extraído tal cual de `animate()`; `getStatePose()` y sus 7 casos se conservan).
- `_clipPeso === 1`: solo `_mixer.update(dt)` + respiración/cabeza encima.
- en transición (`0 < _clipPeso < 1`): corren **ambos** — se posa lo procedural, se hace snapshot
  del `.quaternion` de cada hueso (`_huesosNorm`), `_mixer.update()` escribe la pose del clip, y por
  hueso `quaternion.slerpQuaternions(qProc, qClip, _clipPeso)` (+ lerp de `hips.position`).
- clip → clip: `_accionActual.crossFadeTo(nueva, crossfadeS)` nativo del mixer; `_clipPeso` se
  queda en 1.
- Al llegar `_clipPeso` a 0: `_mixer.stopAllAction()` + `vrm.humanoid.resetNormalizedPose()` (deja
  en reposo piernas/`hips.position` que el clip movió y lo procedural no toca).

### Mapeo estado → clip y gestos de reposo (`CONFIG.animaciones`)

Todo configurable sin tocar código:

| `porEstado` | clip | modo |
|---|---|---|
| `thinking` | `Thinking.vrma` | `bucle` (sin tope — dura lo que dure thinking) |
| `sad` | `Sad.vrma` | `bucle`, `duracionS: 6` |
| `angry` | `Angry.vrma` | `bucle`, `duracionS: 4` |
| `surprised` | `Surprised.vrma` | `unaVez` |
| `happy` | `Blush.vrma` | `unaVez` |
| `talking`, `idle` | — | sin clip (procedural) |

- `modo: 'bucle'` = `LoopRepeat`; `duracionS` opcional = tras N s de controlar el cuerpo hace
  crossfade a procedural (la cara sigue). `modo: 'unaVez'` = `LoopOnce` + `clampWhenFinished`; al
  terminar hace crossfade a procedural **siempre**.
- `sincronizarClipConEstado()` se llama en el `estado !== prevEstado` de `animate()`. Guarda de
  carrera: `_tokenClip` invalida cargas async pendientes si el estado cambió mientras el `.vrma`
  cargaba.

**Gestos de reposo** (`CONFIG.animaciones.gestos`, reemplazan el giro): solo en `estado === 'idle'`
&& `!_audioActivo` && sin clip de estado. Cada `intervaloMinS`–`intervaloMaxS` (25–55s) se elige uno
por peso:

| clip | peso | nota |
|---|---|---|
| `LookAround.vrma` | 6 | frecuente |
| `VRMA_05.vrma` (girar) | 1 | reemplaza el giro a mano |
| `VRMA_07.vrma` (flexiones) | 1 | |
| `VRMA_01.vrma` (cuerpo entero) | 1 | |
| `Sleepy.vrma` | 3 | solo `horaDesde:0`–`horaHasta:6` (00:00–06:00, `new Date().getHours()`) |

`Goodbye.vrma`/`Clapping.vrma`/`VRMA_02.vrma` quedan disponibles pero fuera del repertorio.

**Interrupción (la voz manda)**: si llega audio o cambia el estado a mitad de un gesto o clip,
`updateGestos()`/`sincronizarClipConEstado()` disparan `volverAProcedural()` o un `crossFadeTo` al
clip que toque — siempre con crossfade, nunca corte.

### Carga perezosa + cache

`obtenerClip(archivo)` carga el `.vrma` la primera vez que se usa y cachea el resultado (también el
**fallo**, para no reintentar en cada disparo). Nunca lanza: en error devuelve `{archivo, error}` y
el llamador cae a lo procedural.

### Cómo añadir un clip nuevo

1. Dejar el `.vrma` en `Animaciones/VRMA_MotionPack/`.
2. Agregar la entrada en `CONFIG.animaciones.porEstado` (estado → clip) o
   `CONFIG.animaciones.gestos.repertorio` (gesto de reposo con peso, opcionalmente
   `horaDesde`/`horaHasta`).
3. Nada más — la carga es perezosa/cacheada; si el archivo falta o no parsea, cae a lo procedural
   con un aviso en consola. Si el `.vrma` no trae `specVersion`, `normalizarVrma()` lo parchea en
   memoria automáticamente.

Los clips **no tocan expresiones ni mirada**: si un `.vrma` nuevo trae pistas de expresión/mirada,
`clipDeVrma()` las ignora (usa solo `humanoidTracks`), y si anima `leftEye`/`rightEye`/`jaw` esos
huesos se excluyen. No hay que hacer nada especial para eso.

    # IMPORTANTE: 
    AL MOMENTO DE HACER COMMIT NO PONGAS TU AUDITORIA Claude/Anthropic DETRO DEL COMMIT
