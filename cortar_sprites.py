"""
Corta la imagen con todos los sprites de Rem y los guarda como PNGs
individuales con fondo transparente en la carpeta sprites/.

USO:
  1. Pon la imagen del collage en la misma carpeta que este script.
  2. Cambia IMAGEN_COLLAGE al nombre exacto de tu archivo.
  3. Ejecuta: python cortar_sprites.py
"""

import os
import numpy as np
from PIL import Image

# ── CONFIGURACION ─────────────────────────────────────────────────────
IMAGEN_COLLAGE = "sprites_collage.png"   # ← cambia al nombre de tu imagen

# Nombres en orden: [fila0, fila1, fila2, ...]
# Cada fila es una lista con los nombres de izquierda a derecha
NOMBRES = [
    ["idle_0",    "idle_1",    "idle_2",    "idle_3"],
    ["talking_0", "talking_1", "talking_2", "talking_3"],
    ["thinking_0","thinking_1"],
]

UMBRAL_NEGRO   = 15    # píxeles con RGB < 15 en todos los canales = fondo negro
MIN_TAMAÑO_PX  = 30    # ignorar grupos más pequeños que esto (ruido)
PADDING        = 6     # píxeles extra alrededor de cada sprite al recortar
SPRITES_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")
# ──────────────────────────────────────────────────────────────────────


def quitar_fondo_negro(img_rgba, umbral=UMBRAL_NEGRO):
    """Hace transparentes todos los píxeles casi-negros."""
    arr = np.array(img_rgba, dtype=np.uint8)
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    mascara_negra = (r < umbral) & (g < umbral) & (b < umbral)
    arr[:,:,3][mascara_negra] = 0
    return Image.fromarray(arr, "RGBA")


def encontrar_grupos(valores, min_tam=MIN_TAMAÑO_PX):
    """Devuelve lista de (inicio, fin) de grupos de True consecutivos."""
    grupos = []
    en_grupo = False
    inicio = 0
    for i, v in enumerate(valores):
        if v and not en_grupo:
            inicio = i
            en_grupo = True
        elif not v and en_grupo:
            if i - inicio >= min_tam:
                grupos.append((inicio, i))
            en_grupo = False
    if en_grupo and len(valores) - inicio >= min_tam:
        grupos.append((inicio, len(valores)))
    return grupos


def procesar():
    os.makedirs(SPRITES_DIR, exist_ok=True)

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), IMAGEN_COLLAGE)
    if not os.path.exists(ruta):
        print(f"❌ No encontré la imagen: {ruta}")
        print("   Pon el collage en la misma carpeta que este script y ajusta IMAGEN_COLLAGE.")
        return

    print(f"📂 Cargando: {ruta}")
    img    = Image.open(ruta).convert("RGBA")
    arr    = np.array(img)
    ancho, alto = img.size

    # Máscara de píxeles con contenido (no negros)
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
    mask = (r > UMBRAL_NEGRO) | (g > UMBRAL_NEGRO) | (b > UMBRAL_NEGRO)

    # Encontrar filas con contenido → franjas horizontales
    filas_con_contenido = np.any(mask, axis=1)
    franjas = encontrar_grupos(filas_con_contenido)

    print(f"✅ Detecté {len(franjas)} filas de sprites")

    guardados = 0
    for fi, (y1, y2) in enumerate(franjas):
        if fi >= len(NOMBRES):
            print(f"⚠️  Fila {fi+1}: más filas de las esperadas, se ignora")
            continue

        # Dentro de esta franja, encontrar columnas con contenido
        franja_mask = mask[y1:y2, :]
        cols_con_contenido = np.any(franja_mask, axis=0)
        columnas = encontrar_grupos(cols_con_contenido)

        print(f"   Fila {fi+1}: {len(columnas)} sprites detectados")

        for ci, (x1, x2) in enumerate(columnas):
            if ci >= len(NOMBRES[fi]):
                print(f"   ⚠️  Columna {ci+1} sin nombre asignado, se ignora")
                continue

            nombre = NOMBRES[fi][ci]

            # Añadir padding sin salirse de los límites
            cx1 = max(0,     x1 - PADDING)
            cy1 = max(0,     y1 - PADDING)
            cx2 = min(ancho, x2 + PADDING)
            cy2 = min(alto,  y2 + PADDING)

            recorte = img.crop((cx1, cy1, cx2, cy2))
            recorte = quitar_fondo_negro(recorte)

            # Recortar al bounding box real del sprite (sin bordes vacíos)
            bbox = recorte.getbbox()
            if bbox:
                recorte = recorte.crop(bbox)

            salida = os.path.join(SPRITES_DIR, f"{nombre}.png")
            recorte.save(salida, "PNG")
            print(f"   💾 {nombre}.png  ({recorte.width}×{recorte.height}px)")
            guardados += 1

    print(f"\n✅ Listo. {guardados} sprites guardados en: {SPRITES_DIR}")
    print("   Reinicia Rem.py para verlos.")


if __name__ == "__main__":
    procesar()
