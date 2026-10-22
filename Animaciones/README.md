# Animaciones/ — clips VRMA del avatar

Clips de animación de cuerpo (`.vrma`, formato [VRM Animation](https://vrm.dev/en/vrma/))
que `rem_avatar.html` reproduce sobre el modelo con `THREE.AnimationMixer` +
`@pixiv/three-vrm-animation`. **No van al repo** (están en `.gitignore`, mismo criterio que
`rmvpe.pt` / `hubert_base.pt` / `rem.vrm`) — hay que descargarlos a mano.

## Dónde van

```
Animaciones/
├── catalogo.json       qué clips hay (sí se versiona — ver "Catálogo" más abajo)
├── VRMA_MotionPack/    los clips de antes (categoría "Rem anterior" en el catálogo)
└── nerumi/             los clips sacados de Nerumi, por categoría
```

`rem_avatar.html` no busca clips por su cuenta: usa los del catálogo, identificados por su ruta
relativa a esta carpeta (`nerumi/dance/Dance11-spooky.vrma`). Un clip nuevo tiene que pasar por
`catalogo_animaciones.py` para aparecer. Si un clip del catálogo falta en disco, el avatar cae a la
animación procedural con un aviso en consola (`[Anim] "<id>" no disponible: ... — se mantiene la
animación procedural`), no se rompe.

## De dónde se bajan

### 1. Pack de gestos/emociones — `tk256ailab/vrm-viewer` (licencia MIT)

Repo: <https://github.com/tk256ailab/vrm-viewer>, carpeta `VRMA/`.

Archivos (copiar tal cual a `Animaciones/VRMA_MotionPack/`). La columna "Uso" es la de antes del
catálogo: hoy el uso lo decide `catalogo.json` y casi todos quedan como "Rem anterior", apagados:

| Archivo | Uso |
|---|---|
| `Thinking.vrma`   | estado `thinking` (bucle) |
| `Sad.vrma`        | estado `sad` |
| `Angry.vrma`      | estado `angry` |
| `Surprised.vrma`  | estado `surprised` |
| `Blush.vrma`      | estado `happy` |
| `LookAround.vrma` | gesto de reposo (frecuente) |
| `Sleepy.vrma`     | gesto de reposo (solo 00:00–06:00) |
| `Goodbye.vrma`    | disponible, sin usar por ahora |
| `Clapping.vrma`   | disponible, sin usar por ahora |

El repo está bajo licencia MIT. No trae términos específicos para los `.vrma` más allá del
descargo general ("asegurate de tener los derechos apropiados para los modelos y
animaciones que uses").

### 2. Pack oficial VRoid — VRoid Project / pixiv Inc.

Descarga: <https://vroid.booth.pm/items/5512385> (pack "VRM Animation" oficial del VRoid
Project). Descomprimir y copiar `VRMA_01.vrma` … `VRMA_07.vrma` a
`Animaciones/VRMA_MotionPack/`.

| Archivo | Contenido | Uso |
|---|---|---|
| `VRMA_01.vrma` | mostrar cuerpo entero | gesto de reposo (poco frecuente) |
| `VRMA_02.vrma` | saludo | disponible, sin usar |
| `VRMA_03.vrma` | señal de V | disponible, sin usar |
| `VRMA_04.vrma` | disparar | disponible, sin usar |
| `VRMA_05.vrma` | girar | gesto de reposo (reemplaza el "giro de bailarina" a mano) |
| `VRMA_06.vrma` | pose de modelo | disponible, sin usar |
| `VRMA_07.vrma` | flexiones | gesto de reposo (poco frecuente) |

**Términos de uso** (ver `VRMA_MotionPack/Readme_VRMA_MotionPack_EN.txt`, incluido en el
pack): el copyright es de pixiv Inc. Se permite uso comercial y modificación libremente,
pero **hay que incluir el crédito** "Animation credits to pixiv Inc.'s VRoid Project"
(o en japonés "キャラクターアニメーション: ピクシブ株式会社 VRoidプロジェクト"). Está
**prohibido** redistribuir estos motions (o alteraciones) de forma que se puedan riggear o
extraer, usarlos para contenido sexual o muy violento, o para fines religiosos/políticos.
Aplica la ley japonesa.

## Nota técnica: `specVersion` ausente en el pack `tk256ailab`

Los 9 archivos de `tk256ailab` no traen el campo `extensions.VRMC_vrm_animation.specVersion`
en su glTF. `@pixiv/three-vrm-animation@2.1.3` (la versión que empareja con el
`@pixiv/three-vrm@2` del proyecto) aborta el parseo sin ese campo. `rem_avatar.html` lo
**normaliza al vuelo en el navegador** (inyecta `specVersion: "1.0"` en una copia en
memoria antes de pasársela a `GLTFLoader`) — los archivos en disco quedan intactos y no
hace falta ningún paso manual. El pack oficial VRoid ya trae `specVersion: "1.0"` y no
necesita normalización.

## Catálogo: `catalogo.json`

Registro de **todos** los clips de esta carpeta (los de `VRMA_MotionPack/` y los de
`nerumi/`), con su categoría, etiqueta en español, origen y medidas. A diferencia de los
`.vrma`, **sí se versiona**: solo lleva metadatos.

Lo genera y actualiza `catalogo_animaciones.py` (en la raíz del proyecto):

```bash
venv/bin/python catalogo_animaciones.py          # tras agregar o quitar clips
venv/bin/python catalogo_animaciones.py --check  # solo informa (sale con 1 si hay ilegibles o SHA-256 distintos)
```

- **Lo curado se edita a mano** en el JSON y el script lo conserva: `etiqueta`, `categoria`,
  `origen`, `peso`, `horas`, `nota`, `activoPorDefecto`, y las secciones `categorias`,
  `porEstado`, `poseBase` y `ajustes` (intervalo de reposo y minutos de enfriamiento por defecto).
- **Lo que se cambie desde el panel de control no toca este archivo**: va a `preferencias.json`
  como excepciones (ver "Preferencias del panel de control" en CLAUDE.md).
- **Lo medido lo recalcula el script** en cada corrida: `medido` (duración, giro de la cadera,
  desplazamiento, inclinación del torso y ángulo de cada brazo a lo largo de todo el clip),
  `avisos`, `giraCuerpo`, `fundidoEntradaS` y `sha256`.
- Un clip nuevo entra con etiqueta sacada del nombre y origen `desconocido` (o el de un
  `provenance.json` de su carpeta): **completar a mano**. Un clip que desaparece del disco no se
  borra del catálogo: queda con `"falta": true`.

### `nerumi/`: origen y licencias

Clips sacados de Nerumi. El origen de cada uno está en `catalogo.json` → `origen`, tomado de
los `provenance.json` (con SHA-256 verificado), los `README.md` de cada subcarpeta y la tabla
de autores de `NOTAS-nerumi.md`; si no hay dato, `"desconocido"`.

- **KAWAII ANIMATIONS 100 (FUDASTORE)**: pack **de pago** de la Unity Asset Store. Uso
  personal; **no se pueden redistribuir los archivos**.
- **Bailes**: cada autor (BOOTH, vrcmods, Ko-fi...) tiene sus propios términos, sin revisar, y
  varios bailes están atados a canciones con derechos.
- **Desconocidos**: sin licencia conocida.

Nada de esto va al repo (está en `.gitignore`); el catálogo versionado solo nombra archivos y
autores.
