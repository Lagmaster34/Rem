# Rem — Asistente Virtual IA

## ⚠ Fase 2 en curso: ver "Nota de traspaso — fase 2" al final (estado y PENDIENTES en orden) y `notas_fase2/README.md`
Etapas 2, 4 y 5 hechas y commiteadas (2026-11-06): modo escritorio, ajustes y temas, micrófono.
Pendiente 1 de la nota hecho el 2026-11-07 (adelantada vieja abandonada); lo siguiente es el 2.
**Regla: enseñar siempre el diff antes de cada commit y esperar el ok de Esteban.**

## ⚠ Cambio 2026-11-04: avatar multimodelo y director de animación (leer antes que lo de abajo)
- **Rem (rem.vrm, rem_naenae.vrm) y los 17 clips de `VRMA_MotionPack/` ("Rem anterior") salieron del
  proyecto** (respaldo en `~/Descargas/rem_respaldo/`). Lo que abajo hable de `rem.vrm`, sus visemes vrc.* o
  `Thinking.vrma` es historia.
- Modelos en `models/vrm/` (neru, ls15, lili, noir; créditos en `models/README.md`), solo locales: `*.vrm`/`*.glb`
  en `.gitignore` y rechazados por `hooks/`. Cambio en caliente: botón 👤 / `/modelo` → `prefs_set modelo.vrm` →
  `prefs_actualizadas` → `cambiarModelo()` (desmonta con `VRMUtils.deepDispose`, `uncacheRoot`, invalida por
  `_modeloGen`). `modelos_vrm.py` + WS `modelos_get`/`modelos_lista`.
- Autodetección por modelo: VRM 1.0 sin giro de 180° y con la pose procedural espejada (`_espejarHuesos`: x/z del
  cuaternión negados); lipsync por los binds de aa/ih/ou/ee/oh; emociones a apagar al hablar por nombre de morph.
  `CONFIG.modelos` queda solo para overrides.
- Director (`updateDirector`, ideas del documento de Nerumi): ruleta de reposo cada 60–120 s (35 % idle procedural
  —`IDLES_PROCEDURALES`—, 65 % VRMA con grupo raro 20 %), modo baile (`/bailar`, 💃) con bolsas sin repetición
  (súper raro 3 %), saludo al abrir/cambiar de modelo, estado `listening` durante el push-to-talk, puente de pose
  0,5 s entre clips y 0,12 s en la vuelta del bucle (reemplaza `crossFadeTo`). Catálogo v2: `raro`, `expresion`,
  `saludo`, `ajustes.prob*`; `thinking` ya no tiene clip (procedural).
- Emoción del chat: el modelo abre con `[FELIZ]`/`[TRISTE]`/`[ENOJADA]`/`[SORPRENDIDA]` (regla EMOCIÓN +
  ejemplos de tono); `chat_sesion._extraer_emocion` la quita antes del chat/voz y el servidor manda `emocion`
  → cara + clip de `porEstado`. **Sin banco de cumplimiento todavía** (cuántas respuestas la traen).

## Qué es este proyecto
Asistente personal de IA con personalidad de Rem de Re:Zero. Corre en **Linux (Arch)**.  
Habla (voz de Yoru, Piper local), escucha, recuerda, ejecuta acciones en el sistema y muestra un avatar
3D animado en el escritorio. Con Ollama + STT local funciona sin internet (ver "Voz de Yoru (Piper)").

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
| LLM | Ollama local (Qwen3.5-4B) por defecto; Claude (`claude-sonnet-5`, API de Anthropic) como alternativa |
| TTS | Piper (`piper-tts` 1.8, CPU) con la voz de Yoru (`[tts].modelo`, por defecto `models/piper/`). Ver "Voz de Yoru (Piper)" |
| STT | `faster-whisper` local (`stt/`), push-to-talk |
| GUI | GTK3 + WebKit2 (`rem_chat.py`) — la ventana del avatar con panel de chat, u overlay |
| Avatar 3D | Three.js + `@pixiv/three-vrm` + `@pixiv/three-vrm-animation` en WebGL, vendorizados en `vendor/esm/` |
| Ventana | GTK3 + WebKit2, `venv/bin/python` (PyGObject/pycairo instalados ahí, ver "El venv sí puede tener GTK" más abajo) |

## Archivos principales
| Archivo | Qué hace |
|---------|----------|
| `rem_chat.py` | **La aplicación**: levanta el servidor HTTP/WS y abre UNA presentación, `--modo ventana` (default), `--modo overlay` o `--modo escritorio`. Ver "Modo overlay" y "Modo escritorio" más abajo |
| `escritorio.py` | El modo escritorio en GTK: la layer surface del avatar (arrastre, región de clic, cambio de monitor, posición guardada) y la ventana de chat aparte. Ver "Modo escritorio" |
| `rem_chat_ventana.html` | La ventana de chat del modo escritorio: el panel de chat de siempre con su propio WebSocket (`avatar/chat_remoto.js`) |
| `rem_escritorio.py` | CLI: `mostrar\|ocultar\|alternar` el avatar del modo escritorio (atajo de Hyprland, lanzador) |
| `frases_voz.py` / `frases_escritorio.json` | Frases fijas del avatar de escritorio y su caché con voz (`cache_frases/`) |
| `rem_avatar_server.py` | Servidor HTTP `:18765` + WebSocket `:18766` para el avatar, más la orquestación de push-to-talk (`ptt_start`/`ptt_stop`). Ver "Modo overlay: push-to-talk" más abajo |
| `rem_avatar.html` | HTML y CSS del avatar (ventana y overlay). El script vive en `avatar/` |
| `avatar/` | Script del avatar partido en scripts clásicos que comparten ámbito global (núcleo 3D, clips, director, panel, overlay, WS). Ver `avatar/README.md` |
| `bench_chat.py` | REPL de depuración: si hay servidor lo usa como cliente WS, si no lo levanta él (standalone). Ver "Puntos de entrada" más abajo |
| `acciones.py` | Herramientas del modelo (tool calling nativo) + validación de rutas portada del viejo `Rem.py`. Ver "Acciones del sistema en rem_chat" más abajo |
| `personalidad.py` / `ejemplos_tono.py` | System prompt + contexto dinámico / turnos few-shot del tono. Ver "Ejemplos de tono (few-shot)" |
| `Animaciones/` | Clips `.vrma` del avatar — no van al repo, se descargan a mano. Ver `Animaciones/README.md` y "Animación de cuerpo con clips VRMA" más abajo |
| `chat_sesion.py` | `SesionChat` + `procesar_turno()` — estado de una conversación y el turno "en crudo" contra el LLM, compartido entre `bench_chat.py` y el panel/caja de chat de `rem_chat.py`. Ver "Panel de chat" más abajo |
| `tokens_contexto.py` | Recorte del historial para caber en `num_ctx` + contador de tokens exacto (CLI). Ver "Recorte del historial (num_ctx)" |
| `habla.py` | Pipeline de voz de salida de un turno (Piper -> timeline -> `enviar_audio()`), compartido entre `bench_chat.py` y `rem_chat.py`. Ver "Voz de Yoru (Piper)" |
| `lipsync.py` | Alineaciones fonema→audio de Piper → timeline de visemes. Ver "Lipsync desde las duraciones del propio modelo" |
| `stt/` | Capa de abstracción de voz de ENTRADA (STT): contrato + provider (`local.py` = faster-whisper). Ver "Modo overlay: push-to-talk" más abajo |
| `rem_ptt.py` | CLI del push-to-talk: `rem_ptt.py start\|stop` manda `ptt_start`/`ptt_stop` al servidor por WS — pensado para atarlo a una tecla mantenida en Hyprland |
| `llm/` | Capa de abstracción de LLM (contrato + providers). Ver "Capa de abstracción de LLM" más abajo |
| `config.py` | Módulo compartido: carga `.env` y lee `config.toml`. Lo usan `rem_chat.py`/`bench_chat.py`/`llm/`/`habla.py` |
| `rem_panel.py` / `rem_panel.html` | Panel de control: ventana GTK+WebKit aparte, cliente del servidor de `rem_chat.py`. Ver "Panel de control (`rem_panel.py`)" más abajo |
| `webview_comun.py` | Piezas GTK+WebKit compartidas por `rem_chat.py` y `rem_panel.py`: `crear_webview()`, `cargar_con_retry()`, `redirigir_salida_a_log()` |
| `preferencias.py` | Preferencias editables en vivo desde el panel de control, en `preferencias.json` por encima de `config.toml`. Ver "Preferencias del panel de control" más abajo |
| `catalogo_animaciones.py` | Genera/actualiza `Animaciones/catalogo.json`: mide cada `.vrma` y conserva lo curado. Ver "Catálogo de animaciones" |
| `config.toml` | Config no sensible versionada en git (a diferencia de `.env`, que tiene los secretos) — `[llm]`/`[llm.claude]`/`[tts]`/`[app]`/`[overlay]`/`[stt]` |
| `vendor/` | three.js / three-vrm servidos en local (espejo de esm.sh) para que el avatar cargue sin internet. Ver `vendor/README.md` |

## Capa de abstracción de LLM (`llm/`)
Contrato común para poder cambiar de backend (Ollama local, Claude) sin tocar a los
consumidores (`chat_sesion.procesar_turno()`). Proveedor por defecto: **Ollama** (`llm/local.py`);
**Claude** (`llm/claude.py`) como alternativa — ver `get_provider()` más abajo. (Groq existió como
fallback; se eliminó el 2026-11-04; el último commit que lo tiene es «Saca del repo modelos de terceros (RVC y rem.vrm) e ignóralos».)

- `llm/base.py`: tipos normalizados (`Message`, `ToolSpec`, `ToolCall`, `Chunk` = `TextDelta` |
  `ToolCallChunk` | `Done`) y el ABC `LLMProvider` con `stream_chat(system, messages, tools=None)
  -> AsyncIterator[Chunk]`. **El system prompt es un parámetro explícito, no un `Message` más en la
  lista**: Claude lo lleva como campo de nivel superior y los endpoints OpenAI-compatible como un
  mensaje del array — si se metiera en `messages`, cada provider tendría que extraerlo de ahí para
  dárselo a su API en el formato que le corresponde, y ese paso de ida y vuelta es justo donde se
  rompe el prompt caching (ver "Nada volátil en el system prompt" más arriba).
- `llm/_retry.py`: `reintentar_con_backoff()` — retry con backoff exponencial compartido por
  `claude.py` y `local.py`. Solo cubre conectar y obtener el stream (si la conexión se
  corta a mitad de la respuesta ya no reintenta: reintentar ahí rehace la respuesta desde cero y
  duplicaría texto que el consumidor ya recibió). Loguea tipo + `__cause__` de cada intento (no solo
  `str(e)`), y al agotar los reintentos lanza `RuntimeError(...) from ultimo_error` — la excepción
  original queda encadenada, no se pierde detrás de un mensaje genérico.
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
    GC lo recolecta (p. ej. un loop nuevo y descartable por turno, como el `_drenar_stream_llm()`
    del viejo `Rem.py`), esa Task se destruye a mitad de camino (`Task was destroyed but it is pending!`).
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
  `[llm].provider` en `config.toml` > `"ollama"` por defecto (100% local, sin API key; hoy
  `config.toml` también fija `"ollama"`). Lee `config.toml` a través de
  `config.leer_config_toml()` (ver más abajo). Si falta la API key del provider elegido
  (`ANTHROPIC_API_KEY` para Claude), **falla acá mismo con un `RuntimeError` explícito** en vez
  de dejar que reviente recién en la primera petición con un error de conexión genérico — mismo
  criterio que `ClaudeProvider` rechazando una `api_key` vacía en su propio
  `__init__` (`OllamaProvider` no tiene ese chequeo, no necesita key). Falla con `ValueError` claro
  si se pide un provider que no existe.
- `llm/sentence_splitter.py`: `dividir_en_oraciones()` consume un `AsyncIterator[Chunk]` y emite
  oraciones completas apenas se detecta su final (`. ! ?` seguido de espacio, descarta fragmentos
  < 3 chars). Maneja el caso de que una oración llegue partida entre dos chunks de red. Lo usa
  `chat_sesion.procesar_turno()` para encolar cada oración hacia la voz apenas está lista (ver
  "SentenceSplitter conectado" más abajo).

**Cliente perezoso por event loop (Claude y Ollama)**: ni `ClaudeProvider` ni `OllamaProvider` crean su
cliente HTTP (`AsyncAnthropic`/`httpx.AsyncClient`) en `__init__` — lo arman recién
en el primer uso real, y lo recrean si el event loop actual cambió respecto al de la última llamada
(`_obtener_cliente()`). Motivo: un cliente httpx async que llega a abrir una conexión real queda con
su pool interno atado al loop que estaba corriendo en ese momento; si el provider se usara como
singleton y se lo llamara desde un loop nuevo — p. ej. un loop descartable por turno, el patrón del
`_drenar_stream_llm()` del viejo `Rem.py` — reusar ese cliente revienta con `RuntimeError: Event loop is closed`.
Reproducido con `httpx.AsyncClient` puro (sin mocks): un request exitoso en un loop + el mismo
cliente reusado en otro loop distinto falla así — pero **solo si el primer request llegó a completarse
con éxito** (una conexión que nunca se estableció, p.ej. por un 401, no deja pool que reusar, así que
un test con una API key inválida no alcanza para reproducirlo).

**`config.py`** (módulo compartido, en la raíz, no en `llm/`): `cargar_dotenv()` (carga `.env` al
entorno vía `os.environ.setdefault`, tolera valores con `=` dentro gracias a `split("=", 1)` — las
API keys pueden llevarlo) y `leer_config_toml()` (parsea `config.toml` con `tomlkit`), más un
`leer_*()` por sección. Un solo lugar que lee `.env`/`config.toml` — `llm/__init__.py` también lo usa,
en vez de tener su propia lectura duplicada.

**Banco de pruebas (`bench_chat.py`)**: un REPL de depuración con dos modos alternables en caliente (`SesionChat.cambiar_modo()`, ver "bench.py
eliminado" más abajo): `chat <texto>` corre un turno de LLM (streaming), `voz on|off` encadena la
respuesta al pipeline de voz (`habla.py`), `state <estado>` / `open` controlan el avatar, `modo
ia|eco`, `reset`, `quit`. Cómo llega esos comandos al avatar depende de si detectó un servidor ya
corriendo — ver "Puntos de entrada" abajo.

## Modo eco (`llm/echo.py`) y `bench.py` eliminado
`EchoProvider` implementa el contrato de `LLMProvider` sin llamar a ningún modelo: busca el último
`Message` con `role="user"` en la lista (no asume que sea el último elemento, aunque en el uso normal
lo es) y lo emite tal cual como un único `TextDelta`, ignorando `system` y `tools` por completo, y
cierra con `Done(reason="stop")`. Sin estado, sin cliente HTTP, sin API key — nada que inicializar.
Registrado en el factory (`llm/__init__.py`) como provider `"echo"`, sin requerir configuración.
Sirve para que Rem repita con su voz lo que se escriba, sin IA de por medio: prueba TTS/lipsync/
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
TTS; `bench_chat.py` siempre pasa por `dividir_en_oraciones()`, así que un texto con varias
oraciones se parte en llamadas `_decir()` separadas — sin efecto perceptible con texto normal, solo
importa para probar la síntesis de una frase larga sin cortes.

## Personalidad: Kuroki Yoru (`personalidad.py`)
Desde 2026-11-04 el personaje es **Kuroki Yoru**: otaku hikikomori de 19 años, fría, seca y desganada,
que llama "sirviente" al usuario, se cree superior y en el fondo le tiene aprecio (amistad, cero
romance). Sin signos de exclamación, "…" para las pausas, jerga otaku/internet ocasional y la
muletilla まあ、どうでもいい. Reemplazó a la "amiga paisa" (voseo, jerga antioqueña). El prompt
conserva las reglas duras (longitud, honestidad —corrige lo falso con burla en la primera frase—, no
inventar, herramientas, cuándo hablar de tecnología, emoción: casi nunca etiqueta, [FELIZ] solo
excepcional) y está en tú, no en voseo. El tono sale de los 8 ejemplos de `ejemplos_tono.py` (turnos falsos; ningún mensaje de usuario cuenta
algo de la vida de Esteban, ver "Ejemplos de tono"). Desde 2026-11-05 el prompt incluye "Cómo se te nota
el aprecio" (ideas de las personalidades tsundere/bro de Nerumi, reescritas) y el modo serio se detecta
en código (ver "Modo serio y tope de oraciones"), con su propio ejemplo por categoría.
Antes del TTS, `chat_sesion._para_voz()` cambia "!"/"¡" por puntos, la muletilla japonesa por
"maa, dou demo íi" (Piper/espeak "es" no lee japonés; con "ii" leía el romano II, "dos", y una "í" sola
como "í acentuada") y "skill issue"/"npc(s)" por "skil íshiu"/"enpisí(s)". Medido con
`voz.phonemize()`; los WAV de las variantes probadas están en `~/Descargas/prueba-voz/`. El chat
muestra el texto tal cual.
Si se agrega o quita una tool, actualizar la regla "HERRAMIENTAS" del prompt.

## Configuración (.env en la raíz del proyecto)
```
ANTHROPIC_API_KEY=tu_api_key_de_anthropic
NOMBRE_USUARIO=Esteban
```
`ANTHROPIC_API_KEY` solo hace falta si `[llm].provider`/`REM_LLM_PROVIDER` es `"claude"`; con
`"ollama"` (el default) no hace falta ninguna key. `get_provider()` falla al arrancar con un mensaje
explícito si falta la key del provider elegido — ver "Capa de abstracción de LLM" más arriba.
La voz de salida no va en `.env`: es el modelo Piper de `config.toml` → `[tts]`.
Todas las variables tienen valores por defecto en el código; ninguna es obligatoria con Ollama.

## Nada volátil en el system prompt (para que el prompt caching funcione)
El caching de prompts en los proveedores de inferencia (Ollama y Claude) exige que el prefijo sea
idéntico byte a byte entre llamadas para reusar el cache — cualquier cambio en el system prompt
(fecha, hora, estado de la PC, etc.) rompe el cache en cada turno y obliga a pagar el prompt
completo siempre. Por eso:
- `construir_prompt_sistema()` (usado como mensaje `system`) contiene **solo** contenido estable:
  personalidad y reglas. La memoria larga va aparte, como mensaje después de los ejemplos de tono
  (ver "Ejemplos de tono (few-shot)").
- Todo lo volátil (fecha/hora) va en
  `construir_contexto_dinamico()`, que se antepone al **último mensaje del usuario** en cada turno
  (dentro de `chat_sesion.procesar_turno()`), nunca al system prompt. El estado de la PC ya no va en
  el contexto: es la herramienta de solo lectura `estado_pc` (ver "Acciones del sistema en rem_chat").
- Regla para futuros cambios: si algo cambia en cada turno (timestamps, métricas en vivo, conteos),
  no va en `construir_prompt_sistema()`.

## Ninguna llamada al LLM sin intervención del usuario
Requisito firme del proyecto: la API (Claude, o el provider que esté activo) solo se usa cuando el
usuario escribe o habla.
- No hay saludo generado al arrancar, ni recordatorios por timer. (El viejo `Rem.py` tenía los dos
  —`bienvenida()` con frases estáticas y `RECORDATORIOS` apagados por defecto— más
  `extraer_memoria_importante()` cada 8 mensajes; se fueron con él. Si se porta la extracción de
  memoria, que siga siendo consecuencia de turnos del usuario, nunca de un timer.)
- La precarga de Ollama al arrancar (ver "Precarga de Ollama") no es una llamada a una API de pago:
  es el modelo local evaluando el prefijo fijo, sin generar respuesta para nadie.

## Archivos de datos (creados en runtime, ignorados por git)
| Archivo | Contenido |
|---------|-----------|
| `memoria_larga.json` | Recuerdos a largo plazo (hechos, emociones, eventos, preferencias). Hoy solo se lee: nada la actualiza desde que se fue `Rem.py` |
| `memoria_sistema.json` | Archivos y carpetas conocidas del sistema |
| `preferencias.json` | Lo cambiado desde el panel de control (solo lo que difiere de `config.toml`) |

## Archivos pesados (ignorados por git, descargar manualmente)
| Archivo | Tamaño | Fuente |
|---------|--------|--------|
| Modelo de voz Piper (`.onnx` + `.onnx.json`) | — | Pon tu propio modelo Piper en la ruta de `[tts].modelo` de `config.toml`. Nunca se versiona |
| `rmvpe.pt`, `hubert_base.pt`, `models/Rem_600e_6600s/` | 173 + 181 + 66 MB | **Ya no se usan** (eran de RVC); siguen en disco |
| `rem.vrm` | ~23 MB | **No va en el repo**: su meta VRM (VRoid Hub, autor Skadi) dice `redistribution=disallow`. Colocar a mano |
| `Animaciones/VRMA_MotionPack/*.vrma` | — | `tk256ailab/vrm-viewer` (MIT) + pack VRoid Project — ver `Animaciones/README.md` |

## Arquitectura de concurrencia

```
rem_chat.py — hilo principal (Gtk.main())
├── habla.precargar_tts (daemon thread, inicio) — carga + calienta la voz Piper en background
├── WebView (WebKit2)                    — rem_avatar.html?modo=ventana
└── rem_avatar_server.iniciar_servidor_avatar():
      ├── AvatarHTTP (daemon thread)     — sirve archivos en :18765
      └── AvatarWS   (daemon thread)     — asyncio loop, WebSocket bidireccional en :18766
            ├── _procesar_mensaje_chat() — turno de LLM (create_task), emite chat_delta/done
            └── _chat_worker_habla_task  — cola de voz del panel (Piper→enviar_audio)
```

## Seguridad de acciones del sistema
Lo que queda en el árbol es lo que usan las tools de `acciones.py` (ver "Acciones del sistema en
rem_chat" más abajo); el ejecutor completo del viejo `Rem.py` (`ejecutar_comando` con whitelist y
`_args_permitidos()`, `_git_permitido()`/`_systemctl_permitido()`, mover/copiar/eliminar con
`_mover_a_papelera()`, `descargar_archivo()` saneado, el diálogo `confirmar_accion()`) **se eliminó
con él** — sigue en el historial de git (último commit que lo tiene: 2026-09-22, «feat: portar 4 herramientas del ejecutor de acciones a rem_chat (tool calling nativo)»), con su auditoría.
Si se porta algo de ahí, portar también su validación, no solo la acción.

- `_ruta_segura(ruta, permitir_raiz=False)` (`acciones.py`): valida que la ruta esté dentro de
  `$HOME`, que no sea `$HOME` completo (salvo `permitir_raiz=True`), que no caiga en dirs del sistema
  (`/etc`, `/root`, ...) ni en la lista negra de subrutas sensibles (`_RUTAS_PROHIBIDAS_HOME`:
  `~/.ssh`, `~/.gnupg`, `~/.config`, `~/.local/share/keyrings`, `~/.mozilla`, y el `.env`/`.git` del
  propio proyecto, calculados desde su ubicación real). `buscar_archivos` la usa con
  `permitir_raiz=True` (solo lectura — `glob.glob`, nunca escribe).
- **`buscar_archivos` filtra también los resultados del `glob.glob()`, no solo la carpeta base**
  (`_filtrar_rutas_seguras()`): `"**"` recursivo encuentra coincidencias dentro de `~/.ssh`/
  `~/.config`/etc. igual si están debajo de la base validada. Como defensa en profundidad,
  `_registrar_archivo_sistema()` (el único lugar que escribe en `memoria_sistema`) rechaza una ruta
  que no pase `_ruta_segura()`, y `_buscar_en_memoria_sistema()` ignora una entrada guardada que no
  pase el chequeo.
- `apagar_pc` pasa por confirmación (`TOOLS_QUE_CONFIRMAN`) y no se ofrece en overlay
  (`TOOLS_EXCLUIDAS_OVERLAY`): ahí no hay forma de confirmar.
- CORS restringido a `localhost` en `rem_avatar_server.py`.
- **El WS valida el `Origin`** (`WS_ORIGENES_PERMITIDOS`, vía `websockets.serve(origins=...)`): un
  WebSocket no tiene CORS, así que sin esto cualquier página abierta en el navegador podía conectarse
  a `ws://localhost:18766` y mandar `chat_message` (que dispara tools). Solo se aceptan
  `http://localhost:18765`/`http://127.0.0.1:18765` (las páginas servidas por nuestro HTTP) y la
  ausencia de `Origin` (clientes Python: `bench_chat.py`, `rem_ptt.py`). Lo demás recibe un 403 en
  el handshake (queda un traceback `InvalidOrigin` de `websockets` en el log, a propósito visible).
  Verificado: los 3 aceptados conectan; `https://evil.example`, `http://localhost:8080`, `null` y
  `http://localhost:18765.evil.example` dan 403; la ventana real y `rem_ptt.py` siguen funcionando.
  No protege de un proceso local (puede falsificar la cabecera), que ya tiene el acceso del usuario.

Si en el futuro se agrega una tool que reciba una ruta del modelo, o que devuelva una lista de rutas
encontradas, ese es el lugar a revisar: pasarla (o filtrarla) por `_ruta_segura()` antes de usarla o
devolverla.

**`memoria_sistema.json` ya no se trackea en git** (`git rm --cached`, el `.gitignore` ya tenía
`memoria_*.json` pero no aplica retroactivamente a un archivo agregado antes de esa regla) — el
archivo local sigue existiendo y la app lo sigue leyendo/escribiendo igual, solo que sus cambios ya
no terminan en el historial del repo público. Se verificó todo el historial de git: el archivo
estuvo vacío en su único commit, así que no hizo falta reescribir historia. Se aprovechó para sacar
la clave `"programas"` del JSON, que no existe en el schema que lee `personalidad.cargar_memoria_sistema()`
(solo `archivos`/`carpetas`) — residuo de un formato viejo.

## Puntos de entrada

```bash
venv/bin/python rem_chat.py                    # LA APLICACIÓN — modo ventana (default de config.toml)
venv/bin/python rem_chat.py --modo overlay     # LA APLICACIÓN — modo overlay (ver "Modo overlay" más abajo)
venv/bin/python rem_chat.py --modo escritorio  # LA APLICACIÓN — avatar arrastrable + chat aparte (ver "Modo escritorio")
venv/bin/python bench_chat.py                  # REPL de depuración (ver abajo)
venv/bin/python rem_panel.py                   # panel de control (con Rem ya abierto)
```

- **`rem_chat.py`** es la aplicación: llama a `rem_avatar_server.iniciar_servidor_avatar(permitir_reuso=False)`
  (levanta HTTP `:18765` + WS `:18766`) y abre UNA presentación — `--modo ventana` o `--modo overlay`
  (default: `config.toml` -> `[app].modo`), nunca las dos a la vez. A diferencia de `bench_chat.py`,
  si los puertos ya están ocupados **no** los reusa: sale con un error claro (`ServidorOcupadoError`)
  en vez de abrir una segunda presentación pegada a un servidor ajeno — ver "Modo overlay" más abajo,
  "Instancia única".
- **`bench_chat.py`** se adapta a si ya hay un servidor:
  - **modo cliente** (hay servidor): se conecta como cliente WebSocket y manda `state`/`chat`/`modo`/
    `voz`/`reset` por ahí. El servidor los procesa y la ventana los ve. El turno de LLM lo corre el
    servidor (llegan `chat_delta`/`chat_done` de vuelta y se imprimen).
  - **modo standalone** (no hay servidor): lo levanta él mismo y corre autocontenido (turno de LLM
    en proceso, worker de voz propio) — como antes.
  - **nunca falla en silencio**: si un `state` no tiene a quién llegar (avatar cerrado), lo dice en
    consola; en modo cliente, si la conexión WS se cae lo dice también. En el servidor,
    `enviar_estado()`/`_broadcast_ws()` devuelven el nº de clientes y logean un aviso (con
    antirrebote) cuando es 0.

**El intérprete correcto es siempre `venv/bin/python` (Python 3.10.14, con piper/faster-whisper/PyGObject
instalados) — nunca el `python`/`python3` del sistema.** Esto incluye a `rem_chat.py`: el `python3`
del sistema no tiene ningún rol especial en el proyecto (ver "El venv sí puede tener GTK" más abajo)
— PyGObject/pycairo están en `requirements.txt` igual que el resto.

## Problemas conocidos
- **La boca no se mueve / `lipsync SIN alineación` en el log**: falta el paquete `onnx` (extra
  `piper-tts[alignment]`), que parchea el modelo en memoria para exponer las duraciones. Sin él la
  voz suena igual, pero el timeline cae al reparto parejo.
- **La ventana del avatar no aparece**: verificar `webkit2gtk-4.1` instalado; correr `venv/bin/python rem_chat.py` en una terminal y mirar `rem_chat.log` (consola del frontend volcada ahí). Inspector remoto en `http://127.0.0.1:9222`.
- **Error de audio**: verificar que PipeWire esté corriendo (`systemctl --user status pipewire`).

## Voz de Yoru (Piper): sin edge-tts ni RVC, 100% local

La voz de salida es **Piper** (`piper-tts==1.8.0`). El modelo no viene con el repo: pon tu propio
modelo Piper (`.onnx` + `.onnx.json`) en la ruta de `[tts].modelo` de `config.toml`. Los modelos de
voz no se versionan nunca (`.gitignore` + `hooks/`). edge-tts (red, Microsoft) y RVC (`infer-rvc-python` + fairseq + torch, GPU) se eliminaron
por completo. El avatar sigue siendo el de Rem. Ruta del modelo: `config.toml` → `[tts].modelo`
(`config.leer_modelo_tts()`). **Parámetros de síntesis = los del `.onnx.json` tal cual**
(`noise_scale` 0,667, `length_scale` 1,0, `noise_w` 0,8, sin volumen): no tocarlos.

- **`habla.py`**: `PiperVoice` se carga UNA vez por proceso (`_voz`) y se reusa; síntesis en CPU
  (`onnxruntime`, `CPUExecutionProvider`). `sintetizar(texto)` → `(audio int16, sample_rate,
  timeline, con_alineacion)`; el sample rate sale del `.onnx.json` (vía `AudioChunk.sample_rate`,
  22050 Hz con este modelo), nunca fijo. `decir()` la corre en `asyncio.to_thread` y escribe un WAV
  PCM16 que va por `enviar_audio()` igual que antes. `precargar_tts()` (rem_chat.py siempre,
  bench_chat.py standalone) carga + calienta con "Hola." en un hilo de fondo (~1,1 s + ~0,1 s).
- **`_voz_lock` se quedó, a propósito** (no es el lock de RVC): serializa la carga (precarga vs.
  primer turno) y cada síntesis, porque el fonemizador de Piper (espeak-ng vía
  `piper/espeakbridge.so`) es estado C global del proceso y puede haber dos workers (REPL y panel)
  sintetizando a la vez. Cada síntesis dura ~0,03-0,6 s: serializar no se nota.
- **Ya no hay sección `voz` en `preferencias.py`** (era `voz`/`rate` de edge-tts) ni
  `config.leer_config_voz()`/`leer_dispositivo_rvc()`. La pestaña Voz del panel quedó con
  `seccion: null` (sin opciones, como Personalidad). Un `preferencias.json` viejo con `voz` se
  ignora con un aviso (sección desconocida), sin romper nada.

### Lipsync desde las duraciones del propio modelo (no estimadas)

**Investigado antes de diseñar: piper-tts 1.8 SÍ expone alineaciones fonema→audio.**
`PiperVoice.synthesize(texto, include_alignments=True)` devuelve por `AudioChunk` (uno por oración
que detecta espeak) `phoneme_alignments: [PhonemeAlignment(phoneme, phoneme_ids, num_samples)]`. Sale
de la salida de duraciones de VITS (el tensor `w_ceil`, nodo `Ceil`). **Este modelo no la trae de
fábrica** (solo la salida `output`); `PiperVoice.load(..., include_alignments=True)` la agrega
parcheando el grafo **en memoria** con el paquete `onnx` (extra `piper-tts[alignment]`) — el `.onnx`
en disco no se toca (el SHA-256 sigue igual al de `manifest.json`). Costo: la carga pasa de ~0,5 a
~0,75 s. Verificado: la suma de `num_samples` de un chunk **coincide exacta** con la longitud de su
audio, y en 30 oraciones reales de la prueba sin red hubo 0 chunks sin alineación.

`lipsync.construir_timeline(chunks)` (puro, no carga Piper) convierte esas alineaciones al timeline
de siempre (`{t, viseme, apertura, viseme_vrm, peso_vrm}`, el frontend no cambió):
- IPA de espeak-ng → fonema interno (`_IPA_A_FONEMA`): `ð` (d suave) y `θ` → `th` (nuevo, viseme
  `vrc.v_th`, que los dos perfiles de modelo ya declaraban pero el mapeo grafémico nunca emitía);
  `β`→b, `ɣ`→g, `ɾ`→r, `ʝ`/`ʎ`→y, `ʃ`→ch, semivocales `j`/`w`→i/u. Las africadas llegan partidas
  (`tʃ` = `t`,`ʃ`).
- Las marcas de acento/longitud (`ˈ ˌ ː`) tienen duración propia en el modelo pero no son una boca:
  su tiempo se le da al fonema siguiente (el evento arranca donde arranca el acento).
- `^`/`$` (BOS/EOS) y la puntuación → silencio. Un espacio solo es silencio si dura más de
  `ESPACIO_PAUSA_S` (0,12 s); si no, es habla continua y se mantiene el fonema anterior. Silencios
  seguidos se colapsan.
- Respaldo si un chunk vuelve sin alineación (Piper la descarta si no cuadra, o falta `onnx`): los
  fonemas IPA de ese chunk repartidos parejo en su duración real; `decir()` lo loguea
  (`lipsync SIN alineación`). El viejo conversor grafema→fonema (`texto_a_fonemas()`) se eliminó: el
  IPA del propio Piper es mejor dato.
- Verificado contra la energía real del WAV (RMS por ventana de 20 ms, 3 frases): tramos de vocal
  0,14-0,23, consonante ~0,14, **silencio 0,003-0,067** — el timeline cae donde está el sonido. Y
  con capturas de la cara durante una frase: la boca abre/cierra/redondea cuadro a cuadro.
- `venv/bin/python lipsync.py ["frase"]` sintetiza e imprime fonemas, alineación y timeline.
- Ojo: `espeak.voice = "es"` del modelo es español peninsular (sale `θ` para c/z). Es lo que trae el
  modelo; no se tocó.

### Sin internet: módulos JS vendorizados y llamadas de red

- **`rem_avatar.html` ya no importa de esm.sh**: `vendor/esm/` es un espejo exacto de los bundles
  que esm.sh servía (regenerable con `vendor/espejo_esm.py`, ver `vendor/README.md`), servido por el
  HTTP de `rem_avatar_server.py` (sirve todo `BASE_DIR`; `.mjs`/`.js` salen como `text/javascript`).
- **Hallazgo al vendorizar: la página carga DOS copias de three.** `three@0.169.0` (página +
  `GLTFLoader`) y `three@0.164.1`, que es lo que esm.sh le resolvía al peer `^0.164.1` de
  `@pixiv/three-vrm@2.1.3` y `@pixiv/three-vrm-animation@2.1.3` (`@pixiv/three-vrm@2` sin fijar
  resolvía a 2.1.3). three lo avisa en consola (`Multiple instances of Three.js being imported`).
  Así funcionaba antes y se dejó igual; unificarlas es un cambio aparte, que habría que probar.
- **Llamadas de red en tiempo de ejecución, revisadas** (Python + HTML):
  - Ollama (`127.0.0.1:11434`) — local.
  - Claude (`llm/claude.py`) — solo si se elige como provider; con `ollama` + `stt local` no se
    toca. (Groq también estaba en esta lista; se eliminó después.)
  - **faster-whisper**: `WhisperModel("small")` pasaba por `huggingface_hub.snapshot_download`, que
    **consulta el Hub en cada arranque** aunque el modelo esté en caché (y sin red espera a que
    falle). Arreglado en `stt/local.py`: primero `local_files_only=True`; solo si el modelo no está
    se descarga (una vez, con aviso en el log). En esta máquina no estaba descargado: se bajó una vez
    (~150 s) y desde ahí carga en ~0,6-1 s sin red.
  - `buscar_en_navegador` (tool) y `bench_chat.py --open` abren el navegador — acción del usuario.
  - `bench_chat.py` sondea `http://localhost:18765` — local.
  - Nada más: los bundles vendorizados solo contienen URLs como texto (licencias, el namespace XHTML).

### Prueba sin red y mediciones (2026-11-04, con corriente, GPU P0)

**Sin red de verdad**: no se apagó el wifi (la sesión de Claude Code que hizo la prueba lo
necesita); en su lugar `rem_chat.py --modo ventana` corrió dentro de `unshare -rn` (namespace de red
con SOLO loopback: `esm.sh` no resuelve, `curl` falla), con Ollama alcanzable por un puente `socat`
sobre un socket unix (Wayland/PipeWire también son sockets unix). Resultado: ventana abierta, VRM y
clips cargados desde `vendor/`, WS conectado, Whisper cargado de caché, modo eco y modo ia (Ollama)
hablando con la voz de Yoru y la boca moviéndose.

- **Síntesis por oración** (30 oraciones): 0,028-0,623 s, media 0,149 s; **factor 0,033-0,135×
  tiempo real** (media 0,059×). Ejemplos: 0,68 s de audio en 0,028 s; 6,99 s en 0,62 s.
- **Primer audio — eco**: 0,06-0,18 s desde el mensaje. **ia**: 0,72-3,06 s, dominado por cuánto
  tarda el LLM en completar la primera oración (3,06 s = una primera oración de 130 caracteres), no
  por Piper.
- **Ollama** (`num_gpu = 24` sin tocar, prompt ~2600-3000 tok): **15,2-18,1 tok/s** (8 turnos;
  media ~16,2). Más bajo que los 20,7 de la tabla de calibración, que se midió con 100 tokens y
  `num_ctx` sin llenar.
- **VRAM** (`nvidia-smi`, muestreo cada 0,5 s durante los turnos): **2322 MiB usados de 4096**, de
  los que 2312 MiB son `llama-server` de Ollama. Piper, Whisper y WebKit: 0 en la NVIDIA. Quedan
  ~1770 MiB libres: hay margen para subir `num_gpu` (32 eran ~2994 MiB), pero **no se tocó**
  todavía.
- venv: 6,5 GB → 812 MB tras desinstalar lo de RVC.

### Qué se eliminó

- Código: `cargar_rvc`/`_obtener_rvc`/`_convertir_rvc`/`precargar_rvc`/`_rvc_lock`, la conversión
  mp3→wav 16 kHz, `lipsync.sintetizar_con_timings()` (edge-tts) y `texto_a_fonemas()`, `test_voz.py`
  (A/B edge-tts vs RVC), `apply_shim.py` y `fairseq_shim/`, `bench_chat.py --no-rvc`, `[rvc]` y
  `[voz]` de `config.toml`, la sección `voz` de preferencias.
- Dependencias (89, en `requirements.txt` y desinstaladas del venv): edge-tts, infer-rvc-python,
  fairseq, torch/torchaudio/torchcrepe/triton + los 12 `nvidia-*-cu12`, faiss-cpu, librosa, gradio,
  scipy, etc. — todo lo que solo colgaba de esas. **torch no lo usaba nada más**: faster-whisper va
  sobre ctranslate2 + onnxruntime. Entraron `piper-tts`, `onnx` (+ `ml-dtypes`, `pathvalidate`).
  Quedan en el venv, fuera de `requirements.txt`, restos del viejo `Rem.py` (`pyautogui`,
  `opencv-python`, `speechrecognition`, `pyaudio`...) que nada importa — `pip check` se queja de
  `pyscreeze` (sin `pillow`); no se tocaron.
- **Archivos que quedan en disco sin uso** (no se borraron, ~420 MB): `models/Rem_600e_6600s/`
  66 MB, `hubert_base.pt` 181 MB, `rmvpe.pt` 173 MB.

**Historia (RVC/edge-tts)**: lo que había —A/B de voces de edge-tts (`es-VE-PaolaNeural` `-8%`),
la `rr` imperfecta del modelo RVC japonés, la calibración de `num_gpu` para hacerle sitio a RVC, el
fix de `generate_from_cache()`, el lock de RVC y su precarga— está en git hasta el commit del 2026-10-22 «feat: pestaña Animaciones del panel de control»
(CLAUDE.md, `habla.py`, `test_voz.py`). El `SentenceSplitter` sigue igual: cada oración se encola
apenas está completa y un worker por consumidor la sintetiza mientras la anterior suena.

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
(`click`/`keydown`/`touchstart`) para desbloquear el autoplay. **No servía**: el audio de Rem
empieza a sonar sin que el usuario haya interactuado con la página (primera respuesta apenas se abre
la ventana), así que el `AudioContext` quedaba `'suspended'`.
`WebKitSettings.set_media_playback_requires_user_gesture(False)` **no resolvía esto**: esa política
de WebKit2 solo aplica a elementos de medios (`<audio>`/`<video>`), no a la Web Audio API.

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

## Regresión repetida de la política de autoplay (WebKitGTK 2.52)
El bug: `HTMLMediaElement.play()` se rechaza con `NotAllowedError` y no hay audio. Pasó dos veces
por reordenar/agregar líneas al bloque de configuración del WebView cuando el patrón era
`webview = WebKit2.WebView(); settings = webview.get_settings()` y recién ahí los `set_*` — cualquier
código nuevo por delante lo rompía. **Parte del fix**: armar `WebKit2.Settings()` en un objeto
APARTE, completo, ANTES de crear el WebView.

**Pero eso solo no alcanzaba.** `WebKitSettings:media-playback-requires-user-gesture` no es lo único
que controla esto en 2.52: hay un mecanismo separado y más nuevo, `WebKitWebsitePolicies` con la
propiedad `autoplay` (`WebKitAutoplayPolicy`: `ALLOW` / `ALLOW_WITHOUT_SOUND` / `DENY`) — confirmado
con `list_properties()` que el nombre real es `"autoplay"`, no `"autoplay-policy"`. Es el que de
verdad decide si `play()` se rechaza.

`WebsitePolicies` es una propiedad de **construcción** del `WebView` (`website-policies`, junto a
`settings`), no algo que se pueda mutar después — por eso `rem_chat.py` construye los tres objetos
(`Settings`, `WebsitePolicies`, `WebView`) en ese orden estricto, con
`WebView(settings=settings, website_policies=policies)`:

```python
policies = WebKit2.WebsitePolicies(autoplay=WebKit2.AutoplayPolicy.ALLOW)
webview = WebKit2.WebView(settings=settings, website_policies=policies)
```

Verificado en vivo: sin `WebsitePolicies`, `[Lipsync] play() rechazado ... NotAllowedError`; con
`WebsitePolicies(autoplay=ALLOW)`, `[Lipsync] play() resuelto`. Se mantiene también
`media-playback-requires-user-gesture(False)` en `Settings` (por si algún otro camino lo consulta),
pero **no alcanza solo** — los dos mecanismos son independientes y hace falta el segundo.

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

## Layer surface acotada (histórico — de `rem_overlay.py`, el archivo eliminado)
Cuando existía `rem_overlay.py` (proceso aparte, eliminado — ver "Ventana de escritorio" más
arriba), su layer surface se anclaba solo a `RIGHT`+`BOTTOM` con tamaño fijo (no a los 4 bordes)
para no estirar un canvas WebGL transparente del tamaño del monitor entero renderizando a 60fps
sobre todo el escritorio. Eso trajo dos regresiones que se arreglaron en su momento (click-through
que no sobrevivía a la reasignación de superficie; `_ajustarAnclasPorAspect()` colapsando `anchorX`
a 0,5 en superficies verticales). El primer bug (click-through que no sobrevive a la reasignación
de superficie) SÍ reapareció, con otra forma, en el modo overlay nuevo (ver "Modo overlay:
click-through y la caja de texto" más abajo — ahí se documenta el fix real, `queue_draw()` tras
`input_shape_combine_region()`). `_ajustarAnclasPorAspect()` en sí no volvió: el modo overlay nuevo
no tiene ancho/alto por modo que colapsar, solo el encuadre de medio cuerpo de `CONFIG.overlay`.

## Conflicto de puertos: un solo servidor entre varios procesos
`rem_avatar_server.iniciar_servidor_avatar()` levanta HTTP (`:18765`) + WS (`:18766`) **o** detecta
que ya están corriendo (`_puerto_activo("127.0.0.1", 18765)`) y los reusa — no intenta un bind nuevo
que competiría por el puerto. Lo llaman `rem_chat.py` (siempre) y `bench_chat.py` en modo standalone.
`bench_chat.py` en modo cliente ni siquiera lo llama: se conecta como cliente WS al servidor que ya
esté.

**Bug latente que quedó arreglado en el camino**: `_iniciar_ws()` llamaba a `_ws_ready.set()`
**antes** de `websockets.serve(...)`. Si el puerto `:18766` ya estaba ocupado, `serve()` lanzaba
dentro del hilo daemon `AvatarWS` — que muere en silencio — pero `_ws_ready` ya estaba en `True`, así
que el llamador creía que el WS de ESTE proceso había levantado cuando no. Ahora `_ws_ready.set()` va
**después** del `serve()` exitoso; si falla, la excepción queda en `_ws_bind_error` y `_ws_ready` sin
activar. Y `iniciar_servidor_avatar()` chequea `_puerto_activo()` antes de siquiera intentar el bind,
así que en la práctica ese camino casi no se toca.

## Crash interno del Network Process de WebKit
Reportado como "la ventana del avatar a veces no aparece". En `rem_chat.log` aparece:

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

**Reproducido de forma consistente** en su momento (dos corridas limpias seguidas). Se revisó lo
obvio (procesos WebKit colgados, disco, RAM, `journalctl`/`dmesg`) sin causa de recursos. Posible
correlación con la sesión de Hyprland degradada tras uso intensivo — no confirmado. La causa raíz es
un bug interno de WebKit; si vuelve a pasar, lo primero a probar es reiniciar la sesión de Hyprland.

### Arreglo: reintento con espera exponencial en la carga del VRM
La causa raíz sigue siendo un bug de WebKit, pero que el avatar quede invisible el resto de la
sesión por un crash transitorio sí era evitable — igual que el WebSocket ya se reconecta solo.
`_cargarVRM(intento)` en `rem_avatar.html` envuelve el `loader.load()` original: si el callback de
error dispara, loguea `[VRM] error (intento N/5): ...` y reintenta con `setTimeout` tras
`min(500 * 2**intento, 5000)` ms (mismo patrón que el retry de `load-failed` del WebView en
`rem_chat.py`); al agotar los 5 intentos se rinde en vez de reintentar para siempre.

**Verificado en vivo, tres escenarios** (cache de WebKit limpiada entre corridas en
`~/.cache/rem_chat.py/WebKitCache` para no servir una copia vieja de `rem_avatar.html` — la cache en
disco de WebKit2GTK persiste entre lanzamientos y puede enmascarar cambios recién hechos):
1. Carga normal (sin fallas): sin regresión, el avatar carga igual que antes.
2. Falla transitoria real (se renombró `rem.vrm` para forzar un 404, y se restauró a los ~5s,
   a mitad de la secuencia de reintentos): intento 1 falla y loguea "reintentando en 1000ms...";
   para cuando dispara el reintento el archivo ya está de vuelta, y la carga siguiente
   **se completa con éxito** (`[VRM] OK | expressions: ...`) — el escenario real que motivó el
   pedido.
3. Falla persistente (archivo ausente durante toda la ventana de prueba): se ven los 5 intentos
   con backoff creciente (1000, 2000, 4000, 5000, y el quinto ya sin más espera) y el mensaje final
   de rendición — confirma que no reintenta indefinidamente.

## Ventana de escritorio (`rem_chat.py`)
`rem_chat.py` es GTK3 + WebKit2 y tiene DOS presentaciones (`--modo ventana|overlay`, nunca las dos
a la vez — ver "Modo overlay" más abajo para el segundo). En modo ventana: ventana normal decorada,
opaca, con foco de teclado, título "Rem", 1100×620 redimensionable. Levanta el servidor del avatar
(`rem_avatar_server.iniciar_servidor_avatar(permitir_reuso=False)`) y carga
`rem_avatar.html?modo=ventana` en el WebView. **Es la aplicación** en los dos modos — un solo
proceso, un solo servidor, mismo pipeline de voz y LLM.

**Historia: el overlay se eliminó y después volvió.** `rem_overlay.py` (layer surface
click-through con `gtk-layer-shell`, proceso APARTE lanzado por `rem_avatar_server._lanzar_overlay()`)
se eliminó por completo en su momento — la ventana decorada lo sustituyó. El modo overlay actual
**no es una resurrección de ese archivo**: es `--modo overlay` DENTRO de `rem_chat.py` (mismo
proceso que la ventana, mismo servidor), reconstruido desde cero reusando lo que `rem_overlay.py`
ya tenía bien resuelto (recuperado del historial de git: `WebsitePolicies(autoplay=ALLOW)`, el
volcado de consola con `os.dup2`, el inspector remoto, el retry exponencial de carga) — ver "Modo
overlay" más abajo para el diseño nuevo (click-through parcial con una caja de texto interactiva,
algo que `rem_overlay.py` nunca tuvo, y push-to-talk).

**El venv sí puede tener GTK.** `pip install pygobject pycairo` en el venv compila sin problema
contra las libs GTK3/WebKit2GTK-4.1 ya instaladas en el sistema (Arch no separa paquetes `-dev`).
`pygobject`/`pycairo` están en `requirements.txt`. El `python3` del sistema no tiene ningún rol
especial en el proyecto.

**Log propio (`rem_chat.log`) — `os.dup2`, no `sys.stdout = archivo`.** WebKit2 escribe su volcado
de consola (`set_enable_write_console_messages_to_stdout`) directo al file descriptor 1 nativo del
proceso, sin pasar por el objeto `sys.stdout` de Python — reasignar solo ese objeto captura los
`print()` propios pero deja afuera justo el volcado de consola. Se arregla con
`os.dup2(log_file.fileno(), sys.stdout.fileno())` (y stderr), y `reconfigure(line_buffering=True)`
antes, para que cada línea llegue al toque. Los `print()` de arranque (dónde quedó el log, el
inspector) salen ANTES del `os.dup2`, a la terminal real.

**Caché HTTP**: el servidor manda `Cache-Control: no-cache` en todo (`_LocalHandler.end_headers`).
Antes solo mandaba `Last-Modified` y WebKit cacheaba por heurística en su caché en disco
(`~/.cache/rem_chat.py/WebKitCache`, sobrevive entre arranques): tras editar `rem_avatar.html` la
ventana seguía sirviendo la versión vieja (pasó al conectar el catálogo de animaciones). Con
`no-cache` revalida siempre y un archivo sin cambios vuelve como 304, sin bajarse. Una entrada ya
cacheada SIN esa cabecera no se revalida hasta caducar: si vuelve a pasar con una caché vieja, vaciar
esa carpeta una vez.

**Inspector remoto**: `WEBKIT_INSPECTOR_SERVER=127.0.0.1:9222` (fijado antes de que WebKit2 se
inicialice) — abrir `http://127.0.0.1:9222` en un navegador normal para DevTools.

**Tiling de Hyprland ignora `set_default_size()`** — no es un bug de `rem_chat.py`, es la política
por defecto de un WM tiling: sin una `windowrulev2` para floatear la clase `rem_chat.py`, Hyprland
igual tiling-ea la ventana al tile que le toque en vez de respetar 1100×620. La escena ya lo tolera
bien (el listener de `resize` recalcula el encuadre solo, probado en vivo con la ventana en
~1808×1018), pero si se quiere el tamaño real pedido hace falta algo como
`windowrulev2 = float, class:^(rem_chat.py)$` en la config de Hyprland — eso es decisión/config del
usuario, no algo para forzar desde el código Python.

## Suelo de cuadrícula synthwave y fin de la caminata
`crearSueloSynthwave()` arma un `THREE.GridHelper` (líneas cian,
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
del Network Process de WebKit (ver "Crash interno del Network Process de WebKit" más arriba, no relacionados).

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

## Panel de chat en la ventana de escritorio
`rem_chat.py` ya tenía la ventana y la escena 3D; faltaba el chat en sí. Se agregó como
HTML/CSS/JS vanilla dentro de `rem_avatar.html` (nada de frameworks ni dependencias externas,
como pide el proyecto) — ocupa la mitad derecha de la ventana, opaca, encima del canvas.

**Por qué el canvas se deja a tamaño completo en vez de reducirlo a la mitad izquierda**: se
evaluaron dos diseños — (a) canvas a ancho completo con el panel como `<div>` opaco encima
(`position:fixed; right:0; width:50%`), o (b) redimensionar de verdad el renderer/cámara a la
mitad izquierda. Se eligió (a): más simple, y sin cambios a `recalcularEncuadre()`/el listener de
`resize`, ya probados. El costo (renderizar píxeles que quedan tapados por el panel) es
insignificante para esta escena (una malla + una cuadrícula, sin post-procesado) — no es
comparable al problema de rendimiento que en su momento motivó acotar la layer surface del overlay (ver
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
sincronizados sin necesidad de audio real — este panel es solo texto, no pasa por TTS/lipsync
en absoluto (el pipeline de voz no se tocó).

## Paleta de comandos "/" en el panel de chat

Comandos escritos en el input del panel que se resuelven **enteros en el frontend**: nunca salen por
el WebSocket, no generan `chat_message` ni turno del LLM. Motivo de diseño: el registro de clips solo
lo resuelve `rem_avatar.html` (con `Animaciones/catalogo.json`), así que el backend no tiene nada que
aportar. Todo vive en `crearPanelChat()`.

**`COMANDOS`**: `{ animaciones: {descripcion, listar(), ejecutar(arg)} }`. `listar()` es opcional y es
lo que le da a la paleta un **segundo nivel**. Un solo argumento posicional a propósito — no hay
parser genérico de flags. La estructura queda lista para sumar `modo`/`voz`/`reset` después.

**Apertura**: solo si el texto empieza por `/` **como primer carácter** — `a/b` o `hola /animaciones`
no abren nada (`parsearEntrada()` devuelve `null`). Filtra en vivo con lo que se siga escribiendo.

**Dos niveles**: `/` lista los comandos; al elegir `/animaciones` el input queda en `"/animaciones "`
y la paleta pasa a listar los clips con estado `'ok'` **por su etiqueta**; al elegir uno se ejecuta y
el input se limpia.

**Teclado**: `ArrowUp`/`ArrowDown` navegan, `Enter`/`Tab` seleccionan, `Escape` cierra, click también
(vía `mousedown` + `preventDefault`, para no perder el foco del input entre niveles). **La paleta se
atiende al principio del MISMO listener de `keydown` que el envío** — no en un listener aparte: así el
`preventDefault()` de `Enter` llega seguro antes de `enviarMensaje()` sin depender del orden en que se
registraron los handlers. Con la paleta abierta `Enter` **nunca** envía, ni siquiera sin coincidencias
(si no, un `/anim` a medio escribir se le mandaría al LLM).

**CSS**: `#chat-paleta` es `position:absolute; bottom:100%` dentro de `#chat-inputbar`, que por eso
pasó a `position:relative` — queda siempre dentro del panel de chat. Con los 17 clips de entonces medía 240px de
alto visible sobre 535px de contenido, o sea scroll propio y cero desbordamiento (medido en vivo con
`getBoundingClientRect()`).

**Regla de disparo** (`dispararClipManual()`):
- Usa **la misma** `window.dispararClipDebug()` que el handler WS `debug_clip` de `bench_chat.py` —
  no hay lógica duplicada.
- Si el clip tiene `giraCuerpo` **y hay voz sonando**, no se dispara: queda en `_clipEnEspera` y sale
  al vaciarse la cola de audio, con burbuja de sistema avisando. Solo se guarda **uno**; un pedido
  nuevo reemplaza al anterior.
- Si `giraCuerpo` es `false`, dispara al momento aunque esté hablando.
- Todo disparo manual resetea `_gestoTimer`, para que no se encadene un gesto espontáneo encima.
- Feedback con burbuja `.msg.sistema` (`▶ <etiqueta>` / `⏳ ... en espera`), ya distinta de las de
  usuario y de Rem.

### Un clip manual no lo interrumpe ni el audio ni un estado sin clip

`updateGestos()` corta cualquier gesto si hay audio ("la voz manda"), así que un clip pedido a mano
mientras Rem hablaba **moría al frame siguiente**. Se marca la acción con `_esManual` **en la propia
`AnimationAction`**, no en una variable de módulo — mismo criterio que evitó repetir el bug de
`_gestoActivo`: cuando `_accionActual` cambia o se anula, el flag se va con ella y no puede quedarse
pegado (`hayClipManual()` lo lee de ahí). Con eso:
- `updateGestos()` no lo corta por audio ni por estado.
- `sincronizarClipConEstado()` lo respeta si el estado nuevo **no** trae clip propio (`idle`/`talking`)
  — si no, terminar de hablar (`talking → idle`) cortaba a la mitad el clip recién pedido. Un estado
  **con** clip mapeado (`thinking`/`sad`/...) sigue ganando.
- Alcanza también al `clip <nombre>` de `bench_chat.py`, que pasa por la misma función.

### Dos salidas para el clip en espera, no una

`_avanzarCola()` (cola de audio vacía) es la salida obvia, pero **solo corre si hubo audio real**. Con
la voz del panel apagada no hay ninguno y aun así el backend manda `estado='talking'` con el primer
delta: un clip encolado por "está hablando" se quedaba encolado **para siempre**. Por eso `animate()`
también llama a `_intentarLanzarClipEnEspera()` al salir de `talking`. La función revalida
`hayVozSonando()` antes de soltar nada, así que llamarla de más es inofensivo.

Además hay un rebote de **700ms** (`_ESPERA_TRAS_AUDIO_MS`) antes de disparar: con la voz por oraciones
(ver `SentenceSplitter`) la cola se vacía un instante **entre** dos frases de la misma respuesta, y sin
el rebote el giro salía a mitad de respuesta.

**`_gestoActivo` — todas las rutas nuevas lo liberan.** Encolar **no** lo toca (se pone recién en
`dispararClipDebug()`, en el disparo real), así que un clip que queda en espera y nunca se dispara
—reemplazado por otro, o la ventana se cierra— no deja nada colgado. Las rutas de token obsoleto y de
error de carga ya lo liberaban.

**Verificado en vivo** con una autoprueba temporal contra el DOM real dentro de la ventana (inyectada,
ejecutada y eliminada): **20/20** comprobaciones — `a/b` no abre, `Enter` con la paleta abierta no
envía (ni con la lista vacía), filtrado en vivo, los dos niveles, comando desconocido a burbuja de
sistema sin enviar, clip sin giro disparando al instante mientras habla, y el ciclo completo
giro → espera → disparo al terminar. Tras 5 disparos manuales seguidos los gestos espontáneos
volvieron solos (prueba de que `_gestoActivo` no quedó colgado), y `bench_chat.py` con
`clip VRMA_06` siguió funcionando igual.

## WebSocket bidireccional y `chat_sesion.py`
El WS de `:18766` es bidireccional. `_ws_handler()` en `rem_avatar_server.py` procesa lo que manda
el cliente (el panel de `rem_avatar.html`, o `bench_chat.py` en modo cliente), con mensajes tipados
por un campo `tipo`:

| Dirección | tipo | Payload | Qué hace |
|---|---|---|---|
| cliente → Python | `hola` | `{rol: "avatar"\|"panel"\|"debug"}` | Lo primero que manda cada cliente: su rol (ver "Roles de cliente WS" abajo) |
| cliente → Python | `chat_message` | `{texto}` | Corre un turno completo contra el LLM activo |
| cliente → Python | `cambiar_modo` | `{modo: "ia"\|"eco"}` | Cambia el provider de la sesión de chat compartida |
| cliente → Python | `reset` | — | Limpia el historial de la sesión de chat compartida |
| cliente → Python | `voz` | `{activa: bool}` | Interruptor de voz del panel (`set_voz_chat_activa()`) |
| cliente → Python | `estado` | `{estado}` | Pide poner el avatar en ese estado — se valida y se re-difunde a todos (lo usa el comando `state` de `bench_chat.py` cliente) |
| cliente → Python | `debug_clip` | `{nombre}` | Depuración: dispara un clip VRMA por nombre — se re-difunde a todos (comando `clip` de `bench_chat.py`, ver "Animación de cuerpo con clips VRMA") |
| cliente → Python | `prefs_get` | — | Pide las preferencias efectivas (respuesta `prefs_estado`, solo a quien pregunta) |
| cliente → Python | `prefs_set` | `{seccion, cambios, id?}` | Aplica un parche de preferencias (ver "Preferencias del panel de control") |
| Python → cliente | `prefs_estado` | `{prefs, propias, modo}` | Todas las secciones, valores efectivos; `propias` = claves que vienen del panel, por sección |
| Python → cliente | `prefs_actualizadas` | `{seccion, prefs, propias, id}` | Un cambio aplicado — se difunde a TODOS (avatar y paneles) |
| Python → cliente | `prefs_error` | `{seccion, mensaje, id}` | Parche rechazado — solo a quien lo mandó, no como `error` (eso es burbuja del chat) |
| Python → cliente | `debug_clip` | `{nombre}` | El avatar corre ese clip una vez y vuelve al reposo |
| Python → cliente | `estado` | `{estado}` | Estado emocional/de habla del avatar |
| Python → cliente | `audio` | `{url, timeline}` | WAV a reproducir + timeline de visemes |
| Python → cliente | `chat_delta` | `{texto}` | Un fragmento de la respuesta, tal como llega del LLM |
| Python → cliente | `chat_done` | — | Fin del turno |
| Python → cliente | `modo_actual` | `{modo}` | El modo activo — se manda tras cualquier cambio real |
| Python → cliente | `error` | `{mensaje}` | Algo falló (turno ya en curso, falta API key, modo/estado inválido) |

**`SesionChat` se extrajo de `bench_chat.py` a `chat_sesion.py`** (junto con una función nueva,
`procesar_turno()`) para que el REPL y el panel de chat usen la misma clase en vez de dos copias.
`procesar_turno()` es una versión "en crudo" del turno: emite cada `TextDelta` tal como llega vía
un callback `on_delta`, sin agrupar por oración — a propósito distinta de `_chat()` en
`bench_chat.py`, que sigue intacta (agrupa con `dividir_en_oraciones()` para encolar hacia
TTS/avatar). No se tocó `_chat()` ni nada del pipeline de voz: el panel de chat es un consumidor
nuevo y separado, no un reemplazo.

**La sesión de chat es un singleton compartido, no uno por consumidor**: `rem_avatar_server.
obtener_sesion_chat()` construye (perezoso, recién en el primer uso real) una única `SesionChat` +
snapshot de memoria por proceso, y tanto `_ws_handler()` (panel HTML) como `repl_standalone()` de
`bench_chat.py` la usan — la MISMA instancia cuando corren en el mismo proceso (`bench_chat.py` en
modo standalone). Por eso cambiar de modo desde el botón del panel también lo ve el comando `modo`
del REPL standalone y viceversa: son el mismo objeto. `cambiar_modo_chat()` es el punto de entrada
único (lo llaman `_ws_handler` y el comando `modo` del REPL standalone) — además de mutar la sesión,
manda `modo_actual` por WebSocket. En modo cliente, `bench_chat.py` no toca `SesionChat` directo:
manda `cambiar_modo` por WS y el servidor (el proceso de `rem_chat.py`) lo aplica sobre SU singleton.

Perezoso a propósito: construir la sesión recién en el primer `chat_message`/`cambiar_modo`/`reset` real evita pagar `get_provider()` (que
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

**`habla.py`**: `precargar_tts()`/`sintetizar()`/`decir()`/`worker_habla()`/`TurnoHabla`, salido
de `bench_chat.py` (antes con el prefijo `_`). `_voz`/`_voz_lock` son module-level (una sola
PiperVoice por proceso) — importante porque hay DOS consumidores posibles en el mismo proceso (la
cola del REPL y la del panel, ver más abajo) que no deben cargar el modelo por duplicado ni
fonemizar a la vez (ver "Voz de Yoru (Piper)").

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

**Interruptor de voz del panel** (`_chat_voz_activa`/`set_voz_chat_activa()` en
`rem_avatar_server.py`, mensaje WS `{tipo: "voz", activa: bool}`): equivalente a `voz on|off` del
REPL, pero **independiente** — no hay sincronización entre los dos, cada uno controla si SUS
PROPIOS turnos hablan. Arranca en `True` (a diferencia de `voz_activa` del REPL, que arranca en
`False`): la ventana existe para hablar con Rem, así que el botón (🔊/🔇 en el header del panel) es
para silenciarla, no para tener que activarla primero. Es puramente local en el frontend — a
diferencia de `cambiar_modo`, no hay confirmación del backend ni un tipo `voz_actual` que
sincronizar (un on/off no puede fallar, y no hay ningún otro cliente cuyo estado deba reflejar).

**`rem_chat.py` precarga la voz al arrancar** (`habla.precargar_tts()` en un hilo de fondo, antes
de `iniciar_servidor_avatar()`, mismo patrón que `bench_chat.py`): en la ventana la voz es una
capacidad de primera clase, así que siempre precarga.

**Verificado en vivo, los cuatro escenarios**:
1. Panel con voz activa, modo eco: `chat_message` por WS produjo exactamente una línea `hablando:
   "..."` en el log, la síntesis (en su día, conversión RVC), `enviado por WebSocket`, y el navegador real (`rem_chat.py`)
   registró `[Lipsync] mensaje de audio recibido` + `play() resuelto` — la ventana efectivamente
   habla.
2. Interruptor en `False`: el mismo `chat_message` completó `chat_delta`/`chat_done` normalmente
   (el texto se sigue viendo) pero sin ninguna línea `hablando:` nueva en el log — cero turnos de
   síntesis cuando la voz está apagada.
3. **Doble consumidor** (el panel del servidor + un turno inyectado por otro cliente WS): cada turno
   se sintetiza/encola **una sola vez**, desde la cola/worker de quien lo disparó. Con
   `rem_chat.py` corriendo y `bench_chat.py` en modo cliente conectado encima, un `chat` desde
   bench va por WS → el servidor lo corre en SU cola → una línea `hablando:`, sin duplicar.
   - Nota sobre alcance: `enviar_audio()` **difunde** cada turno a todos los clientes WS conectados.
     Si hay más de un cliente (poco común hoy: solo `rem_chat.py` tiene WebView), el mismo audio
     suena en todos, cada uno una vez. Lo que importa es que el BACKEND nunca sintetiza/encola el
     mismo turno dos veces.
4. **Un solo servidor entre procesos**: el proceso que reusa un servidor ajeno (`bench_chat.py`
   modo cliente, o `iniciar_servidor_avatar()` detectando uno ya arriba) NUNCA corre su propio
   `_ws_handler` — sus `_ws_clients`/`_chat_sesion` quedan vacíos. Por eso `bench_chat.py` en modo
   cliente manda todo por WS al servidor real (el proceso de `rem_chat.py`), no llama a
   `enviar_estado()`/`procesar_turno()` en su propio proceso (donde no llegarían a nadie).

## Encuadre 3D consciente del panel de chat
El panel de chat ocupa la mitad derecha de la ventana, así que Rem hay que centrarla en la mitad
IZQUIERDA (el área 3D visible), no en el canvas completo.

**`fraccionAreaVisible3D()`** devuelve qué fracción del CANVAS COMPLETO ocupa el área 3D visible:
`1 - CONFIG.chat.anchoFrac`. `worldX(n)` en sí no cambió — sigue midiendo en fracciones del canvas
completo, a propósito: `camera.aspect` tiene que seguir atado al tamaño REAL del render, o la imagen
se distorsiona. Lo que cambió es qué se le pasa: `recalcularEncuadre()` hace
`worldX(CONFIG.pet.anchorX * fraccionAreaVisible3D())` — `CONFIG.pet.anchorX` es una fracción DEL
ÁREA VISIBLE (0=su borde izquierdo, 1=justo donde empieza el panel), y vale `0.5` (centrada en su
área).

**`CONFIG.chat.anchoFrac` es la única fuente de verdad para el ancho del panel** — la lee tanto
`fraccionAreaVisible3D()` (encuadre) como `crearPanelChat()`, que fija el custom property CSS
`--chat-panel-width` (`${CONFIG.chat.anchoFrac * 100}%`) ANTES de crear el `<div>` del panel. El
CSS del `<head>` usa `width: var(--chat-panel-width, 50%)` — el `50%` es solo el valor de respaldo
por si el custom property no llegara a fijarse (no debería notarse nunca, se fija sincrónicamente
muy temprano en el mismo `<script type="module">`). Antes el 50% estaba hardcodeado en dos lugares
(el CSS y, implícitamente, en cualquier cálculo de encuadre que lo asumiera) — ahora un cambio a
`CONFIG.chat.anchoFrac` mueve los dos a la vez, no pueden desincronizarse.

**`CONFIG.pet.alturaPantalla`** (el modelo ocupa esta fracción del alto visible) vale `0.65`. Junto
con `anchorX` eran valores por modo (`CONFIG.modos.{overlay,ventana}`) cuando existía el overlay;
al eliminarlo quedaron aplanados en `CONFIG.pet` directo.

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
esto por sí solo centraría a Rem en el medio del CANVAS COMPLETO (debajo del panel) — se corrige con
`camera.setViewOffset(window.innerWidth, window.innerHeight, offsetX, 0, window.innerWidth,
window.innerHeight)`, con `offsetX = (0.5 - fracXCanvas) * window.innerWidth`: un corrimiento de
"lente descentrado" (el mismo truco que un objetivo tilt-shift o un corrimiento de cámara de
arquitectura) que reencuadra la imagen ya renderizada sin volver a rotar la cámara (rotar la
reintroduciría el ángulo que se acaba de eliminar).

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
├── README.md         (de dónde sale cada conjunto + licencias)
├── catalogo.json     (versionado: QUÉ clips hay — ver "Catálogo de animaciones")
├── VRMA_MotionPack/  (los 17 de antes: tk256ailab + pack oficial VRoid — categoría "Rem anterior")
└── nerumi/           (172 clips de Nerumi, por categoría: dance/ idle/ greetings/ actions/sit|lying/ ...)
```

Los `.vrma` están en `.gitignore` (mismo criterio que `rmvpe.pt`/`rem.vrm`); `catalogo.json` no. Si
un clip falta o no parsea, el avatar cae a la animación procedural con un aviso (`[Anim] "<id>" no
disponible: … — se mantiene la animación procedural`), sin romperse, y ese clip sale de la paleta y
del repertorio por el resto de la sesión (`_clipsFallidos`).

### Librería: `@pixiv/three-vrm-animation@2.1.3` (solo el loader plugin)

- Versión emparejada con `@pixiv/three-vrm@2.1.3` (mismo `three-vrm-core`). Comparten el three
  0.164.1, no el 0.169.0 de la página — ver "Sin internet: módulos JS vendorizados". Subir todo a `@3` rompería la integración fina con internals de v2 (`expr._binds`,
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

### Catálogo, precarga y caché

**Qué clips hay sale de `Animaciones/catalogo.json`** (ver "Catálogo de animaciones"), no de
`CONFIG`: `CONFIG.animaciones` guarda solo el comportamiento del motor (fundidos, `cacheMax`,
`baileMinS`, mezcla de la pose base). El intervalo de reposo y los minutos de enfriamiento salen de
`catalogo.json` → `ajustes`, pisables por el panel (`ajusteAnim()`); qué clips están activos, los
pesos y el estado → clip también pueden venir del panel (`_prefsAnim`, ver "Preferencias del panel
de control"). `cargarCatalogo()` lo baja al arrancar (no en
overlay) con `cache: 'no-cache'`; sin catálogo no hay clips y todo sigue procedural. Los clips se
identifican por su ruta relativa a `Animaciones/` (`nerumi/dance/Dance11-spooky.vrma`).

- **Precarga solo de los fijos** (`precargarClipsFijos()`: los de `porEstado` y la pose base, hoy 6):
  con 189 clips (58 MB) no se puede precargar todo (la página ya gasta ~40 % de un núcleo). El resto se
  carga la primera vez que se usa.
- **Caché LRU** (`obtenerClip()`, `_podarCacheClips()`): hasta `cacheMax` (20) clips parseados, sin
  contar los fijos ni los fallos; al pasarse se desaloja el usado hace más tiempo (con
  `mixer.uncacheClip`), salvo el que suena y el que se desvanece. `_clipCargando` evita cargar dos veces
  el mismo clip si se pide mientras ya está en vuelo.
- **Paleta `/animaciones`**: todos los clips usables (activos o no — pedirlo a mano es explícito),
  agrupados por categoría (`orden`) con una cabecera por grupo (`.pal-grupo`, no seleccionable);
  filtra también por el nombre del grupo ("/animaciones bailes").
- **`giraCuerpo` y `fundidoEntradaS` salen del catálogo, medidos**. Un clip con `fundidoEntradaS`
  (empieza con los brazos arriba) entra con ese fundido (0,8 s) en vez de `fadeIn`, y su crossfade
  clip→clip es al menos ese.

### Estado → clip y gestos de reposo

**`porEstado` del catálogo** (`{clips, modo, duracionS?, enfriamiento?}`):

| estado | clip(s) | modo |
|---|---|---|
| `thinking` | `VRMA_MotionPack/Thinking.vrma` | `bucle` (sin tope — dura lo que dure thinking) |
| `sad` | `Idle38_Cry` | `unaVez`, con enfriamiento |
| `angry` | `Idle26_Shout` | `unaVez`, con enfriamiento |
| `surprised` | `Idle68_Surprise` | `unaVez` |
| `happy` | `Idle74_Cheer` / `Idle65_ThumbsUp` | `unaVez`; al azar sin repetir el último (con dos, alterna) |
| `talking` | — | sin clip (procedural) |
| `idle` | — | sin clip: **procedural** (ver "Clip de POSE BASE de idle" abajo) |

- `modo: 'bucle'` = `LoopRepeat`; `duracionS` opcional = tras N s de controlar el cuerpo hace
  crossfade a procedural (la cara sigue). `modo: 'unaVez'` = `LoopOnce` + `clampWhenFinished`; al
  terminar hace crossfade a procedural **siempre**.
- **Enfriamiento** (`_elegirClipDeEstado()`): un clip de un estado con `enfriamiento` que se reprodujo
  por estado hace menos de `enfriamientoMin` minutos (5, de `ajustes`; el panel lo pisa) no vuelve a salir: ese
  estado solo pone la cara (`[Anim] sad: clip en enfriamiento ... — solo la cara`). Solo cuentan los
  disparos por estado, no los de la paleta.
- `sincronizarClipConEstado()` se llama en el `estado !== prevEstado` de `animate()`. Guarda de
  carrera: `_tokenClip` invalida cargas async pendientes si el estado cambió mientras el `.vrma`
  cargaba.

**Clip de POSE BASE de idle** (`CONFIG.animaciones.idle`) — **DESACTIVADO (`archivo: null`)**. El
mecanismo sigue existiendo entero; lo que se apagó es su uso. La pose de reposo es el **idle
procedural**, con los brazos en `CONFIG.brazos.*` (`separacion` 1,20 rad, `codoFlexionBase` -0,30).

**Por qué se apagó: `Relax.vrma` producía una T-pose casi permanente.** Se midió el ángulo Z del
`upperArm` sobre las pistas crudas del `.vrma` (ya con el espejo VRM0 que aplica `clipDeVrma()`;
el reposo procedural es ±68,8°):

| t | leftUpperArm | rightUpperArm |
|---|---|---|
| 0,0s | **+69,7°** | **−60,0°** (= reposo procedural) |
| 0,9s | +12,0° | −8,4° |
| 1,8s | −17,1° | +7,0° (= horizontal) |
| 3,9s | −18,5° | +1,5° |

El clip arranca con los brazos abajo y en ~1,2s los sube a la horizontal, donde se queda el **83-85%
de su ciclo de 3,93s** — y corría en `modo: 'bucle'` mezclado al 0,8 sobre los brazos
(`mezclaBrazos`), o sea reposo real = 0,8 × T-pose, para siempre.

**No era un bug del mixer ni del orden de la mezcla** (se descartaron las dos hipótesis obvias): los
gestos sí corrían `LoopOnce` y sí volvían a la base (`[Anim] idle base:` en el log tras cada uno), y
`actualizarAnimacionClips()` **compone** correctamente (procedural → snapshot de `.quaternion` →
`_mixer.update()` → `slerp(qProc, qClip, peso)` → `vrm.update()`), no sobrescribe. Era el contenido
del clip.

Si se quiere recuperar la pose de manos/brazos de un clip sin la T-pose, el camino es
`modo: 'poseFija'` (congela el frame 0, que sí tiene los brazos abajo), no `modo: 'bucle'`. **Antes
de habilitar cualquier `.vrma` como pose base, medirle el ángulo del `upperArm` a lo largo de todo el
clip, no solo mirar su primer frame.**

Cuando está activo, no es un gesto ni un clip de estado — es **la base**: cede a cualquier gesto/clip
de estado con crossfade (`reproducirClip`/`sincronizarClipConEstado`) y se vuelve a él al terminar
(`volverABaseIdle()`, llamada desde `_alTerminarClip` para gestos). Config:
- `archivo: null` → procedural puro (**el valor actual**). Un `.vrma` → pose base.
- `modo: 'bucle'` → el clip corre en loop, con `timeScale` variable (`velMin`–`velMax`,
  `_actualizarVelIdle()`) para romper la periodicidad de un ciclo corto (~4s). `modo: 'poseFija'` →
  solo el primer frame, congelado (`timeScale = 0`, no `paused` — sigue entrando en la mezcla) —
  arregla la pose sin aportar movimiento.
- `mezclaBrazos` (0..1): **del clip solo se toman los brazos** (`_HUESOS_BRAZO_IDLE`: hombro/
  upperArm/lowerArm/mano). El resto del cuerpo queda 100% procedural — los brazos rectos son el
  problema real, el resto ya se ve bien. En `actualizarAnimacionClips()`, rama `idleBrazos`
  (`_accionActual._esIdle && _clipPeso >= 0.999`): `slerp(qProcedural, qClip, mezclaBrazos)` solo en
  esos huesos, `copy(qProcedural)` en el resto. No se llama `aplicarRespiracionEncima`/
  `aplicarCabezaSigueMiradaEncima` (lo procedural ya las puso, sería doble).
- `ampProcedural`: multiplica el ruido Perlin de `getStatePose('idle')` mientras el clip de idle
  domina la mezcla (`_idleAmpMult`) — >1 rompe más el patrón del bucle.
- Los gestos de reposo SÍ se disparan sobre el clip de idle (crossfade idle → gesto → idle) —
  `updateGestos()` ya no bloquea por `_clipPesoObjetivo === 1`, solo por clip de estado / audio /
  no-idle.

**Gestos de reposo** (`_elegirGesto()`): solo en `estado === 'idle'` && `!_audioActivo` && sin clip
de estado, cada `intervaloReposo` (4–9 s, de `ajustes`) tras terminar el anterior. El repertorio es el catálogo:
clips usables y **activos** (`clipActivo()`: preferencia del panel por clip, si no categoría activa +
`activoPorDefecto`), dentro de su franja `horas`. Se sortea **primero la categoría** por su peso
(`pesoCategoria()`: idle 4, dance 1) y **después el clip** dentro de ella por el suyo — así el
reparto es la proporción de las categorías, no depende de cuántos clips tenga cada una (medido sobre
20 000 sorteos con el catálogo real: idle 79,5 %, dance 20,5 %, 0 repeticiones seguidas). No se
repite el último gesto mientras quede otro candidato.

**Bailes cortos** (`_opcionesGesto()`): 11 bailes de Nerumi son unidades de bucle de menos de 4 s
(`doodle` 0,33 s, `ankha` 1 s...). Un baile más corto que `baileMinS` (8 s, la mediana) se repite en
`bucle` con tope = ciclos completos hasta llegar (`brooklinbloodpop` 8 × 1,03 s, `doodle` 25 × 0,33 s,
verificado en vivo), así el corte cae en frontera de ciclo. Igual para el disparo manual.

**Ritmo real = intervalo + duración del clip.** Los dos números a tocar son `intervaloReposo` y los
pesos (de categoría en el catálogo/panel, de clip en el catálogo).

**`debug_clip` — disparar un clip por nombre bajo demanda** (para grabar video sin esperar al
sorteo). `window.dispararClipDebug(nombre)` en `rem_avatar.html` lo corre como si fuera un gesto de
reposo (vuelta al reposo con crossfade; un baile corto se repite hasta `baileMinS`); acepta el id
del catálogo o el nombre de archivo con o sin `.vrma` (`resolverClip()`: `VRMA_05`, `Dance11-spooky`),
cualquier clip del catálogo aunque no esté activo. Se llega por
WebSocket (`{tipo: "debug_clip", nombre: "VRMA_05"}`) desde `bench_chat.py` (comando `clip <nombre>`,
en los dos modos) o desde la consola del inspector remoto. Si no está en el catálogo o no carga,
avisa en consola y no dispara nada. Se comporta como cualquier gesto: si entra audio o cambia el estado, se interrumpe
con crossfade (la voz manda).
- Guarda de carrera: usa `_tokenClip` igual que `updateGestos()`, y en la rama de token obsoleto
  **libera `_gestoActivo`**. Sin eso, un `.vrma` grande (VRMA_03 son 1,3 MB) pisado por otro pedido
  mientras cargaba dejaba `_gestoActivo` en `true` sin dueño y **los gestos de reposo no volvían a
  dispararse nunca**. Reproducido a propósito (dos `debug_clip` en paralelo, el lento perdiendo el
  token) y verificado que los gestos espontáneos siguen después.

**Interrupción (la voz manda)**: si llega audio o cambia el estado a mitad de un gesto o clip,
`updateGestos()`/`sincronizarClipConEstado()` disparan `volverAProcedural()` o un `crossFadeTo` al
clip que toque — siempre con crossfade, nunca corte.

### Cómo añadir un clip nuevo

1. Dejar el `.vrma` en `Animaciones/` (en la subcarpeta de su categoría).
2. `venv/bin/python catalogo_animaciones.py`: lo mide y lo agrega al catálogo con etiqueta del nombre
   de archivo, origen `desconocido` y `activoPorDefecto` según la política (categoría activa y sin
   avisos que lo descalifiquen). **Completar a mano** en `catalogo.json` la `etiqueta` y el `origen`.
   `giraCuerpo` y el fundido salen medidos, no hay que adivinarlos.
3. Si tiene que salir por un estado, agregarlo a `porEstado`; como pose base, a `poseBase.archivo`
   (antes, mirar `medido.brazoIzq/brazoDer` en todo el clip — la lección de `Relax.vrma`).
4. Nada más: la página relee el catálogo al cargarse. Si el `.vrma` no trae `specVersion`,
   `normalizarVrma()` lo parchea en memoria.

### Presupuesto de VRAM del render (`CONFIG.render`)

`pixelRatioMax` (1.0) y `resolucionMaxPx` (~1,6 Mpx) topan el framebuffer del WebGL; `aplicarTamanoRender()`
(arranque + resize) baja el `devicePixelRatio` efectivo y deja que el canvas se reescale por CSS.
**El WebGL va por la iGPU Intel, no por la NVIDIA ni por software** (corregido 2026-11-06, ver
"Renderer WebGL: iGPU Intel"): estas mitigaciones bajan el trabajo de la iGPU y de la página, pero
**no liberan VRAM para el LLM**, que no comparten — el `num_gpu` de
`config.toml` no depende de esto (24/28 se limitaban por el pico de VRAM de RVC en la conversión, no
por la ventana; RVC ya no existe — ver "Voz de Yoru (Piper)").

Los clips **no tocan expresiones ni mirada**: si un `.vrma` nuevo trae pistas de expresión/mirada,
`clipDeVrma()` las ignora (usa solo `humanoidTracks`), y si anima `leftEye`/`rightEye`/`jaw` esos
huesos se excluyen. No hay que hacer nada especial para eso.

## Soporte multimodelo del avatar

El código de `rem_avatar.html` ya no asume un modelo VRM concreto — soporta `rem.vrm` (raíz del
proyecto) y `models/rem_naenae.vrm` (ver `models/README.md` para su origen/licencia), y agregar
uno nuevo no toca lógica, solo `CONFIG.modelos`.

**Cómo se elige el modelo**: `config.toml` → `[avatar].modelo` (por defecto
`"models/rem_naenae.vrm"`; `"rem.vrm"` sigue disponible como alternativa, ninguno de los dos se
borra). `config.leer_modelo_avatar()` lo lee; `rem_avatar_server.url_avatar(modo)` es el ÚNICO
punto que arma la URL de la página con `?modelo=...` — lo usan tanto `rem_chat.py` como
`bench_chat.py` (`_abrir_navegador()`/`URL_AVATAR`), así que no hay dos lugares leyendo
`config.toml` por separado. En `rem_avatar.html`, `MODELO_ACTIVO` sale de
`new URLSearchParams(location.search).get('modelo')` (default `"rem.vrm"` si falta el param —
abrir la página a mano sin query sigue funcionando) y `PERFIL_MODELO = CONFIG.modelos[MODELO_ACTIVO]`
cae a `CONFIG.modelos['rem.vrm']` con un warning si el valor no tiene perfil (typo en config.toml).

**Qué declara cada entrada de `CONFIG.modelos`**:
- `lipsync.visemas`: por cada uno de los 15 visemes canónicos que manda `lipsync.py`
  (`timeline[].viseme`, formato `"vrc.v_*"` — es una convención interna del proyecto, no un nombre
  que se asuma presente en ningún VRM), la lista de `{morph, peso}` a la(s) que contribuye. `morph`
  es la CLAVE real que hay que buscar en `morphTargetDictionary` de este archivo en particular (ver
  más abajo por qué eso casi nunca es el nombre "bonito" del glTF). Una lista vacía (`[]`) es a
  propósito "sin morph" (boca cerrada de verdad, más barato que escribir peso 0 cada frame) — no es
  lo mismo que un nombre no encontrado, que queda logueado como advertencia.
- `expresionesSuprimirHabla`: qué claves de `EXPR_PROFILES`/`_exprMap` (`happy`/`sad`/`angry`/
  `surprised`) bindean morphs de boca en ESTE modelo y hay que apagar mientras `_audioActivo`, para
  que no compitan con los visemes. rem.vrm solo necesita `['surprised']`; el modelo nuevo necesita
  las 4, porque sus `Fcl_ALL_*` son shapes de "cara completa" (cejas+ojos+boca en un solo morph
  esculpido, convención VRoid), a diferencia de rem.vrm donde solo "Surprised" tocaba la boca.

**Cómo agregar un modelo nuevo**: cargarlo una vez con un perfil vacío (`lipsync: {visemas: {}}`),
mirar el log `[Lipsync][diag] claves únicas en los N diccionarios` (te da el vocabulario real de
claves que existen) y `[Diag] expresión "aa"/"ih"/... — N bind(s): -> malla(s)=[...] morph_index=N`
(los binds de VRM0 apuntan a `{mesh, index}` directo, sin pasar por nombre — son la fuente más
confiable para saber qué índice es cada vocal, igual que se hizo para los dos modelos actuales).
Con eso arriba, completar `lipsync.visemas` con esas claves. Revisar también qué expresiones
bindean morfos de boca (mismo log `[Diag] expresión ...`) para `expresionesSuprimirHabla`.

### `morphTargetDictionary` degenera a claves numéricas — confirmado en los DOS modelos

Ver "Cómo three.js construye morphTargetDictionary" más arriba: se creía un problema específico de
cómo se exportó `rem.vrm` (targets sin nombre real). Se confirmó agregando `models/rem_naenae.vrm`
—un archivo cuyo glTF crudo SÍ nombra sus targets (`extras.targetNames` trae literalmente
`"Face.M_F00_000_00_Fcl_MTH_A"`, etc., confirmado con `dump_vrm.py`)— que en runtime
`morphTargetDictionary` **igual** degenera a claves `"0".."40"` en STRING. Es decir: no es un
problema de cómo se exportó cada archivo, es un efecto del pipeline de carga (`GLTFLoader` +
`VRMLoaderPlugin@2` + `VRMUtils.removeUnnecessaryJoints`) en esta versión de three-vrm. La
"resolución por nombre" en `localizarMallaFacial()`/`CONFIG.modelos[...].lipsync.visemas` sigue
siendo válida — busca esa clave (sea "4" o "Fcl_MTH_A") en `morphTargetDictionary` real y nunca
escribe a ciegas en un índice — pero la clave que hay que declarar casi siempre termina siendo el
número de posición, no el nombre "bonito" del glTF.

### Pendiente: resolver morphs por el nombre REAL, no por la posición degenerada

Lo de arriba funciona (probado en los dos modelos) pero es frágil: si el orden de
`geometry.morphAttributes.position` cambiara entre versiones del loader, las claves numéricas
declaradas en `CONFIG.modelos` quedarían apuntando a otra cosa sin que nada avise (los índices
existen igual, solo que a un morph distinto). La resolución robusta de verdad es leer
`extras.targetNames` del **JSON crudo del glTF** (`gltf.parser.json.meshes[i].primitives[j].extras
.targetNames`, disponible en el callback de `loader.load()` vía `gltf.parser`) al cargar el modelo,
en vez de depender de `morphTargetDictionary` reconstruido por three.js — así `CONFIG.modelos[...]
.lipsync.visemas` podría declarar el nombre real ("Fcl_MTH_A") siempre, y el código correlacionaría
ese nombre con la posición real leyendo el glTF directo, sin pasar por la degeneración. No
implementado todavía — los índices numéricos hardcodeados por modelo (confirmados en vivo, no
adivinados) son la solución pragmática actual.

## Bug de encuadre: medición por huesos contaminada por el offset provisorio

`recalcularEncuadre()` se llama DOS veces al cargar un modelo: una con la medición provisoria por
`Box3` (antes de posar nada), y otra un frame después con la medición real por huesos
(`medirAlturaHuesos()`, ver "Encuadre del avatar" más arriba). El bug: `medirAlturaHuesos()` leía
`head`/`leftFoot`/`rightFoot` con `getWorldPosition()` — posiciones de MUNDO — pero para ese
momento `vrm.scene.position.y` YA tenía el offset Y de la primera pasada (Box3). `altura` (una
RESTA, `head.y - pie.y`) cancelaba ese offset sola y salía bien, pero `centro` (un PROMEDIO,
`(tope+pie)/2`) NO lo cancelaba — quedaba contaminado con el offset Y de la pasada anterior
completo. `recalcularEncuadre()` trataba ese `centro` contaminado como si fuera local, así que el
resultado final del `position.y` quedaba desplazado exactamente por ese offset previo.

Con `rem.vrm` el offset de la primera pasada era chico (~0,46u, porque `Box3` mide un poco más de
la mitad de la altura real por el problema de skinning ya documentado) y el error pasaba
inadvertido — se veía "bien" a simple vista aunque no estuviera perfecto. Con
`models/rem_naenae.vrm` el offset de la primera pasada resultó mucho más grande (~0,93u, porque acá
`Box3` YA mide casi bien, así que el "salto" entre pasadas es mayor) y el error sacaba la cabeza
completamente del cuadro — así se detectó.

**Arreglo**: `medirAlturaHuesos()` pone `vrm.scene.position.y = 0` (y
`updateMatrixWorld(true)`) antes de leer las posiciones de mundo, y restaura el valor previo
después — mide en un sistema sin el offset contaminante, sea cual sea. Verificado en vivo con los
dos modelos: `rem.vrm` pasó de `position.y=-0,571` a `-1,032` (mejor encuadrada, más margen arriba)
y `models/rem_naenae.vrm` de `-0,043` (cabeza fuera de cuadro) a `-0,977` (cuerpo completo visible),
coincidiendo ambos con el cálculo teórico hecho a mano para descartar que fuera casualidad.

## Renderer WebGL: iGPU Intel (no software, no NVIDIA) — medido 2026-11-06

CLAUDE.md decía "WebGL por software" porque `WebKitWebProcess` no salía en
`nvidia-smi --query-compute-apps` — pero esa consulta solo lista procesos de **cómputo** (CUDA),
nunca los gráficos: no podía verlo aunque usara la NVIDIA. No hubo ninguna decisión detrás
(`webview_comun.py` pide `HardwareAccelerationPolicy.ALWAYS`). Medido con la app en modo escritorio
(Hyprland anidado): el `WebKitWebProcess` tiene abierto `/dev/dri/renderD128`, que es la Intel
(`/sys/class/drm/renderD128` → driver `i915`; la NVIDIA es `renderD129`) y ningún `/dev/nvidia*`.
Carga las librerías EGL/GL de NVIDIA y Mesa (`libgallium`), pero dibuja en la Intel. La tabla
completa de `nvidia-smi` (que sí lista procesos gráficos, tipo `G`) solo muestra `llama-server`:
**VRAM de la NVIDIA del avatar = 0**. **CPU del `WebKitWebProcess` con el avatar en reposo: ~42 % de
un núcleo** (JS, animación, física del pelo, composición). `WEBGL_debug_renderer_info` no sirve para
esto: WebKit devuelve un valor fijo (`"Apple GPU"`). No se probó dibujar en la NVIDIA: le quitaría
VRAM a Ollama (3,5 de 4 GB). Bajar los fps mientras Whisper transcribe (20-30 fps) no acelera
Whisper (A/B 2026-11-06: 1,70-1,79 s en los tres casos), así que esa CPU no es lo que lo frena.

## Modo overlay: arranque, superficie y exclusión mutua con el modo ventana

`rem_chat.py --modo overlay` (o `config.toml` -> `[app].modo = "overlay"`) abre, en el MISMO
proceso y con el MISMO servidor que el modo ventana, una layer surface (`gtk-layer-shell`)
transparente anclada IZQUIERDA+ABAJO, tamaño configurable en `config.toml` -> `[overlay]`
(`ancho`/`alto`/`margen_izquierdo`/`margen_inferior`/`capa`/`zona_exclusiva`, default 420×600,
capa `top`). El avatar se ve de medio cuerpo (cadera hacia arriba) sobre el escritorio, con una
caja de texto discreta abajo. Nunca los dos modos a la vez — ver "Instancia única" más abajo.

`GDK_BACKEND=wayland` se fuerza en el proceso ANTES de que GDK se inicialice, solo en modo overlay
(en modo ventana no hace falta y no se toca): `gtk-layer-shell` aborta si GDK arrancó con XWayland,
y `GtkLayerShell` se importa ANTES que `Gtk`/`WebKit2`/`Gdk` (exige enlazarse antes que
`libwayland-client`) — mismo orden que ya usaba `rem_overlay.py` (ver "Ventana de escritorio" más
arriba). Si el paquete de sistema `gtk-layer-shell` no está instalado, `rem_chat.py --modo overlay`
sale con un mensaje claro (`sudo pacman -S gtk-layer-shell`) en vez de un `ImportError` críptico.

**Instancia única — `ServidorOcupadoError`.** `iniciar_servidor_avatar()` ahora toma
`permitir_reuso: bool` (default `True`, sin cambios para `bench_chat.py`, que
sigue reusando un servidor ya levantado sin competir por el puerto). `rem_chat.py` llama con
`permitir_reuso=False`: si los puertos `:18765`/`:18766` ya están ocupados (otra instancia de
`rem_chat.py`, en cualquier modo), sale con un error claro a la terminal Y al log (código 1) en vez
de abrir una segunda presentación pegada al servidor de la primera — el chequeo va ANTES de abrir
`rem_chat.log` con `'w'`, que si no truncaría el log de la instancia que sigue viva.
`_comprobar_instancia_unica()` además nombra el proceso que tiene el puerto (`ss -ltnp`) para que
el mensaje sea accionable, no solo "ocupado". Verificado en vivo: con una instancia corriendo (en
cualquier modo), lanzar una segunda en cualquier modo sale con `exit=1` y el mensaje nombra el pid
real; el log de la primera instancia queda intacto (no se pisa).

**Bind HTTP también robusto ahora, con el mismo patrón que el WS.** `_iniciar_http()` tenía el
mismo bug que `_iniciar_ws()` ya tenía arreglado (ver "Conflicto de puertos" más arriba): si el
bind fallaba (carrera entre el chequeo de `_puerto_activo()` y el bind real), el hilo daemon moría
en silencio y el llamador creía que había levantado. Ahora usa el mismo mecanismo
(`_http_ready`/`_http_bind_error`) que `_ws_ready`/`_ws_bind_error`.

## Modo overlay: click-through y la caja de texto (la región interactiva la mide la PÁGINA)

El overlay es click-through en TODA la superficie salvo el rectángulo de la caja de texto — pero,
a diferencia de un overlay estático, ese rectángulo se mueve (la caja puede reposicionarse/cambiar
de tamaño con un resize de la ventana o un cambio de CSS) y solo la PÁGINA sabe dónde está de
verdad. `rem_chat.py` no adivina la geometría: `crearOverlayUI()` en `rem_avatar.html` mide la caja
con `getBoundingClientRect()` (vía un `ResizeObserver` + al arrancar) y se lo manda a Python por un
`WebKitUserContentManager` script message handler llamado `"rem"`
(`window.webkit.messageHandlers.rem.postMessage(JSON.stringify({tipo:'region', x,y,w,h}))`) — el
mismo canal que ya usa `bench_chat.py`/el panel para nada relacionado, registrado aparte para esto.
`_EntradaOverlay.on_mensaje()` en `rem_chat.py` recibe ese mensaje y llama a
`gdk_win.input_shape_combine_region()` con esa región exacta (o una región VACÍA — todo
click-through — mientras la página todavía no reportó nada: mejor una caja inalcanzable unos
segundos que una superficie de 420×600 que se traga los clics del escritorio desde el frame cero).

**Bug real encontrado y arreglado: la región nueva no se aplicaba sin forzar un redibujado.**
`input_shape_combine_region()` por sí solo no bastaba — confirmado en vivo con
`wlr-virtual-pointer` contra un Hyprland anidado (ver "Verificación en vivo" más abajo): el
puntero seguía cayendo en la ventana de abajo incluso sobre la caja. La causa: GDK/Wayland aplica
la input region recién en el PRÓXIMO commit del toplevel, y el contenido lo pinta el WebView (su
propio commit) — sin forzar un `queue_draw()` del toplevel después de
`input_shape_combine_region()`, la región nueva podía quedar sin comitear indefinidamente. Se
arregló agregando `self.win.queue_draw()` justo después — mismo síntoma, otra forma, del bug
documentado en "Layer surface acotada" más arriba (`rem_overlay.py` lo resolvía reaplicando la
región en más eventos, no forzando el redibujado; acá alcanzó con esto).

**`WebKit2.Settings` en `_crear_webview()` es ahora compartido entre los dos modos** (antes vivía
solo en `main()` de la ventana) — la única diferencia por modo es `transparente` (color de fondo
`RGBA(0,0,0,0)` en overlay vs. el violeta oscuro opaco de siempre en ventana). Todo lo demás
(WebGL, `WebsitePolicies(autoplay=ALLOW)`, volcado de consola, developer extras) es idéntico.

**Teclado: `ON_DEMAND` fijo secuestraba el foco — se hizo dinámico.** Medido en vivo en Hyprland
(que sigue el puntero, `follow_mouse`): con `GtkLayerShell.KeyboardMode.ON_DEMAND` fijado una vez
al crear la layer surface, bastaba con que el puntero PASARA por encima de la caja (sin clic) para
que la superficie tomara el foco de teclado — y lo CONSERVABA al alejarse, hasta que otra ventana
se enfocara a la fuerza, dejando el resto del escritorio sin poder escribir. `_EntradaOverlay`
alterna el modo en runtime: `NONE` por defecto, `ON_DEMAND` solo mientras el puntero está sobre la
caja (`enter-notify-event`/`leave-notify-event` de GTK, filtrando `Gdk.NotifyType.INFERIOR` para no
contar cruces internos con hijos) **o** la caja de texto tiene el foco real dentro de la página (la
página lo avisa con `{tipo:'foco', caja: bool}` por el mismo canal de mensajes, en los eventos
`focus`/`blur` del `<input>`) — así escribir sin soltar el mouse de la caja, o alejar el mouse a
mitad de frase, no corta el foco. Al dejar de cumplirse las dos condiciones, vuelve a `NONE` y
Hyprland le devuelve el teclado a la ventana de antes. `Enter` con texto también suelta el foco
explícitamente (`$input.blur()`) tras enviar, para no quedarse con el teclado secuestrado sin
querer escribir más.

**Verificado en vivo — click-through, foco de teclado, push-to-talk, cambio de modo**: instrumentado
con un cliente C mínimo de `wlr-virtual-pointer-unstable-v1` (mueve/clickea el puntero por protocolo,
sin depender de X11) contra la sesión Wayland REAL (Hyprland) y, para las pruebas de foco de
teclado más invasivas, un Hyprland ANIDADO aparte (otro `WAYLAND_DISPLAY`, otro cursor, aislado de
la sesión real) con dos ventanas `foot` de prueba a los lados:
- Hover sobre CUALQUIER punto de la superficie que NO sea la caja (esquina transparente, el cuerpo
  opaco de Rem) atraviesa a la ventana de abajo — sin eventos en la página, sin captura de
  puntero/teclado.
- Hover sobre la caja SÍ la atraviesa: `mouseenter` en la página, `teclado -> ON_DEMAND` en el log
  de `rem_chat.py`. Al alejarse sin clic, vuelve a `NONE` — la ventana de abajo recupera el
  teclado.
- Clic en la caja: foco real (`focus` de la página, captura confirmada con `ydotool type` escribiendo
  el texto en la caja — capturado en pantalla, ver `ui_*.png` en el historial de la sesión de
  pruebas). Alejar el puntero MIENTRAS se escribe conserva el foco (no cae a `NONE`) gracias al aviso
  `{tipo:'foco'}` — solo se suelta al perder el foco real de la caja (blur, Enter, Escape).
- Cambio de modo ventana <-> overlay en la misma sesión: ambos arrancan, cargan el VRM, hacen su
  encuadre respectivo y hablan sin errores nuevos — solo se puede tener uno a la vez (ver
  "Instancia única" más arriba).

## Modo overlay: encuadre de medio cuerpo

`CONFIG.overlay.encuadre` (en `rem_avatar.html`) controla el recorte — medido por huesos, mismo
criterio que el encuadre de cuerpo entero del modo ventana (`medirAlturaHuesos()`, ver "Encuadre
del avatar" más arriba), no por `Box3` (que da la mitad de la altura real en un `SkinnedMesh`, ver
esa misma sección). `medirMedioCuerpo()` mide dos cosas, con `vrm.scene.position.y` puesto en 0
durante la medición (mismo fix que `medirAlturaHuesos()`, para no contaminar el centro con el
offset de una pasada anterior — ver "Bug de encuadre" más arriba):

- **Alto**: el tramo desde el hueso `hips` (menos `bajoCaderaFrac` del tramo cadera-cabeza, para
  bajar el corte un poco por debajo de la cintura) hasta el hueso `head` (más `sobreCabezaFrac`,
  margen para pelo/adornos sin hueso propio) — `ocupaAltoFrac` de esa altura en fracción del alto
  visible de la superficie.
- **Ancho**: la mayor distancia lateral al eje de la cadera entre hombros/brazos/manos (con los
  brazos YA en su pose de reposo — ver más abajo, "sin T-pose"), más `anchoExtraFrac` de margen
  (mangas sueltas/volados del vestido no tienen hueso propio y sobresalen de las manos medidas —
  0,18 no alcanzaba, subido a 0,34 tras verlo recortado en captura real).

`recalcularEncuadre()` calcula la altura visible objetivo por las DOS restricciones (alto y ancho)
y usa la MÁS RESTRICTIVA (`Math.max`): en una superficie vertical angosta (420×600, aspect ~0,7) el
cuerpo con los brazos separados es más ancho que alto — ajustar solo por alto (lo que hacía la
primera versión) cortaba los brazos por los costados, confirmado con captura real antes del fix.
El resto de la fórmula (distancia de cámara, `setViewOffset`, `anchorX`/`anchorY`) es la misma que
el modo ventana — `_anclasEncuadre()` decide qué fracciones usar según `ES_OVERLAY`, sin ramificar
el resto del código de encuadre.

**El corte de cadera se apoya en el borde INFERIOR de la superficie**, no centrado — a diferencia
del modo ventana (donde el centro del cuerpo cae en `anchorY`), acá el sobrante vertical (si
`ocupaAltoFrac` deja margen) queda ARRIBA, transparente, no como un hueco entre Rem y la caja de
texto de abajo (`CONFIG.overlay.encuadre.baseSobreBordeFrac`, 0 por defecto).

**Sin T-pose ni clips VRMA: el cuerpo es 100% procedural, congelado en el estado `idle`.**
`estadoCorporal()` devuelve siempre `'idle'` en modo overlay, sin importar el `estado` real (que
sigue variando y sí afecta cara/mirada) — así los brazos quedan en la pose de reposo de
`CONFIG.brazos` (nunca T-pose ni gesticulando) y nunca se dispara `sincronizarClipConEstado()` (que
retorna de inmediato si `ES_OVERLAY`, sin tocar el mixer — no existe mixer en overlay:
`inicializarAnimacionClips()`/`precargarClips()` no se llaman). `getStatePose()`/`updateLook()` y
el guard de `updateSaccades()` para `thinking` leen `estadoCorporal()` en vez de `estado` crudo, por
la misma razón. `window.dispararClipDebug()` (comando `clip` de `bench_chat.py`/paleta
`/animaciones`) es un no-op explícito en overlay, con log, en vez de fallar contra un mixer que no
existe.

**El VRM nace oculto y solo se muestra tras el primer encuadre real** (`vrm.scene.visible = false`
al cargar, `true` recién en `animate()` tras `medirMedioCuerpo()` + `recalcularEncuadre()`) — sin
esto, el frame o dos entre la carga (T-pose, encuadre provisorio por `Box3` con el recorte de
cuerpo entero) y la primera medición real se verían, sobre un fondo TRANSPARENTE, como un parpadeo
feo de la T-pose mal encuadrada. En modo ventana no hace falta (el fondo synthwave ya tapa ese
instante).

**Sin suelo, sin panel de chat.** `crearSueloSynthwave()` no se llama en overlay (`if (!ES_OVERLAY)
crearSueloSynthwave();`) — sin geometría de piso ni niebla, y el renderer usa `alpha: true` +
`setClearColor(0x000000, 0)` en vez del fondo opaco violeta del modo ventana. `crearPanelChat()`
tampoco se llama; en su lugar, `crearOverlayUI()` monta solo el indicador de estado + la caja
(`<html class="overlay">`, fijada por un `<script>` inline en el `<head>`, ANTES del script
principal, para que el CSS `pointer-events:none`/fondo transparente aplique desde el primer frame
sin esperar al módulo — un frame de fondo oscuro sobre el escritorio real sería un parpadeo
visible).

## Modo overlay: push-to-talk (voz de entrada, `stt/`)

Paquete `stt/` (mismo patrón que `llm/`): `base.py` (`STTProvider`, ABC — `transcribir(audio:
np.ndarray) -> str`, sincrónico a propósito, ver su docstring), `local.py`
(`LocalSTTProvider`, faster-whisper; el único provider desde que se quitó el de Groq),
`microfono.py` (`Grabador`, captura con `sounddevice`/PortAudio sobre PipeWire, abierto SOLO entre
`iniciar()`/`detener()`), `__init__.py` (`get_stt_provider()`/`obtener_stt()` — instancia única por
proceso, mismo criterio que `llm.get_provider()`: `REM_STT_PROVIDER` (env) > `[stt].provider` en
`config.toml` > `"local"`).

**`local` (default) corre en CPU a propósito**: la VRAM (4 GB) es para el LLM local (cuando se
decidió, la compartía con RVC, que ya no existe). `config.toml` -> `[stt.local]`: `model="small"`,
`compute_type="int8"`, `device="cpu"`, `language="es"`, `beam_size=1` (decodificación voraz, la más
rápida — ver la comparación de latencia más abajo), `initial_prompt` con vocabulario del proyecto
(Rem, Ollama, Claude, Hyprland, etc., para sesgar nombres propios/técnicos). `WhisperModel.transcribe()`
corre con `vad_filter=True` (recorta silencio antes de decodificar — sin esto Whisper alucina texto
sobre pausas/ruido de fondo) y `condition_on_previous_text=False` (cada push-to-talk es un
enunciado suelto; arrastrar texto previo como contexto solo propaga alucinaciones).

**Precarga igual que la voz**: `rem_chat.py` lanza `stt.precargar_stt()` en un hilo daemon, ANTES de
levantar el servidor, en los dos modos (la voz de entrada es de primera clase, sin flag para
omitirla — mismo criterio que la precarga de la voz). `LocalSTTProvider._lock` (un `threading.Lock`)
serializa carga y transcripciones — mismo motivo que `habla._voz_lock`: la precarga en hilo de
fondo y un primer `ptt_stop` real pueden coincidir.

**Push-to-talk end-to-end**: `rem_ptt.py start|stop` (proceso corto, pensado para atarse a una
tecla mantenida) manda `{tipo:'ptt_start'}`/`{tipo:'ptt_stop'}` por WS al servidor de `rem_chat.py`
y espera una confirmación (`ptt_estado`) antes de salir — nunca falla en silencio: código 0
aceptado, 1 sin conexión/sin respuesta, 2 ignorado (con el motivo impreso). Toda la lógica vive en
`rem_avatar_server.py` (`_ptt_iniciar()`/`_ptt_detener()`), corriendo en `_ws_loop` sin locks (un
solo hilo): `ptt_start` abre `stt.microfono.Grabador` (`asyncio.to_thread`, no bloquea el loop),
manda `ptt_estado: escuchando`; `ptt_stop` lo cierra, descarta grabaciones más cortas que
`[stt].min_grabacion_s` (toque accidental), transcribe (`asyncio.to_thread`), muestra el texto en
la caja/panel (`ptt_transcripcion`; `[stt].mostrar_transcripcion_s` es cuánto lo enseña la
interfaz, no una espera) y a la vez lo corre como un `chat_message` normal
(`_procesar_mensaje_chat(texto, t_ref=...)`) — mismo turno de LLM/voz que si se hubiera escrito, sin
duplicar ese pipeline. Un tope de grabación (`[stt].max_grabacion_s`) se agenda con
`call_later()` al abrir el micrófono, por si se pierde el `ptt_stop` (tecla soltada fuera de foco,
proceso `rem_ptt.py stop` muerto).

**Decisión — `ptt_start` mientras Rem habla: SE IGNORA, no la interrumpe.** Documentado en el
propio código (comentario extenso sobre `_ptt_motivo_ocupada()`): interrumpir exigiría cancelar el
turno de LLM en curso, vaciar la cola de síntesis (Piper corre en un hilo que no se puede
cancelar a mitad) y cortar el `<audio>` del frontend, coordinado entre procesos — mucha superficie
para un beneficio dudoso. Ignorar garantiza lo que sí importa: **el micrófono nunca está abierto
mientras suena la voz de Rem**, así que no puede grabarse a sí misma. `_ptt_motivo_ocupada()`
compone la razón real de "Rem está ocupada" con varias señales, ninguna sola alcanza: turno de LLM
en curso (`_chat_turno_activo`), la cola de síntesis con trabajo pendiente
(`cola._unfinished_tasks` — frases encoladas O en conversión que el worker no marcó todavía),
**algún frontend reportando audio sonando** (`voz_estado`, ver el punto siguiente — necesario
porque el turno de LLM y la síntesis pueden haber terminado mientras el `<audio>` del navegador
sigue sonando) y un margen tras el último fin de habla (`[stt].espera_tras_habla_s`, eco de sala).
El pedido ignorado nunca es silencioso: se difunde `ptt_estado: ignorado` con el motivo, que la UI
muestra como aviso.

**`voz_estado` — el frontend le dice al backend cuándo suena de verdad, no cuándo lo despachó.**
`rem_avatar.html` manda `{tipo:'voz_estado', reproduciendo: bool}` por WS al recibir un audio nuevo
(`true`, en `encolarAudio()` — cierra el hueco entre que el servidor lo despacha y que el
`<audio>` realmente empieza a sonar) y al vaciarse la cola (`false`, en `_avanzarCola()`).
`_registrar_voz_estado()` en el servidor mantiene `_ws_reproduciendo` (el set de websockets con
audio sonando) y marca `_ultimo_fin_habla` al vaciarse — de ahí sale `espera_tras_habla_s`.

**Casos límite probados en vivo, no solo el camino feliz**: toque muy corto (`start`+`stop`
inmediato) descarta la grabación por `min_grabacion_s` sin transcribir nada; un `ptt_stop` SIN
`ptt_start` previo (huérfano — puede pasar si el `stop` de un toque corto de verdad llega ANTES que
su propio `start`, dos procesos `rem_ptt.py` distintos) ahora SIEMPRE contesta con el estado actual
(antes se quedaba mudo y `rem_ptt.py` esperaba el timeout de 2s sin respuesta — bug real encontrado
durante la prueba, arreglado agregando un `ptt_estado` explícito en esa rama); ese mismo huérfano
sirve de guarda contra la carrera de un toque muy corto (`_ptt_stop_huerfano_t`, ventana de 0,5s):
un `ptt_start` que llega justo después de un `stop` huérfano se ignora también (`"toque muy corto"`)
en vez de abrir el micrófono y dejarlo grabando hasta el tope; `ptt_start` repetido mientras ya se
está grabando/transcribiendo se ignora con el motivo correspondiente.

**Mediciones en vivo, esta máquina** (RTX 3050, `faster-whisper` "small" int8 en CPU; frases de
prueba sintetizadas con `edge-tts` e inyectadas por un sumidero nulo de PulseAudio/PipeWire —
`module-null-sink` + `PULSE_SOURCE=<sink>.monitor`/`REM_MIC_DEVICE=pulse` — para no depender de
hablar de verdad frente al micrófono real, y reproducibles):
- **Latencia de STT** (duración del audio vs. tiempo de transcripción, `beam_size=1`): factor
  ~0,17-0,38× tiempo real — una frase de ~4s tarda ~1,1-1,3s en transcribir. Cargado el modelo, la
  primera transcripción real de la sesión no paga penalidad de arranque en frío (la precarga ya
  hizo una de calentamiento).
- **Tiempo total, soltar la tecla -> primer audio de Rem SONANDO** (no solo despachado — mide hasta
  el evento `voz_estado: true` real): ~6-9s para una respuesta corta de Claude, dominado por el
  turno de LLM + TTS/RVC de la primera oración, no por el STT (que es la porción más chica,
  ~1-1,3s de esos 6-9s). `habla.TurnoHabla` ahora acepta un `t_ref` opcional (el instante en que se
  soltó la tecla, pasado por `_ptt_detener()`) para que el log de "primer audio enviado" muestre
  las dos cifras: desde que arrancó el turno de LLM, y desde que el usuario soltó la tecla — la
  segunda es la que le importa a la latencia percibida.
- **RAM de faster-whisper** (`/proc/self/status`, VmRSS): proceso recién importado ~38 MiB ->
  provider creado sin modelo ~40 MiB -> modelo "small" int8 cargado + calentado ~900 MiB (pico
  ~1,4 GiB durante la carga) -> tras transcribir, estable en ~960 MiB. Con RVC + Ollama ya cargados
  en el proceso real de `rem_chat.py`, el total medido en vivo (`faster-whisper` cargado dentro del
  mismo proceso) llegó a ~4 GiB de RSS del proceso Python — RAM del sistema (23,6 GiB en esta
  máquina), no VRAM: no compite con la calibración de `num_gpu`.
- **Micrófono real**: `sounddevice.InputStream` abre en ~2ms sobre PipeWire (medido con el
  dispositivo predeterminado del sistema). No se pudo grabar audio real de una persona hablando
  frente al micrófono en esta sesión (el `@DEFAULT_SOURCE@` del sistema está silenciado —
  `pactl get-source-mute` devuelve `yes`, una configuración preexistente de la máquina, no algo que
  tocara esta implementación) — por eso las mediciones end-to-end de arriba usan el sumidero nulo.
  El camino de código es el mismo (`Grabador` no distingue el origen); si el mute se destraba, no
  hace falta cambiar nada para que capture voz real.

## Líneas de Hyprland para push-to-talk (SUPER+H mantenida)

No se edita `hyprland.conf` desde el código — son las líneas a agregar a mano. **Son TRES**, y la
tercera es `bindrt`, no `bindr`:

```
bind   = SUPER, H,       exec, /mnt/extra/rem/Rem/venv/bin/python /mnt/extra/rem/Rem/rem_ptt.py start
bindr  = SUPER, H,       exec, /mnt/extra/rem/Rem/venv/bin/python /mnt/extra/rem/Rem/rem_ptt.py stop
bindrt = SUPER, Super_L, exec, /mnt/extra/rem/Rem/venv/bin/python /mnt/extra/rem/Rem/rem_ptt.py stop
```

`bind` (sin `r`) dispara al PRESIONAR, `bindr` al SOLTAR — juntas dan un push-to-talk real sin un
daemon aparte escuchando teclado. **Por qué la tercera**: `bindr = SUPER, H` solo dispara si SUPER
sigue pulsada al soltar H. Si se suelta Super ANTES que H (pasa sin darse cuenta), ese `stop` nunca
llega y la grabación quedaba abierta (pasó en una prueba real: 18 s hasta pulsar otra vez).
`bindrt = SUPER, Super_L` manda el `stop` también al soltar Super. Es inocuo si ya se mandó: un
`ptt_stop` sin grabación en curso se contesta con `ptt_estado: idle` ("no estaba grabando") y no
hace nada más. Efecto colateral aceptado: cada vez que se suelta Super (con o sin H) se lanza un
`rem_ptt.py stop` corto. La guarda de "toque muy corto" (`_ptt_stop_huerfano_t`, que ignora un
`start` llegado justo después de un `stop` huérfano) se bajó de 0,5 s a 0,3 s por eso: con este
tercer bind los `stop` huérfanos son frecuentes, y 0,5 s se comía un SUPER+H pulsado justo después de
otro atajo con Super.

**Tiene que ser `bindrt`; `bindr` y `bindir` NO sirven — medido, no supuesto.** Se probaron seis
variantes de un bind de release sobre el propio modificador (`bindr`/`bindir`/`bindrt`, con y sin
modificador en la definición) con una tecla mantenida detrás. Con el modificador solo, disparan
casi todas; **con otra tecla ya pulsada bajo ese modificador (el caso real: SUPER+H), solo dispara
`bindrt`**. La `t` es "transparent, cannot be shadowed by other binds": el bind de SUPER+H ya
consumió la tecla y "tapa" a los demás binds de release del mismo modificador. Un `bindr = SUPER,
Super_L` normal (lo que se documentó primero, sin probar) no corta nada.

**Un `ptt_stop` solo corta la grabación que abrió el mismo pulsador** (2026-11-06): `rem_ptt.py` manda
`origen: "tecla"` y mantener el botón 🎙 del chat, `origen: "boton"` (sin origen cuenta como tecla). Una
grabación automática (toque del botón o modo conversación) no la corta ningún `ptt_stop`, solo su
detector u otro toque. Motivo, visto con el micrófono real: el `bindrt` de soltar Super manda un
`stop` cada vez que se suelta Super por cualquier cosa, y cortaba una grabación del botón a los
0,15 s («sin_voz»). Un stop ignorado se contesta solo a quien lo mandó (`ptt_estado: escuchando` con
la nota) y queda en el log (`[PTT] stop de tecla ignorado: la grabación es automática (boton)`).

**Red de seguridad independiente de las teclas**: `[stt].max_grabacion_s` (30 s por defecto, en
`config.toml`) — `_ptt_iniciar()` agenda un `call_later()` al abrir el micrófono que cierra Y
transcribe solo, pase lo que pase con las teclas. Un `ptt_stop` que llega después del tope es
huérfano e inocuo.

**Verificado en vivo** (Hyprland real, teclado virtual de `ydotool`, audio inyectado por un sumidero
nulo de PipeWire para no depender del micrófono, que en esta máquina está silenciado a nivel
sistema). Se usaron binds temporales en memoria (`hyprctl keyword`, ya retirados) sobre
**CTRL + código 191 (F13)** en lugar de SUPER+H, porque `Super_L` tiene un bind propio de caelestia
(`bindi = Super, Super_L, global, caelestia:launcher`) y inyectar SUPER habría abierto el lanzador en
el escritorio en uso. El mecanismo de Hyprland es el mismo (solo cambia la máscara de modificador),
pero **la interacción concreta con el lanzador de caelestia no se probó**. Resultados:
- Control, solo `bind`+`bindr` de la tecla: pulsar, soltar el modificador primero y después la tecla
  → la grabación siguió abierta (3 s después de soltar el modificador y 3 s después de soltar la
  tecla) hasta un `stop` manual. Reproduce el fallo real.
- Con el tercer bind como `bindr`: igual, no corta. Con `bindrt`: la grabación termina al soltar el
  modificador aunque la tecla siga pulsada (3,86 s de audio, transcribe, responde).
- Orden normal (tecla primero, modificador después) con los tres binds: una sola grabación, una sola
  transcripción, sin efectos dobles (el segundo `stop` llega huérfano y se ignora).
- Tope de duración: con `max_grabacion_s = 6` (temporal), `start` sin ningún `stop` → a los 6 s
  exactos `tope de 6s alcanzado`, transcribe y responde; un `stop` posterior contesta "no estaba
  grabando".

## Precarga de Ollama al arrancar, y por qué el tok/s real varía tanto

**Precarga**: `rem_chat.py` lanza `llm.precargar_provider()` en un hilo de fondo junto a las de la voz y
STT. Con Ollama llama a `OllamaProvider.precargar()` — una petición a `/api/chat` con `messages`
vacío (Ollama carga el modelo y responde `done_reason: "load"`, sin generar). Tiene que llevar las
MISMAS `options` (`num_gpu`, `num_ctx`...) y `keep_alive` que las peticiones reales: Ollama recarga
el modelo si cambian las opciones de carga, y una precarga con otros valores no serviría. Con
Claude no hace nada. No bloqueante: si falla solo lo loguea (`[LLM] precarga falló`). Medido: el
modelo carga en ~4 s en paralelo con RVC y Whisper, sin OOM de VRAM (3238 MiB usados con los tres), y
el primer turno reporta `carga del modelo: 1ms` (antes ~6,7 s). Ojo: `keep_alive = "10m"` sigue
descargando el modelo tras 10 min sin uso, y el primer turno de después vuelve a pagar la carga; la
precarga solo cubre el arranque. El log por turno de `[Ollama]` ahora incluye los tokens/tiempo del
prompt y los tok/s de generación.

**La precarga también evalúa el prefijo fijo** (`chat_sesion.precargar_prefijo(tools)`, lanzado por
`rem_chat.py` con `acciones.tools_disponibles(MODO)`): system + tools + ejemplos de tono + memoria
larga, más un mensaje de usuario de relleno y `num_predict: 1`. Así ese prefijo queda en la caché KV
de Ollama y el primer turno solo evalúa lo nuevo. Para que la caché pegue, el prefijo tiene que
serializarse idéntico al de un turno real: `OllamaProvider._payload()` lo arman `stream_chat()` y
`precargar()` con el mismo código, `chat_sesion._prefijo_fijo()` lo comparten `procesar_turno()` y la
precarga, y las **tools tienen que ser las del modo activo** (el template del modelo las mete en el
bloque system; ventana y overlay ofrecen tools distintas). `num_predict` no es opción de carga: no
provoca recarga del modelo.
Medido (2026-09-27, con corriente, GPU P0; modelo descargado entre corridas, A/B alternados, 4 rondas,
primer turno "Hola, Rem." con las tools de ventana, ~1913 tok de prompt): precarga vieja (solo carga)
→ 1er token a **~2,0 s** (prompt evaluado en ~1970 ms); precarga con prefijo → 1er token a **~0,29 s**
(~256 ms). La precarga tarda ~2 s más (3,7 s vs 1,7 s), pero en segundo plano. Sigue valiendo lo de
`keep_alive`: tras 10 min sin uso el modelo se descarga y el primer turno de después paga carga y
prefijo.

**El "5 tok/s del primer turno" NO era Whisper ni competencia por núcleos.** Investigado con un banco
directo contra Ollama (mismo payload que `OllamaProvider`, prompt real de ~1170 tokens):
- **Whisper no compite en régimen estable**: con `faster-whisper` transcribiendo en bucle continuo
  (peor caso, `cpu_threads` 0/2/1) los tok/s de Ollama quedaron dentro del mismo rango que sin él
  (6,0-6,3 con Whisper, 6,6 sin). En el uso real ni siquiera coinciden: la transcripción termina
  ANTES de que empiece el turno de LLM, y un `ptt_start` mientras Rem responde se ignora. No se
  tocó `cpu_threads` de faster-whisper (nada que limitar).
- **Tampoco los hilos de CPU**: `num_thread` = default/4/8/12 dan 6,5-6,6 tok/s, idénticos. La
  decodificación no está limitada por los núcleos.
- **Causa medida: estado de energía de la GPU.** Durante la generación la GPU sube un instante a P3
  (memoria a 5470 MHz, ~19,7 tok/s la primera generación corta) y enseguida cae a **P5 con memoria a
  810 MHz y PCIe gen 2** (de gen 4) — y ahí se queda: ~6,6 tok/s constantes, un valor tan estable
  que delata un tope fijo, no ruido. La decodificación con 24 capas en GPU está limitada por ancho de
  banda de memoria. `nvidia-smi -q -d PERFORMANCE` reporta `SW Power Cap: Active` y `SW Thermal
  Slowdown: Active`, y **el portátil estaba en batería** (`ACAD online=0`, `BAT1 Discharging`, 29%).
  Una carga CUDA concurrente (imitando a RVC) no la saca de P5.
- **Verificado con corriente conectada** (el equipo se enchufó a mitad de la sesión, batería 16-19%
  cargando): la GPU pasa a **P0, memoria a 6001 MHz, PCIe gen 4**, y Ollama da **21,7-22,2 tok/s
  estables** (5 generaciones seguidas, banco directo) y ~20 tok/s por `rem_chat.py` — 3,3× lo de
  batería, y coincide con la tabla de calibración de `num_gpu` (20,7). O sea: en batería ~6,6 tok/s,
  con corriente ~20-22. Los ~16-17 tok/s de aquella corrida de `rem_chat.py` en batería siguen sin
  causa confirmada (no se muestreó la GPU). Forzar relojes en batería (`nvidia-smi -lmc`) requiere
  root y no se hizo.
- **Ninguna medición de tok/s sin este dato**: el log `[Ollama]` de cada turno ahora termina con
  `energía: AC (batería 18% cargando) | GPU P0→P0 (mem 6001 MHz)` (`llm/_energia.py`: `/sys/class/
  power_supply` + `nvidia-smi`, de mejor esfuerzo — `n/d` si no están). La GPU se muestrea al llegar
  el primer token y al terminar (`P3→P5`: sube a P3 un par de segundos y luego cae; mirar solo uno
  engaña). También va en `Done.usage` (`energia`, `gpu_pstate_inicio/fin`, `gpu_mem_mhz_fin`).

## Contexto dinámico condicional, historial limpio y prompt sin acciones (rem_chat: ventana Y overlay)

Un "Hola, Rem." recibía respuestas como "tu disco está casi lleno" (medido: **6 de 6**) y, en otra
prueba, leía los 11 GB de RAM como espacio en disco. Causa: el bloque volátil que se anteponía a cada
mensaje (`[ESTADO ACTUAL DE LA PC: … Disco /: 13.8 GB libres]`) y ~665 de los ~1020 tokens del system
prompt (catálogo de acciones JSON, reglas de seguridad, instrucción de "MEMORIA DEL SISTEMA"), que
empujaban a un modelo de 4B a hablar de discos, archivos y comandos. Cambios, todos en el camino
compartido `chat_sesion.procesar_turno()` (ventana y overlay lo usan igual):

1. **Contexto condicional, con palabras clave en `config.toml` -> `[contexto]`.** Cada línea tiene su
   modo (`linea_pc`, `linea_fecha`: `"condicional"` | `"siempre"` | `"nunca"`) y su lista
   (`palabras_pc`, `palabras_fecha`), con coincidencia por palabra completa/frase sin distinguir
   mayúsculas ni tildes (`"ram"` no salta con "programa"; `personalidad.palabra_clave_pc()`). Sin
   ninguna coincidencia el mensaje va tal cual, sin bloque alguno. `memoria_sistema` (archivos/carpetas
   conocidos) ya no se inyecta en rem_chat: solo servía a las acciones de búsqueda, que rem_chat no
   ejecuta. La línea de PC, cuando se inyecta, va sin la hora duplicada ni el `[PC]` anidado y con
   etiqueta neutra (`obtener_info_pc()`). Cada turno loguea `[Contexto] fecha|PC|nada`.
   Como bonus, `obtener_info_pc()` (0,2 s de `cpu_percent`) ya no corre en cada turno.
   **Después se quitó la línea de PC del todo** (`linea_pc`/`palabras_pc` ya no existen): aun
   condicional, el modelo sacaba la PC/RAM en saludos. Ahora es la tool `estado_pc`, que el modelo
   llama solo si le preguntan. Solo queda la línea de fecha (`palabra_clave()` hace la coincidencia).
2. **La fecha también es condicional — decidido con datos.** Se probó primero una variante con SOLO
   fecha/hora (sin la línea de PC): 0 de 6 derivaban. Pero por el pipeline real (`chat_message` por WS,
   prompt sin acciones) la fecha se leyó en voz alta sin que nadie la pidiera en 1 de 5 y 1 de 12
   respuestas a "Hola, Rem." (~2 de 23, ≈9%). La regla acordada era "si no desvía, la fecha va siempre": no se cumplía del todo, así que
   `linea_fecha = "condicional"` (palabras: hora, fecha, día, hoy, mañana, ayer, semana, mes, año…).
   **Desde 2026-11-05 los disparadores son solo preguntas explícitas** ("qué hora", "hora es", "qué
   día es", "a cuántos estamos", "día de la semana", "qué año es"...): con palabras sueltas ("hoy",
   "día", "tarde") la fecha se colaba en charla normal y Yoru la recitaba.
   Volver a "siempre" es una línea de config.
3. **El historial guarda solo el texto del usuario.** Antes cada turno se guardaba con su bloque de
   fecha/PC pegado y lo arrastraba para siempre (datos caducos que el modelo terminaba comentando). Ahora
   `procesar_turno()` anexa `Message(user, texto)` al historial y arma aparte, solo para ese turno, la
   copia del último mensaje con el contexto. Verificado con un provider falso que captura lo enviado:
   historial limpio, cero mensajes anteriores con `[FECHA`/`[ESTADO`.
4. **Sin el bloque ACCIONES DEL SISTEMA + REGLAS DE SEGURIDAD + MEMORIA DEL SISTEMA** en el prompt
   de rem_chat. Prompt de un "Hola": **1166 → ~416 tokens**. (Primero era un recorte opcional,
   `con_acciones=False`; al eliminar `Rem.py`, su único otro usuario, el bloque se borró del texto.)

**Medido (el modelo tiene temperatura 0,7; muestras chicas, es evidencia, no prueba)**, 6 × "Hola, Rem.":
prompt completo + contexto completo: 6/6 comentan PC/disco. Sin acciones pero con contexto completo:
5/6. Sin acciones y sin contexto: 0/6. Solo fecha/hora: 0/6 en el banco directo, pero ~2/23 leyéndola en voz alta por el pipeline real. Con
ambas líneas condicionales (pipeline real, 12 × "Hola, Rem."): 0/12 mencionan la fecha, 0/12 datos de
PC. Y las preguntas que sí las necesitan funcionan: "¿Qué hora es?" → "Es 16:55"; "¿Cuánta RAM estoy
usando?" → "12.5 GB" (real: 12); "¿el disco?" → "13.8 GB libres" (real: 14 G). Lo que sigue pasando (el modelo inventa
charla técnica: "los logs del servidor", "¿ya actualizaste el kernel?") **no viene del contexto**: es
el propio modelo de 4B con la personalidad técnica.

### Acciones del sistema en rem_chat (`acciones.py`)

rem_chat ejecuta acciones por **tool calling nativo** (`stream_chat(tools=...)`), no por JSON en el
texto (que en modo voz se leería en voz alta). `acciones.py` tiene 4 tools: `abrir_programa` (solo
resuelve contra `.desktop` instalados, nunca ejecuta un nombre arbitrario), `apagar_pc` (con
confirmación; no se ofrece en overlay), `buscar_en_navegador` y `buscar_archivos`. Si el modelo pide
una tool, `procesar_turno()` descarta el texto que la acompañe y habla la respuesta de
`acciones.ejecutar_tool_async()`. `bench_chat.py` llama a `procesar_turno()` **sin** `tools=`.

**`estado_pc` y `calcular` se quitaron (2026-11-05)**: con las tools en cada turno, el modelo de 4B las
llamaba sin motivo — "me despidieron del trabajo" → `estado_pc` en 2 de 2, "examen de cálculo" →
`calcular` ("Da 30."), y después imitaba esas cifras de CPU/RAM en respuestas normales. Su código
(evaluador AST de `calcular` incluido) está en git hasta el commit anterior a ese cambio. `psutil` salió
de `requirements.txt` (nada más lo usaba). La regla HERRAMIENTAS ahora dice "No ves el estado de la PC:
nunca inventes esas cifras".

**Tools bajo demanda** (`chat_sesion.pide_herramientas()`): las tools solo se le mandan al modelo si el
mensaje contiene un disparador de `config.toml` → `[herramientas].disparadores` (palabra completa, sin
tildes; `"busca*"` acepta cualquier terminación; formas verbales a propósito: `lanza`/`lanzar*`, no
`lanza*`, que pegaba con "lanzamiento"). Se loguea `[Tools] sí, por 'abre*'` / `no`. Prefijo medido:
**1597 tok sin tools, 2126 con tools** (antes 2374 siempre, con 6 tools). Alternar no rompe la caché:
Ollama conserva los dos prefijos, y solo la primera aparición de cada variante paga la evaluación
completa (~0,9 s sin tools, ~1,7 s con tools); después cada turno evalúa en ~130 ms alterne o no.
Por eso `precargar_prefijo()` calienta las dos variantes. Además el **final del system prompt** cambia con la
variante (`construir_prompt_sistema(con_herramientas=)`): con tools lleva la regla HERRAMIENTAS; sin
tools, una sola línea ("solo hablas; no ofreces hacer nada en la PC ni fuera de ella"). Prefijo: **1518
tok sin tools, 2133 con tools**; la caché se comporta igual (cada variante paga su primera evaluación,
1,4 s / 1,85 s en frío, y luego ~140-165 ms alternando). Ofrecimientos de acciones no pedidas: 10 de 20
turnos largos con la regla siempre presente → 1 de 34 turnos con la línea de "solo conversas". Banco del 2026-11-05 (33 turnos): tools
ofrecidas 1 vez ("abre steam" → `abrir_programa`), 0 llamadas espurias. Efecto secundario visto: sin
tools en una conversación larga, Yoru empieza a ofrecer acciones que no tiene ("si quieres que busque
X, dímelo", "déjame ver la lista de paquetes") y el patrón se repite turno a turno.

**Marcas en el texto** (`chat_sesion._quitar_marcas()`): el modelo a veces escribe como texto una tool
call o una etiqueta inventada (`[ENJOYED abrir_programa('steam')]`). Un filtro del stream quita todo
lo que va entre corchetes y las llamadas tipo `nombre_con_guion('...')` o `nombre('...')` antes del
chat, la voz y el historial, y lo loguea (`[Marcas] quitado de la respuesta ...`). Retiene solo la
última palabra (o un `[` abierto) hasta ver qué la sigue. Probado con 500 particiones aleatorias de
cada caso: resultado idéntico. `_para_voz()` aplica la misma limpieza como red de seguridad. Efecto
aceptado: un `print('hola')` en una explicación técnica también se quita.

**Prueba con stubs (2026-09-27, histórica: aún con 6 tools siempre presentes)**: las tools con efectos
(abrir/apagar/navegador/archivos) se reemplazan por stubs; `estado_pc`/`calcular` corren de verdad.
15/15 llamadas correctas (2 por tool con efectos, 4 `estado_pc`, 3 `calcular` con el resultado
correcto). Controles sin tool: 5/6 — "abrí tu mente, parce" abrió un programa (el falso positivo
con modismos ya conocido). `calcular` ×3 con 12×7, 15 % de 240 y 3 GiB en MiB: 9/9 (`12*7`,
`240*0.15`, `3*1024`). Caché: el prefijo (system + tools + ejemplos) se serializa idéntico entre
turnos; tras la precarga, cada turno evalúa ~2330 tok en 244-459 ms (en frío: 2271 ms).

El resto del catálogo viejo (`ejecutar_comando`, mover/copiar/eliminar, volumen, captura, etc.) se
eliminó con `Rem.py` (recuperable del commit del 2026-09-22, «feat: portar 4 herramientas del ejecutor de acciones a rem_chat (tool calling nativo)»). Si se porta algo de ahí:
- **Auditoría de seguridad propia del nuevo contexto**, no solo mover código: en rem_chat la entrada
  también llega por VOZ (STT), es decir, texto que puede venir mal transcrito o de audio ajeno; la
  confirmación tiene que funcionar en GTK/overlay (¿cómo confirma una acción destructiva una
  superficie click-through con una caja de texto?); y la regla "toda acción destructiva pasa por
  confirmación" no puede degradarse por comodidad.
- Actualizar la regla "HERRAMIENTAS" de `personalidad.py` para que liste lo que existe.

    # IMPORTANTE: 
    AL MOMENTO DE HACER COMMIT NO PONGAS TU AUDITORIA Claude/Anthropic DETRO DEL COMMIT

## Recorte del historial (num_ctx) — `tokens_contexto.py`

**Qué hace Ollama si el turno no cabe** (verificado 2026-11-05, Ollama 0.33.3, num_ctx 4096: system con
un secreto, un ejemplo con otro, 40 pares de relleno): conserva el mensaje de system pero descarta los
mensajes más viejos, que son **los ejemplos de tono** (el modelo recordaba el secreto del system y había
perdido el del ejemplo), y llena hasta ~3968 tok sin dejar sitio a la respuesta. Por eso
`procesar_turno()` recorta antes: `PresupuestoContexto.recortar()` quita turnos completos del principio
del historial (un user + sus respuestas) hasta que prompt + 400 tok de margen quepa en num_ctx. Nunca
toca system, tools, ejemplos ni memoria larga, ni el último mensaje. Solo con providers que exponen
`num_ctx` (Ollama).

- **Sin llamadas extra por turno**: Ollama no tiene `/api/tokenize`, y tokenizar con otra petición
  evicta la caché KV. El costo del prefijo fijo sale exacto del `prompt_eval_count` de la respuesta
  anterior (incluye lo cacheado: medido, 819 tok las dos veces con 640 → 74 ms); el historial se estima
  por caracteres con una razón chars/token recalibrada con cada respuesta (`eval_count`). Costo: ~0,45 ms.
  Error medido (40 turnos): ±30 tok en régimen, hasta -84 justo tras un recorte grande.
- **Histéresis de 600 tok**: quitar el turno más viejo invalida la caché KV de todo el historial. Sin
  histéresis se recortaba un par por turno y cada turno pasaba de ~0,8 a ~2 s; con ella, un recorte
  grande cada varios turnos.
- `venv/bin/python tokens_contexto.py` imprime el desglose exacto del prefijo (system, ejemplos, cada
  tool); con rutas de archivo como argumentos, cuenta sus tokens. Usa el tokenizador real vía Ollama
  (evicta la caché KV: nunca dentro de un turno).

## Modo serio y tope de oraciones (2026-11-05)

**Modo serio detectado en código**, como la fecha: `config.toml` → `[modo_serio]` tiene `disparadores`
(muerte, ruptura, despido, soledad, estrés/ánimo; frases, no "solo" suelto) y `excepciones` ("personaje",
"jefe", "partida", "juego"...: "se murió mi personaje" no dispara). Si dispara, `procesar_turno()` pega
`instruccion_modo_serio(categoria, texto, glosario)` (91-95 tok; 106 con glosa, entre corchetes) al
final del último mensaje, solo en ese turno: no toca el prefijo cacheado ni queda en el historial (el
turno serio evaluó el prompt en ~140 ms, como cualquier otro). En el system queda una línea ("cuando algo
le duele de verdad, cambias de tono"). Con la regla larga siempre en el system, 0 de 5 frases serias
salían bien.

**Un ejemplo fijo por categoría** (`[modo_serio.categorias]`: muerte, ruptura, trabajo, soledad, estres;
gana la primera que coincide; `chat_sesion.EJEMPLOS_MODO_SERIO`), escrito genérico para que encaje aunque
el modelo lo copie literal, que lo hace en ~60 % de los turnos serios. `[modo_serio].glosario` añade
aclaraciones si el mensaje las contiene ("«la u» es la universidad": antes leyó "la uva"). Historia
(2026-11-05, 6 frases serias que no están en los ejemplos × 2, fondo clasificado a mano):

| Variante | Copias literales | Fallan en el fondo |
|---|---|---|
| Un ejemplo fijo para todo | 4/6 | 0/6 |
| 4 ejemplos rotando al azar | 10/12 | 6/12 (copiaba uno que no venía al caso) |
| Sin ejemplo | 0/12 | 8/12 (juzga, y cita situaciones de los ejemplos de tono) |
| **Uno por categoría** (actual) | ~14/24 | ~1-2/24 |

**"…pero al menos…" — corrección**: se atribuyó a la frase "no le buscas el lado bueno" (8 en 20 turnos
con ella, 1 sin ella), pero dos corridas idénticas posteriores dieron 8 y 1. Es variación entre corridas
(temperatura 0,7), no un efecto medido. La frase sigue fuera, sin evidencia de que importe. Lo mismo con
la jerga: 6 de 20 turnos en una corrida, 1 de 20 en las dos siguientes, sin cambiar nada.

**Tope de oraciones** (`[respuesta].max_oraciones`, 3): `_limitar_oraciones()` corta el stream al
completar la N-ésima oración (mismo criterio que `llm/sentence_splitter`) y emite
`Done(reason="limite_oraciones", usage=None)`. El cierre baja filtro por filtro hasta `stream_chat()`
(decorador `_cierra_entrada`: salir de un `async for` no cierra el generador de entrada) y Ollama
cancela la generación (`srv stop: cancel task` en su log). Lo cortado no llega al chat, a la voz ni al
historial. Esos turnos no calibran el presupuesto de contexto (no hay `prompt_eval_count`). Medido en la
conversación larga: 5 cortes en 20 turnos, media 2,8 oraciones y máximo 3 (antes: media 2,9, máximo 4, y
respuestas de dos párrafos).

**Tests**: `venv/bin/python tests/test_filtros_texto.py` — etiqueta de emoción (al inicio va a la cara;
a mitad de texto la quita `_quitar_marcas`), marcas, un solo párrafo, bloques de código, tope de
oraciones, `_para_voz()` y detección del modo serio (categorías, glosa, falsos positivos).

**Bloques de código ```** : en el chat y el historial no se toca nada de lo que va dentro (ni saltos de
línea, ni marcas como `arr[0]`/`print('x')`); `_quitar_marcas` retiene un bloque abierto hasta que se
cierra, `_un_parrafo` aplana solo lo de fuera (una lista fuera de un bloque sí se aplana) y conserva el
salto de antes y después de cada bloque, y `_limitar_oraciones` no cuenta los puntos de dentro. La voz
lo aplana todo. Bugs encontrados al escribir el test: `$` en Python también casa antes de un `\n` final
(se cortaba la valla de cierre "```\n"; ahora `\Z`), y los ``` del final se cuentan en múltiplos de 3. Los casos de stream se prueban con 300 particiones aleatorias: el texto
y lo registrado en el log tienen que salir idénticos en todas.

## Ejemplos de tono (few-shot) — `ejemplos_tono.py`

> **Histórico**: las mediciones de abajo (jerga, "chimba", tú/vos...) son de la personalidad paisa,
> reemplazada el 2026-11-04 por Kuroki Yoru (ver "Personalidad" más arriba). El mecanismo
> (orden del prefijo, caché, sin ejemplos en eco) sigue igual.

`EJEMPLOS_TONO` (turnos user/assistant falsos, 8 pares) define el tono de Yoru en vez de describirlo
en el prompt. `chat_sesion.procesar_turno()` arma cada turno así:

```
system (fijo) → EJEMPLOS_TONO → memoria larga (si hay) → historial → [contexto dinámico + último mensaje]
```

**Ningún mensaje de usuario de los ejemplos cuenta algo de la vida de Esteban** (2026-11-05): como turnos,
el modelo los tomaba como cosas que le habían pasado ("tu perro murió y tu novia te dejó"). Los 3 pares
serios (perro, ruptura, soledad) se quitaron: los cubre el modo serio con su ejemplo por categoría. "Este
finde voy a una fiesta" y "mañana empiezo a estudiar" pasaron a preguntas ("¿qué opinas de las
fiestas?", "¿está mal dejar las cosas para mañana?").

Medido con el mismo banco, 2 corridas por variante (hola ×5, halago, gracias, teclado, JavaScript, 10
turnos de conversación y 5 preguntas tipo "¿qué sabes de mí?"):

| Variante | Prefijo + "hola" | "hola" distintos | Copias de un ejemplo | Citan hechos de los ejemplos | "procrastinas" |
|---|---|---|---|---|---|
| Turnos, ejemplos con hechos (antes) | 1408 tok | 10/10 | 1/48 | 3/10 | 7/10 |
| Ejemplos dentro del system + regla "solo sabes lo que te dijo" | 1477 | **1/10** | 19/48 (5 primeras palabras) | 0-1/10 | 0/10 |
| **Turnos sin hechos personales** (actual) | **1296** | 10/10 | 1/48 | 0/10 | 0/10 |

Probado y descartado por el camino: un mensaje separador tras los ejemplos (3/10 citan hechos), la regla
"solo sabes lo que te dijo" con los ejemplos como turnos (7-9/15: le hace listar los ejemplos como cosas
que le contaste), y los ejemplos dentro del system (no los cita, pero los usa como tabla: "hola" → la misma
respuesta 10 de 10 veces, y parte las respuestas en líneas el 25-35 %, de ahí `_un_parrafo`). "procrastinas"
venía de la frase del system "si él procrastina…", reformulada a "si lo ves aplazando algo…". Lo que sigue
saliendo en "¿qué sabes de mí?" son caracterizaciones sacadas del propio personaje ("eres un npc con skill
issue"), no hechos de los ejemplos.

- **system + ejemplos es idéntico byte a byte en cada turno** — es el prefijo que reusan las cachés.
  Ollama cachea por prefijo solo; para Claude, el último ejemplo lleva `Message.fin_prefijo_cache=True`
  y `ClaudeProvider` pone ahí un segundo `cache_control`.
- **La memoria larga no va en el system prompt** (`construir_bloque_memoria()`, como mensaje aparte
  tras los ejemplos): así un cambio de memoria no invalida system + ejemplos.
- **El contexto dinámico sigue pegado al ÚLTIMO mensaje, no antes del historial**: si fuera antes, cada
  turno que lo trae invalidaría la caché de todo el historial.
- **Sin ejemplos en modo eco** (`isinstance(sesion.provider, EchoProvider)`, cubre también
  `REM_LLM_PROVIDER=echo`).

**Medido (Ollama, Qwen3.5-4B, con corriente, GPU P0)**: system prompt 733 → 659 tok; ejemplos 519 tok;
prefijo fijo ~1178 tok. Primer turno en frío: 1er token a 946 ms → 1611 ms (+0,66 s, solo se paga una
vez por carga del modelo). Conversación nueva con el prefijo cacheado: 1195 tok evaluados en ~280 ms
(antes: 750 tok en ~270 ms) — la caché pega y el costo extra en caliente es ~nulo. Tool calling con
`tools=` (camino del panel): 15/15 llamadas correctas con ejemplos (13/15 sin ellos).

**Medido con carga emocional (2026-09-27, `bench_chat.py` sin tools, 3 rondas × 8 mensajes
independientes, con `reset` entre cada uno)**: 5 mensajes emotivos ("ya me funcionó todo!!", "se me
borró el proyecto entero", "quiubo rem", "este bug me tiene mamado", "gané la partida") + 3 neutros.
Groserías: "gonorrea" en 3 de 24 (2 son la copia literal de abajo). "mamado"/"mames" en 3, pero solo
como eco de la palabra del usuario. Jerga ("parce", "quiubo", "pues", "qué boleta", "pa") en 7 de 24:
6 de 15 en los emotivos y 1 de 9 en los neutros. **"quiubo rem" copió literal** la respuesta del
ejemplo en 2 de 3 (es el mismo input que el ejemplo); hay copias parciales ("¡Uy, qué alivio,
parce!", "qué boleta" usado fuera de lugar, una mención de la vram sacada del ejemplo). Salida
completa en `pruebas_voz/tono_paisa/bench_emocional_2026-09-27.txt`.

**Segunda pasada, con permiso explícito de jerga en QUIÉN SOS** (system 654 → 740 tok; además el
ejemplo "quiubo rem" pasó a "quiubo, qué más" y "qué boleta" a "qué mamera"). Mismos 24 mensajes:
"gonorrea" genuina 2/24 (antes 1, más 2 copias); sin ecos de "mamado" (antes 3); jerga en 12/24 (12 de
15 emotivos, 0 de 9 neutros; antes 6/15 y 1/9); 0 copias literales (antes 2), aunque "¡Uy, qué
chimba! Ya era hora" es casi el ejemplo del lipsync; mezclas tú/vos 2/24 (antes 1). Problemas nuevos:
"qué chimba" celebrando que se borró el proyecto (2 de 3), el saludo trae la PC/RAM sin que nadie la
mencione (3 de 3), y 12×7 mal en 2 de 3. Salida en `bench_emocional_2026-09-27_v2.txt`.

**Tercera pasada: jerga asociada a situaciones** (la línea de QUIÉN SOS ahora dice qué decir cuando
algo sale bien/mal, "nunca 'qué chimba' ante una mala noticia", nevera/no te preocupés; la línea
anterior se reemplazó entera, así que ya no dice "nunca tú ni usted" ni "en lo técnico hablás
normal"). Nuevo ejemplo de mala noticia ("se me dañó el disco…"), estado de la PC fuera del contexto,
y regla de `calcular`. Mismos 24 mensajes, sin tools (`bench_chat.py`): "chimba" ante malas noticias
0/3 (v2: 2/3); en buenas noticias 6/6 lo usa bien. Mención espontánea de PC 2/3 en "quiubo rem" (v2:
3/3), 0 en el resto. Argentinismos: 0 "heladera" (v2: 1), pero apareció "locro" y un mexicanismo,
"chingado", en una respuesta neutra. Mezclas tú/vos 0/24 (v2: 2). Jerga en 15/15 emotivos y 1/9
neutros. 12×7 bien 3/3 (sin la tool). Nuevo defecto: monotonía, 5 de 6 buenas noticias arrancan
"¡Uy, qué chimba, parce!" y 3 "ya era hora"; 2 respuestas de "se borró el proyecto" parafrasean el
ejemplo nuevo ("¿Tenías … en git? Mirá…"). "Hola"/"quiubo" a veces responde con "qué gonorrea",
como si fuera mala noticia. Salida en `bench_emocional_2026-09-27_v3.txt`.

**Cuarta pasada, por la ruta CON tools** (`procesar_turno(tools=tools_disponibles("ventana"))` con
precarga del prefijo, como la ventana; tools con efectos en stub). La línea de jerga ya no lista
palabras, solo el criterio (alegría ante buenas, fastidio ante malas, nunca al revés; variar cómo se
empieza), y volvieron "nunca tú ni usted" y "en lo técnico hablás normal" (system 794 → 829 tok).
Ejemplos: 19 pares (+2 buenas noticias con otras aperturas, +1 mala noticia no técnica, +2 de charla
sin tecnología —un plan y el frío de Yarumal, no comida, para no pisar "recomendame algo para
almorzar"—; se quitó "probé el modelo nuevo y va volando"). Prefijo completo 2406 → 2558 tok.
Resultados (24 respuestas): aperturas de buenas noticias 4 fórmulas distintas en 6 (v3: 5 de 6 eran
"¡Uy, qué chimba, parce!"), "ya era hora" 1/6 (v3: 3/6), pero "¡Hágale, por fin!" salió copiado del
ejemplo nuevo. El ejemplo de mala noticia se parafrasea 3/3 ("¡Qué gonorrea! ¿Tenías … en git?"); "chimba"
ante malas 0/3. PC en el saludo 2/3 ("la RAM te dio un infarto", "¿te pegó el sistema?"). El único
"gonorrea" del saludo (1/3) es **vocativo** ("¡Quiubo, gonorrea!"), casi copia del ejemplo, no queja.
**Regresión: mezclas tú/vos 6/24** ("pásalo", "mira", "tienes", "puedes", "si te equivocas"), frente a
0/24 en v3 sin tools; las dos rutas no son del todo comparables (el bloque de tools cambia el
prompt). 12×7: `calcular` 1/3, las otras 2 contestó "84." de cabeza (bien); el ejemplo "cuánto es 15%
de 80000" → "Doce mil." enseña justo lo contrario de la regla de `calcular`. Contagio del ejemplo del
clima: "Pues claro/Pues sí" abre las 3 respuestas al bug, y un almuerzo terminó hablando de Yarumal.
Ninguna tool se disparó por error. Salida en `bench_emocional_2026-09-27_v4_tools.txt`.

**Quinta pasada, solo tú/vos (2026-09-29, misma ruta con tools)**. Descripciones de las tools
reescritas en infinitivo/impersonal (antes decían "Úsala", "nunca calcules": formas de tú dentro del
bloque de tools); fuera el par "15% de 80000" → "Doce mil." (contradecía `calcular`); el ejemplo del
frío arranca "Es que estamos en Yarumal" en vez de "Pues claro". Tú en 3/24 (v4: 6/24), ninguna
mezclada con vos en la misma frase: "¿Quieres algo más?", "Oye, no te preocupes", "No te asustes…
mira los backups". Lo que queda en el prompt con forma de tú: la palabra "tú" en "nunca tú ni
usted" y "no los has encontrado" en un ejemplo (válido también con vos); el bloque de tools que
arma el template de Qwen está en inglés. `calcular` 3/3 en 12×7. Salida en
`bench_emocional_2026-09-29_v5_tuvos.txt`.

El viejo par `abrime el firefox` → "De una, ya te lo abro." se quitó: **sin** tools (p. ej.
`bench_chat.py`, que llama a `procesar_turno()` sin `tools=`) el modelo contestaba "De una, ya te la
abrí." sin abrir nada. Lo reemplaza un par donde Rem se niega a algo que no puede hacer
(`instalame el discord`).

## Preferencias del panel de control (`preferencias.py`)

Base del panel de control (ventana GTK+WebKit aparte, en construcción: pestañas Personalidad,
Animaciones, Voz y Modelo — el VRM del avatar, no el LLM). `preferencias.json` (ignorado por git)
guarda solo lo cambiado desde el panel; prioridad `preferencias.json` > `config.toml` > default del
código. `config.toml` sigue siendo la base versionada.

- **Esquema por sección** (`ESQUEMA`): cada clave con su validador y su valor base (leído de
  `config.toml` directo, no por `config.leer_*()`, que ya devuelven el valor efectivo). Hoy: `modelo`
  (`vrm`) y `animaciones` (ver abajo); la sección `voz` (edge-tts) se eliminó con él. Cada pestaña agrega su sección al
  implementarse. **Cada clave se reemplaza entera** en un parche (no hay fusión profunda de
  objetos): quien cambie `porEstado.happy` tiene que mandar el `porEstado` completo.
- **`aplicar(seccion, cambios)`** valida el parche ENTERO antes de tocar nada: una clave desconocida
  o un valor inválido lo rechaza completo (`PreferenciaInvalida`, con mensaje para el usuario).
  `None` borra la preferencia (vuelve a `config.toml`); un valor igual al de `config.toml` tampoco se
  guarda. `vrm` exige ruta relativa a un `.vrm` existente dentro del proyecto (sin `..` ni absolutas).
- **Concurrencia**: la cache del JSON se invalida por mtime (lo puede leer otro proceso, p. ej.
  `bench_chat.py` standalone) y la escritura es atómica (`.tmp` + `os.replace`) bajo un lock. Un JSON
  roto o con valores que ya no validan no tumba la app: se ignora lo inválido con un aviso.
- **Quién aplica**: lo que se lee en cada uso no necesita nada — `config.leer_modelo_avatar()` (en
  `url_avatar()`) ya pasa por acá. Lo que hay que avisar se registra con
  `al_cambiar(seccion, callback)`; corre en un hilo aparte (`asyncio.to_thread` en el servidor) y un
  oyente que falla no deshace lo guardado.
- **Sección `animaciones`**, validada contra `Animaciones/catalogo.json` (cacheado por mtime):
  `categorias` ({cat: bool}), `clips` ({id: bool}), `pesos` ({cat: 0..20}) y `porEstado` ({estado:
  [ids]}, `[]` = sin clip; solo estados que el catálogo ya mapea) son **excepciones** al catálogo
  (base `{}`); `enfriamientoMin` (0..120) e `intervaloReposo` ({minS, maxS}, 1..600, min ≤ max)
  tienen su base en `catalogo.json` → `ajustes`. Un id o categoría fuera del catálogo se rechaza.
  El avatar pide `prefs_get` al conectar y aplica `prefs_estado`/`prefs_actualizadas` de
  `animaciones` en caliente (`aplicarPrefsAnim()`): el siguiente gesto/estado ya los usa, y un clip
  de estado nuevo se precarga. Verificado en vivo: apagar `dance` (115 → 65 activos, solo salen
  idles), `porEstado.happy = [VRMA_02]`, `sad = []` (solo la cara), `enfriamientoMin = 0` (`Shout` dos
  veces seguidas) y el reset (vuelta a 115 y 4–9 s).
- **Protocolo**: `prefs_get`/`prefs_set` → `prefs_estado`/`prefs_actualizadas`/`prefs_error` (ver la
  tabla de "WebSocket bidireccional"). Verificado (cuando existía la sección `voz`) con el servidor real y dos
  clientes WS: un cambio llega a los dos y queda aplicado; 8 parches inválidos (clave desconocida mezclada con
  una válida, rate fuera de rango, voz con basura, `../`, ruta absoluta, `.vrm` inexistente, sección
  desconocida, parche vacío) se rechazan sin tocar el archivo ni difundir nada.

## Panel de control (`rem_panel.py`)

Ventana GTK3+WebKit2 aparte (`Rem — Panel de control`, 900×640), **solo cliente**: no levanta
servidor ni abre puertos. Carga `http://localhost:18765/rem_panel.html` del servidor de `rem_chat.py`
y habla por el WS de siempre con los mensajes `prefs_*` (ver "Preferencias del panel de control").
Lanzador: `lanzadores/rem-panel.sh` / **Rem Panel** (no cierra ni reinicia `rem_chat.py`).

- **Necesita Rem abierto** (ventana u overlay): si el HTTP `:18765` no responde, diálogo de error +
  mensaje a la terminal y sale con 1. Solo se sondea el HTTP: un connect/close crudo al WS deja un
  traceback de handshake fallido (`EOFError`) en `rem_chat.log` — se vio al probar. Si el WS se cae
  después, la página muestra "Sin conexión" y reintenta (backoff 1→8 s); verificado cerrando y
  reabriendo `rem_chat.py` con el panel abierto.
- **Instancia única** por `Gtk.Application` (`dev.rem.panel`): una segunda invocación hace
  `register()` → `get_is_remote()` y sale tras traer al frente la primera, **antes** de abrir
  `rem_panel.log` con `'w'` (si no, lo truncaba — mismo cuidado que `rem_chat.py`).
- **Log** `rem_panel.log` (consola de la página incluida, vía `webview_comun.redirigir_salida_a_log()`)
  e **inspector remoto en `:9223`** (fijo, no `setdefault`: `:9222` es de `rem_chat.py`).
- **`webview_comun.py`**: `crear_webview()`/`cargar_con_retry()`/`redirigir_salida_a_log()` salieron
  de `rem_chat.py` tal cual (mismo orden Settings → WebsitePolicies → WebView). Se importa después de
  fijar el entorno y, en overlay, después de `GtkLayerShell`. Verificado: la ventana sigue con
  `WebsitePolicies.autoplay = ALLOW`, `[WS] conectado` y el VRM cargado.
- **Página** (`rem_panel.html`, vanilla, paleta del panel de chat): barra lateral con las pestañas
  (Personalidad, Animaciones, Voz, Modelo; flechas para navegar, la última abierta se recuerda en
  `localStorage`) y estado de conexión. Cada pestaña declara su `seccion` de `preferencias.ESQUEMA`
  (`null` = todavía sin opciones; Voz es `null` desde Piper). Hoy Modelo muestra cada valor efectivo con su origen
  (`panel` / `config.toml`) y **Restablecer** (manda `null`). `aplicarCambio()` manda `prefs_set` con
  un `id` y resuelve/rechaza al volver ese `id` (timeout 5 s); un cambio hecho por OTRO cliente llega
  como `prefs_actualizadas` sin `id` conocido y solo repinta. El resto de mensajes del WS (audio,
  estado, chat) se ignora.
- **Pestaña Animaciones** (`pintarAnimaciones()`): lee `Animaciones/catalogo.json` (de nuevo en cada
  reconexión) y calcula lo efectivo con las mismas reglas que el avatar. Tres tarjetas: **Ritmo**
  (reposo entre gestos mín/máx, enfriamiento), **Emociones** (por estado: fichas con los clips, ×
  para quitar, un `select` agrupado por categoría para agregar, Restablecer; sin clips = "solo la
  cara") y **Gestos de reposo** (por categoría: interruptor, "N de M activos", peso y Ver clips; por
  clip: interruptor, duración, origen —licencia/fuente/URL en el `title`—, avisos medidos en ámbar si
  lo dejan fuera por defecto, horario, "raro", nota y **Probar**, que manda `debug_clip`). Buscador
  por nombre, archivo o autor (despliega las categorías con coincidencias). Una excepción igual al
  valor por defecto no se guarda; apagar/encender una categoría entera borra las excepciones de sus
  clips; "Restablecer todas las animaciones" manda todo a `null`. En overlay (el servidor manda
  `modo` en `prefs_estado`) avisa que ahí no hay clips y deshabilita Probar. Al repintar conserva el
  scroll y el control con foco (`data-foco`). Verificado sin ventanas, con un banco de pruebas en un
  `Gtk.OffscreenWindow` (servidor real + la página, pasos por JS, capturas del render): cada acción
  deja en `preferencias.json` exactamente la excepción esperada, los errores del backend salen en la
  línea de estado y el campo vuelve al valor real, sin scroll horizontal a 420 px.
- El panel se identifica como `panel` (ver "Roles de cliente WS"): no cuenta como destinatario del
  estado/audio, así que con el avatar cerrado el aviso de "no llega a nadie" salta igual.

## Roles de cliente WS

Cada cliente manda `{"tipo": "hola", "rol": ...}` al conectar: `rem_avatar.html` → `avatar`,
`rem_panel.html` → `panel`, `bench_chat.py` modo cliente → `debug`. `rem_ptt.py` no se identifica
(manda un `ptt_*` y se va). El servidor guarda el rol en `_ws_roles` y lo borra al desconectar; un
rol fuera de `ROLES_WS` se ignora con un aviso.

**Los mensajes se siguen difundiendo a TODOS los clientes**: el rol solo decide quién cuenta como
destinatario para `_avisar_sin_destinatarios()` y para el valor que devuelven `_emitir_ws()`/
`_broadcast_ws()`/`enviar_audio()`. Estado, audio y `debug_clip` cuentan solo `avatar`
(`DESTINO_AVATAR`); los mensajes del chat, `avatar` + `debug` (`DESTINO_CHAT`); `prefs_actualizadas`,
`avatar` + `panel`. `enviar_audio()` devuelve `False` (y no copia el WAV) si no hay ningún avatar,
aunque haya otros clientes. Un cliente sin identificar no cuenta.

Verificado con el servidor real y clientes de cada rol: solo panel → estado 0, audio `False`, chat 0
(con aviso); + un cliente sin identificar o con rol inválido → igual; panel + debug → chat 1; panel +
avatar → estado 1, audio `True`; al desconectar el avatar vuelve a 0 y su rol se borra. Con
`rem_chat.py` real, un `state idle` desde `bench_chat.py` cliente no dejó aviso: la ventana se contó
como avatar.

## Catálogo de animaciones (`Animaciones/catalogo.json`)

Fuente de verdad de los 189 clips del avatar: 172 de `Animaciones/nerumi/` (sacados de Nerumi) y los
17 de `VRMA_MotionPack/` (categoría **Rem anterior**). Versionado (`!Animaciones/catalogo.json` en
`.gitignore`); los `.vrma` no. Uso y licencias: `Animaciones/README.md`.

**Estructura**: `categorias` (etiqueta, `activa`, `peso`, `orden`, `nota`), `porEstado` (estado →
`{clips: [...], modo, enfriamiento?}`), `poseBase`, `ajustes` (`intervaloReposo`, `enfriamientoMin`:
los defaults que el panel pisa) y `clips` (clave = ruta relativa a
`Animaciones/`). Cada clip: `etiqueta` (español), `categoria`, `origen` (`autor`, `pack`, `url`,
`licencia`, `fuente`, `sha256Verificado` si sale de un `provenance.json`), `peso`, `horas`, `nota`,
`activoPorDefecto`, y lo medido: `giraCuerpo`, `fundidoEntradaS`, `avisos`, `medido`, `sha256`.

**`catalogo_animaciones.py`** mide con cinemática directa propia (numpy, sin three.js): duración, giro
de la cadera (yaw desenrollado), desplazamiento horizontal, inclinación del torso y, **para cada
brazo, el ángulo con el "abajo" del torso a lo largo de todo el clip** (0° colgando, 90° en cruz)
— la lección de `Relax.vrma`. Calibrado contra las cifras ya medidas de los clips viejos: `Relax`
da brazos >60° el 82 % del ciclo (antes 83-85 %), `VRMA_01`/`VRMA_05` 418,5°/408,2°, `LookAround`
40,4°, `VRMA_06` 36,2° — idénticas. Recalcula lo medido en cada corrida y **conserva lo curado**;
un clip nuevo entra con etiqueta del nombre y origen `desconocido` (o el de su `provenance.json`);
uno que desaparece queda con `"falta": true`; uno ilegible se informa y no entra. `--check` sale con
1 si hay ilegibles o SHA-256 distintos del `provenance.json` (hoy: 0 y 14/14 verificados). Probado
sobre una copia con un clip nuevo, uno borrado, uno corrupto y uno con un byte de más.

**Avisos** (umbrales al principio del script): `empieza-brazos-alto`/`termina-brazos-alto` (>60° en
el primer/último frame), `brazos-alto-mayoria` (>60° más de la mitad del clip), `gira` (>90°, =
`giraCuerpo`), `acrobacia` (torso >90°), `se-sale` (cadera >0,5 m), `largo` (>30 s). Si empieza con
los brazos altos, `fundidoEntradaS = 0.8` (en vez del `fadeIn` normal): el fundido no los levanta
de golpe.

**Lo que se midió en los 172 de Nerumi**: todos parsean (a 144 les falta `specVersion`, lo parchea
`normalizarVrma()`). Los 58 idles kawaii empiezan y terminan en la misma pose neutra (brazos ~12°).
De 81 idles, 11 empiezan/terminan con los brazos altos o son acrobacias/se salen (`idle14-idle2`,
`idle8-robot`, `idle12-dab`, `idle0-break2`, `Backflip`, `Handstand`, `head-spin`, `worm`,
`break`, `Stretch2`, `FeelDown`). De 58 bailes, 36 empiezan o terminan con los brazos altos (su
estilo; se reproducen una vez), 3 son largos (`ghost-complete` 163 s, `Dance42-ghost` 61 s,
`seetinh` 30 s) y 3 se salen de cuadro. Los de `sit` no bajan la cadera (en Nerumi van sobre un
asiento): sueltos, Rem queda sentada en el aire. `Blush.vrma` (el viejo `happy`) lleva un brazo en
alto el 66 % del clip.

**Valores por defecto** (decididos con Esteban): activas solo las categorías `idle` (peso 4) y
`dance` (peso 1). Dentro, `activoPorDefecto` sale de la política `activo_generado()`: fuera los
`acrobacia`/`se-sale`/`largo`, y los de brazos altos al empezar/terminar salvo en `dance` (ahí
quedan activos con el fundido largo). Además, apagados a mano con su `nota`: `Idle01_breathing`
(candidato a pose base, hasta verlo), `Cry`/`Shout`/`Surprise`/`Surprise2` (reacciones,
reservadas a estados) y los dos `lets-groove` (también apagados en Nerumi). Resultado: 115 de 189
activos (65 de reposo, 50 bailes). Peso de clip 0,25 en los "raros" de Nerumi (`JumpAround`,
`Backflip`, `Handstand`, `JumpForJoy`, `RareDance*`); `Idle99_Sleepy` y el viejo `Sleepy` solo de
00:00 a 06:00 (`horas`).

**`porEstado`**: `thinking` → `Thinking.vrma` (viejo, bucle); `sad` → `Idle38_Cry`; `angry` →
`Idle26_Shout` (los dos `unaVez` con `enfriamiento`: si se reprodujo hace menos de N minutos, esa
vez solo la cara); `surprised` → `Idle68_Surprise`; `happy` → `Idle74_Cheer` / `Idle65_ThumbsUp`
al azar sin repetir. `talking` y la pose base siguen procedurales (`poseBase.archivo = null`,
`candidato` = `Idle01_breathing`).

**Origen** (`origen.fuente` dice de dónde salió cada dato): FUDASTORE / KAWAII ANIMATIONS 100 (77
clips; pack de pago, no redistribuible), autores de bailes de la tabla de NOTAS (thedao77, Umai,
vyath pack...), tk256ailab (MIT) y VRoid Project (crédito obligatorio) para Rem anterior, y
`desconocido` en 54 (bailes sin autor, idles no kawaii, sit no kawaii, lying, tutorial,
`greet.vrma`).


## Nota de traspaso — fase 2 (2026-11-05; leer antes de seguir)

**Meta**: reemplazar el modo ventana por un avatar de escritorio al estilo Nerumi —se arrastra por la
pantalla, reacciona a los clics, abre el chat en una ventana aparte, menú propio con clic derecho— con
**código propio**. El material de trabajo está en `notas_fase2/` (ignorada por git; empezar por su
`README.md`): análisis de Nerumi, tabla de equivalencias, clasificación de clips de medio cuerpo y las
herramientas de prueba.

### Estado

- **Etapa 0 — hecha** (prueba en un Hyprland anidado, `notas_fase2/prueba_arrastre/`). Una layer surface
  se arrastra cambiando sus márgenes. La posición **tiene que salir del cursor global** (`j/cursorpos`
  del socket de Hyprland, 0,1-0,5 ms): con deltas locales de la superficie el arrastre se pasaba de
  largo (+7 % lento, ~+80 % rápido) porque un evento llega antes de que Hyprland mueva la capa. Con
  `cursorpos` la posición final fue exacta en arrastres lentos y rápidos, también con un WebView
  transparente encima; durante el arrastre siguen llegando eventos con el puntero fuera de la
  superficie. Click-through fuera del cuerpo con `input_shape_combine_region` (+ `queue_draw()`, ver
  "Modo overlay"). Hyprland no anima los cambios de margen. **No se cubrió**: varios monitores (los
  márgenes son relativos al monitor de la capa; se probó con uno) ni la región de clic dinámica (la
  prueba usaba un rectángulo fijo; la página real tendrá que mandar el del modelo dibujado, como hoy
  manda el de la caja del overlay). Contrapartida: el arrastre solo funciona en Hyprland.
- **Etapa 1 — hecha** (commit «Avatar: el script de rem_avatar.html pasa a avatar/»): el script del
  avatar está en `avatar/`, en scripts clásicos que comparten el ámbito global (ver
  `avatar/README.md`), sin cambiar comportamiento. Verificado con la app real en ventana y overlay.
  VRAM: 3146 MiB con Ollama cargado, igual con ventana u overlay (WebKit dibuja WebGL en la iGPU
  Intel, ver "Renderer WebGL"; en la NVIDIA solo está `llama-server`).
- **Etapas 2 y 3 — hechas y commiteadas** (2026-11-05/06, `02e16b4` + `10d3cdf`): `--modo escritorio`
  con avatar arrastrable, inclinación y pose de «colgada», región de clic que sigue al cuerpo,
  reacciones con voz, mirada al cursor, botones, menú propio del clic derecho y chat en ventana aparte.
  Ver "Modo escritorio".
- **Etapa 4 — hecha y commiteada** (2026-11-06, `2e97135`): ver "Panel de control: pestañas nuevas y
  temas".
- **Etapa 5 — hecha y commiteada** (2026-11-06, `21000ce`): ver "Voz de entrada: fin de frase,
  veredictos y modo conversación". La palabra de activación queda para después.
- **Congelamiento total con Gesto ▸ Saludar** (`@KA_Idle52_Curtsy`, en la sesión real; **no
  reproducido** en el anidado): el commit `e2e5dc9` añadió latidos de diagnóstico (`[Bucle] vivo`,
  `[GTK] vivo`, el vigilante) y protecciones de clips. Ver "Congelamientos del avatar". **Si vuelve a
  pasar: pedirle a Esteban las últimas 40 líneas de `rem_chat.log`** (dicen si se colgó la interfaz
  o la superficie dejó de recibir frames).
- **Nombre del personaje en la interfaz**: `personalidad.NOMBRE_PERSONAJE` llega a la página por la URL
  (`url_avatar()` → `?personaje=`, `NOMBRE_PERSONAJE` en `avatar/config.js`) y lo usan la caja de texto
  ("Escríbele a Yoru…", antes "Rem" fijo en el overlay) y los estados del panel ("Yoru está pensando…").
- **Visto, sin resolver**: en el overlay dentro del Hyprland anidado el avatar se ve al cargar pero no
  en capturas tomadas mientras habla ni tras cambiar de modelo. Ya pasaba antes de la etapa 1. Sin
  confirmar en la sesión real.

### Hecho el 2026-11-06 (sesión de pendientes)

- Rem Cerrar con la app colgada: pidfile + cierre del árbol de procesos (`1ec596f`; detalle en los
  comentarios de `lanzadores/_comun.sh`). **No probado con la app real colgada**, solo con una falsa.
- Entorno aislado de pruebas, `REM_DATOS` + `tests/entorno_aislado.sh` (`3ccab2a`).
- Lo transcrito va al LLM sin la espera de 1 s (`a34b335`); la medición llega hasta que el audio
  suena y el log anota la energía (`e2bcc91`).
- Un `ptt_stop` solo corta la grabación de su pulsador, y el aviso de PTT ignorado se ve (`7607c81`).
- Transcripción adelantada durante el silencio de fin de frase (`8f4560e`).
- Pruebas con el micrófono real (Esteban, con cargador): toque 3,35-3,95 s y SUPER+H 2,77-3,62 s de
  fin de voz a audio sonando; «videojuegos» bien; la pausa larga no cortó; «muerto» bien detectado.
  Fueron antes de la transcripción adelantada.

### Pendientes, en orden (2026-11-06, al cerrar la sesión)

1. ~~**Medir las dos frases con pausa con `adelantar_s = 0`**~~ — hecho (2026-11-07): en las dos sale
   mejor la adelantada; salía peor con una continuación corta y se arregló abandonando la adelantada
   vieja (ver "A/B con `adelantar_s = 0`" en "Voz de entrada").
2. **Cambiar el `initial_prompt`** de `[stt.local]` al de conversación, **sin «sirviente»**, y volver a
   medir los errores por palabra (comparación previa en "`initial_prompt` técnico vs. de
   conversación": 17,3 % el actual, 11,1 % el de conversación con «sirviente»).
3. **Avisos con voz** (lo que hoy sale en el chat sin voz). Frases aprobadas por Esteban, en el
   registro de Yoru de `personalidad.py` (tú, «sirviente», sin exclamaciones, sin español de España),
   para sintetizar con la caché de `frases_voz.py` como las reacciones del escritorio:
   - Micrófono silenciado o sin audio (`muerto`/`silencio`): «No me llega nada del micro, sirviente.
     ¿Lo tienes silenciado?» · «…Silencio total. Revisa el micro.» · «Tu micro está muerto. O mudo.
     Revísalo.»
   - Llega audio pero no voz (`sin_voz`): «No oí nada. Repite.» · «…¿Dijiste algo? Más alto,
     sirviente.» · «Solo oí ruido. Otra vez.»
   - Frase inventada por Whisper: «Eso no lo dijiste tú, ¿verdad? Repite.» · «…Creo que oí
     fantasmas. Dilo de nuevo.» · «Mi oído se inventó algo. Otra vez, sirviente.»
   - Error de un turno: «Se me trabó la cabeza. Dímelo otra vez.» · «…Lag mental. Repite,
     sirviente.» · «Algo falló de mi lado. Por esta vez no es skill issue tuyo.»
   - No se pudo abrir el micrófono: «No puedo abrir el micro. Revisa que esté conectado.» · «El micro
     no me deja entrar, sirviente. Revísalo.»
   - Falló la transcripción: «No te entendí. Repite.» · «…Se me perdió lo que dijiste. Otra vez.»
   - Escribir con la tecla de voz pulsada: «Suelta la tecla primero, sirviente.» · «O hablas o
     escribes. Suelta la tecla.»
   - Confirmación de apagar la PC: «¿Apago la PC, sirviente? Dime sí o no en el chat.» · «¿Seguro que
     apago la PC? Confírmalo en el chat.» — **unificarlas con el grupo `confirmar` de
     `frases_escritorio.json`** (hoy «Confírmalo en el chat, sirviente.» / «Confírmalo en el chat.»).
   - En `frases_escritorio.json`, «…Vale. Vuelvo a hablar.» → «…Bueno. Vuelvo a hablar.».
   - **Se quedan solo escritos**: «No te escuché: Yoru está hablando» (y «Yoru ya está respondiendo»:
     ella está hablando), los fallos de la propia voz, «Voz detectada», la depuración y los avisos de
     la interfaz (modo, modelo, clips, comandos, conexión).
   - **Modo conversación: un sonido corto en vez de frase** (aprobados): al abrir el micrófono dos
     notas que suben, mi5 (659,3 Hz, 90 ms) → silencio 25 ms → si5 (987,8 Hz, 140 ms); al cerrar,
     las mismas al revés (si5 → mi5). Seno + 25 % de 2.º armónico, ataque 8 ms, caída exponencial
     (constante = duración/2,2), pico −16 dBFS, 22050 Hz, 255 ms en total. El cierre por «nadie
     habló» usa el de cerrar, sin frase.
4. **MPRIS / «localhost» en la barra de música**: opcional, para el final, sin cambiar cómo se
   reproduce el audio. WebKitGTK 2.52 publica por MPRIS los `<audio>` y no tiene un ajuste para
   apagarlo; las salidas vistas son reproducir con la Web Audio API (riesgo: el `AudioContext` se
   quedaba suspendido sin gesto del usuario, ver "Reproducción de audio") o reproducir desde Python
   (toca la cola de voz y el aviso `voz_estado`).

Después: 5) quitar el modo ventana (cuando `notas_fase2/tabla_equivalencias.md` esté completa);
6) animaciones en el overlay. **Medir VRAM con `nvidia-smi` en cada etapa** (con Ollama cargado;
`num_gpu = 99`; hoy 3577 de 4096 MiB).

**Reglas de trabajo**:
- **El entorno de prueba nunca puede tocar el escritorio, los archivos ni los puertos de Esteban; si
  pasa, avisarle.** Pruebas siempre dentro de `tests/entorno_aislado.sh`, y la app de prueba solo con
  el Hyprland anidado ya arriba (si no, se abre en su escritorio real: pasó el 2026-11-06). Mientras
  una prueba ocupa los puertos 18765/18766 su Rem no puede arrancar (también pasó): cerrar siempre la
  prueba al terminar.
- **Enseñar el diff antes de cada commit y esperar el ok de Esteban**; sin líneas de
  Claude/Anthropic en el mensaje.

### Decisiones tomadas

- **Nada de Nerumi va al repo público.** Nerumi no tiene licencia (todos los derechos reservados).
  `~/Descargas/Riclado de nerumoi/` es solo referencia: `mic-check.js` y `themes.css` de ahí tienen el
  80 % de líneas idénticas a Nerumi. Se reescribe con código propio buscando una experiencia parecida;
  las ideas y los valores numéricos sí se usan.
- **Sin Electron**: GTK + WebKit + el mismo servidor y WebSocket. El chat, la voz, el recorte de
  historial, las tools bajo demanda y el modo serio salen gratis por `chat_message`.
- **Estilo visual propio**, no la paleta Lumi/Midnight de Nerumi.
- **El overlay se queda quieto en su sitio**; después de la etapa 2 tendrá animaciones, solo con clips
  aptos para medio cuerpo (`notas_fase2/clips_medio_cuerpo.md`: 60 aptos, 45 activos por defecto; anular
  la traslación de cadera volvería aptos muchos de los 39 que "se desplazan", porque los pies no se ven)
  y reutilizando `avatar/clips.js`.
- **La ventana vieja se mantiene** hasta cumplir `notas_fase2/tabla_equivalencias.md`.

### Personalidad: cerrado, pendiente y descartado

**Corrección de método**: una sola corrida no prueba nada (temperatura 0,7). "al menos" salió 8 y 1 veces
en dos corridas idénticas; la jerga, 6 y 1 de 20. Toda comparación va con 2-3 corridas por variante.

- Cerrado (commit «Personalidad: modo serio por categoría, filtros y ejemplos sin hechos personales»):
  ejemplos de tono como turnos y sin hechos personales; modo serio con un ejemplo por categoría y
  glosario; frase "si lo ves aplazando algo…"; `_un_parrafo` y bloques de código. Ver "Ejemplos de tono"
  y "Modo serio y tope de oraciones".
- Descartado: ejemplos dentro del system (los usa como tabla: "hola" → la misma respuesta 10 de 10),
  regla "solo sabes lo que te dijo" con ejemplos como turnos (le hace listar los ejemplos), separador
  tras los ejemplos, mini-ejemplos rotando al azar, modo serio sin ejemplo (juzga).
- Pendiente: el modo serio copia literal el ejemplo de su categoría en ~60 % de los turnos (encaja porque
  es genérico, pero repite); en "¿qué sabes de mí?" inventa caracterizaciones sacadas del personaje
  ("eres un npc con skill issue"); la jerga sigue alta (10 menciones en 38 respuestas frente a 5
  antes); el banco de cumplimiento de las etiquetas de emoción del chat sigue sin hacerse.


## Modo escritorio (`--modo escritorio`, etapa 2 de la fase 2)

Lanzador **Rem Escritorio** (`lanzadores/rem-escritorio.sh`; si ya está abierto en este modo le manda
SIGUSR1 y reaparece si estaba oculto, en vez de reiniciar). Dos ventanas en el mismo proceso que el
servidor (`escritorio.py`):

- **Avatar**: layer surface `rem_escritorio` (capa/tamaño en `config.toml` → `[escritorio]`, 380×620
  `top` por defecto), transparente, cuerpo entero, con clips y director como la ventana vieja
  (sin suelo ni panel). Teclado siempre `NONE`. La posición (monitor + márgenes) se guarda en
  `escritorio_estado.json` (ignorado por git) al soltar y se recupera al abrir.
- **Chat**: ventana GTK normal con `rem_chat_ventana.html`, perezosa (se crea al abrirla por primera
  vez) y que al cerrarse solo se oculta. Hyprland la mete en mosaico; para que respete
  `chat_ancho`/`chat_alto` hace falta una `windowrule` de flotante para su título («Yoru — chat»).

**Arrastre** (Python): el press de GTK guarda el cursor GLOBAL (`j/cursorpos` del socket de Hyprland)
y el agarre; el arrastre arranca cuando se cumplen las dos condiciones, en cualquier orden: la página
avisó `presion` (se pulsó el cuerpo, no un botón ni el menú) y el ratón pasó 6 px. Cada 16 ms:
`cursorpos` → márgenes acotados al área útil del monitor (sin las zonas reservadas; puede salirse un
30 % por los lados, el aire transparente de la superficie) → `posicion(gx, gy)` a la página. Visto en
vivo: con el STT calentándose (CPU a tope) `presion` llegaba después de los movimientos y un arrastre
entero se tomaba como clic; por eso el orden no importa. Un clic sin arrastre llega a la página como
`clic(x, y)`. **Varios monitores**: durante el arrastre la capa no cambia de monitor (eso la recrea y se
perdería el arrastre en curso); al soltar con el cursor en otro monitor pasa a ese (`set_monitor`, el
`Gdk.Monitor` se busca por posición) con el mismo agarre. Probado con una salida headless en el
Hyprland anidado; no con dos monitores físicos. Fuera de Hyprland no hay arrastre (aviso en el log).

**Página** (`avatar/escritorio_ui.js` + `escritorio.css`):
- *Inclinación*: muelle amortiguado (~0,45 del crítico, `CONFIG.escritorio.inclinacion`) hacia
  `-vx·k` / `-vy·k`; rota la escena alrededor del punto agarrado (cuelga del cursor) y se aplica
  antes de `vrm.update()`, así pelo y falda reaccionan. Cara de sorpresa mientras se arrastra. **La
  velocidad la calcula `escritorio.py`** (filtro de 60 ms con sus marcas de tiempo) y la manda en
  `posicion(gx, gy, vx, vy)`: calculada en la página, con las llamadas llegando a ráfagas, daba picos
  y ceros, y en la sesión real de Esteban la inclinación no se notaba (además la ganancia era la
  mitad: 300 px/s daban ~7°; ahora ~18°). Al soltar se loguea la inclinación máxima.
- *Colgada* (`_actualizarColgada`, `CONFIG.escritorio.colgada`): mientras se arrastra, piernas
  colgando con un péndulo propio que se queda atrás del movimiento (signo medido en vivo), pataleo,
  pies en punta y brazos abiertos agitándose; se mezcla encima del clip/procedural con fundido de
  0,25 s y vuelve en 0,6 s. Procedural porque ningún clip sirvió: `@KA_Sit_SwingingLegs` y
  `@KA_Sit_WithBothLegsUp` de frente se leen como sentada (la falda atraviesa los muslos) y
  `@KA_Swimming_Idle` casi no se distingue de estar de pie (vistos en capturas).
- *Mirada al cursor* (`CONFIG.escritorio.mirarCursor`): `escritorio.py` manda `cursor(x, y)` (px de
  superficie, de `cursorpos` a 10 Hz, solo si cambia); se suma a la base de la mirada en
  `_miradaBase()` (ojos con `peso` 0,6, cabeza con `CONFIG.mirada.cabezaFraccion`, ~5-9°) y vuelve al
  frente tras `volverTrasS` (4 s) sin mover el ratón. Los signos de yaw/pitch se le preguntan a
  `vrm.lookAt` una vez por modelo (con Neru: yaw +1, pitch −1; el pitch supuesto estaba al revés).
- *Región de clic*: cajas alrededor de los huesos proyectados (torso, brazos, piernas, cabeza) +
  botones y menú si se ven, cada 90 ms y solo si cambió (cuantizado a 3 px). Sigue al cuerpo en los
  clips y al inclinarse. El pelo largo y las puntas de la falda quedan fuera (atraviesan).
- *Clics*: cara breve + vaivén; 3+ en 4 s, molesta; 5+, enojada (`recibirEmocion('angry')`, su clip
  con enfriamiento) y 7 s sin reaccionar. Sin doble clic (retrasaría todas las reacciones).
- *Frases con voz*: los textos fijos están en `frases_escritorio.json` (versionado). `frases_voz.py`
  los sintetiza con Piper al arrancar (19 frases en ~5 s) en `cache_frases/` (ignorado por git: WAV +
  timeline; la clave es el texto tal como lo lee la voz, tras `_para_voz`, y la identidad del modelo
  Piper, así que cambiar una frase o la voz la regenera; las que sobran se borran). La página manda
  `decir_frase` y el servidor la dice con `enviar_audio` solo si la voz está activa, no hay turno ni
  voz en cola ni audio sonando, y el micrófono está cerrado (`_motivo_no_decir_frase`); si no, queda
  en la burbuja. Una reacción nunca corta una respuesta. Las frases sin letras («…») no se dicen.
- *Botones* al pasar el ratón (chat, menú, ocultar) a la derecha de la cabeza; *menú* del clic
  derecho: chat, bailar, voz, modelo (lista), panel de control, ocultar, salir. *Burbuja* sobre la
  cabeza: reacciones, «Te escucho…» con el push-to-talk, «…» pensando, lo transcrito.

**Mensajes página → Python por el WebSocket, no por `messageHandlers`**: `{tipo:'escritorio',
datos:{...}}` → `rem_avatar_server.establecer_oyente_escritorio()` → `GLib.idle_add`. Con el script
message handler (como el overlay) la app se colgaba al rato: Hyprland mostraba «no responde» y SIGTERM
no la cerraba. Con gdb (la app lanzada como hijo; `ptrace` a un proceso ajeno no está permitido): el
hilo principal esperando para siempre en `JSC::Heap::acquireAccessSlow`, con todos los hilos de
Python ociosos. Cada mensaje crea `JSCValue` en Python y la región se manda cada ~90 ms. Con el
WebSocket, 12 arrastres + 16 clics + 7 turnos con voz sin cuelgue y SIGTERM cierra en 0,3 s. El
overlay sigue usando el handler (pocos mensajes); si algún día se cuelga, es lo mismo.
`kill -USR2 <pid>` vuelca las pilas de Python al log (`faulthandler`).

**Chat aparte** (`avatar/chat_remoto.js`): rol WS `chat` (cuenta en `DESTINO_CHAT`). Al conectar el
servidor le manda `modo_actual`, `voz_actual` y la confirmación en curso si la hay
(`_saludar_chat`). Lo que vive en la página del avatar se pide por el servidor:
`al_avatar {cmd:{que: estado_get|baile|clip}}` → `cmd_avatar` a los avatares, y
`del_avatar {info:{que: estado|sistema|modelo_cargado|baile|clip_lanzado}}` → `info_avatar` a los
chats. `panel_chat.js` ya no toca globales del avatar: recibe un anfitrión (`anfitrionChat()`,
`chat_local.js` en la página del avatar, `chat_remoto.js` en la de chat); el CSS del panel pasó a
`avatar/panel_chat.css`. `voz_actual` se difunde al cambiar (el menú del avatar y el chat la pintan).
`apagar_pc` sí se ofrece: al pedir confirmación el avatar abre el chat, que la recibe al conectar.

**Ocultar sin desmapear**: «Ocultar» deja la capa mapeada, vacía la región de clic y pausa el dibujo
(`_renderPausado`). Antes la desmapeaba y el lanzador mandaba SIGUSR1 para volver a mostrarla: en la
sesión real de Esteban no reaparecía. Mostrar/ocultar/alternar: `rem_escritorio.py
mostrar|ocultar|alternar` (por WebSocket); el lanzador lo usa si ya hay una instancia en modo
escritorio (SIGUSR1 queda de respaldo).

**Hyprland (líneas para `hyprland.conf`, no se editan desde aquí)**: el chat flotante, sin borde y
centrado en el monitor del avatar (`escritorio.py` enfoca ese monitor antes de mapear la ventana;
verificado con dos salidas en el anidado, 0.56.2), y un atajo para mostrar/ocultar:

```
windowrule = float true, match:class rem_chat\.py, match:title .+ — chat
windowrule = size 440 640, match:class rem_chat\.py, match:title .+ — chat
windowrule = center true, match:class rem_chat\.py, match:title .+ — chat
windowrule = border_size 0, match:class rem_chat\.py, match:title .+ — chat
bind = SUPER, Y, exec, /mnt/extra/rem/Rem/venv/bin/python /mnt/extra/rem/Rem/rem_escritorio.py alternar
```

**Blur opcional para el tema Cristal** (líneas para `hyprland.conf`; sintaxis validada con
`hyprctl keyword` en 0.56.2, efecto no visto: el anidado tiene fondo liso). `ignore_alpha` hace que
solo se desenfoque detrás de lo opaco (menú, botones, burbuja, el cuerpo), no toda la superficie:

```
layerrule = blur true, match:namespace rem_escritorio
layerrule = ignore_alpha 0.3, match:namespace rem_escritorio
```

**Verificado** (Hyprland anidado, 2026-11-05): transparencia y click-through fuera del cuerpo;
arrastre con posición final exacta (+520/−120 px); inclinación en ráfaga de capturas; botones,
menú, reacciones y enfado; chat en Eco e IA con streaming, `/animaciones` y `/bailar` reenviados,
confirmación de `apagar_pc` (contestada «No» por WS, los botones Sí/No están a 27 px); ocultar +
SIGUSR1; cambio a un segundo monitor; ventana y overlay sin regresiones. **VRAM con Ollama
cargado: 3572 MiB de 4096** (3562 `llama-server`; el avatar y el chat, 0 en la NVIDIA).


## Panel de control: pestañas nuevas y temas (etapa 4 de la fase 2)

**Pestañas** (`PESTANAS` en `rem_panel.html`; cada una declara las `secciones` de preferencias que
espera). Antes había cuatro —Personalidad, Animaciones, Voz y Modelo— (nunca hubo una de Memoria,
comprobado en todo el historial de git). Ahora: **Apariencia** (tema), **Avatar** (absorbe Modelo:
el VRM, ahora con un desplegable de `models/vrm/`, + el comportamiento del avatar de escritorio),
**Escritorio** (capa, respetar barras, tamaño, volver a la esquina inicial), **Animaciones** (la de
siempre + una tarjeta de modo baile), **Voz** (deja de estar vacía: voz activa y volumen), **Chat**
(IA/Eco, borrar la conversación, proveedor del LLM en solo lectura) y **Personalidad** (igual que
antes, sin opciones). **Micrófono** no se muestra hasta la etapa 5. `rem_panel.py --pestana ID` abre
en una pestaña (`?pestana=`); con el panel ya abierto le llega `panel_pestana` por el WS. El id viejo
`modelo` se traduce a `avatar` (`ALIAS_PESTANA`).

**Secciones de preferencias nuevas** (`preferencias.ESQUEMA`): `apariencia.tema` (base
`config.toml [apariencia]`), `avatar.{mirarCursor, mirarPeso, inclinacion, reacciones, clicsEnojo,
frasesVoz}` (defaults en el código), `escritorio.{capa, respetarBarras, tamano}` (base `[escritorio]`)
y `voz.{activa, volumen}`. **La voz activa pasa a ser una preferencia**: el mensaje WS `voz` va por
`preferencias.aplicar("voz")`, su oyente llama a `set_voz_chat_activa()` (que difunde `voz_actual` a
avatar, chat y panel) y al levantar el servidor se lee de ahí (`_iniciar_voz_desde_prefs`). Así sobrevive
a un reinicio (verificado). `escritorio.py` aplica `escritorio` en vivo (`set_layer`,
`set_exclusive_zone` 0/−1, `set_size_request` con la esquina inferior izquierda fija; verificado: nivel
2→3, 380×620→456×744 y vuelta). La página del avatar recibe `avatar`/`escritorio`/`voz` por
`window.__remPrefs` (ws.js → `aplicarPrefsGenerales`) y el volumen va al `<audio>`.

**Menú del clic derecho**: Chat · Modo IA/Eco · Voz · Bailar · Modelo ▸ · Gesto ▸ (saludar, uno al
azar) · Posición ▸ (esquina inicial) · Encima de pantalla completa (casilla = capa `overlay`) ·
Ajustes ▸ (las 7 pestañas) · Ocultar · Salir. Submenús desplegados en el sitio (`_menuSub`).

**Temas** (`avatar/temas.css`, `<html data-tema>`): Synthwave (los colores de siempre), Cristal (gris
carbón translúcido, acento azul hielo) y Yoru (#232027 con #9458C3/#7044A3). Tokens `--t-*`; los tintes
del acento son `color-mix(... var(--t-acento) N%, transparent)`, así que bordes y brillos cambian con el
tema. `panel_chat.css`, `escritorio.css` y el CSS de `rem_panel.html` se convirtieron de colores fijos a
tokens (el verde/ámbar de estado del panel siguen fijos: son semánticos). Lo aplican la página del
avatar (también el panel de la ventana vieja), la ventana de chat y el panel. Con Synthwave la ventana
vieja se ve igual que antes (comparada en captura). Ninguno usa la paleta ni el `themes.css` de Nerumi.

**Verificado** (anidado, 2026-11-06): menú con todos los ítems y Ajustes ▸ Apariencia abriendo el panel
en esa pestaña; tema Yoru aplicado a la vez en panel, chat y menú; las 7 pestañas pintadas; voz apagada
desde el interruptor del panel (guardada, sin síntesis, persiste al reiniciar); capa y tamaño en vivo;
reacciones apagadas; baile desde el panel; ventana y overlay sin errores. VRAM con Ollama cargado:
3572 MiB de 4096 (igual que en la etapa 2).


## Voz de entrada: fin de frase, veredictos y modo conversación (etapa 5 de la fase 2)

Código propio en `stt/analisis.py` (los valores de referencia salen de la guía de Nerumi; el código
no). Umbrales y tiempos en `config.toml [stt.voz]`; el modo conversación se enciende/apaga en el
panel (pestaña **Micrófono**, preferencia `microfono.conversacion`, activo por defecto).

**Cuándo hay voz** (tramas de 20 ms, dBFS): umbral = piso de ruido + 12 dB, nunca por debajo de
−45 dBFS. El piso es la **mínima mediana de ventanas de 0,4 s**. Se probó antes la mediana del 30 %
de tramas más bajas y fallaba en dos casos que cubre `tests/test_stt_analisis.py`: voz continua
(15 s de voz: el umbral subía por encima de la voz y cortaba a los 4 s) y hablar desde el primer
instante (el piso empezaba a nivel de voz). El detector en vivo (`FinDeFrase`) además busca el inicio
de la voz hacia atrás cuando el piso baja. Coste: ~0,2 ms por bloque de 50 ms (en el hilo de
PortAudio, gancho `Grabador(al_bloque=)`). En un cuarto con ruido a −28 dBFS el viejo umbral fijo
de 0,028 RMS (−31 dBFS) nunca daría la frase por terminada; el adaptativo sí (test).

**Dos formas de grabar** (`rem_avatar_server`):
- *Mantenida*: SUPER+H (`rem_ptt.py`) o mantener el botón 🎙 del chat más de 260 ms
  (`ptt_start`/`ptt_stop`), igual que antes.
- *Automática*: un toque del botón 🎙 (`mic_toque`) o el modo conversación. Corta sola tras
  `silencio_s` (1 s) de silencio después de la voz (sin contar los primeros `gracia_s`, 0,65 s), a
  los `max_voz_s` (15 s) de voz, si en `muerto_temprano_s` (4 s) no llega audio, o si nadie habla en
  `espera_voz_toque_s` (8 s; en conversación, `cierre_inactividad_s`, 30 s). Otro toque mientras
  graba la corta ya. El tope de seguridad de una grabación automática va por detrás de esos tiempos
  (si coincidía con los 30 s de conversación ganaba él y el motivo salía mal).

**Veredicto antes de transcribir** (`veredicto()`): `muerto` (pico < −80 dBFS y ≥ 1,5 s), `silencio`
(lo mismo, más corto), `sin_voz` (ninguna trama sobre el umbral) o `enviar`. Después de Whisper,
`inventada` si el texto es una de `frases_inventadas` («Gracias.», «Subtítulos… Amara.org»…, sin
tildes ni signos) **y** hubo menos de 120 ms de voz. Cada uno sale como `mic_veredicto` y se ve en el
chat (también «🎙 Voz detectada (1,3 s de voz)»), en la caja del overlay y en la burbuja del
escritorio (solo texto). Whisper con `vad_filter` no se inventó nada en la prueba (un chasquido de
80 ms dio texto vacío): `inventada` solo está probado con el test.

**Modo conversación** (sin etiqueta del modelo): tras un turno **por voz**, si la respuesta termina en
«?» (admite comillas o «…» detrás), `_reabrir_conversacion()` espera a que no haya turno, ni voz en
cola, ni audio sonando, y `reabrir_tras_s` (0,55 s) desde el último fin de voz, y reabre en
automático. Se cierra si la respuesta no pregunta, si nadie habla en 30 s, si hay un veredicto sin
voz, o al escribir un mensaje. Mensaje WS `conversacion {activa, motivo}`.

**Verificado** (2026-11-06, Hyprland anidado; micrófono simulado con un sumidero nulo y su monitor,
`REM_MIC_DEVICE=pulse PULSE_SOURCE=…monitor`, frases dichas con Piper): toque → fin de frase →
«voz detectada» → turno; en Eco «¿Me escuchas bien?» reabre el micrófono solo y la segunda frase lo
cierra; solo ruido → `sin_voz` a los 8 s; fuente silenciada → `muerto` a los 4 s; SUPER+H/mantener
igual que antes; botón real (toque y mantener, rojo mientras graba); conversación cerrada a los 30 s
con ruido de fondo. Ventana y overlay sin errores. **VRAM con Ollama cargado: 3572 MiB** (igual).

**Latencia, de que dejas de hablar al primer audio de la respuesta** (modo IA, Ollama caliente, frase
de 3,4 s, 3 medidas): **4,9–5,2 s** = 1,0 s de silencio de espera + ~1,65 s de Whisper + 1,0 s de
`mostrar_transcripcion_s` (pausa para ver lo entendido) + ~1,3 s de LLM hasta la primera oración y
voz. En Eco, 3,7 s. Los dos tramos fijos (silencio 1 s y la pausa de 1 s) son los fáciles de bajar.
Whisper oía «Lloro» por «Yoru»: se añadió «Yoru» a `initial_prompt`.

**Sin la pausa de 1 s** (2026-11-06): `ptt_transcripcion` sale y el turno arranca a la vez
(`mostrar_transcripcion_s` queda solo como cuánto lo enseña la interfaz; entre el fin de la grabación
y el flag del turno no hay ningún `await`, así que un `ptt_start` no se cuela). A/B en la misma
sesión (entorno aislado, Hyprland anidado, micrófono simulado, modo IA con Ollama caliente, frase de
3,2 s, 3 medidas por variante, la espera vuelta a meter a mano para la B): **con la pausa 4,25 /
4,45 / 4,39 s (media 4,36); sin ella 3,55 / 3,47 / 3,24 s (media 3,42)**: ~0,94 s menos. Desglose
de ahora: 1,0 s de silencio de espera + ~1,7 s de Whisper (5,7 s de audio grabado contando el silencio
inicial) + ~0,7 s de LLM y voz. Lo que queda fijo y se podría bajar es `[stt.voz].silencio_s` (1 s),
a costa de cortar frases con pausas largas. Whisper sigue oyendo a veces «video-cuegos».

**Transcripción adelantada** (2026-11-06, `[stt.voz] adelantar_s`/`adelantar_min_voz_s`): en una
grabación automática, tras 0,35 s de silencio se transcribe ya lo dicho (`Grabador.instantanea()`,
`STTProvider.transcribir_adelantada()`), y si al cortar no hubo voz nueva se usa ese texto: Whisper
queda escondido dentro del segundo de silencio. Dos protecciones, medidas en una simulación en tiempo
real con el detector y el Whisper de la app (sin ellas, «Oye Yoru» + 0,4 s + «¿cómo estás?» pasaba de
1,40 a 4,07 s: la adelantada sobre 0,7 s de voz alucinaba y sus reintentos a otras temperaturas
bloqueaban a la de verdad): solo con ≥ 1 s de voz, y la adelantada va a temperatura 0 sin reintentos;
si algún segmento no pasa los umbrales con los que faster-whisper reintentaría (compresión > 2,4,
logprob < −1 sin ser silencio) devuelve `None` y se transcribe de nuevo, así que la precisión es la de
siempre. Whisper va de uno en uno: hablar tras una pausa deja la adelantada vieja corriendo y lo
que venga después la espera (ver abajo, «A/B con `adelantar_s = 0`»). En la app (anidado, micrófono
simulado, 3 toques por frase), sonando desde que dejas de hablar: sin pausa **2,68-2,92 s** (antes
~3,5); pausa 0,4 s + continuación larga 3,04-4,60 s
(adelantada de ~2,1 s, solo esconde 0,64 s); «Oye Yoru» + 0,4 s + «¿cómo estás?» 2,97-3,65 s (sin
adelantada en la pausa). El log dice por qué vía salió el texto: `STT (adelantada (1,62s de
Whisper))` o `STT (normal (la adelantada quedó vieja…))`, y el tiempo es el que se espera tras cortar.

**A/B con `adelantar_s = 0` y adelantada vieja abandonada** (2026-11-07). Banco: la app en el anidado
(entorno aislado), modo **Eco** (sin LLM: lo único que cambia entre variantes es el camino de Whisper),
con corriente, micrófono simulado, toques del botón y las dos variantes alternadas en la misma sesión
(un lanzador que lee `adelantar_s` de un archivo en cada grabación, sin tocar `config.toml`). Frases de
Piper con `sil(0.3)` alrededor y 0,4 s entre partes. Sonando desde que dejas de hablar, medias:

| Frase | `adelantar_s = 0` | 0,35 (antes del arreglo) | 0,35 (con el arreglo) |
|---|---|---|---|
| Sin pausa (3,7 s) | 3,04 · 3,40 | 2,31 | 2,59 |
| 2,2 s + pausa + continuación larga (4,3 s) | 3,51 · 3,00 · 3,66 | 2,96 · 2,33 (9 pares; pierde en 2 por la variación de Whisper) | 2,79 |
| «Oye Yoru,» + pausa + «¿cómo estás?» | 2,94 · 3,15 | 2,22 | 2,35 |
| 2,1 s + pausa + **continuación corta** («¿y tú?», 0,6 s) | 3,38 · 3,44 | **3,58** (peor en 4 de 5 con la vieja) | **3,20** (mejor o igual en 6 de 6) |

(Cada celda, una corrida de 3-6 pares; las de `= 0` son el emparejado de cada corrida. El nivel absoluto
se mueve entre corridas en ~0,3 s.) El caso que salía peor era el de continuación corta: la adelantada
de la pausa seguía ocupando Whisper al cortar, la final no llegaba a lanzarse y la normal la esperaba.
Arreglo: en cuanto el detector ve voz después de lanzarla, `_quizas_adelantar` activa su
`threading.Event` y `LocalSTTProvider` la abandona **al salir del codificador** (envuelve `encode()` de
esa instancia mientras dura la llamada): el codificador es ~1,0 s de ~1,5 s y no se puede cortar a mitad;
lo que se ahorra es la decodificación (~0,5 s), suficiente para que la final se lance en la pausa final.
Log: `[PTT] transcripción adelantada vieja (hubo voz después): se abandona` y `[STT] adelantada
abandonada tras el codificador`. Descartado: dos workers de Whisper en paralelo (aislado: la final, 1 s
después de la vieja, tarda 2,24 s con dos workers frente a 2,52 con uno y 1,5 sola: compiten por la CPU;
+250 MiB de RAM). Whisper oye «Oye Yoru» como «¡Oh, GTK» (palabra del `initial_prompt` técnico) y «¿y
tú?» como «¿Listo?»: lo trata el pendiente del `initial_prompt`.

**`initial_prompt` técnico vs. de conversación** (medido, sin cambiar): con 14 frases × 2 ruidos
(Piper), el actual da 17,3 % de errores por palabra y cuela palabras técnicas («Oye Yoru, ¿cómo
estás?» → «Ollama, ¿cómo estás?»); uno con vocabulario de conversación (Yoru, sirviente, videojuegos,
por favor, estuve, servidor, micro, PC…) 11,1 % y ninguna colada; el mínimo sin lista, 15,4 %.

**Qué mide la línea `[PTT] medición`** (corregido 2026-11-06): antes la cerraba `voz_estado: true`,
que la página manda al RECIBIR el audio (en `encolarAudio()`, antes de `play()`), aunque el log decía
«SONANDO». Ahora `voz_estado` solo apunta esa llegada y la cierra un mensaje nuevo, `voz_sonando`,
que `avatar/cara.js` manda en el evento `playing` del `<audio>`; la línea da las dos cifras desde que
dejaste de hablar («audio recibido en la página» y «SONANDO»). Medido: 3,34 / 3,42 / 3,78 s sonando,
0,07-0,08 s después de recibido. La línea de STT y la de medición llevan además
`energía: AC|batería N% …; perfil <platform_profile>, EPP <preferencia>` (`llm/_energia.py`,
`estado_alimentacion()` + `perfil_cpu()`: solo lee `/sys`, no `nvidia-smi`, porque Whisper va en CPU),
y la de STT el factor de tiempo real sobre el audio grabado y sobre la voz sola: con 5,7 s grabados y
2,6 s de voz (lo que cuenta el detector), Whisper tarda ~1,6 s = 0,28× el audio, 0,6× la voz. Las cifras
de septiembre (0,17-0,38×) eran sobre el audio grabado: comparables a 0,28×, no a 0,6×.


## Entorno aislado de pruebas (`REM_DATOS`, `tests/entorno_aislado.sh`)

**Toda prueba que arranque la app (o el panel, o toque preferencias) va dentro de
`tests/entorno_aislado.sh [-d CARPETA] -- comando...`.** Con `REM_DATOS=<dir>` (`config.DATOS_DIR` /
`config.ruta_datos()`), todo lo que la app escribe en tiempo de ejecución va a esa carpeta:
`preferencias.json`, `escritorio_estado.json`, `memoria_*.json`, `cache_frases/`, `rem_chat.log`,
`rem_panel.log`, `rem_chat.pid` y los datos de WebKit (caché, localStorage: un `WebContext` propio en
`<dir>/webkit`, `webview_comun._contexto_aislado()`; sin `REM_DATOS` se usa el contexto por defecto de
siempre). Lo que solo se lee (`config.toml`, `.env`, modelos, catálogo) sigue en el proyecto, y
`tmp_audio/` también (lo sirve el HTTP; son temporales). El log dice `ENTORNO AISLADO` al arrancar.

El envoltorio siembra la carpeta (si es nueva; por defecto `${TMPDIR:-/tmp}/rem_prueba.XXXXXX`, y
siempre fuera del repo: `-d` dentro del repo se rechaza, y `config.py` aborta si `REM_DATOS` cae dentro)
con una COPIA de los datos reales, corre el comando con `REM_DATOS` y al terminar busca cambios y
borrados en los archivos reales (proyecto, `lanzadores/logs/` y
`~/.cache|~/.local/share/rem_chat.py|rem_panel.py`): si hay alguno lo lista y sale con 3.
**Se niega a correr (sale con 4) si hay una instancia real viva** (pidfile real válido o los puertos
18765/18766 ocupados por quien sea): con los puertos tomados la app de la prueba no levanta y sus
clientes hablarían con la real. Se eligió esto y no puertos distintos con `REM_DATOS` porque los
puertos están fijos en el servidor, los orígenes del WS, las páginas, `rem_ptt.py`, `rem_escritorio.py`,
`bench_chat.py` y los clientes de prueba: cambiarlos solo en pruebas tocaba todo eso y las pruebas
correrían con una configuración distinta de la real. Los lanzadores también respetan `REM_DATOS`
(pidfile y logs en `<dir>`; un lanzador dentro de una prueba nunca cierra la instancia real).
`notas_fase2/prueba_arrastre/verificar.sh` se niega a correr sin `REM_DATOS`.

**Auditoría de escrituras** (2026-11-06, grep de `open` w/a, `json.dump`, `write_text`, `shutil`,
`os.remove`/`unlink`/`rmtree`, `os.replace`, `sf.write`, `makedirs`, `FileHandler` —no hay—,
`localStorage` y redirecciones de shell en todo lo versionado): pasan por `config.ruta_datos()` o
`REM_DATOS` preferencias, estado del escritorio, `memoria_sistema` (`acciones.py`), caché de frases,
logs, pidfile, logs de lanzadores y el localStorage (`WebContext` aislado). Fuera, justificadas:
`tmp_audio/` (temporales servidos por el HTTP; la limpieza de WAV viejos solo podría afectar a una
instancia real, que el envoltorio ya excluye), `catalogo_animaciones.py` (herramienta que regenera el
`catalogo.json` versionado), `vendor/espejo_esm.py` y `lanzadores/instalar.sh` (herramientas de
instalación, no de ejecución). **Verificado** (2026-11-06, Hyprland anidado): modo escritorio + 3
`prefs_set` + el panel abierto → todo en la carpeta aislada, los hashes de los archivos reales iguales;
control negativo (escribir, borrar o crear un archivo real) → detectado, salida 3.

## Congelamientos del avatar: diagnóstico y red de seguridad de los clips (2026-11-06)

**El caso**: en la sesión real de Esteban, Gesto ▸ Saludar eligió `@KA_Idle52_Curtsy` y el avatar se
quedó congelado del todo (sin parpadeo, mirada, clics, arrastre ni chat); el log terminaba en
`reproduciendo … (unaVez, gesto)` y los dos `WebKitWebProcess` dormidos al 0 % de CPU. **No se
reprodujo**: en el anidado, Curtsy por `debug_clip` ×3 y por el menú real (salió 2 veces en 5) a 60 fps.
El `.vrma` está sano (53 canales, 6,63 s, lineal, tiempos crecientes, cuaterniones unitarios, nada
no finito; igual que los otros saludos del pack, a todos les falta `specVersion` y los parchea
`normalizarVrma()`). Los «6,63 s» del log eran su duración (`cargado — Ns` imprime `durS`), no lo
que tardó en cargar. Con el código de entonces todo lo periódico del log salía desde los frames, así
que "ninguna línea más" = la página dejó de recibir frames; y como tampoco respondía el arrastre (que
mueve Python), lo más probable es que se colgara el proceso de la interfaz (como el cuelgue de
JavaScriptCore de la etapa 2) o que el compositor dejara de mandar frame callbacks. La hipótesis (a),
una excepción que corta `requestAnimationFrame`, no encaja: es la primera línea de `animate()`.

**Diagnóstico para la próxima vez**:
- `avatar/bucle.js`: el frame va en try/catch (error con su pila, como mucho uno por segundo);
  latido `[Bucle] vivo: N fps, E errores, clip …` cada 10 s; `webglcontextlost`/`restored` y
  `visibilitychange` al log; un temporizador (no depende de los frames) avisa `[Bucle] sin frames
  desde hace N s` y `vuelven a llegar frames`; `error`/`unhandledrejection` de la página al log con
  pila (`[Página] …`).
- `rem_chat.py` (`_iniciar_vigilante`): `[GTK] vivo (página: último latido hace N s)` cada 10 s; un
  hilo aparte avisa `[Vigilante] el bucle de GTK no late…` (y vuelca las pilas de Python) o `la
  página del avatar no manda latido…`. La página manda `latido_pagina` por el WS con el suyo.
- **Cómo leerlo**: no sale `[GTK] vivo` → proceso de la interfaz colgado (pilas en el log; `gdb`
  solo funciona lanzando la app como hijo). Sale `[GTK] vivo` pero `[Bucle] sin frames` → la superficie
  no recibe frames: en escritorio la página se lo dice a Python (`sin_frames`) y `escritorio.py`
  fuerza un redibujado y un commit de márgenes. Probado pausando el Hyprland anidado 9 s con SIGSTOP:
  `sin frames` a los 3 s, GTK vivo, redibujado forzado, y `vuelven a llegar frames` al reanudarlo.
  Excepciones en el frame → `[Bucle] error en el frame` con pila.

**Red de seguridad de los clips** (`avatar/clips.js`, `director.js`): una carga que no termina en
`CARGA_MAX_S` (15 s) se da por fallida esa vez (no queda en caché: el siguiente pedido reintenta);
`reproducirSeguro()` y `.catch(errorDeCarga())` en saludo, gesto, clip manual, emoción y baile:
cualquier error descarta el clip (`abortarGesto`) y vuelve al reposo con aviso; `_vigilarGesto()`
libera el control si un gesto sigue activo pasada su duración + 8 s (30 s si no se sabe); 30 frames
seguidos con error paran el mixer y vuelven a lo procedural (`_descartarAnimacion`). El saludo
cancelado ahora dice por qué (p. ej. `estado talking` si el arrastre soltó una frase con voz).

**Saludos**: fuera `@KA_Idle52_Curtsy` («Reverencia») y `@KA_Idle44_GreetingBow` («Saludo con
reverencia») (`saludo: false` en `catalogo.json`; `catalogo_animaciones.py` conserva el campo).
Quedan `nerumi/greet.vrma` (Saludo inicial, 11,7 s), `@KA_Idle16_WaveHands` (Saludar con las dos
manos, 8,0 s) y `@KA_Idle45_WaveHandSlightly` (Saludar con la mano, 7,0 s), **precargados** con los
fijos (`_clipsFijos`: precarga 9 → 12). `al_avatar` acepta además `saludar`/`gesto` (lo mismo que
Gesto ▸ del menú). Probado: 5 Saludar seguidos cada 0,5 s, uno a mitad de un arrastre con el botón
pulsado y otro justo al soltar, sin errores y con los gestos de reposo volviendo después.
Aparte: al abrir el menú con el clic derecho el puntero cuenta como dentro (con el ratón quieto, un
"salir" de GTK al cambiar la región lo cerraba a los 1,2 s).
