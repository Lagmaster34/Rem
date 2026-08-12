"""Inspecciona un archivo .vrm (GLB binario) y vuelca su estructura relevante.

Un .vrm es un GLB: cabecera de 12 bytes (magic "glTF", version, length)
seguida de chunks (length uint32 + type uint32 "JSON"/"BIN\\0" + data).
Solo se necesita el primer chunk (JSON) para leer los metadatos VRM.
"""

import json
import struct
import sys

RUTA_VRM = "rem.vrm"

GLB_MAGIC = b"glTF"
CHUNK_TYPE_JSON = b"JSON"


def leer_glb_json(ruta):
    with open(ruta, "rb") as f:
        data = f.read()

    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"Magic inválido: {magic!r} (se esperaba {GLB_MAGIC!r})")

    offset = 12
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, offset)
    offset += 8

    if chunk_type != CHUNK_TYPE_JSON:
        raise ValueError(f"Primer chunk no es JSON: {chunk_type!r}")

    chunk_data = data[offset:offset + chunk_length]
    gltf = json.loads(chunk_data)

    return gltf, version, length


def encabezado(titulo):
    print()
    print("=" * 60)
    print(titulo)
    print("=" * 60)


def detectar_version_vrm(gltf):
    extensions = gltf.get("extensions", {})
    if "VRMC_vrm" in extensions:
        return "1.0", extensions["VRMC_vrm"]
    if "VRM" in extensions:
        return "0.x", extensions["VRM"]
    return None, None


def dump_expresiones_vrm1(vrmc_vrm):
    encabezado("EXPRESIONES (VRM 1.0)")
    expressions = vrmc_vrm.get("expressions", {})

    preset = expressions.get("preset", {})
    print(f"-- preset ({len(preset)}) --")
    for nombre in preset.keys():
        print(f"  {nombre}")

    custom = expressions.get("custom", {})
    print(f"-- custom ({len(custom)}) --")
    for nombre in custom.keys():
        print(f"  {nombre}")


def dump_expresiones_vrm0(vrm_ext):
    encabezado("BLEND SHAPE GROUPS (VRM 0.x)")
    blend_shape_master = vrm_ext.get("blendShapeMaster", {})
    grupos = blend_shape_master.get("blendShapeGroups", [])
    print(f"-- blendShapeGroups ({len(grupos)}) --")
    for grupo in grupos:
        nombre = grupo.get("name", "<sin name>")
        preset_name = grupo.get("presetName", "<sin presetName>")
        print(f"  name={nombre!r}  presetName={preset_name!r}")


def dump_morph_targets(gltf):
    encabezado("MORPH TARGETS DEL MODELO (meshes[].primitives[].extras.targetNames)")
    nombres = []
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            extras = prim.get("extras", {})
            for nombre in extras.get("targetNames", []):
                if nombre not in nombres:
                    nombres.append(nombre)

    print(f"-- únicos ({len(nombres)}) --")
    for nombre in nombres:
        print(f"  {nombre}")


def dump_huesos_humanoides(gltf, version, vrm_ext):
    encabezado("HUESOS HUMANOIDES MAPEADOS (humanoid.humanBones)")

    if version == "1.0":
        human_bones = vrm_ext.get("humanoid", {}).get("humanBones", {})
        nombres = list(human_bones.keys())
    elif version == "0.x":
        human_bones = vrm_ext.get("humanoid", {}).get("humanBones", [])
        nombres = [b.get("bone", "<sin bone>") for b in human_bones]
    else:
        nombres = []

    print(f"-- mapeados ({len(nombres)}) --")
    for nombre in nombres:
        print(f"  {nombre}")


def dump_spring_bones_vrm0(vrm_ext):
    encabezado("SPRING BONES (VRM 0.x extensions.VRM.secondaryAnimation)")
    secondary = vrm_ext.get("secondaryAnimation")

    if not secondary:
        print("extensions.VRM.secondaryAnimation no existe o está vacío.")
        return

    bone_groups = secondary.get("boneGroups", [])
    collider_groups = secondary.get("colliderGroups", [])

    if not bone_groups and not collider_groups:
        print("extensions.VRM.secondaryAnimation existe pero no tiene boneGroups ni colliderGroups.")
        return

    print(f"boneGroups: {len(bone_groups)}")
    print(f"colliderGroups: {len(collider_groups)}")

    if bone_groups:
        print()
        print("-- detalle de boneGroups --")
        for i, grupo in enumerate(bone_groups):
            comment = grupo.get("comment", "<sin comment>")
            stiffiness = grupo.get("stiffiness", "<sin stiffiness>")
            drag_force = grupo.get("dragForce", "<sin dragForce>")
            gravity_power = grupo.get("gravityPower", "<sin gravityPower>")
            n_bones_raiz = len(grupo.get("bones", []))
            print(f"  [{i}] comment={comment!r}")
            print(f"      stiffiness={stiffiness}  dragForce={drag_force}  gravityPower={gravity_power}")
            print(f"      huesos raíz en 'bones': {n_bones_raiz}")


def main():
    try:
        gltf, glb_version, glb_length = leer_glb_json(RUTA_VRM)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Error leyendo {RUTA_VRM}: {e}", file=sys.stderr)
        sys.exit(1)

    encabezado("CABECERA GLB")
    print(f"archivo:     {RUTA_VRM}")
    print(f"glb version: {glb_version}")
    print(f"glb length:  {glb_length} bytes")

    version, vrm_ext = detectar_version_vrm(gltf)

    encabezado("VERSIÓN VRM DETECTADA")
    if version == "1.0":
        print("VRM 1.0  (extensions.VRMC_vrm presente)")
    elif version == "0.x":
        print("VRM 0.x  (extensions.VRM presente)")
    else:
        print("No se detectó extensión VRM (ni VRMC_vrm ni VRM)")

    if version == "1.0":
        dump_expresiones_vrm1(vrm_ext)
    elif version == "0.x":
        dump_expresiones_vrm0(vrm_ext)

    dump_morph_targets(gltf)

    if vrm_ext is not None:
        dump_huesos_humanoides(gltf, version, vrm_ext)

    if version == "0.x":
        dump_spring_bones_vrm0(vrm_ext)


if __name__ == "__main__":
    main()
