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
| `config.js` | Modo (ventana/escritorio) y `FIJADO` (escritorio fijado en la esquina), `CONFIG` y selección de modelo |
| `escena.js` | Renderer, escena, estado global, encuadre y suelo synthwave |
| `modelo.js` | Carga del VRM, cambio de modelo en caliente, helpers de huesos/expresiones |
| `cara.js` | Expresiones, parpadeo y lipsync |
| `cuerpo.js` | Mirada, springs, pose procedural, ruido Perlin, peso, saccades, dedos |
| `clips.js` | Clips VRMA: carga, catálogo, mixer, mezcla y puente de pose |
| `director.js` | Director de animación: ruleta de reposo, bailes, saludo, emoción |
| `bucle.js` | `animate()` y resize |
| `chat_local.js` | Anfitrión del panel de chat en la página del avatar + disparo manual de clips |
| `panel_chat.js` / `panel_chat.css` | Panel de chat (ventana vieja y `rem_chat_ventana.html`); lo que depende del avatar lo da `anfitrionChat()` |
| `chat_remoto.js` | Solo `rem_chat_ventana.html`: su WebSocket (rol `chat`) y su anfitrión |
| `overlay_ui.js` | Caja de texto e indicador del escritorio fijado en la esquina (el antiguo modo overlay); en ventana monta el panel de chat |
| `escritorio_ui.js` / `escritorio.css` | Modo escritorio: inclinación al arrastrar, región de clic, reacciones, botones, menú, burbuja y fijar en la esquina |
| `menu_ventana.js` | Menú del clic derecho de la ventana (cambiar de modo, abrir panel, cerrar) |
| `temas.css` | Los tres temas (Synthwave, Cristal, Yoru) como tokens `--t-*`; los usan el chat, el escritorio y `rem_panel.html` |
| `ws.js` | WebSocket con `rem_avatar_server.py` |

El modo escritorio (`?modo=escritorio`, `&fijo=1` fijado en la esquina; `?modo=overlay` es un
alias de fijado) usa esta misma página con `escritorio_ui.js` en vez del panel; ver "Modo
escritorio" y "Lanzador Yoru y escritorio fijado" en CLAUDE.md.
