// avatar/clips.js — clips VRMA: carga, catálogo, mixer, mezcla con lo procedural y puente de pose.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// ANIMACIÓN POR CLIPS VRMA — pose de cuerpo con THREE.AnimationMixer
// ═══════════════════════════════════════════════════
// Los .vrma (formato VRM Animation) reemplazan las poses de cuerpo por estado
// y el "giro de bailarina" a mano. Regla dura: los clips SOLO mueven huesos
// de cuerpo — se excluyen leftEye/rightEye/jaw y se ignoran las pistas de
// expresión/mirada que traiga el .vrma (pelean con el lipsync por índice y el
// parpadeo, que ya funcionan). Respiración, parpadeo, saccades, mirada a
// cámara y jaw se aplican SIEMPRE encima del mixer, también durante un clip.
// Transiciones: procedural<->clip con el fundido de _clipPeso (fadeIn/fadeOut);
// clip<->clip y la vuelta de un bucle con el PUENTE DE POSE (_iniciarPuente).
// Carga perezosa + cache; si un clip falta en disco o no parsea, se cae a lo
// procedural con un aviso. QUÉ se reproduce lo decide el DIRECTOR (más abajo).
// Config: CONFIG.animaciones.
let _mixer = null;
let _accionActual = null;      // THREE.AnimationAction en curso, o null (= procedural puro)
let _accionAnterior = null;    // solo la pose base de idle la usa (ver _cambiarAccion)
let _clipPeso = 0;             // 0 = procedural puro, 1 = clip puro; rampa en actualizarAnimacionClips()
let _clipPesoObjetivo = 0;
let _clipTopeTimer = null;     // segundos restantes de un clip 'bucle' con duracionS, o null
// id -> {archivo, va, clip, gen} | {archivo, error} — orden = LRU. `va` (el
// VRMAnimation parseado) es del rig y sirve para cualquier modelo; `clip` es
// el AnimationClip armado para el modelo de generación `gen` (ver _clipParaModelo).
const _clipCache = new Map();
const _clipCargando = new Map(); // id -> Promise en vuelo, para no cargar dos veces el mismo
// Declarados acá arriba, no junto a cargarCatalogo(): _gestoTimer (más abajo)
// sortea su intervalo al cargar el módulo y lee los dos vía ajusteAnim().
let _catalogo = null;             // Animaciones/catalogo.json, ver cargarCatalogo()
const _clipsFallidos = new Set(); // ids que fallaron al cargar: fuera de la paleta y del repertorio
// Preferencias del panel (sección 'animaciones' de preferencias.py, llegan por
// WS: prefs_estado al conectar, prefs_actualizadas al cambiar). Lo que no
// traigan sale del catálogo. {categorias: {cat: bool}, clips: {id: bool},
// pesos: {cat: n}, porEstado: {estado: [ids]}, enfriamientoMin, intervaloReposo}
let _prefsAnim = {};
const _huesosNorm = [];        // [{nombre, node, q, qPrev, qPuente}] — todos los huesos normalizados, para la mezcla
let _hipsNode = null;

// Puente de pose (ver CONFIG.animaciones.puenteS): foto de la pose visible
// (qPuente por hueso + _puenteHips) y slerp desde ella hacia lo que escriba el
// mixer, durante `dur` segundos. null = sin puente.
let _puente = null;            // {t, dur}
const _puenteHips = new THREE.Vector3();
let _qPrevValido = false;      // qPrev tiene la pose del frame anterior (para el puente del bucle)

// Clip de POSE BASE de idle (CONFIG.animaciones.idle): de él solo se toman los
// brazos (el problema real: cuelgan rectos en procedural); el resto del cuerpo
// queda 100% procedural. Ver reproducirIdle()/actualizarAnimacionClips().
const _HUESOS_BRAZO_IDLE = new Set([
  'leftShoulder', 'rightShoulder', 'leftUpperArm', 'rightUpperArm',
  'leftLowerArm', 'rightLowerArm', 'leftHand', 'rightHand',
]);
let _idleVelObjetivo = 1.0;    // timeScale objetivo del clip de idle en bucle
let _idleVelTimer = 0;
let _idleAmpMult = 1;          // multiplicador del ruido de getStatePose('idle') — >1 con clip de idle
const _qClipTmp = new THREE.Quaternion();
const _vClipTmp = new THREE.Vector3();
const _hipsPosProc = new THREE.Vector3();
let _tokenClip = 0;            // invalida cargas async pendientes si el estado/gesto cambió mientras tanto

// Fundido procedural<->clip (ver CONFIG.animaciones.fadeIn/fadeOut/
// fadeOutInterrupcion). _clipPeso sigue siendo el progreso LINEAL 0..1 (lo
// que ya leen los umbrales/ramas de actualizarAnimacionClips sin cambiar);
// easeInOutCubic(_clipPeso) es el peso real usado para mezclar cuaterniones,
// respiración y mirada — así el umbral "<=0.001"/">=0.999" sigue siendo
// exacto (ease(0)=0, ease(1)=1, monótona) y solo la curva de MEZCLA cambia.
let _clipFadeSalidaS = null; // duración de la salida en curso (fadeOut o fadeOutInterrupcion) — null = no hay salida en curso
let _clipFadeEntradaS = null; // fundido de entrada del clip en curso (fundidoEntradaS del catálogo) — null = fadeIn
function easeInOutCubic(x) {
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

// ¿El cuerpo lo controla ahora mismo un clip pedido A MANO? (paleta
// "/animaciones" o 'clip <nombre>' de bench_chat.py). Se lee de la acción en
// curso, así que no hay flag de módulo que pueda quedarse pegado.
function hayClipManual() { return _accionActual?._esManual === true; }

// Ruleta de reposo (ver DIRECTOR): cada intervaloReposo (60–120 s, de
// catalogo.json -> ajustes) un intento; si en ese momento está ocupada,
// pierde el turno y se sortea un intervalo completo nuevo (como Nerumi).
let _gestoTimer = _sortearIntervaloGesto();
let _gestoActivo = false;      // un gesto VRMA de reposo/saludo controla el cuerpo (incluida la salida con fundido)
let _ultimoGestoDisparado = null; // id del último idle VRMA — para no repetirlo dos veces seguidas

function _sortearIntervaloGesto() {
  const { minS, maxS } = ajusteAnim('intervaloReposo', { minS: 60, maxS: 120 });
  return minS + Math.random() * (maxS - minS);
}

function inicializarAnimacionClips() {
  _mixer = new THREE.AnimationMixer(vrm.scene);
  _mixer.addEventListener('finished', _alTerminarClip);
  // Vuelta de un bucle: puente cortito desde la pose del frame anterior.
  _mixer.addEventListener('loop', e => {
    if (e.action === _accionActual && _qPrevValido) _iniciarPuente(CONFIG.animaciones.puenteBucleS, true);
  });
  _huesosNorm.length = 0;
  for (const nombre of Object.keys(vrm.humanoid.humanBones)) {
    const node = vrm.humanoid.getNormalizedBoneNode(nombre);
    if (node) _huesosNorm.push({ nombre, node, q: new THREE.Quaternion(),
                                 qPrev: new THREE.Quaternion(), qPuente: new THREE.Quaternion() });
  }
  _hipsNode = vrm.humanoid.getNormalizedBoneNode('hips');
  console.log(`[Anim] mixer listo — ${_huesosNorm.length} huesos normalizados para la mezcla`);
}

// Los .vrma de tk256ailab no traen extensions.VRMC_vrm_animation.specVersion y
// VRMAnimationLoaderPlugin@2.1.3 aborta el parseo sin él. Se parchea una COPIA
// en memoria (specVersion:"1.0") — el archivo en disco queda intacto. El pack
// oficial VRoid ya lo trae: para esos devuelve la URL original sin tocar nada.
async function normalizarVrma(url) {
  const MAGIC = 0x46546c67, JSON_T = 0x4e4f534a, BIN_T = 0x004e4942;
  let buf;
  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    buf = await resp.arrayBuffer();
  } catch (e) {
    throw new Error(`no se pudo descargar (${e.message})`);
  }
  const dv = new DataView(buf);
  if (buf.byteLength < 20 || dv.getUint32(0, true) !== MAGIC || dv.getUint32(16, true) !== JSON_T) {
    return url; // no parece un .glb — que GLTFLoader tire su propio error
  }
  const version = dv.getUint32(4, true);
  const jsonLen = dv.getUint32(12, true);
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jsonLen)));
  const ext = json.extensions && json.extensions.VRMC_vrm_animation;
  if (!ext || ext.specVersion != null) return url; // ya está bien
  ext.specVersion = '1.0';

  const binOff = 20 + jsonLen;
  let bin = null;
  if (binOff + 8 <= buf.byteLength && dv.getUint32(binOff + 4, true) === BIN_T) {
    bin = new Uint8Array(buf, binOff + 8, dv.getUint32(binOff, true));
  }
  let jsonBytes = new TextEncoder().encode(JSON.stringify(json));
  const pad = (4 - (jsonBytes.length % 4)) % 4;
  if (pad) {
    const p = new Uint8Array(jsonBytes.length + pad);
    p.set(jsonBytes); p.fill(0x20, jsonBytes.length);
    jsonBytes = p;
  }
  const total = 12 + 8 + jsonBytes.length + (bin ? 8 + bin.length : 0);
  const out = new Uint8Array(total);
  const odv = new DataView(out.buffer);
  odv.setUint32(0, MAGIC, true); odv.setUint32(4, version, true); odv.setUint32(8, total, true);
  odv.setUint32(12, jsonBytes.length, true); odv.setUint32(16, JSON_T, true);
  out.set(jsonBytes, 20);
  if (bin) {
    const bp = 20 + jsonBytes.length;
    odv.setUint32(bp, bin.length, true); odv.setUint32(bp + 4, BIN_T, true);
    out.set(bin, bp + 8);
  }
  console.log(`[Anim] ${url.split('/').pop()}: specVersion ausente → parcheado a "1.0" en memoria`);
  return URL.createObjectURL(new Blob([out], { type: 'model/gltf-binary' }));
}

// Arma un THREE.AnimationClip SOLO con las pistas de hueso de cuerpo, replicando
// la parte humanoid de createVRMAnimationHumanoidTracks (three-vrm-animation
// v2.1.3) pero con el THREE de esta página (el mismo que el mixer) y sin las
// pistas de expresión/mirada. El retargetizado real (matrices de mundo del rig
// origen -> local del rig del modelo) ya lo hizo VRMAnimationLoaderPlugin.
const _EXCLUIR_HUESOS_CLIP = new Set(['leftEye', 'rightEye', 'jaw']);
function clipDeVrma(va) {
  const metaV = vrm.meta?.metaVersion ?? '1';   // '0' para VRM 0.x
  const tracks = [];
  for (const [name, orig] of va.humanoidTracks.rotation) {
    if (_EXCLUIR_HUESOS_CLIP.has(name)) continue;
    const node = vrm.humanoid.getNormalizedBoneNode(name);
    if (!node) continue;                          // hueso que este modelo no tiene → se ignora
    // VRM0: espejo 180° en Y → negar x,z de cada cuaternión (índices pares del array plano).
    const values = metaV === '0'
      ? Float32Array.from(orig.values, (v, i) => (i % 2 === 0 ? -v : v))
      : Float32Array.from(orig.values);
    tracks.push(new THREE.QuaternionKeyframeTrack(`${node.name}.quaternion`, orig.times, values));
  }
  for (const [name, orig] of va.humanoidTracks.translation) {   // solo hips
    const node = vrm.humanoid.getNormalizedBoneNode(name);
    if (!node) continue;
    const animY = va.restHipsPosition?.y || 1;
    const humanY = vrm.humanoid.normalizedRestPose?.hips?.position?.[1] ?? animY;
    const scale = humanY / animY;
    const values = Float32Array.from(orig.values, (v, i) => (metaV === '0' && i % 3 !== 1 ? -v : v) * scale);
    tracks.push(new THREE.VectorKeyframeTrack(`${node.name}.position`, orig.times, values));
  }
  return new THREE.AnimationClip('cuerpo', va.duration ?? -1, tracks);
}

// ── CATÁLOGO (Animaciones/catalogo.json) ─────────────────────────────────
// Se descarga una vez al arrancar (no en overlay: ahí no hay mixer). Si no
// llega, no hay clips y todo sigue procedural — nada se rompe.

function aplicarPrefsAnim(prefs) {
  _prefsAnim = prefs ?? {};
  if (_catalogo) {
    const ids = Object.keys(_catalogo.clips);
    console.log(`[Anim] preferencias del panel aplicadas — ${ids.filter(id => clipUsable(id) && clipActivo(id)).length} ` +
                `clips activos en el reposo, intervalo ${JSON.stringify(ajusteAnim('intervaloReposo', null))}, ` +
                `enfriamiento ${ajusteAnim('enfriamientoMin', null)} min`);
  }
  // Un clip de estado nuevo se precarga ya. Solo con el VRM cargado (clipDeVrma
  // lo necesita); si todavía no, la precarga del arranque ya lo incluye.
  if (_mixer) _catalogoListo.then(precargarClipsFijos);
}

// Ajuste con default en catalogo.json -> ajustes, pisable por el panel.
function ajusteAnim(clave, porDefecto) {
  return _prefsAnim[clave] ?? _catalogo?.ajustes?.[clave] ?? porDefecto;
}

// estado -> {clips, modo, ...}: el del catálogo, con la lista de clips del
// panel si la hay ([] = ese estado sin clip, solo la cara). null = sin mapeo.
function porEstadoEfectivo(est) {
  const m = _catalogo?.porEstado?.[est];
  if (!m) return null;
  const clips = _prefsAnim.porEstado?.[est];
  return clips ? { ...m, clips } : m;
}

async function cargarCatalogo() {
  try {
    const r = await fetch(CONFIG.animaciones.catalogoUrl, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    _catalogo = await r.json();
    const ids = Object.keys(_catalogo.clips ?? {});
    console.log(`[Anim] catálogo: ${ids.length} clips, ${ids.filter(clipUsable).length} en disco, ` +
                `${ids.filter(id => clipUsable(id) && clipActivo(id)).length} activos en el reposo`);
  } catch (e) {
    console.warn(`[Anim] no se pudo leer el catálogo (${e.message}) — sin clips, todo procedural`);
    _catalogo = null;
  }
}

// Arranca ya: el VRM tarda más en cargar, así que para precargarClipsFijos()
// el catálogo suele estar listo. Overlay no lo necesita (sin mixer).
const _catalogoListo = ES_OVERLAY ? Promise.resolve() : cargarCatalogo();

function infoClip(id) { return _catalogo?.clips?.[id] ?? null; }
function clipUsable(id) {
  const c = infoClip(id);
  return !!c && !c.falta && !c.error && !_clipsFallidos.has(id);
}
function etiquetaClip(id) { return infoClip(id)?.etiqueta ?? id.split('/').pop().replace(/\.vrma$/i, ''); }
function clipGiraCuerpo(id) { return infoClip(id)?.giraCuerpo === true; }
function categoriaActiva(cat) {
  return _prefsAnim.categorias?.[cat] ?? (_catalogo?.categorias?.[cat]?.activa === true);
}
function pesoCategoria(cat) {
  return _prefsAnim.pesos?.[cat] ?? _catalogo?.categorias?.[cat]?.peso ?? 1;
}
// ¿Entra en el sorteo de gestos de reposo? Una preferencia por clip gana;
// si no hay, categoría activa + activoPorDefecto del catálogo. No afecta al
// estado -> clip ni a la paleta: esos usan cualquier clip usable.
function clipActivo(id) {
  const c = infoClip(id);
  if (!c) return false;
  return _prefsAnim.clips?.[id] ?? (categoriaActiva(c.categoria) && c.activoPorDefecto === true);
}
function poseBaseArchivo() { return _catalogo?.poseBase?.archivo ?? null; }
function poseBaseModo() { return _catalogo?.poseBase?.modo ?? CONFIG.animaciones.idle.modo; }

// id del catálogo a partir de lo que llega por WS/paleta: el id exacto, o el
// nombre de archivo con o sin ".vrma" (así 'clip VRMA_05' de bench_chat.py
// sigue andando). null si no hay ninguno; con varios, el primero y un aviso.
function resolverClip(nombre) {
  if (infoClip(nombre)) return nombre;
  const n = String(nombre).toLowerCase().replace(/\.vrma$/i, '');
  const hits = Object.keys(_catalogo?.clips ?? {})
    .filter(id => id.split('/').pop().toLowerCase().replace(/\.vrma$/i, '') === n);
  if (hits.length > 1) console.warn(`[Anim] "${nombre}" es ambiguo (${hits.join(', ')}) — se usa ${hits[0]}`);
  return hits[0] ?? null;
}

// Clips usables para la paleta, agrupados: categorías por 'orden', dentro
// por etiqueta.
function clipsDisponibles() {
  if (!_catalogo) return [];
  const cats = _catalogo.categorias ?? {};
  const orden = cat => cats[cat]?.orden ?? 99;
  return Object.keys(_catalogo.clips).filter(clipUsable).map(id => {
    const c = _catalogo.clips[id];
    return { nombre: id, etiqueta: c.etiqueta, giraCuerpo: c.giraCuerpo === true,
             categoria: c.categoria, grupo: cats[c.categoria]?.etiqueta ?? c.categoria };
  }).sort((a, b) => orden(a.categoria) - orden(b.categoria) || a.etiqueta.localeCompare(b.etiqueta, 'es'));
}

// Los de estado y la pose base: se precargan y nunca se desalojan del caché.
function _clipsFijos() {
  const s = new Set();
  for (const est of Object.keys(_catalogo?.porEstado ?? {})) for (const id of porEstadoEfectivo(est).clips ?? []) s.add(id);
  if (poseBaseArchivo()) s.add(poseBaseArchivo());
  // Los saludos (al abrir, al cambiar de modelo y Gesto ▸ Saludar): precargados
  // para que salgan sin esperar la carga la primera vez.
  for (const [id, c] of Object.entries(_catalogo?.clips ?? {})) if (c.saludo) s.add(id);
  return s;
}

// Carga perezosa + caché LRU. Cachea también el fallo, para no reintentar en
// cada disparo. Nunca lanza: en error devuelve {archivo, error} y el llamador
// cae a lo procedural.
// Una carga que no termina (red de WebKit caída a mitad, un parseo colgado) no
// puede dejar esperando al gesto que la pidió: a los CARGA_MAX_S se da por
// fallida esta vez (no se marca el clip como roto; el siguiente pedido reintenta).
const CARGA_MAX_S = 15;
function _conTiempoMaximo(promesa, id) {
  let timer;
  const limite = new Promise(res => {
    timer = setTimeout(() => {
      console.warn(`[Anim] "${id}" no terminó de cargar en ${CARGA_MAX_S} s — se descarta esta vez`);
      res({ archivo: id, error: new Error(`no cargó en ${CARGA_MAX_S} s`), _temporal: true });
    }, CARGA_MAX_S * 1000);
  });
  return Promise.race([promesa, limite]).finally(() => clearTimeout(timer));
}

function obtenerClip(id) {
  if (_clipCache.has(id)) {
    const e = _clipCache.get(id);
    _clipCache.delete(id); _clipCache.set(id, e);   // al final = usado hace poco
    return Promise.resolve(_clipParaModelo(e));
  }
  if (_clipCargando.has(id)) return _clipCargando.get(id).then(_clipParaModelo);
  const p = _conTiempoMaximo(_cargarClip(id), id).then(entry => {
    _clipCargando.delete(id);
    if (!entry._temporal) _clipCache.set(id, entry);   // un tiempo agotado se reintenta
    return entry;
  });
  _clipCargando.set(id, p);
  return p.then(e => { const r = _clipParaModelo(e); _podarCacheClips(); return r; });
}

// El AnimationClip depende del modelo (nombres de nodo, espejo VRM 0.x, escala
// de la cadera): se arma para el modelo actual y se rearma tras un cambio.
// Sin modelo montado (en pleno cambio) queda sin clip y el llamador no
// reproduce nada (su token ya quedó viejo de todos modos).
function _clipParaModelo(e) {
  if (e.error || !e.va) return e;
  if (e.clip && e.gen === _modeloGen) return e;
  if (!vrm) { e.clip = null; return e; }
  const clip = clipDeVrma(e.va);
  if (clip.tracks.length === 0) {
    console.warn(`[Anim] "${e.archivo}": 0 pistas de hueso para este modelo — se mantiene la animación procedural`);
    _clipsFallidos.add(e.archivo);
    return { archivo: e.archivo, error: new Error('0 pistas de hueso tras el filtrado') };
  }
  e.clip = clip;
  e.gen = _modeloGen;
  return e;
}

async function _cargarClip(id) {
  try {
    const url = CONFIG.animaciones.carpeta + id.split('/').map(encodeURIComponent).join('/');
    const urlUsable = await normalizarVrma(url);
    let gltf;
    try {
      gltf = await loader.loadAsync(urlUsable);
    } finally {
      if (urlUsable.startsWith('blob:')) URL.revokeObjectURL(urlUsable);
    }
    const va = gltf.userData?.vrmAnimations?.[0];
    if (!va) throw new Error('sin vrmAnimations (¿glTF sin extensión VRMC_vrm_animation?)');
    console.log(`[Anim] "${id}" cargado — ${va.duration?.toFixed?.(2) ?? '?'}s`);
    return { archivo: id, va, clip: null, gen: -1 };
  } catch (e) {
    console.warn(`[Anim] "${id}" no disponible: ${e.message} — se mantiene la animación procedural`);
    _clipsFallidos.add(id);
    return { archivo: id, error: e };
  }
}

// Desaloja los clips usados hace más tiempo por encima de cacheMax (sin
// contar fijos ni fallos), salvo el que suena y el que se está desvaneciendo.
function _podarCacheClips() {
  const fijos = _clipsFijos();
  const candidatos = [..._clipCache].filter(([id, e]) => e.va && !fijos.has(id));
  let sobran = candidatos.length - CONFIG.animaciones.cacheMax;
  for (const [id, e] of candidatos) {
    if (sobran <= 0) break;
    const acc = _mixer?.existingAction(e.clip);
    if (acc && (acc === _accionActual || acc === _accionAnterior)) continue;
    if (acc) acc.stop();
    if (e.clip) _mixer?.uncacheClip(e.clip);
    _clipCache.delete(id);
    sobran--;
  }
}

// Al cargar el VRM: estado -> clip y pose base, en paralelo, sin bloquear el
// render (obtenerClip nunca lanza).
function precargarClipsFijos() {
  const ids = [..._clipsFijos()].filter(clipUsable);
  return Promise.all(ids.map(obtenerClip)).then(entries => {
    const ok = entries.filter(e => e.clip).length;
    console.log(`[Anim] precarga: ${ok}/${ids.length} clips de estado/pose base cargados`);
  });
}

// ── PUENTE DE POSE ───────────────────────────────────────────────────────
// Foto de la pose: la visible ahora (clip -> clip, llamado entre frames), o la
// del frame anterior (desdePrev: la vuelta de un bucle, que el mixer ya aplicó
// en este mismo update). Luego _aplicarPuente() hace slerp desde la foto.
function _iniciarPuente(dur, desdePrev = false) {
  if (!(dur > 0) || !_huesosNorm.length) return;
  for (const h of _huesosNorm) h.qPuente.copy(desdePrev ? h.qPrev : h.node.quaternion);
  if (_hipsNode) _puenteHips.copy(_hipsNode.position);
  _puente = { t: 0, dur };
}

function _aplicarPuente(dt) {
  if (!_puente) return;
  _puente.t += dt;
  const u = easeInOutCubic(clamp(_puente.t / _puente.dur, 0, 1));
  for (const h of _huesosNorm) {
    _qClipTmp.copy(h.node.quaternion);
    h.node.quaternion.slerpQuaternions(h.qPuente, _qClipTmp, u);
  }
  if (_hipsNode) { _vClipTmp.copy(_hipsNode.position); _hipsNode.position.lerpVectors(_puenteHips, _vClipTmp, u); }
  if (u >= 1) _puente = null;
}

// Cambia la acción en curso. Sin crossFadeTo: la vieja se corta y la nueva
// entra a pleno peso; la suavidad la pone el puente (si había un clip a la
// vista — si no, la entrada la hace el fundido de _clipPeso).
function _cambiarAccion(nueva, durPuente) {
  if (_accionActual && _accionActual !== nueva) {
    if (_clipPeso > 0.001) _iniciarPuente(durPuente);
    _accionActual.stop();
  }
  if (_accionAnterior && _accionAnterior !== nueva) _accionAnterior.stop();
  _accionAnterior = null;
  _accionActual = nueva;
}

// opciones: modo 'bucle'|'unaVez', duracionS (tope), y quién lo pidió:
//   esGesto  — idle VRMA de la ruleta o saludo: lo corta el audio/estado.
//   esManual — paleta /animaciones o 'clip <x>' de bench_chat.py: no lo corta nada.
//   esEmocion— clip de la emoción del chat: tampoco lo corta el audio (sale
//              justo cuando empieza a hablar).
//   esBaile  — modo baile: al terminar, el director encadena el siguiente.
function reproducirClip(entry, { modo, duracionS, esGesto, esManual, esEmocion, esBaile }) {
  if (!_mixer || !entry?.clip) return false;
  // Clip que arranca con los brazos arriba (fundidoEntradaS del catálogo):
  // entrada más larga, para que no los levante de golpe.
  const fundidoEntrada = infoClip(entry.archivo)?.fundidoEntradaS ?? null;
  const durPuente = Math.max(CONFIG.animaciones.puenteS, fundidoEntrada ?? 0);
  const nueva = _mixer.clipAction(entry.clip);
  const marcar = a => {
    a._esGesto = !!esGesto; a._esManual = !!esManual; a._esEmocion = !!esEmocion; a._esBaile = !!esBaile;
    a._esIdle = false;
  };
  // Ya es el clip activo y a pleno peso (p.ej. thinking re-entrado en el mismo
  // turno): no reiniciar el loop desde t=0, solo refrescar el tope.
  if (nueva === _accionActual && _clipPesoObjetivo === 1 && !nueva.paused) {
    _clipTopeTimer = (duracionS != null) ? duracionS : null;
    _gestoActivo = !!esGesto;
    marcar(nueva);
    return true;
  }
  nueva.reset();
  nueva.setLoop(modo === 'bucle' ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
  nueva.clampWhenFinished = (modo !== 'bucle'); // sostiene el último frame mientras se funde la salida
  nueva.enabled = true;
  nueva.paused = false;
  nueva.timeScale = 1;
  nueva.setEffectiveWeight(1);
  marcar(nueva);
  nueva.play();
  _cambiarAccion(nueva, durPuente);
  _gestoActivo = !!esGesto;
  _clipTopeTimer = (duracionS != null) ? duracionS : null;
  _clipFadeEntradaS = fundidoEntrada;
  _clipFadeSalidaS = null;
  _clipPesoObjetivo = 1;
  const tipo = esBaile ? ', baile' : esEmocion ? ', emoción' : esManual ? ', manual' : esGesto ? ', gesto' : '';
  console.log(`[Anim] reproduciendo "${entry.archivo}" (${modo}${duracionS != null ? `, tope ${duracionS.toFixed(2)}s` : ''}${tipo})`);
  return true;
}

// ── Red de seguridad de los gestos ────────────────────────────────────────
// Un clip que falla al cargar, al reproducirse o que se queda colgado nunca
// puede dejar el cuerpo congelado ni _gestoActivo en true sin dueño: se
// descarta, se avisa en el log y se vuelve al reposo.
function abortarGesto(motivo) {
  console.warn(`[Anim] gesto abortado: ${motivo} — vuelve al reposo`);
  _gestoActivo = false;
  _caraGesto = null;
  try { volverABaseIdle(true); } catch (e) { volverAProcedural(true); }
}

// reproducirClip() con try/catch: true si arrancó.
function reproducirSeguro(entry, opciones, que) {
  try {
    if (reproducirClip(entry, opciones)) return true;
    abortarGesto(`${que}: el mixer no aceptó "${entry?.archivo}"`);
  } catch (e) {
    console.error(`[Anim] ${que}: error al reproducir "${entry?.archivo}": ${e?.message ?? e}\n${e?.stack ?? ''}`);
    abortarGesto(`${que}: error al reproducir`);
  }
  return false;
}

// Para el .catch() de una carga: si el pedido sigue siendo el vigente, abortar.
function errorDeCarga(tok, que) {
  return e => {
    console.error(`[Anim] ${que}: error en la carga: ${e?.message ?? e}\n${e?.stack ?? ''}`);
    if (tok === _tokenClip) abortarGesto(`${que}: falló la carga`);
  };
}

// No corta el mixer: solo baja el objetivo de mezcla. actualizarAnimacionClips()
// rampa _clipPeso a 0 y recién ahí para las acciones y resetea la pose. La CARA
// no se toca — la maneja updateExpressions().
function volverAProcedural(interrumpido = false) {
  _clipPesoObjetivo = 0;
  _clipTopeTimer = null;
  _clipFadeSalidaS = interrumpido ? CONFIG.animaciones.fadeOutInterrupcion : CONFIG.animaciones.fadeOut;
}

// Clip de POSE BASE de idle (catalogo.json -> poseBase, hoy desactivado). No
// es un gesto ni un clip de estado: es la base. Loop continuo; cede a gestos/
// clips de estado y se vuelve a él al terminar (ver volverABaseIdle). Marca
// _accionActual._esIdle para que actualizarAnimacionClips() haga la mezcla
// especial (del clip solo los brazos, el resto procedural).
async function reproducirIdle() {
  const archivo = poseBaseArchivo();
  const modo = poseBaseModo();
  if (!_mixer || !archivo) { volverAProcedural(); return; }
  const tok = ++_tokenClip;
  const entry = await obtenerClip(archivo);
  if (tok !== _tokenClip) return;
  if (entry.error || !entry.clip) { volverAProcedural(); return; }

  const acc = _mixer.clipAction(entry.clip);
  if (acc === _accionActual && _accionActual._esIdle) { _clipPesoObjetivo = 1; return; }

  acc.reset();
  acc.setLoop(THREE.LoopRepeat, Infinity);
  acc.clampWhenFinished = false;
  acc.enabled = true;
  acc.paused = false;
  acc.setEffectiveWeight(1);
  acc._esGesto = acc._esManual = acc._esEmocion = acc._esBaile = false;
  acc._esIdle = true;
  acc.play();
  // 'poseFija': timeScale 0 (no 'paused') — el frame no avanza pero la acción
  // sigue entrando en la mezcla.
  acc.timeScale = (modo === 'poseFija') ? 0 : 1;
  if (modo === 'poseFija') acc.time = 0;
  _cambiarAccion(acc, CONFIG.animaciones.puenteS);
  _gestoActivo = false;
  _clipTopeTimer = null;
  _idleVelObjetivo = 1.0;
  _idleVelTimer = 0;
  _clipFadeEntradaS = null;
  _clipPesoObjetivo = 1;
  console.log(`[Anim] idle base: "${archivo}" (${modo})`);
}

// Fin de un gesto, o su interrupción: volver a la BASE — al clip de idle si
// está configurado y seguimos elegibles, o a lo procedural.
function volverABaseIdle(interrumpido = false) {
  // Un estado con clip propio (thinking, listening...) vuelve a ese clip.
  if (_mixer && porEstadoEfectivo(estado) && !_esEstadoUnaVez()) { sincronizarClipConEstado(); return; }
  if (_mixer && poseBaseArchivo()) {
    reproducirIdle();
  } else {
    volverAProcedural(interrumpido);
  }
}

// Los clips 'unaVez' de un estado (happy/sad... por 'state' de bench_chat.py)
// no se repiten al terminar: vuelven a la base.
function _esEstadoUnaVez() { return porEstadoEfectivo(estado)?.modo === 'unaVez'; }

// Varía lento el timeScale del clip de idle en bucle (velMin..velMax).
function _actualizarVelIdle(dt) {
  const cfg = CONFIG.animaciones.idle;
  _idleVelTimer -= dt;
  if (_idleVelTimer <= 0) {
    _idleVelObjetivo = cfg.velMin + Math.random() * (cfg.velMax - cfg.velMin);
    _idleVelTimer = (cfg.velCambioS ?? 9) * (0.6 + Math.random() * 0.8);
  }
  if (_accionActual) _accionActual.timeScale = lerp(_accionActual.timeScale, _idleVelObjetivo, dt * 0.4);
}

function _alTerminarClip(e) {
  if (e.action !== _accionActual) return;   // una acción vieja — ignorar
  // Un baile terminado: el director encadena el siguiente de la bolsa con un
  // puente desde el último frame (clampWhenFinished lo sostiene), sin pasar
  // por lo procedural.
  if (e.action._esBaile) { _siguienteBaile = true; return; }
  // Backstop: la salida NATURAL ya debería estar en curso desde los últimos
  // fadeOut segundos del clip (ver actualizarAnimacionClips); esto cubre un
  // clip más corto que fadeOut. _gestoActivo se libera recién cuando el peso
  // llega a 0, no acá.
  volverABaseIdle(false);
}

// Estado/emoción -> clip (catálogo, porEstado). De varios clips, uno al azar
// sin repetir el último. Con 'enfriamiento', un clip reproducido hace menos de
// enfriamientoMin minutos no vuelve a salir: si no queda ninguno, null — solo
// la cara.
const _ultimoClipEstado = new Map();   // estado -> id del último clip que salió
const _ultimoUsoClipEstado = new Map(); // id -> performance.now() de su último disparo

function _elegirClipDeEstado(est, m) {
  let ids = (m.clips ?? []).filter(clipUsable);
  if (m.enfriamiento) {
    const minutos = ajusteAnim('enfriamientoMin', 5);
    const ahora = performance.now();
    const listos = ids.filter(id => !(ahora - (_ultimoUsoClipEstado.get(id) ?? -Infinity) < minutos * 60000));
    if (ids.length && !listos.length) {
      const hace = Math.round((ahora - Math.max(...ids.map(id => _ultimoUsoClipEstado.get(id)))) / 1000);
      console.log(`[Anim] ${est}: clip en enfriamiento (se reprodujo hace ${hace}s, mínimo ${minutos} min) — solo la cara`);
    }
    ids = listos;
  }
  if (ids.length > 1) ids = ids.filter(id => id !== _ultimoClipEstado.get(est));
  return ids.length ? ids[Math.floor(Math.random() * ids.length)] : null;
}

// Cambio de 'estado' (lo manda el backend: thinking/talking/idle, o un
// 'state happy' de bench_chat.py; listening es local). Un estado CON clip en
// porEstado lo dispara (con guarda de carrera por token). Uno sin clip corta
// los gestos de reposo, pero NO un baile, un clip de emoción ni uno manual:
// esos los maneja el director (thinking -> talking pasa en cada turno).
function sincronizarClipConEstado() {
  if (ES_OVERLAY) return; // overlay: sin clips VRMA (no hay mixer)
  const m = porEstadoEfectivo(estado);
  const id = m ? _elegirClipDeEstado(estado, m) : null;
  if (id) {
    const tok = ++_tokenClip;
    _gestoActivo = false;
    const est = estado;
    obtenerClip(id).then(entry => {
      if (tok !== _tokenClip) return;                 // el estado cambió mientras cargaba
      if (entry.error || !entry.clip) { volverAProcedural(true); return; }
      _ultimoClipEstado.set(est, id);
      if (m.enfriamiento) _ultimoUsoClipEstado.set(id, performance.now());
      reproducirClip(entry, { modo: m.modo, duracionS: m.duracionS });
    });
    return;
  }
  if (hayClipManual() || _bailando || _accionActual?._esEmocion) return;
  // Sin clip propio (idle, talking): la pose base de reposo, también hablando.
  // Un gesto de reposo en curso solo sigue si seguimos en idle.
  if (_gestoActivo && estado === 'idle') return;
  _gestoActivo = false;
  if (poseBaseArchivo()) reproducirIdle();
  else if (_accionActual) { ++_tokenClip; volverAProcedural(true); }
}

// Opciones de reproducción de un gesto/baile: una vez, salvo un baile corto,
// que se repite hasta baileMinS en ciclos completos.
function _opcionesGesto(id, entry, extra = {}) {
  const dur = entry.clip.duration;
  const min = CONFIG.animaciones.baileMinS;
  if (infoClip(id)?.categoria === 'dance' && dur > 0 && dur < min) {
    return { modo: 'bucle', duracionS: Math.ceil(min / dur) * dur, ...extra };
  }
  return { modo: 'unaVez', ...extra };
}

function _sorteoPonderado(items) {
  const total = items.reduce((s, x) => s + x.peso, 0);
  if (!(total > 0)) return null;
  let r = Math.random() * total;
  for (const x of items) { r -= x.peso; if (r <= 0) return x; }
  return items[items.length - 1];
}

function _logGesto(msg) {
  console.log(`[Gesto] t=${clock.getElapsedTime().toFixed(1)}s ${msg}`);
}
