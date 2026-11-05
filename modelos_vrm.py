"""modelos_vrm.py — los modelos VRM locales del avatar (models/vrm/*.vrm).

Lista lo que hay en disco para el selector de modelo (botón 👤 del chat,
/modelo, pestaña Modelo del panel) leyendo SOLO el chunk JSON del .glb — el
meta del VRM (título, autor, licencia) está ahí, no hace falta tocar los
buffers binarios (20-30 MB por modelo). Los VRM nunca se versionan: es la
carpeta local de cada máquina (ver .gitignore, hooks/ y models/README.md).

Para agregar un modelo (p. ej. Yoru cuando esté lista): dejar el .vrm en
models/vrm/. rem_avatar.html autodetecta lo que necesita de él; si el meta
exige crédito, anotarlo también en models/README.md.
"""
import json
import os
import struct

import config

CARPETA = os.path.join(config.BASE_DIR, "models", "vrm")

_cache: dict = {}   # ruta absoluta -> (mtime, dict) — el meta no cambia mientras el archivo no cambie


def _leer_json_glb(ruta: str) -> dict:
    with open(ruta, "rb") as f:
        cabecera = f.read(20)
        magic, _version, _total, largo, tipo = struct.unpack("<IIIII", cabecera)
        if magic != 0x46546C67 or tipo != 0x4E4F534A:
            raise ValueError("no es un glb")
        return json.loads(f.read(largo))


def _info(ruta: str) -> dict:
    """Meta normalizado de un .vrm, sea VRM 0.x (extensions.VRM) o 1.0
    (extensions.VRMC_vrm). Nunca lanza: un archivo ilegible vuelve con error."""
    rel = os.path.relpath(ruta, config.BASE_DIR).replace(os.sep, "/")
    base = {"ruta": rel, "archivo": os.path.basename(ruta),
            "mb": round(os.path.getsize(ruta) / 1e6, 1)}
    try:
        js = _leer_json_glb(ruta)
    except Exception as e:
        return {**base, "titulo": os.path.basename(ruta), "error": f"{type(e).__name__}: {e}"}
    ext = js.get("extensions", {})
    if "VRMC_vrm" in ext:
        m = ext["VRMC_vrm"].get("meta", {})
        return {**base, "version": "1.0",
                "titulo": m.get("name") or base["archivo"],
                "autor": ", ".join(m.get("authors") or []) or "desconocido",
                "credito": m.get("creditNotation") == "required",
                "redistribucion": bool(m.get("allowRedistribution")),
                "modificacion": m.get("modification"),
                "comercial": m.get("commercialUsage"),
                "licenciaUrl": m.get("licenseUrl")}
    m = ext.get("VRM", {}).get("meta", {})
    url = m.get("otherLicenseUrl") or m.get("otherPermissionUrl") or ""
    return {**base, "version": "0.x",
            "titulo": m.get("title") or base["archivo"],
            "autor": m.get("author") or "desconocido",
            # VRoid Hub codifica las condiciones en la URL de la licencia.
            "credito": "credit=necessary" in url,
            "redistribucion": "redistribution=allow" in url if url else None,
            "modificacion": ("allow" if "modification=allow" in url else "disallow") if url else None,
            "comercial": m.get("commercialUssageName"),
            "licenciaUrl": url or None}


def listar() -> list[dict]:
    """Los .vrm de models/vrm/, ordenados por título."""
    if not os.path.isdir(CARPETA):
        return []
    res = []
    for nombre in sorted(os.listdir(CARPETA)):
        if not nombre.lower().endswith(".vrm"):
            continue
        ruta = os.path.join(CARPETA, nombre)
        mtime = os.path.getmtime(ruta)
        hit = _cache.get(ruta)
        if not hit or hit[0] != mtime:
            hit = (mtime, _info(ruta))
            _cache[ruta] = hit
        res.append(hit[1])
    return sorted(res, key=lambda d: d["titulo"].lower())


if __name__ == "__main__":
    for d in listar():
        print(json.dumps(d, ensure_ascii=False))
