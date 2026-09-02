# Animaciones/ — clips VRMA del avatar

Clips de animación de cuerpo (`.vrma`, formato [VRM Animation](https://vrm.dev/en/vrma/))
que `rem_avatar.html` reproduce sobre el modelo con `THREE.AnimationMixer` +
`@pixiv/three-vrm-animation`. **No van al repo** (están en `.gitignore`, mismo criterio que
`rmvpe.pt` / `hubert_base.pt` / `rem.vrm`) — hay que descargarlos a mano.

## Dónde van

Todos los `.vrma` van juntos en:

```
Animaciones/VRMA_MotionPack/
```

`rem_avatar.html` los busca ahí por nombre exacto (ver `CONFIG.animaciones` en ese archivo:
`porEstado` mapea estados emocionales a clips, `gestos.repertorio` los gestos de reposo).
Si un clip falta en disco, el avatar cae a la animación procedural con un aviso en consola
(`[Anim] "<archivo>" no disponible: ... — se mantiene la animación procedural`), no se rompe.

## De dónde se bajan

### 1. Pack de gestos/emociones — `tk256ailab/vrm-viewer` (licencia MIT)

Repo: <https://github.com/tk256ailab/vrm-viewer>, carpeta `VRMA/`.

Archivos que usa este proyecto (copiar tal cual a `Animaciones/VRMA_MotionPack/`):

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
