# models/ — modelos locales (voz y avatar)

Nada de esta carpeta se versiona salvo los README (`.gitignore` + `hooks/`): los modelos son
**solo locales**.

## `vrm/` — modelos del avatar

Se elige en caliente desde la ventana (botón 👤 del chat o `/modelo`); la elección queda en
`preferencias.json`. Por defecto: `config.toml` → `[avatar].modelo`. Para agregar uno (p. ej.
Yoru), dejar el `.vrm` en `models/vrm/`: `rem_avatar.html` autodetecta VRM 0.x/1.0, lipsync y
expresiones. Si su licencia pide crédito, anotarlo abajo.

| Archivo | Título | Autor | VRM | Licencia (del meta del archivo) | Crédito |
|---|---|---|---|---|---|
| `neru.vrm` | つらら | あわ | 0.x | VRoid Hub: todos, comercial OK, modificar y redistribuir OK | no obligatorio |
| `ls15.vrm` | LS15 | とまこ | 0.x | VRoid Hub: igual que つらら | no obligatorio |
| `lili.vrm` | Lili | Noel | 1.0 | VRM 1.0: comercial (empresa), redistribuir y modificar OK | **obligatorio: Noel** |
| `noir.vrm` | Noir | Noel | 1.0 | VRM 1.0: igual que Lili | **obligatorio: Noel** |

Origen: los cuatro vienen del paquete de la app Nerumi 0.10.0. Las condiciones son las que
declara el meta de cada archivo (no se pudieron contrastar con su página de VRoid Hub).
