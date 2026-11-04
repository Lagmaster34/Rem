# vendor/ — módulos JS servidos en local

`rem_avatar.html` carga three.js y three-vrm desde aquí (vía el HTTP de
`rem_avatar_server.py`, que sirve toda la raíz del proyecto) en vez de desde
esm.sh: el avatar arranca sin internet.

`esm/` es un **espejo exacto** de los archivos que esm.sh servía (mismos bundles
`es2022`), solo con los imports absolutos reescritos a `/vendor/esm/...`.

| Paquete | Versión | Licencia |
|---|---|---|
| three | 0.169.0 (página + `GLTFLoader`) | MIT — `licencias/LICENSE_three` |
| three | 0.164.1 (el que usan three-vrm y three-vrm-animation) | MIT — `licencias/LICENSE_three` |
| @pixiv/three-vrm | 2.1.3 | MIT — `licencias/LICENSE_three-vrm` |
| @pixiv/three-vrm-animation | 2.1.3 | MIT — `licencias/LICENSE_three-vrm-animation` |

**Dos copias de three, a propósito.** esm.sh resolvía el peer `three@^0.164.1`
de three-vrm a 0.164.1, distinto del 0.169.0 que importa la página. Así
funcionaba ya antes de vendorizar; se dejó igual para no cambiar el
comportamiento. Unificarlas es un cambio aparte, que habría que probar.

Regenerar (necesita internet solo ese momento):

```bash
venv/bin/python vendor/espejo_esm.py vendor/esm
```
