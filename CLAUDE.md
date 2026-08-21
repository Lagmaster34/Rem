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

## Configuración (.env en la raíz del proyecto)
```
GROQ_API_KEY=tu_api_key_de_groq
NOMBRE_USUARIO=Esteban
CIUDAD=Yarumal
MODELO_VISION=meta-llama/llama-4-scout-17b-16e-instruct
VOZ_REM=es-VE-PaolaNeural
TTS_RATE=-8%
REM_LAYER=top
REM_OVERLAY_W=520
REM_OVERLAY_H=860
```
`REM_LAYER` (`top`|`overlay`) y `REM_OVERLAY_W`/`REM_OVERLAY_H` los lee `rem_overlay.py`, no
`Rem.py` — controlan la capa del compositor y el tamaño fijo de la layer surface (ver
"Layer surface acotada" más abajo).
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
    activo (`_audioSource` truthy): sus binds incluyen el morph `"Huh"` (índice 25, fuera del rango
    4-18 de los visemes, pero igual un gesto de boca) que si no competiría visualmente con el viseme
    activo. `Talk` bindea `"Ah"` (índice 19, también boca) pero nunca se llama desde ningún lado del
    código — no hizo falta suprimirla aparte.

## AudioContext bloqueado en el overlay (autoplay policy)
El overlay GTK es **click-through por diseño** (`_aplicar_click_through` en `rem_overlay.py`) — nunca
va a recibir un click/keydown/touchstart real, así que el `AudioContext` del navegador nunca sale de
`'suspended'` ahí dentro (los navegadores bloquean audio sin gesto de usuario). En un navegador normal
sí funciona: `rem_avatar.html` engancha `click`/`keydown`/`touchstart` sobre `document` con
`{ once: true }` para resumirlo apenas hay uno.

Cuando `ctx.state` sigue `'suspended'` tras `resume()`, el frontend manda por WebSocket
`{"tipo": "audio_bloqueado", "url": "..."}` de vuelta a Python (antes el `_ws_handler` descartaba
todo lo que llegaba del cliente — ahora lo procesa). `rem_avatar_server.py` responde reproduciendo
ese mismo WAV con `sounddevice` desde `tmp_audio/` (el archivo sigue ahí, se borra recién a los 5
min) — sin lipsync, pero se oye. También se intentó `WebKitSettings.set_media_playback_requires_user_gesture(False)`
en `rem_overlay.py` para desactivar la política de autoplay directamente en WebKit2, pero **no se
pudo verificar en vivo** (esta máquina de desarrollo no tiene `webkit2gtk-4.1` instalado) — confirmar
si existe en la versión real de WebKit2GTK instalada y si con eso ya alcanza sin necesitar el fallback.

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
(medido en este modelo: Box3 ≈ 0,80u vs. huesos ≈ 1,55u). La fórmula de encuadre en sí es correcta
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


    # IMPORTANTE: 
    AL MOMENTO DE HACER COMMIT NO PONGAS TU AUDITORIA Claude/Anthropic DETRO DEL COMMIT
