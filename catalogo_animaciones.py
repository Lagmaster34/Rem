#!/usr/bin/env python3
"""catalogo_animaciones.py — genera/actualiza Animaciones/catalogo.json.

El catálogo es la ÚNICA fuente de verdad de los clips .vrma del avatar: lo leen
rem_avatar.html (repertorio, estado -> clip, paleta /animaciones) y el panel de
control (pestaña Animaciones). Ver "Catálogo de animaciones" en CLAUDE.md.

Qué hace este script, y qué NO:
  - MIDE cada .vrma con cinemática directa propia (sin three.js): duración, giro
    de la cadera, desplazamiento, inclinación del torso y el ángulo de cada
    brazo respecto al torso a lo largo de TODO el clip (la lección de
    Relax.vrma: no basta con mirar el primer frame). Con eso recalcula
    `medido`, `avisos`, `giraCuerpo` y `fundidoEntradaS` en cada corrida.
  - Comprueba el SHA-256 de los clips que figuran en un provenance.json.
  - Agrega los clips NUEVOS con valores generados (etiqueta desde el nombre de
    archivo, origen desde un provenance.json de su carpeta o "desconocido").
  - CONSERVA todo lo curado a mano de los clips existentes (etiqueta,
    categoria, origen, peso, horas, nota, activoPorDefecto) y las secciones
    `categorias`/`porEstado`/`poseBase`/`ajustes`. Un clip que ya no está en disco no se
    borra: queda con "falta": true (el avatar lo ignora).

    venv/bin/python catalogo_animaciones.py          # actualiza el catálogo
    venv/bin/python catalogo_animaciones.py --check  # solo informa, no escribe
"""
import argparse
import hashlib
import json
import math
import os
import re
import struct
import sys

import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANIM_DIR = os.path.join(BASE_DIR, "Animaciones")
CATALOGO = os.path.join(ANIM_DIR, "catalogo.json")

# Umbrales de los avisos. Calibrados contra los clips viejos, cuyas cifras ya
# estaban medidas (CLAUDE.md): Relax.vrma da brazos >60° el 82% del ciclo (antes:
# 83-85%), VRMA_01/VRMA_05 giran 418,5°/408,2°, LookAround 40,4°.
BRAZO_ALTO_GRADOS = 60    # brazo a más de esto del "abajo" del torso = levantado
GIRO_CUERPO_GRADOS = 90   # más que esto y Rem deja de mirar a cámara
ACROBACIA_GRADOS = 90     # torso inclinado más que esto (tumbada, de cabeza)
SE_SALE_M = 0.5           # la cadera se aleja más que esto en horizontal
LARGO_S = 30              # más que esto secuestra el cuerpo demasiado tiempo
FUNDIDO_LARGO_S = 0.8     # fundido de entrada si el clip arranca con los brazos arriba
# Avisos que impiden que un clip NUEVO arranque activo por defecto. Los brazos
# altos al empezar/terminar no descalifican en 'dance' (es su estilo y se
# reproducen una vez, con el fundido largo); en el resto, sí.
AVISOS_DESCALIFICAN = {"acrobacia", "se-sale", "largo"}
AVISOS_BRAZOS = {"empieza-brazos-alto", "termina-brazos-alto"}


# ── Lectura de glTF binario ────────────────────────────────────────────
def _leer_glb(ruta):
    with open(ruta, "rb") as f:
        datos = f.read()
    magic, _, total = struct.unpack_from("<III", datos, 0)
    if magic != 0x46546C67:
        raise ValueError("no es un .glb")
    off, js, binario = 12, None, b""
    while off < total:
        n, tipo = struct.unpack_from("<II", datos, off)
        trozo = datos[off + 8: off + 8 + n]
        if tipo == 0x4E4F534A:
            js = json.loads(trozo)
        elif tipo == 0x004E4942:
            binario = trozo
        off += 8 + n
    return js, binario, hashlib.sha256(datos).hexdigest()


_NCOMP = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}


def _accesor(js, binario, i):
    a = js["accessors"][i]
    if a["componentType"] != 5126:
        raise ValueError("accesor no float")
    bv = js["bufferViews"][a["bufferView"]]
    n = _NCOMP[a["type"]]
    inicio = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    paso = bv.get("byteStride", 4 * n)
    if paso == 4 * n:
        arr = np.frombuffer(binario, dtype="<f4", count=a["count"] * n, offset=inicio)
        return arr.reshape(a["count"], n).astype(np.float64)
    return np.array([np.frombuffer(binario, "<f4", n, inicio + k * paso)
                     for k in range(a["count"])], np.float64)


# ── Cinemática directa ─────────────────────────────────────────────────
def _qmul(a, b):
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    return np.array([w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2,
                     w1*z2 + x1*y2 - y1*x2 + z1*w2, w1*w2 - x1*x2 - y1*y2 - z1*z2])


def _qrot(q, v):
    u, w = np.array(q[:3]), q[3]
    return 2*np.dot(u, v)*u + (w*w - np.dot(u, u))*v + 2*w*np.cross(u, v)


def _muestrear(tiempos, valores, t):
    if t <= tiempos[0]:
        return valores[0]
    if t >= tiempos[-1]:
        return valores[-1]
    i = np.searchsorted(tiempos, t) - 1
    f = (t - tiempos[i]) / (tiempos[i + 1] - tiempos[i])
    a, b = valores[i], valores[i + 1]
    if len(a) == 4:   # nlerp: de sobra para medir ángulos
        if np.dot(a, b) < 0:
            b = -b
        q = a * (1 - f) + b * f
        return q / np.linalg.norm(q)
    return a * (1 - f) + b * f


def medir(ruta):
    """Medidas de un .vrma, o lanza si no se puede leer como VRM Animation."""
    js, binario, sha = _leer_glb(ruta)
    ext = (js.get("extensions") or {}).get("VRMC_vrm_animation")
    if not ext:
        raise ValueError("sin extensión VRMC_vrm_animation")
    huesos = {k: v["node"] for k, v in ext.get("humanoid", {}).get("humanBones", {}).items()}
    if "hips" not in huesos:
        raise ValueError("sin hueso hips")
    nodos = js["nodes"]
    padre = {h: i for i, n in enumerate(nodos) for h in n.get("children", [])}
    pistas, dur = {}, 0.0
    for anim in js.get("animations", []):
        for c in anim["channels"]:
            s = anim["samplers"][c["sampler"]]
            t = _accesor(js, binario, s["input"]).ravel()
            pistas[(c["target"]["node"], c["target"]["path"])] = (t, _accesor(js, binario, s["output"]))
            dur = max(dur, float(t[-1]))
    rest_r = [np.array(n.get("rotation", [0, 0, 0, 1]), float) for n in nodos]
    rest_t = [np.array(n.get("translation", [0, 0, 0]), float) for n in nodos]

    def pose(t):
        cache = {}

        def mundo(i):
            if i not in cache:
                r = _muestrear(*pistas[(i, "rotation")], t) if (i, "rotation") in pistas else rest_r[i]
                p = _muestrear(*pistas[(i, "translation")], t) if (i, "translation") in pistas else rest_t[i]
                if i in padre:
                    pr, pp = mundo(padre[i])
                    cache[i] = (_qmul(pr, r), pp + _qrot(pr, p))
                else:
                    cache[i] = (r, p)
            return cache[i]
        return mundo

    torso_alto = huesos.get("upperChest", huesos.get("chest", huesos.get("spine", huesos["hips"])))
    ts = np.linspace(0, dur, max(2, min(400, int(dur * 30) + 1))) if dur > 0 else np.array([0.0])
    yaws, posiciones, inclin = [], [], []
    brazos = {"Izq": [], "Der": []}
    for t in ts:
        mundo = pose(t)
        hr, hp = mundo(huesos["hips"])
        adelante = _qrot(hr, np.array([0, 0, 1.0]))
        yaws.append(math.atan2(adelante[0], adelante[2]))
        posiciones.append(hp)
        arriba = mundo(torso_alto)[1] - hp
        arriba = arriba / (np.linalg.norm(arriba) or 1)
        inclin.append(math.degrees(math.acos(np.clip(arriba[1], -1, 1))))
        for lado, ua, la in (("Izq", "leftUpperArm", "leftLowerArm"), ("Der", "rightUpperArm", "rightLowerArm")):
            if ua in huesos and la in huesos:
                v = mundo(huesos[la])[1] - mundo(huesos[ua])[1]
                v = v / (np.linalg.norm(v) or 1)
                # 0° = colgando a lo largo del torso, 90° = en cruz, 180° = arriba
                brazos[lado].append(math.degrees(math.acos(np.clip(np.dot(v, -arriba), -1, 1))))
    y = np.unwrap(np.array(yaws))
    pos = np.array(posiciones)
    medido = {
        "durS": round(dur, 2),
        "giroGrados": round(math.degrees(y.max() - y.min()), 1),
        "desplazamientoM": round(float(np.max(np.linalg.norm((pos - pos[0])[:, [0, 2]], axis=1))), 2),
        "inclinacionMaxGrados": round(max(inclin), 1),
        "specVersion": "specVersion" in ext,
    }
    for lado, angulos in brazos.items():
        if angulos:
            a = np.array(angulos)
            medido[f"brazo{lado}"] = {
                "inicio": round(float(a[0]), 1), "fin": round(float(a[-1]), 1),
                "mediana": round(float(np.median(a)), 1), "max": round(float(a.max()), 1),
                "fraccionAlto": round(float(np.mean(a > BRAZO_ALTO_GRADOS)), 2),
            }
    return medido, sha


def avisos_de(m):
    av = []
    brazos = [m[k] for k in ("brazoIzq", "brazoDer") if k in m]
    if any(b["inicio"] > BRAZO_ALTO_GRADOS for b in brazos):
        av.append("empieza-brazos-alto")
    if any(b["fin"] > BRAZO_ALTO_GRADOS for b in brazos):
        av.append("termina-brazos-alto")
    if any(b["fraccionAlto"] > 0.5 for b in brazos):
        av.append("brazos-alto-mayoria")
    if m["giroGrados"] > GIRO_CUERPO_GRADOS:
        av.append("gira")
    if m["inclinacionMaxGrados"] > ACROBACIA_GRADOS:
        av.append("acrobacia")
    if m["desplazamientoM"] > SE_SALE_M:
        av.append("se-sale")
    if m["durS"] > LARGO_S:
        av.append("largo")
    return av


# ── Valores generados para clips nuevos ─────────────────────────────────
def categoria_de(rel):
    """Categoría por carpeta: Animaciones/nerumi/<cat>/..., con actions/<x>/
    como su propia categoría (sit, lying) y greet.vrma suelto en saludos."""
    partes = rel.split("/")
    if partes[0] == "VRMA_MotionPack":
        return "rem-anterior"
    if partes[0] == "nerumi":
        if len(partes) == 2:
            return "greetings" if partes[1].startswith("greet") else "otros"
        if partes[1] == "actions" and len(partes) > 3:
            return partes[2]
        return partes[1]
    return partes[0] if len(partes) > 1 else "otros"


def etiqueta_de(rel):
    nombre = os.path.splitext(os.path.basename(rel))[0]
    nombre = re.sub(r"^@KA_(Idle|Sit|Combat|Swimming|Death)?\d*_?", "", nombre)
    nombre = re.sub(r"^(Rare)?Dance\d+-", "", nombre)
    nombre = re.sub(r"([a-z])([A-Z])", r"\1 \2", nombre).replace("-", " ").replace("_", " ")
    return nombre.strip().capitalize() or rel


def _provenance_por_archivo():
    """{ruta relativa a Animaciones/: (entrada, provenance)} de todos los
    provenance.json (sus 'file' son relativos a la carpeta del pack, nerumi/)."""
    res = {}
    for d, _, archivos in os.walk(ANIM_DIR):
        if "provenance.json" not in archivos:
            continue
        ruta = os.path.join(d, "provenance.json")
        with open(ruta, encoding="utf-8") as f:
            prov = json.load(f)
        rel_prov = os.path.relpath(ruta, ANIM_DIR)
        for clip in prov.get("clips", []):
            # 'file' viene relativo a la raíz del pack de Nerumi (la carpeta que
            # aquí es Animaciones/nerumi/): se resuelve buscando el sufijo.
            sufijo = clip["file"]
            raiz_pack = os.path.relpath(d, ANIM_DIR).split("/")[0]
            res[f"{raiz_pack}/{sufijo}"] = (clip, prov, rel_prov)
    return res


def origen_generado(rel, provs):
    if rel in provs:
        clip, prov, rel_prov = provs[rel]
        return {"autor": prov.get("creator", "desconocido"), "pack": prov.get("packageName"),
                "url": None, "licencia": "desconocida", "fuente": rel_prov}
    return {"autor": "desconocido", "pack": None, "url": None, "licencia": "desconocida",
            "fuente": "sin datos: completar a mano"}


def activo_generado(categoria, avisos, categorias):
    if not categorias.get(categoria, {}).get("activa", False):
        return False
    if AVISOS_DESCALIFICAN & set(avisos):
        return False
    if categoria != "dance" and AVISOS_BRAZOS & set(avisos):
        return False
    return True


# ── Main ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="solo informa; no escribe el catálogo")
    args = ap.parse_args()

    if os.path.exists(CATALOGO):
        with open(CATALOGO, encoding="utf-8") as f:
            cat = json.load(f)
    else:
        cat = {"version": 1, "categorias": {}, "porEstado": {}, "poseBase": {"archivo": None}, "clips": {}}
    clips_previos = cat.get("clips", {})
    provs = _provenance_por_archivo()

    nuevos, errores, sha_mal, clips = [], [], [], {}
    ilegibles = set()
    for d, _, archivos in sorted(os.walk(ANIM_DIR)):
        for a in sorted(archivos):
            if not a.lower().endswith(".vrma"):
                continue
            rel = os.path.relpath(os.path.join(d, a), ANIM_DIR).replace(os.sep, "/")
            previo = clips_previos.get(rel)
            try:
                medido, sha = medir(os.path.join(d, a))
            except Exception as e:
                errores.append(f"{rel}: {type(e).__name__}: {e}")
                ilegibles.add(rel)
                if previo:
                    clips[rel] = {**previo, "error": f"{type(e).__name__}: {e}"}
                continue
            avisos = avisos_de(medido)
            if previo is None:
                categoria = categoria_de(rel)
                curado = {
                    "etiqueta": etiqueta_de(rel), "categoria": categoria,
                    "origen": origen_generado(rel, provs), "peso": 1, "horas": None, "nota": None,
                    "activoPorDefecto": activo_generado(categoria, avisos, cat.get("categorias", {})),
                }
                nuevos.append(rel)
            else:
                curado = {k: previo.get(k) for k in
                          ("etiqueta", "categoria", "origen", "peso", "horas", "nota", "activoPorDefecto")}
            entrada = {
                **curado,
                "giraCuerpo": "gira" in avisos,
                "fundidoEntradaS": FUNDIDO_LARGO_S if "empieza-brazos-alto" in avisos else None,
                "avisos": avisos,
                "medido": medido,
                "sha256": sha,
            }
            if rel in provs:
                ok = provs[rel][0].get("sha256") == sha
                entrada["origen"] = {**entrada["origen"], "sha256Verificado": ok}
                if not ok:
                    sha_mal.append(rel)
            clips[rel] = entrada

    faltan = [rel for rel in clips_previos if rel not in clips]
    for rel in faltan:
        clips[rel] = {**clips_previos[rel], "falta": True}
    for rel, e in clips.items():
        if rel not in faltan:
            e.pop("falta", None)
        if rel not in ilegibles:
            e.pop("error", None)

    cat["clips"] = dict(sorted(clips.items()))
    sin_categoria = sorted({e["categoria"] for e in clips.values()} - set(cat.get("categorias", {})))

    print(f"[Catálogo] {len(clips)} clips ({len(nuevos)} nuevos, {len(faltan)} faltan en disco, "
          f"{len(errores)} ilegibles)")
    for x in errores:
        print(f"  ilegible: {x}")
    for rel in faltan:
        print(f"  falta en disco (se conserva lo curado): {rel}")
    for rel in sha_mal:
        print(f"  SHA-256 distinto del provenance.json: {rel}")
    if sin_categoria:
        print(f"  categorías sin definir en 'categorias': {', '.join(sin_categoria)}")
    print(f"  provenance verificados: {sum(1 for e in clips.values() if e.get('origen', {}).get('sha256Verificado'))}"
          f"/{sum(1 for r in clips if r in provs)}")

    if args.check:
        return 1 if (errores or sha_mal) else 0
    tmp = CATALOGO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, CATALOGO)
    print(f"[Catálogo] escrito {os.path.relpath(CATALOGO, BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
