"""Regenera vendor/esm/: espejo exacto de los módulos que esm.sh servía a
rem_avatar.html, con los imports absolutos ("/three@...") reescritos a
"/vendor/esm/...". Solo hace falta internet para correr ESTE script; la página
ya no lo necesita. Uso (desde la raíz del proyecto):

    venv/bin/python vendor/espejo_esm.py vendor/esm

Para cambiar de versión: editar ENTRADAS y los imports de rem_avatar.html.
"""
import os
import re
import sys
import urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "vendor/esm"
ENTRADAS = ["/three@0.169.0", "/three@0.169.0/examples/jsm/loaders/GLTFLoader.js",
            "/@pixiv/three-vrm@2.1.3", "/@pixiv/three-vrm-animation@2.1.3"]
RE = re.compile(r'((?:from|import)\s*\(?\s*)(["\'])(/[^"\'\s]+)\2')
def local(p):
    path, _, q = p.partition("?")
    path = path.replace("^", "")
    if q: path += "__" + q.replace("=", "-").replace("&", "_")
    if not path.endswith((".mjs", ".js")): path += ".js"
    return path.lstrip("/")
hechos, cola = {}, list(ENTRADAS)
while cola:
    p = cola.pop()
    if p in hechos: continue
    with urllib.request.urlopen("https://esm.sh" + p) as r:
        txt = r.read().decode()
    deps = [m.group(3) for m in RE.finditer(txt)]
    txt = RE.sub(lambda m: f'{m.group(1)}{m.group(2)}/vendor/esm/{local(m.group(3))}{m.group(2)}', txt)
    dst = os.path.join(OUT, local(p))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "w").write(txt)
    hechos[p] = local(p)
    cola += deps
for p, l in sorted(hechos.items()): print(f"{p}  ->  vendor/esm/{l}  ({os.path.getsize(os.path.join(OUT, l))} B)")
