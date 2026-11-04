# hooks/ — hooks de git del proyecto

Los hooks de git **no viajan con el repo**: un clon nuevo no los tiene activos hasta instalarlos.
Hay que hacerlo una vez por clon.

| Hook | Qué rechaza |
|---|---|
| `pre-commit` | Un commit que incluya `*.onnx`, `*.onnx.json` o algo bajo `models/piper/` (o la ruta vieja `models/yoru_piper/`), aunque se haya agregado con `git add -f`. También una copia renombrada del modelo (compara el contenido con los SHA-256 del `manifest.json` local). |
| `pre-push` | Un push cuyos commits contengan esas rutas — segunda barrera por si un commit se hizo con `--no-verify`. |

Los modelos de voz Piper no se versionan nunca (además están en `.gitignore`).

## Instalar

Opción A — que git use esta carpeta directamente (los cambios a `hooks/` aplican solos):

```bash
git config core.hooksPath hooks
```

Opción B — copiarlos (hay que repetirlo si cambian):

```bash
cp hooks/pre-commit hooks/pre-push .git/hooks/ && chmod +x .git/hooks/pre-commit .git/hooks/pre-push
```

Comprobar que están activos:

```bash
echo x > /tmp/prueba.onnx && cp /tmp/prueba.onnx . && git add -f prueba.onnx && git commit -m prueba
# debe decir "pre-commit: RECHAZADO"; después: git rm --cached prueba.onnx && rm prueba.onnx
```

`git commit --no-verify` y `git push --no-verify` se saltan los hooks: no usarlos en este repo.
