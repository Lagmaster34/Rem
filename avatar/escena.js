// avatar/escena.js — renderer y escena, estado global, encuadre responsivo y suelo synthwave.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// RENDERER + ESCENA
// ═══════════════════════════════════════════════════
// Opaco: la ventana de rem_chat.py no es transparente (a diferencia del
// overlay eliminado). El color de fondo real lo fija crearSueloSynthwave().
// En overlay el canvas es transparente (alpha) para que se vea el escritorio
// detrás; sin suelo ni fondo de escena (ver crearSueloSynthwave, no se llama).
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: ES_TRANSPARENTE });
renderer.outputColorSpace = THREE.SRGBColorSpace;
if (ES_TRANSPARENTE) renderer.setClearColor(0x000000, 0);
document.body.appendChild(renderer.domElement);

// Renderer WebGL real (Fase 0 del comparativo de modelos) — WEBGL_debug_renderer_info
// es la única forma de saber si WebGL corre por la GPU (NVIDIA/iGPU) o por
// software (llvmpipe/SwiftShader/Mesa "software rasterizer"), más allá de lo
// que reporte nvidia-smi (que solo ve lo que llega a la GPU NVIDIA, no dice
// nada si el compositor rasteriza por CPU). La extensión puede no estar
// disponible (algunos navegadores la bloquean por fingerprinting) — se
// loguea ese caso también, no se asume nada en silencio.
(() => {
  const gl = renderer.getContext();
  const dbg = gl.getExtension('WEBGL_debug_renderer_info');
  if (!dbg) {
    console.warn('[GPU] WEBGL_debug_renderer_info no disponible — no se puede identificar el renderer real');
    return;
  }
  const renderer_ = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
  const vendor_   = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
  console.log(`[GPU] UNMASKED_RENDERER_WEBGL: "${renderer_}" | UNMASKED_VENDOR_WEBGL: "${vendor_}"`);
})();

// Tamaño del framebuffer con tope de VRAM (CONFIG.render). setPixelRatio(r) +
// setSize(w,h) → framebuffer = w·r × h·r, canvas CSS = w × h: con r<1 renderiza
// a menos resolución y el navegador reescala el canvas. Se llama al arrancar y
// en cada resize.
function aplicarTamanoRender() {
  const w = window.innerWidth, h = window.innerHeight;
  const R = CONFIG.render;
  let ratio = Math.min(window.devicePixelRatio || 1, R.pixelRatioMax);
  if (R.resolucionMaxPx > 0) {
    const px = w * h * ratio * ratio;
    if (px > R.resolucionMaxPx) ratio *= Math.sqrt(R.resolucionMaxPx / px);
  }
  renderer.setPixelRatio(ratio);
  renderer.setSize(w, h);
  console.log(`[Render] ventana ${w}x${h} · ratio ${ratio.toFixed(3)} · framebuffer `
            + `${Math.round(w * ratio)}x${Math.round(h * ratio)}`);
}
aplicarTamanoRender();

const scene = new THREE.Scene();

// Cámara tipo teleobjetivo — plano medio VTuber.
// Posición/lookAt reales los fija recalcularEncuadre() una vez medido el modelo;
// esto es solo un placeholder razonable para el primer frame antes de esa carga.
// far=45: la línea de horizonte del suelo synthwave queda a
// camera.position.z + CONFIG.suelo.tamano/2 (~27u con los valores por
// defecto) — con far=20 la cámara la recortaba directo, invisible sin error.
const camera = new THREE.PerspectiveCamera(CONFIG.camera.fov, window.innerWidth / window.innerHeight, 0.1, 45);
camera.position.set(0, 0, 1.6);
camera.lookAt(0, 0, 0);

// Inspección manual desde la consola del navegador (window.__rem.vrm, .scene, .camera).
window.__rem = { vrm: null, scene, camera };

// Iluminación tipo estudio de stream
scene.add(new THREE.AmbientLight(CONFIG.lighting.ambient.color, CONFIG.lighting.ambient.intensity));
const keyLight  = new THREE.DirectionalLight(CONFIG.lighting.key.color,  CONFIG.lighting.key.intensity);  keyLight.position.set(...CONFIG.lighting.key.pos);   scene.add(keyLight);
const fillLight = new THREE.DirectionalLight(CONFIG.lighting.fill.color, CONFIG.lighting.fill.intensity); fillLight.position.set(...CONFIG.lighting.fill.pos); scene.add(fillLight);
const rimLight  = new THREE.DirectionalLight(CONFIG.lighting.rim.color,  CONFIG.lighting.rim.intensity);  rimLight.position.set(...CONFIG.lighting.rim.pos);   scene.add(rimLight);

// ═══════════════════════════════════════════════════
// ESTADO GLOBAL
// ═══════════════════════════════════════════════════
let estado = 'idle';
let prevEstado = '';
let vrm = null;
let _renderPausado = false;   // modo escritorio con el avatar oculto: no se dibuja
const clock = new THREE.Clock();
const lerp  = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// ═══════════════════════════════════════════════════
// ENCUADRE RESPONSIVO — anclas normalizadas (0..1 de pantalla), no world units fijas
// ═══════════════════════════════════════════════════
// n: 0 = izquierda/arriba, 1 = derecha/abajo. worldX/anchoVisible/alturaVisible
// se recalculan en recalcularEncuadre() y se usan para convertir fracciones a
// coordenadas de mundo en el momento de escribir vrm.scene.position.
let _anchoVisible = 0, _alturaVisible = 0;
let _modeloAlturaLocal = 1.5, _modeloCentroLocal = 0.75; // fallback razonable antes de medir
let _modeloAnchoLocal = 0;        // solo overlay: ancho del cuerpo con brazos (medirMedioCuerpo); 0 = sin medir
let _modeloAlturaBox3 = 0;        // guardada solo para el log comparativo
let _medirHuesosPendiente = false; // se remide con huesos en el frame siguiente a la carga
let _modeloPositionY = 0;

const worldX = n => (n - 0.5) * _anchoVisible;

// El panel de chat tapa el CONFIG.chat.anchoFrac derecho de la ventana — el
// área 3D realmente visible es más angosta que window.innerWidth. worldX()
// de arriba sigue midiendo en fracciones del CANVAS COMPLETO (a propósito:
// camera.aspect tiene que seguir atado al tamaño real del render, si no la
// imagen se distorsiona) — esta función devuelve qué fracción del canvas
// completo ocupa el área 3D visible, para convertir un anchorX pensado
// "dentro de esa área" (0=su borde izquierdo, 1=su borde derecho, justo
// donde empieza el panel) a la fracción real del canvas completo que
// worldX() espera.
function fraccionAreaVisible3D() {
  if (ES_TRANSPARENTE) return 1;  // sin panel: toda la superficie es área 3D
  return 1 - CONFIG.chat.anchoFrac;
}

// Anclas de encuadre del modo activo: en ventana CONFIG.pet; en overlay las de
// CONFIG.overlay.encuadre (mismos nombres, así recalcularEncuadre() no ramifica).
function _anclasEncuadre() {
  if (ES_ESCRITORIO) return CONFIG.escritorio.encuadre;
  if (!ES_OVERLAY) return CONFIG.pet;
  const E = CONFIG.overlay.encuadre;
  return { alturaPantalla: E.ocupaAltoFrac, anchorX: E.anchorX, anchorY: 0.5 };
}

// Box3.setFromObject() sobre un VRM con SkinnedMesh da la caja de la geometría
// SIN aplicar el skinning (el shader deforma los vértices en GPU, no en los
// datos de la geometría en CPU) — en este modelo eso da ~la mitad de la altura
// real. Medimos altura real con huesos: head - min(leftFoot, rightFoot), con
// +18% arriba para cubrir pelo/adornos que no tienen hueso propio. Usa
// getRawBoneNode (el hueso real posado), no el proxy normalizado.
function medirAlturaHuesos() {
  const headB  = vrm?.humanoid?.getRawBoneNode('head');
  const lFootB = vrm?.humanoid?.getRawBoneNode('leftFoot');
  const rFootB = vrm?.humanoid?.getRawBoneNode('rightFoot');
  if (!headB || !lFootB || !rFootB) {
    console.warn('[Encuadre] faltan huesos head/leftFoot/rightFoot — se mantiene la medición por Box3');
    return null;
  }

  // Medir con vrm.scene.position.y en 0 — si no, el offset Y que ya haya
  // puesto la pasada anterior (Box3, o esta misma función en una llamada
  // previa tras un resize) se filtra en "centro". "altura" es una RESTA
  // (head - pie) y cancela ese offset sola, pero "centro" es un PROMEDIO y
  // no lo cancela — sin este reset, recalcularEncuadre() queda contaminado
  // con el offset anterior completo. Confirmado en vivo con
  // models/rem_naenae.vrm: sin esto, el modelo terminaba ~0.93u más arriba
  // de lo debido (cabeza fuera de cuadro); rem.vrm tenía el mismo bug pero
  // ~0.46u, nunca lo bastante grave como para notarse a simple vista.
  const yPrevio = vrm.scene.position.y;
  vrm.scene.position.y = 0;
  vrm.scene.updateMatrixWorld(true);

  const headPos = new THREE.Vector3(), lFootPos = new THREE.Vector3(), rFootPos = new THREE.Vector3();
  headB.getWorldPosition(headPos);
  lFootB.getWorldPosition(lFootPos);
  rFootB.getWorldPosition(rFootPos);

  vrm.scene.position.y = yPrevio;
  vrm.scene.updateMatrixWorld(true);

  const pieY = Math.min(lFootPos.y, rFootPos.y);
  const alturaCruda = headPos.y - pieY;   // hueso head al pie más bajo, sin margen
  const altura = alturaCruda * 1.18;      // +18% para pelo/adornos por encima de la cabeza
  const tope = headPos.y + (altura - alturaCruda);
  const centro = (tope + pieY) / 2;

  return { altura, centro };
}

// Overlay: encuadre de medio cuerpo. Mismo método que medirAlturaHuesos()
// (huesos reales, con vrm.scene.position.y en 0 para no contaminar "centro"
// con el offset de una pasada anterior) pero el tramo va de la CADERA (hueso
// hips, más un margen) a la cabeza (hueso head, más margen para pelo/adornos)
// en vez de cabeza-pies. Devuelve {altura, centro} igual que la de cuerpo entero.
function medirMedioCuerpo() {
  const headB = vrm?.humanoid?.getRawBoneNode('head');
  const hipsB = vrm?.humanoid?.getRawBoneNode('hips');
  if (!headB || !hipsB) {
    console.warn('[Encuadre] faltan huesos head/hips — overlay sin medio cuerpo medido');
    return null;
  }
  const yPrevio = vrm.scene.position.y;
  vrm.scene.position.y = 0;
  vrm.scene.updateMatrixWorld(true);
  const headPos = new THREE.Vector3(), hipsPos = new THREE.Vector3();
  headB.getWorldPosition(headPos);
  hipsB.getWorldPosition(hipsPos);
  // Ancho con los brazos ya en su pose de reposo: la mayor distancia lateral
  // al eje de la cadera entre hombros/brazos/manos, a ambos lados.
  let semiancho = 0;
  const _p = new THREE.Vector3();
  for (const n of ['leftShoulder', 'rightShoulder', 'leftUpperArm', 'rightUpperArm',
                   'leftLowerArm', 'rightLowerArm', 'leftHand', 'rightHand']) {
    const b = vrm.humanoid.getRawBoneNode(n);
    if (b) { b.getWorldPosition(_p); semiancho = Math.max(semiancho, Math.abs(_p.x - hipsPos.x)); }
  }
  vrm.scene.position.y = yPrevio;
  vrm.scene.updateMatrixWorld(true);

  const E = CONFIG.overlay.encuadre;
  const tramo = headPos.y - hipsPos.y;
  const base  = hipsPos.y - tramo * E.bajoCaderaFrac;
  const tope  = headPos.y + tramo * E.sobreCabezaFrac;
  const ancho = 2 * semiancho * (1 + E.anchoExtraFrac);
  console.log(`[Encuadre] overlay medio cuerpo: hips.y=${hipsPos.y.toFixed(3)} head.y=${headPos.y.toFixed(3)} `
            + `tramo=${tramo.toFixed(3)}u -> base=${base.toFixed(3)} tope=${tope.toFixed(3)} | `
            + `semiancho huesos=${semiancho.toFixed(3)}u -> ancho con margen=${ancho.toFixed(3)}u`);
  return { altura: tope - base, centro: (tope + base) / 2, ancho };
}

function recalcularEncuadre() {
  const fovRad = camera.fov * Math.PI / 180;
  const ANCLAS = _anclasEncuadre();

  // 1) Distancia de cámara tal que el modelo (altura real medida) ocupe
  //    CONFIG.pet.alturaPantalla del alto visible de pantalla.
  let alturaVisibleObjetivo = _modeloAlturaLocal / ANCLAS.alturaPantalla;
  if (ES_OVERLAY && _modeloAnchoLocal > 0) {
    // Ajuste por ancho: el alto visible mínimo para que el cuerpo con brazos
    // quepa en ocupaAnchoFrac del ancho. Gana el más restrictivo (el mayor).
    const porAncho = _modeloAnchoLocal / (CONFIG.overlay.encuadre.ocupaAnchoFrac * camera.aspect);
    alturaVisibleObjetivo = Math.max(alturaVisibleObjetivo, porAncho);
  }
  camera.position.set(0, 0, alturaVisibleObjetivo / (2 * Math.tan(fovRad / 2)));
  camera.lookAt(0, 0, 0);
  camera.updateProjectionMatrix();

  // 2) Alturas/anchos visibles reales a esa distancia (fórmulas pedidas).
  _alturaVisible = 2 * camera.position.z * Math.tan(fovRad / 2);
  _anchoVisible  = _alturaVisible * camera.aspect;

  // 3) Y del modelo: el centro de su caja (medida) debe caer en anchorY de
  //    pantalla, con la cámara siempre mirando al origen (paso 1).
  // Ventana: el centro del cuerpo entero cae en anchorY. Overlay: el corte de
  // cadera se apoya sobre el borde inferior (más baseSobreBordeFrac).
  const centroObjetivoMundo = ES_OVERLAY
    ? -_alturaVisible / 2 + _modeloAlturaLocal / 2 + CONFIG.overlay.encuadre.baseSobreBordeFrac * _alturaVisible
    : _alturaVisible * (0.5 - ANCLAS.anchorY);
  _modeloPositionY = centroObjetivoMundo - _modeloCentroLocal;

  // La X es fija (sin caminata): CONFIG.pet.anchorX, una fracción del ÁREA 3D
  // VISIBLE (no del canvas completo) — fraccionAreaVisible3D() la convierte a
  // fracción de canvas completo antes de pasarla a worldX() (ver esa función).
  const fracXCanvas = ANCLAS.anchorX * fraccionAreaVisible3D();
  const posX = worldX(fracXCanvas);
  if (vrm) {
    vrm.scene.position.y = _modeloPositionY;
    vrm.scene.position.x = posX;
  }

  // Cámara alineada con Rem en X — antes quedaba siempre en x=0 mientras
  // Rem estaba desplazada a un costado (posX), así que la veía en tres
  // cuartos: su cuerpo mira al frente de la escena (-Z), pero el vector
  // cámara->Rem tenía una componente en X, y los ojos (ver "MIRADA A
  // CÁMARA" más abajo) tenían que girar para compensar ESE ángulo
  // estructural además de cualquier seguimiento real — y ese giro extra
  // competía con el rango de mirada bastante angosto que trae el modelo
  // (ver CONFIG.mirada y el log de rangos al cargar el VRM). Con
  // camera.position.x y el lookAt en el mismo X que el modelo, el vector
  // cámara->Rem es puramente -Z: vista frontal de verdad.
  //
  // Como el punto que mira la cámara siempre proyecta al centro de la
  // imagen, esto por sí solo centraría a Rem en el medio del CANVAS
  // COMPLETO — en modo ventana, debajo del panel de chat. setViewOffset()
  // corrige eso sin volver a rotar la cámara (que reintroduciría el
  // ángulo que se acaba de eliminar): es un corrimiento de "lente
  // descentrado" (el mismo truco que un objetivo tilt-shift o un
  // corrimiento de cámara de arquitectura) que reencuadra la imagen ya
  // renderizada para que Rem siga apareciendo en fracXCanvas del canvas,
  // como antes.
  camera.position.x = posX;
  camera.lookAt(posX, 0, 0);
  const offsetX = (0.5 - fracXCanvas) * window.innerWidth;
  camera.setViewOffset(window.innerWidth, window.innerHeight, offsetX, 0, window.innerWidth, window.innerHeight);
  camera.updateProjectionMatrix();

  posicionarSuelo(posX);

  console.log(`[Encuadre] z=${camera.position.z.toFixed(3)} anchoVisible=${_anchoVisible.toFixed(3)} `
            + `alturaVisible=${_alturaVisible.toFixed(3)} position.y=${_modeloPositionY.toFixed(3)} `
            + `position.x=${posX.toFixed(3)} (anchorX=${ANCLAS.anchorX}) viewOffsetX=${offsetX.toFixed(1)}px`);
}

// ═══════════════════════════════════════════════════
// SUELO DE CUADRÍCULA SYNTHWAVE
// ═══════════════════════════════════════════════════
// GridHelper + Fog — nada de reflejos ni post-procesado (la GPU de esta
// máquina ya anda justa compartiendo VRAM con el LLM local, ver
// CLAUDE.md). La niebla es lo que da la sensación de perspectiva hacia un
// horizonte, no geometría extra: las líneas lejanas se funden con
// colorFondo en vez de dibujarse nítidas hasta el infinito.
let _grid = null, _horizonte = null;

function crearSueloSynthwave() {
  const cfg = CONFIG.suelo;
  _grid = new THREE.GridHelper(cfg.tamano, cfg.divisiones, cfg.colorLinea, cfg.colorLinea);
  _grid.material.transparent = true;
  _grid.material.opacity = 0.8;
  scene.add(_grid);

  // Línea de horizonte: más brillante que el resto de la cuadrícula, en el
  // borde lejano — refuerza el punto de fuga. fog=false para que no se
  // apague con la distancia como el resto de la cuadrícula: es justo la
  // marca de "hasta acá se ve", tiene que quedar siempre legible.
  const mitad = cfg.tamano / 2;
  const geomHorizonte = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-mitad, 0, -mitad),
    new THREE.Vector3( mitad, 0, -mitad),
  ]);
  const matHorizonte = new THREE.LineBasicMaterial({
    color: cfg.colorHorizonte, transparent: true, opacity: 0.9, fog: false,
  });
  _horizonte = new THREE.Line(geomHorizonte, matHorizonte);
  scene.add(_horizonte);

  scene.fog = new THREE.Fog(cfg.colorFondo, cfg.nieblaCerca, cfg.nieblaLejos);
  scene.background = new THREE.Color(cfg.colorFondo);
  renderer.setClearColor(cfg.colorFondo, 1); // opaca — la ventana no es transparente

  console.log('[Suelo] synthwave creado:', cfg);
}

// Alinea el suelo con los pies de Rem (Y) y con la cámara (X) — se llama
// desde recalcularEncuadre() cada vez que cambia _modeloPositionY/posX
// (carga, remedición por huesos, resize). El punto de fuga de la cuadrícula
// lo determina el eje óptico REAL de la cámara (camera.position.x, no dónde
// termina apareciendo Rem en pantalla tras el setViewOffset) — como ahora
// la cámara mira exactamente a posX (ver recalcularEncuadre()), centrar
// también el suelo en posX pone el punto de fuga justo detrás de Rem, en
// vez de en el x=0 fijo de antes (que ya no significa nada particular).
function posicionarSuelo(posX = 0) {
  if (!_grid) return;
  const pieY = _modeloPositionY + (_modeloCentroLocal - _modeloAlturaLocal / 2);
  _grid.position.set(posX, pieY, 0);
  if (_horizonte) _horizonte.position.set(posX, pieY, 0);
}

// Overlay y escritorio son transparentes y sin suelo: nada de cuadrícula, niebla ni fondo.
if (!ES_TRANSPARENTE) crearSueloSynthwave();
