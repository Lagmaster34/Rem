# models/ — modelos VRM alternativos del avatar

Modelo VRM activo por defecto desde `config.toml` → `[avatar].modelo` (ver `CONFIG.modelos`
en `rem_avatar.html`). `rem.vrm` (en la raíz del proyecto, ver el README de la raíz /
`INSTALL.md`) sigue disponible como alternativa — ninguno de los dos se borra al agregar el
otro, el código no depende de un modelo concreto.

**No van al repo** (`.gitignore`: `*.glb` y `models/*.vrm`) — hay que colocarlos a mano.

## `rem_naenae.vrm`

Descargado como `.glb` de VRoid Hub y renombrado a `.vrm` (mismos bytes — la licencia
prohíbe modificarlo, y renombrar la extensión no cambia el contenido del archivo).

- **Autor**: NaeNae (Discord: `NaeNae#6225`, contacto: `ruffrabittz@gmail.com`).
- **Fuente**: [VRoid Hub](https://hub.vroid.com/) — página de licencia:
  <https://hub.vroid.com/license?allowed_to_use_user=everyone&characterization_allowed_user=everyone&corporate_commercial_use=allow&credit=necessary&modification=disallow&personal_commercial_use=nonprofit&redistribution=allow&sexual_expression=allow&version=1&violent_expression=allow>
- **Condiciones** (leídas del propio archivo, bloque `extensions.VRM.meta`):
  - Uso comercial (corporativo): **no permitido** (`corporate_commercial_use=disallow` en el
    meta del archivo — el link de arriba lo muestra en "allow" porque es la licencia
    genérica de la plantilla de VRoid Hub, pero el meta embebido en este `.vrm` en concreto
    trae `commercialUssageName: "Disallow"`, que es el que rige).
  - Uso comercial personal: sin ánimo de lucro (`personal_commercial_use=nonprofit`).
  - **Modificación: no permitida** (`modification=disallow`) — por eso este archivo se
    coloca tal cual, solo renombrado de `.glb` a `.vrm`. No se le quita la textura
    "Thumbnail" no usada, no se le agregan morph targets ni se tocan sus binds, aunque eso
    sería una mejora técnica (ver el análisis en el historial de este proyecto).
  - Redistribución: permitida, **con crédito obligatorio** a "NaeNae".
  - Expresión violenta/sexual: permitida (irrelevante para este proyecto).
  - Si este proyecto (o este modelo) se comparte o publica alguna vez, hay que incluir el
    crédito de arriba.

Este modelo es más pesado que `rem.vrm` (más vértices, más texturas 2048², sin colisionadores
de spring bone en `rem.vrm` pero 12 en este) — el costo medido en FPS es moderado (~7% menos
que `rem.vrm` en esta máquina, ver CLAUDE.md), y el lipsync se ve bien en vivo, mejor incluso
que en `rem.vrm` — verificado por Esteban, no solo con capturas fijas (que no alcanzan para
juzgar movimiento).
