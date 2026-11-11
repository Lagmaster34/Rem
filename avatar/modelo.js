// avatar/modelo.js — carga del VRM, cambio de modelo en caliente y helpers de huesos/expresiones.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// CARGA VRM
// ═══════════════════════════════════════════════════
const loader = new GLTFLoader();
loader.register(p => new VRMLoaderPlugin(p));
// El MISMO loader carga .vrm y .vrma. El plugin de animación es inerte para un
// .vrm (su afterRoot chequea la extensión VRMC_vrm_animation y sale si no está).
loader.register(p => new VRMAnimationLoaderPlugin(p));

// Retry con espera exponencial: el WebKit2GTK de este proyecto sufre crashes
// internos del Network Process (ver CLAUDE.md, "crash interno del Network
// Process de WebKit") que pueden tirar abajo este fetch justo en el peor
// momento. El WebSocket ya se reconecta solo; loader.load() no tiene retry propio,
// así que sin esto un crash en esa ventana deja el avatar invisible por el
// resto de la sesión aunque el resto del pipeline (audio, lipsync, WS) siga
// funcionando con normalidad. La causa raíz es un bug de WebKit, no algo que
// se arregle acá — esto solo evita que un fallo transitorio sea permanente.
const VRM_MAX_INTENTOS = 8;

function _cargarVRM(intento = 1, gen = _modeloGen) {
  const _t0Carga = performance.now();
  const ruta = MODELO_ACTIVO;
  _cargandoModelo = true;
  loader.load('/' + ruta.split('/').map(encodeURIComponent).join('/'),
    gltf => {
      if (gen !== _modeloGen) {
        // Se pidió otro modelo mientras este cargaba: se tira sin montarlo.
        console.log(`[Modelo] "${ruta}" llegó tarde (ya se pidió otro) — descartado`);
        VRMUtils.deepDispose(gltf.scene);
        return;
      }
      _cargandoModelo = false;
      console.log(`[Modelo] "${ruta}" descargado+parseado en ${(performance.now() - _t0Carga).toFixed(0)}ms`);
      vrm = gltf.userData.vrm;
      window.__rem.vrm = vrm;
      VRMUtils.removeUnnecessaryJoints(vrm.scene);
      // VRM 0.x mira a -Z: se gira 180° para que mire a la cámara (+Z). VRM 1.0
      // ya mira a +Z. Ver _esVRM1.
      _esVRM1 = vrm.meta?.metaVersion !== '0';
      vrm.scene.rotation.y = _esVRM1 ? 0 : Math.PI;
      console.log(`[Modelo] VRM ${_esVRM1 ? '1.0' : '0.x'} — "${vrm.meta?.name ?? vrm.meta?.title ?? '?'}"`
                + ` de ${vrm.meta?.authors?.join(', ') ?? vrm.meta?.author ?? '?'}`);
      vrm.scene.scale.set(1, 1, 1);
      vrm.scene.position.set(0, 0, 0); // posición neutra: medir la caja sin offsets propios
      // Un clip VRMA puede sacar un miembro fuera del bounding box con el que se
      // subió la geometría — sin esto el frustum culling lo recorta en silencio
      // a mitad de animación (está en el ejemplo oficial de three-vrm-animation).
      vrm.scene.traverse(o => { o.frustumCulled = false; });
      scene.add(vrm.scene);
      // Oculto hasta el primer frame ya posado y medido (ver animate()): el VRM
      // nace en T-pose, y con el encuadre provisorio (Box3) ese frame se vería
      // mal — sobre todo en overlay (fondo transparente) y al cambiar de modelo.
      vrm.scene.visible = false;
      inicializarAnimacionClips(); // mixer + lista de huesos normalizados para la mezcla
      _catalogoListo.then(precargarClipsFijos); // clips de estado/pose base, sin bloquear el render

      // Medición inicial por Box3 — placeholder para el primer frame o dos, hasta
      // que la remedición por huesos (más abajo, en animate()) la corrija. Se
      // guarda en _modeloAlturaBox3 solo para el log comparativo.
      const caja = new THREE.Box3().setFromObject(vrm.scene);
      _modeloAlturaBox3 = caja.max.y - caja.min.y;
      _modeloAlturaLocal = _modeloAlturaBox3;
      _modeloCentroLocal = (caja.max.y + caja.min.y) / 2;
      console.log(`[Encuadre] altura por Box3 (provisoria): ${_modeloAlturaBox3.toFixed(3)} u`
                + ` (min.y=${caja.min.y.toFixed(3)}, max.y=${caja.max.y.toFixed(3)})`);

      recalcularEncuadre(); // fija camera.position.z, vrm.scene.position.y/x y el lookAt (provisorio)
      _medirHuesosPendiente = true; // remedir con huesos en el próximo frame, una vez posado (ver animate())

      const names = vrm.expressionManager?.expressions?.map(e => e.expressionName) ?? [];
      console.log('[VRM] OK | expressions:', names.join(', '));
      console.log('[VRM] springBones:', vrm.springBoneManager ? 'sí' : 'no');
      // Diagnóstico de lo que necesita la animación natural (ver "RUIDO
      // PERLIN 1D"/"MICRO-SACCADES" más abajo): si este modelo no trajera
      // alguno de estos, mejor saberlo acá que verlo fallar en silencio.
      console.log('[VRM] lookAt (micro-saccades):', vrm.lookAt ? 'sí' : 'no',
                  '| leftShoulder/rightShoulder (respiración en hombros):',
                  !!getB('leftShoulder'), !!getB('rightShoulder'));
      if (vrm.lookAt) {
        // target=camera es solo documentación viva (vrm.lookAt.target dice
        // "mira a la cámara" a quien lea/inspeccione esto en consola) —
        // autoUpdate=false porque el cálculo real lo dispara a mano
        // updateSaccades() (más abajo, "MIRADA A CÁMARA + MICRO-SACCADES"),
        // llamando a vrm.lookAt.lookAt(...) él mismo para poder sumarle
        // encima las saccades y el apartar-la-mirada antes de que
        // vrm.update() aplique el resultado a los huesos de los ojos. Con
        // autoUpdate en true (el default), vrm.update() volvería a llamar a
        // este mismo lookAt() por su cuenta y pisaría ese trabajo.
        vrm.lookAt.target = camera;
        vrm.lookAt.autoUpdate = false;

        // Rangos reales del lookAt de ESTE modelo (extensión VRM 0.x
        // firstPerson.lookAt{Horizontal,Vertical}{Inner,Outer,Down,Up}):
        // cada uno define inputMaxValue/outputScale — el ángulo pedido
        // (yaw/pitch en grados) se recorta a outputScale grados de rotación
        // real de ojo, en proporción lineal hasta inputMaxValue grados de
        // pedido (más allá de eso, se satura en outputScale). Confirmado
        // para rem.vrm inspeccionando el glTF crudo (dump_vrm.py): las
        // cuatro curvas son la identidad soportada por three-vrm
        // ([0,0,0,1,1,1,1,0], sin easing extra), con xRange=90/yRange=10 —
        // o sea el ojo real solo gira ~1/9 de lo que se le pide, hasta un
        // tope de 10° en cualquier dirección. Se loguea acá (no solo en el
        // script de inspección offline) para que quede visible en vivo si
        // el modelo cambia algún día.
        const ap = vrm.lookAt.applier;
        if (ap?.rangeMapHorizontalInner) {
          const fmt = rm => `in≤${rm.inputMaxValue}° -> out≤${rm.outputScale}°`;
          console.log('[VRM] rangos de lookAt — horizontal(inner/outer):',
                      fmt(ap.rangeMapHorizontalInner), '/', fmt(ap.rangeMapHorizontalOuter),
                      '| vertical(down/up):', fmt(ap.rangeMapVerticalDown), '/', fmt(ap.rangeMapVerticalUp));
        } else {
          console.warn('[VRM] no se pudo leer vrm.lookAt.applier.rangeMap* — ¿lookAtTypeName no es "Bone"?');
        }
      }
      {
        const dedosFaltantes = [];
        for (const lado of ['left', 'right']) {
          for (const dedo of ['Thumb', 'Index', 'Middle', 'Ring', 'Little']) {
            for (const falange of ['Proximal', 'Intermediate', 'Distal']) {
              if (!getB(`${lado}${dedo}${falange}`)) dedosFaltantes.push(`${lado}${dedo}${falange}`);
            }
          }
        }
        console.log(`[VRM] dedos: ${30 - dedosFaltantes.length}/30 mapeados`,
                    dedosFaltantes.length ? `— faltan: ${dedosFaltantes.join(', ')}` : '');
        console.log('[VRM] piernas (para clips VRMA):',
                    !!getB('rightUpperLeg'), !!getB('rightLowerLeg'),
                    !!getB('leftUpperLeg'), !!getB('leftLowerLeg'));
        // Sin jaw, aplicarVisemesPostUpdate() ya lo tolera (jawB queda null,
        // ver el guard `if (jawB)`) — esto es solo para que se note en el
        // log de arranque, no un chequeo funcional.
        if (!vrm.humanoid.getRawBoneNode('jaw')) {
          console.log('[VRM] sin hueso "jaw" — la apertura de mandíbula no se anima por hueso; '
                     + 'los visemes (morph targets) siguen moviendo la boca igual.');
        }
      }
      _exprMap = buildExprMap(names);
      localizarMallaFacial(gltf);
      _alMontarModelo();
    },
    xhr => { if (xhr.total) console.log('[VRM] cargando', Math.round(xhr.loaded / xhr.total * 100) + '%'); },
    err => {
      if (gen !== _modeloGen) return;   // ya se pidió otro modelo
      console.error(`[VRM] error (intento ${intento}/${VRM_MAX_INTENTOS}):`, err);
      if (intento < VRM_MAX_INTENTOS) {
        const espera = Math.min(500 * (2 ** intento), 8000);
        console.warn(`[VRM] reintentando en ${espera}ms...`);
        setTimeout(() => { if (gen === _modeloGen) _cargarVRM(intento + 1, gen); }, espera);
      } else {
        _cargandoModelo = false;
        console.error(`[VRM] no se pudo cargar "${ruta}" tras ${VRM_MAX_INTENTOS} intentos — el avatar queda invisible hasta elegir otro modelo.`);
        window.__remChat?.onSistema?.(`⚠ No se pudo cargar el modelo ${ruta}.`);
      }
    }
  );
}

// ═══════════════════════════════════════════════════
// CAMBIO DE MODELO EN CALIENTE
// ═══════════════════════════════════════════════════
// Se pide desde el chat (botón 👤, /modelo) o el panel de control: los dos
// mandan prefs_set {modelo: {vrm}} y el servidor difunde prefs_actualizadas,
// que llega acá (ver WEBSOCKET). La elección queda guardada en
// preferencias.json. Si Rem está hablando, espera a que termine.
let _cargandoModelo = false;
let _modeloCambioPendiente = null;

function cambiarModelo(ruta) {
  if (!ruta) return;
  if (ruta === MODELO_ACTIVO && (vrm || _cargandoModelo)) { _modeloCambioPendiente = null; return; }
  if (hayVozSonando()) {
    if (_modeloCambioPendiente !== ruta) console.log(`[Modelo] cambio a "${ruta}" en espera: está hablando`);
    _modeloCambioPendiente = ruta;
    return;
  }
  _modeloCambioPendiente = null;
  console.log(`[Modelo] cambiando "${MODELO_ACTIVO}" -> "${ruta}"`);
  _modeloGen++;            // invalida cualquier carga en vuelo del modelo anterior
  desmontarModelo();
  MODELO_ACTIVO = ruta;
  PERFIL_MODELO = CONFIG.modelos[ruta] ?? {};
  _cargarVRM(1, _modeloGen);
}

function _memoriaRender() {
  const m = renderer.info.memory;
  return `geometrías=${m.geometries} texturas=${m.textures}`;
}
window.__rem.memoria = _memoriaRender;

// Suelta TODO lo del modelo anterior: acciones y bindings del mixer, la escena
// (geometrías, materiales MToon y sus texturas: VRMUtils.deepDispose), las
// listas de render, y el estado del módulo que apuntaba a sus huesos/mallas.
// No hay VRMLookAtQuaternionProxy que limpiar: no se usa createVRMAnimationClip.
// Los clips VRMA parseados se conservan (son del rig, no del modelo): su
// AnimationClip se reconstruye para el modelo nuevo (ver _clipParaModelo).
function desmontarModelo() {
  ++_tokenClip;
  _reiniciarDirector();
  if (!vrm) return;
  const antes = _memoriaRender();
  if (_mixer) {
    _mixer.stopAllAction();
    _mixer.uncacheRoot(vrm.scene);
    for (const e of _clipCache.values()) if (e.clip) _mixer.uncacheClip(e.clip);
    _mixer = null;
  }
  for (const e of _clipCache.values()) { e.clip = null; e.gen = -1; }
  _accionActual = _accionAnterior = null;
  _clipPeso = _clipPesoObjetivo = 0;
  _clipTopeTimer = null;
  _puente = null;
  scene.remove(vrm.scene);
  VRMUtils.deepDispose(vrm.scene);
  renderer.renderLists.dispose();
  vrm = null;
  window.__rem.vrm = null;
  _huesosNorm.length = 0;
  _hipsNode = null;
  _visemeSlots = {};
  _visemeSlotsUnicos = [];
  _viaLipsync = 'expressionManager';
  _exprMap = {};
  _expresionesSuprimirHabla = new Set();
  for (const k of Object.keys(curExpr)) curExpr[k] = 0;
  _modeloAlturaLocal = 1.5; _modeloCentroLocal = 0.75; _modeloAnchoLocal = 0;
  _medirHuesosPendiente = false;
  console.log(`[Modelo] desmontado — memoria de render: antes ${antes} | después ${_memoriaRender()}`);
}

// Recién montado (primera carga o cambio): saludo y aviso al chat.
function _alMontarModelo() {
  console.log(`[Modelo] montado — memoria de render: ${_memoriaRender()}`);
  _saludoPendiente = true;
  // La pose base arranca ya (no espera a un cambio de estado).
  _catalogoListo.then(() => { if (_mixer && vrm) sincronizarClipConEstado(); });
  const titulo = vrm.meta?.name ?? vrm.meta?.title ?? MODELO_ACTIVO.split('/').pop();
  const autor = vrm.meta?.authors?.join(', ') ?? vrm.meta?.author ?? null;
  window.__remChat?.onModeloCargado?.(MODELO_ACTIVO, titulo, autor);
}

_cargarVRM();

// ═══════════════════════════════════════════════════
// HELPERS: HUESOS Y EXPRESIONES
// ═══════════════════════════════════════════════════
const getB = n => vrm?.humanoid?.getNormalizedBoneNode(n) ?? null;

// Candidatos de nombre por clave lógica — se resuelven contra los nombres reales del VRM al cargar
const _exprCandidates = {
  happy:     ['happy', 'joy', 'blendshape.joy', 'preset.happy'],
  sad:       ['sad', 'sorrow', 'blendshape.sorrow', 'preset.sad'],
  angry:     ['angry', 'blendshape.angry', 'preset.angry'],
  // En los VRM 0.x de VRoid esta expresión no tiene presetName estándar
  // (presetName='unknown'): three-vrm la expone por su nombre literal, 'Surprised'.
  surprised: ['surprised', 'Surprised', 'blendshape.surprised', 'preset.surprised'],
  // VRM 0.x "Fun" = VRM 1.0 "relaxed" (three-vrm ya traduce el preset).
  relaxed:   ['relaxed', 'fun', 'blendshape.fun', 'preset.relaxed'],
  blink:     ['blink', 'blendshape.blink', 'blinkleft', 'blinkl'],
  // Presets estándar de VRM para los 5 visemes (vocales) — usados solo como
  // fallback vía expressionManager cuando el modelo no expone morph targets
  // vrc.* directos (ver localizarMallaFacial() / FONEMA_A_VISEME_VRM en lipsync.py).
  aa: ['aa', 'a', 'blendshape.a'],
  ee: ['ee', 'e', 'blendshape.e'],
  ih: ['ih', 'i', 'blendshape.i'],
  oh: ['oh', 'o', 'blendshape.o'],
  ou: ['ou', 'u', 'blendshape.u'],
};

// Mapa clave lógica → nombre real de expresión en este VRM (null si no hay equivalente)
let _exprMap = {};

function buildExprMap(names) {
  const map = {};
  for (const [key, candidates] of Object.entries(_exprCandidates)) {
    const found = names.find(n => candidates.includes(n.toLowerCase()));
    map[key] = found ?? null;
  }
  console.log('[VRM] mapa de expresiones resuelto:', map);
  return map;
}

function trySetExpr(key, value) {
  const name = _exprMap[key];
  if (!vrm?.expressionManager || !name) return;
  vrm.expressionManager.setValue(name, clamp(value, 0, 1));
}
