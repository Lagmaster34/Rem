// avatar/dependencias.mjs — las dependencias de los scripts del avatar.
// Es el único módulo ES: importa three/three-vrm vendorizados y los publica en
// el ámbito global para los scripts clásicos de avatar/ (ver avatar/README.md).
// rem_avatar.html lo carga ANTES que ellos: los <script type="module"> y los
// <script defer> se ejecutan en el orden en que aparecen en el documento.
// Módulos vendorizados en vendor/esm/ (espejo exacto de lo que servía esm.sh,
// ver vendor/README.md): la página carga sin internet. OJO: three-vrm y
// three-vrm-animation traen SU propio three (0.164.1, el que esm.sh les
// resolvía por su peer ^0.164.1), distinto del 0.169.0 de la página — así
// funcionaba ya antes de vendorizar, y se dejó igual a propósito.
import * as THREE from '/vendor/esm/three@0.169.0.js';
import { GLTFLoader }    from '/vendor/esm/three@0.169.0/examples/jsm/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '/vendor/esm/@pixiv/three-vrm@2.1.3.js';
// Solo el loader plugin (parser + retargetizador de rotaciones al rig del modelo).
// NO se usa createVRMAnimationClip: ese además arma pistas de expresión/mirada y
// auto-crea un VRMLookAtQuaternionProxy en la escena — acá los clips solo mueven
// huesos de cuerpo (ver "ANIMACIÓN POR CLIPS VRMA" más abajo). Versión 2.1.3:
// empareja con @pixiv/three-vrm@2.1.3 (mismo three-vrm-core).
import { VRMAnimationLoaderPlugin } from '/vendor/esm/@pixiv/three-vrm-animation@2.1.3.js';

Object.assign(globalThis, { THREE, GLTFLoader, VRMLoaderPlugin, VRMUtils, VRMAnimationLoaderPlugin });
