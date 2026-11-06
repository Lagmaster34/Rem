# avatar/ — el script del avatar 3D

Lo que antes era un único `<script type="module">` de ~3960 líneas dentro de
`rem_avatar.html`, partido por secciones. **El código no cambió**: es el mismo,
en el mismo orden (comprobado al partirlo: las partes juntas reproducen el
módulo original línea a línea).

## Por qué scripts clásicos y no módulos ES

Las secciones comparten ~80 variables globales que se reasignan de una a otra
(`vrm`, `estado`, `_mixer`...). Con módulos ES cada una tendría que exportar e
importar ese estado (un `import` es de solo lectura), y eso es reescribir cientos
de referencias. Los scripts clásicos comparten el ámbito global igual que lo
compartían las secciones del módulo, así que se pudieron separar sin tocar el
código. Cada archivo lleva `"use strict"` (el módulo ya era estricto).

Diferencias con el módulo único que hay que tener presentes al editar:

- **Orden de carga**: los archivos se ejecutan uno tras otro, en el orden de los
  `<script>` de `rem_avatar.html`. Una función declarada en un archivo posterior
  NO existe todavía mientras corre el código de nivel superior de uno anterior
  (en el módulo único las declaraciones de función se elevaban a todo el
  archivo). Dentro de funciones, callbacks y el bucle no importa: para entonces
  ya cargó todo.
- **Nombres globales**: una función o variable de nivel superior es global para
  toda la página. No usar nombres de propiedades de `window` (`top`, `name`,
  `status`, `close`...).
- **three/three-vrm** los publica `dependencias.mjs` (el único módulo) en
  `globalThis`. Los `<script type="module">` y `<script defer>` se ejecutan en el
  orden del documento, así que llega antes que el resto.

## Archivos

| Archivo | Qué tiene |
|---|---|
| `dependencias.mjs` | Imports de three, GLTFLoader, three-vrm y three-vrm-animation (vendorizados) |
| `config.js` | Modo (ventana/overlay), `CONFIG` y selección de modelo |
| `escena.js` | Renderer, escena, estado global, encuadre y suelo synthwave |
| `modelo.js` | Carga del VRM, cambio de modelo en caliente, helpers de huesos/expresiones |
| `cara.js` | Expresiones, parpadeo y lipsync |
| `cuerpo.js` | Mirada, springs, pose procedural, ruido Perlin, peso, saccades, dedos |
| `clips.js` | Clips VRMA: carga, catálogo, mixer, mezcla y puente de pose |
| `director.js` | Director de animación: ruleta de reposo, bailes, saludo, emoción |
| `bucle.js` | `animate()` y resize |
| `panel_chat.js` | Panel de chat del modo ventana |
| `overlay_ui.js` | Caja de texto e indicador del modo overlay |
| `ws.js` | WebSocket con `rem_avatar_server.py` |

Es la base para el modo escritorio (etapa 2 de la fase 2, ver CLAUDE.md): la
página nueva cargará los mismos archivos del núcleo y su propia interfaz en vez
de `panel_chat.js`/`overlay_ui.js`.
