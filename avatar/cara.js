// avatar/cara.js — expresiones emocionales, parpadeo y lipsync (audio + timeline de visemes).
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// SISTEMA DE EXPRESIONES EMOCIONALES
// ═══════════════════════════════════════════════════
// Claves que faltan en un perfil valen 0.
const EXPR_PROFILES = {
  idle:      {},
  talking:   { happy: 0.3 },
  thinking:  { sad: 0.1 },
  listening: { relaxed: 0.25 },   // escuchando el push-to-talk: atenta, amable
  happy:     { happy: 1.0, surprised: 0.1 },
  sad:       { sad: 0.9 },
  angry:     { angry: 0.8 },
  surprised: { happy: 0.1, surprised: 1.0 },
};
const EXPR_CLAVES = ['happy', 'sad', 'angry', 'surprised', 'relaxed'];
const curExpr = { happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };

// Qué expresiones bindean morphs de boca en ESTE modelo y hay que suprimir
// mientras hay audio, para que no compitan con los visemes. Lo calcula
// _detectarSupresionHabla() al cargar (o lo fija el perfil del modelo).
let _expresionesSuprimirHabla = new Set();

// La cara de este frame: la del estado, y encima (por máximo, no suma) la
// emoción del chat si hay una viva, o si no la del gesto de reposo en curso
// (campo "expresion" del catálogo / estilo procedural), o el happy suave del
// baile. Sin emoción ni gesto, solo la del estado.
function _caraObjetivo() {
  const obj = { ...(EXPR_PROFILES[estado] ?? EXPR_PROFILES.idle) };
  const encima = cara => { for (const [k, v] of Object.entries(cara)) obj[k] = Math.max(obj[k] ?? 0, v); };
  const E = CONFIG.expresiones;
  if (_emocion) encima({ [_emocion.nombre]: E.emocionPeso[_emocion.nombre] ?? 0.8 });
  else if (_caraGesto && estado === 'idle') encima(_caraGesto);
  else if (_bailando) encima({ happy: E.bailePeso });
  return obj;
}

function updateExpressions(dt) {
  const obj = _caraObjetivo();
  const f = _audioActivo ? CONFIG.expresiones.supresionHabla : 1;
  for (const k of EXPR_CLAVES) {
    curExpr[k] = lerp(curExpr[k], obj[k] ?? 0, dt * 2.5);
    trySetExpr(k, _expresionesSuprimirHabla.has(k) ? curExpr[k] * f : curExpr[k]);
  }
}

// ═══════════════════════════════════════════════════
// SISTEMA DE PARPADEO NATURAL
// ═══════════════════════════════════════════════════
let blinkPhase = 'wait'; // 'wait' | 'closing' | 'opening' | 'doubleWait'
let blinkTimer  = 2.5 + Math.random() * 2;
let blinkVal    = 0;
let blinkDouble = false;
let blinkDoubleWait = 0;

function updateBlink(dt) {
  // Intervalo base por estado — thinking parpadea más
  const baseInterval = estado === 'thinking' ? 1.8
                     : estado === 'talking'   ? 2.2 : 3.5;

  switch (blinkPhase) {
    case 'wait':
      blinkTimer -= dt;
      if (blinkTimer <= 0) {
        blinkPhase = 'closing';
        blinkDouble = Math.random() < 0.05; // 5% doble parpadeo
      }
      break;
    case 'closing':
      blinkVal += dt / 0.08; // cierra en 80ms
      if (blinkVal >= 1) { blinkVal = 1; blinkPhase = 'opening'; }
      break;
    case 'opening':
      blinkVal -= dt / 0.12; // abre en 120ms
      if (blinkVal <= 0) {
        blinkVal = 0;
        if (blinkDouble) { blinkDouble = false; blinkDoubleWait = 0.07; blinkPhase = 'doubleWait'; }
        else              { blinkPhase = 'wait'; blinkTimer = baseInterval * (0.7 + Math.random() * 0.8); }
      }
      break;
    case 'doubleWait':
      blinkDoubleWait -= dt;
      if (blinkDoubleWait <= 0) blinkPhase = 'closing';
      break;
  }
  trySetExpr('blink', blinkVal);
}

// ═══════════════════════════════════════════════════
// LIPSYNC REAL — audio del backend + timeline de visemes (lipsync.py)
// ═══════════════════════════════════════════════════
// Un <audio> de HTML en vez de Web Audio API: el audio puede empezar a sonar
// antes de que el usuario interactúe con la página (primera respuesta de Rem
// apenas se abre la ventana), y un AudioContext se queda 'suspended' hasta un
// gesto real — set_media_playback_requires_user_gesture(False) en WebKit2 no
// lo destraba porque esa política es solo para elementos de medios, no para
// la Web Audio API. HTMLMediaElement.play() sí arranca sin gesto en este
// WebView (con WebsitePolicies(autoplay=ALLOW), ver rem_chat.py), así que
// elimina el problema de raíz en vez de trabajar alrededor de él.
const _audioEl = new Audio();
let _audioActivo = false; // true entre 'playing' y 'ended'/'error'

// Le avisa al backend cuándo la cola de audio pasa a tener algo (true, al
// RECIBIR el audio: cierra el hueco entre que el servidor lo despacha y que
// suena) o se vacía (false). El push-to-talk lo usa para no abrir el micrófono
// mientras Rem habla (ver rem_avatar_server, "Push-to-talk"). Solo manda
// cuando cambia el valor.
let _vozReportada = false;
function _reportarVoz(reproduciendo) {
  if (reproduciendo === _vozReportada) return;
  _vozReportada = reproduciendo;
  if (_ws && _ws.readyState === WebSocket.OPEN) {
    _ws.send(JSON.stringify({ tipo: 'voz_estado', reproduciendo }));
  }
}

function _avanzarCola() {
  _audioActivo = false;
  _timeline = [];
  if (_audioPlayQueue.length > 0) {
    _reproducirSiguienteDeCola();
  } else {
    _audioPlaying = false;
    _reportarVoz(false);
    if (estado === 'talking') estado = 'idle';
    // Cola de voz vacía: es el momento de soltar un clip que gira el cuerpo y
    // quedó esperando a que Rem terminara de hablar (ver _clipEnEspera).
    _intentarLanzarClipEnEspera();
  }
}

// Logs de diagnóstico explícitos alrededor de toda la reproducción — el
// volcado de consola de rem_chat.py a rem_chat.log deja verlos en vivo.
_audioEl.addEventListener('playing', () => {
  console.log('[Lipsync] evento "playing" ->', _audioEl.src);
  _audioActivo = true;
  estado = 'talking';
  // Suena de verdad: cierra la medición de latencia del push-to-talk en el
  // servidor (voz_estado se manda antes, al RECIBIR el audio).
  if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send(JSON.stringify({ tipo: 'voz_sonando' }));
});
_audioEl.addEventListener('ended', _avanzarCola);
// MediaError.code: 1=ABORTED 2=NETWORK 3=DECODE 4=SRC_NOT_SUPPORTED.
// code=3 confirmaría que WebKit no puede decodificar el WAV (el sample rate
// lo pone el modelo de Piper — 22050 Hz con la voz de Yoru) — distinto de un NotAllowedError de
// play(), que sería la política de autoplay todavía activa.
const _MEDIA_ERROR_NOMBRES = { 1: 'ABORTED', 2: 'NETWORK', 3: 'DECODE', 4: 'SRC_NOT_SUPPORTED' };
_audioEl.addEventListener('error', () => {
  const err = _audioEl.error;
  console.error('[Lipsync] evento "error" para', _audioEl.src,
    '| code:', err?.code, `(${_MEDIA_ERROR_NOMBRES[err?.code] ?? '?'})`,
    '| message:', err?.message,
    '| readyState:', _audioEl.readyState, '| networkState:', _audioEl.networkState);
  _avanzarCola();
});
// Sonidos cortos del modo conversación (el servidor manda {tipo:'sonido'}):
// dos notas que suben al abrir el micrófono y las mismas al revés al cerrarlo.
// Se generan aquí (WAV en un blob) y suenan en un <audio> aparte: no son voz,
// no pasan por la cola ni por voz_estado. Al acabar se avisa con sonido_fin
// (el servidor espera al de abrir antes de abrir el micrófono).
// Cada nota: seno + 25 % de 2.º armónico, ataque 8 ms, caída exponencial
// (constante = duración/2,2) y 3 ms de cierre para que no chasquee; pico
// −16 dBFS, 22050 Hz. mi5 = 659,3 Hz, si5 = 987,8 Hz.
const _sonidoEl = new Audio();
const _SONIDOS_NOTAS = {
  mic_abre:   [[659.3, 90], [0, 25], [987.8, 140]],
  mic_cierra: [[987.8, 90], [0, 25], [659.3, 140]],
};
const _sonidosUrl = {};
function _wavDeNotas(notas, sr = 22050) {
  const muestras = [];
  for (const [f, ms] of notas) {
    const n = Math.round(sr * ms / 1000), tau = ms / 1000 / 2.2;
    const ataque = 0.008 * sr, cierre = 0.003 * sr;
    for (let i = 0; i < n; i++) {
      if (!f) { muestras.push(0); continue; }
      const t = i / sr;
      let env = i < ataque ? i / ataque : Math.exp(-(t - 0.008) / tau);
      if (n - i < cierre) env *= (n - i) / cierre;
      muestras.push(env * (Math.sin(2 * Math.PI * f * t) + 0.25 * Math.sin(4 * Math.PI * f * t)));
    }
  }
  const pico = Math.max(...muestras.map(Math.abs)) || 1;
  const k = Math.pow(10, -16 / 20) / pico;
  const buf = new ArrayBuffer(44 + muestras.length * 2), v = new DataView(buf);
  const txt = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  txt(0, 'RIFF'); v.setUint32(4, 36 + muestras.length * 2, true); txt(8, 'WAVE');
  txt(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  txt(36, 'data'); v.setUint32(40, muestras.length * 2, true);
  muestras.forEach((m, i) => v.setInt16(44 + i * 2, Math.round(clamp(m * k, -1, 1) * 32767), true));
  return URL.createObjectURL(new Blob([buf], { type: 'audio/wav' }));
}
let _sonidoId = null;
function _sonidoTerminado() {
  if (_sonidoId === null) return;
  const id = _sonidoId;
  _sonidoId = null;
  if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send(JSON.stringify({ tipo: 'sonido_fin', id }));
}
_sonidoEl.addEventListener('ended', _sonidoTerminado);
_sonidoEl.addEventListener('error', _sonidoTerminado);
function tocarSonido(nombre, id) {
  const notas = _SONIDOS_NOTAS[nombre];
  if (!notas) { console.warn('[Sonido] desconocido:', nombre); _sonidoId = id; _sonidoTerminado(); return; }
  _sonidoTerminado();   // uno anterior a medias: ya no se espera
  _sonidosUrl[nombre] ??= _wavDeNotas(notas);
  _sonidoId = id;
  console.log('[Sonido]', nombre);
  _sonidoEl.src = _sonidosUrl[nombre];
  _sonidoEl.play().catch(e => { console.warn('[Sonido] play() rechazado:', e?.name, e?.message); _sonidoTerminado(); });
}

_audioEl.addEventListener('stalled', () => {
  console.warn('[Lipsync] evento "stalled" para', _audioEl.src,
    '| readyState:', _audioEl.readyState, '| networkState:', _audioEl.networkState);
});

// Vocabulario canónico de 15 visemes que manda el timeline de lipsync.py
// (timeline[].viseme, "vrc.v_*") — es una convención INTERNA de este
// proyecto para hablar de "el viseme de la vocal a", no un nombre que se
// asuma presente en ningún VRM. Cada modelo declara en CONFIG.modelos[...]
// .lipsync.visemas a qué morph(s) REAL(es) de SU archivo contribuye cada uno
// de estos 15 nombres, y con qué peso — ver localizarMallaFacial() más abajo,
// que resuelve esos nombres reales contra morphTargetDictionary. Ya no hay
// ningún índice fijo en el código: si un modelo no declara un viseme, o
// declara un morph que no existe en el archivo, se loguea y ese viseme
// simplemente no mueve nada (nunca se escribe a ciegas en una posición).
const VISEME_NAMES = [
  'vrc.v_aa', 'vrc.v_e', 'vrc.v_ih', 'vrc.v_oh', 'vrc.v_ou',
  'vrc.v_pp', 'vrc.v_ff', 'vrc.v_ss', 'vrc.v_dd', 'vrc.v_kk',
  'vrc.v_nn', 'vrc.v_rr', 'vrc.v_ch', 'vrc.v_sil', 'vrc.v_th',
];

const JAW_MAX_RAD        = 0.25;  // apertura máxima del hueso jaw, en radianes (eje X)
const JAW_SMOOTH_SPEED   = 20;    // suavizado exponencial (lerp con dt)

// nombre canónico -> [{mesh, idx, peso}, ...], resuelto en localizarMallaFacial()
// contra el perfil del modelo activo (PERFIL_MODELO.lipsync.visemas).
let _visemeSlots = {};
// Deduplicado de TODOS los (mesh,idx) que aparecen en _visemeSlots — para
// poder poner todo en 0 una vez por frame antes de sumar los visemes activos
// (varios visemes canónicos pueden compartir el mismo morph real, ver el
// perfil "reducido" del modelo nuevo: dd/nn/ss/th/rr/ch comparten "ih").
let _visemeSlotsUnicos = [];
let _audioPlayQueue = [];  // cola FIFO: {url, timeline} — para no solapar frases
let _audioPlaying  = false;
let _timeline       = [];
let _timelineIdx     = 0;
let _jawApertura     = 0;
// "Energía del habla": versión suavizada de _jawApertura, usada para que la
// gesticulación de brazos en modo talking siga la intensidad real de lo que
// se está diciendo (ver "BRAZOS ACOPLADOS AL CUERPO" y getStatePose(),
// case 'talking') en vez de moverse siempre igual. Sube rápido, baja rápido
// también (mismo dt*8) — no hace falta que sea más lenta al bajar, el
// envolvente de ruido de getStatePose() ya aporta la parte "lenta".
let _hablaEnergia = 0;
function actualizarHablaEnergia(dt) {
  const objetivo = _audioActivo ? clamp(_jawApertura * 1.3, 0, 1) : 0;
  _hablaEnergia = lerp(_hablaEnergia, objetivo, dt * 8);
}

// Tres vías de lipsync, en orden de preferencia:
//   'directo' (perfil)  — CONFIG.modelos[ruta].lipsync.visemas, resuelto por
//                         NOMBRE contra morphTargetDictionary. Solo si el
//                         modelo tiene perfil a mano.
//   'directo' (vocales) — AUTODETECTADO: los binds de las expresiones
//                         aa/ih/ou/ee/oh dicen qué (malla, índice de morph) es
//                         cada vocal; las consonantes se aproximan con
//                         _VISEMAS_POR_VOCAL. Sin depender del nombre del morph
//                         (que este loader degenera a "0".."N", ver CLAUDE.md).
//                         Es la vía de los VRM de VRoid (Fcl_MTH_A..O).
//   'expressionManager' — último recurso: los 5 presets vía setValue().
let _viaLipsync = 'expressionManager';
const VRM_VISEME_KEYS = ['aa', 'ee', 'ih', 'oh', 'ou'];

// Viseme canónico -> [vocal, peso]. sil/pp = boca cerrada de verdad (sin
// morph). Es la tabla que se afinó a ojo con un modelo VRoid (solo vocales):
// las 5 vocales 1:1 y las consonantes como un poco de "i" o "a".
const _VISEMAS_POR_VOCAL = {
  'vrc.v_sil': [], 'vrc.v_pp': [],
  'vrc.v_aa': [['aa', 1]], 'vrc.v_e': [['ee', 1]], 'vrc.v_ih': [['ih', 1]],
  'vrc.v_oh': [['oh', 1]], 'vrc.v_ou': [['ou', 1]],
  'vrc.v_ff': [['ih', 0.3]], 'vrc.v_dd': [['ih', 0.2]], 'vrc.v_nn': [['ih', 0.2]],
  'vrc.v_ss': [['ih', 0.3]], 'vrc.v_th': [['ih', 0.2]], 'vrc.v_kk': [['aa', 0.3]],
  'vrc.v_rr': [['ih', 0.25]], 'vrc.v_ch': [['ih', 0.4]],
};

// Binds de morph de una expresión (clave lógica de _exprMap):
// [{mesh, idx, peso}] — una entrada por primitive (las mallas "baked" de VRoid
// se cargan como varios Mesh que comparten geometría: hay que escribir en todos).
function _bindsDeExpresion(clave) {
  const nombre = _exprMap[clave];
  const expr = nombre ? vrm.expressionManager?.getExpression(nombre) : null;
  const res = [];
  for (const b of expr?._binds ?? []) {
    if (!b.primitives || b.index == null) continue;   // bind de material/textura, no de morph
    for (const mesh of b.primitives) res.push({ mesh, idx: b.index, peso: Math.min(1, b.weight ?? 1) });
  }
  return res;
}

function _agregarSlot(nombre, mesh, idx, peso, vistos) {
  _visemeSlots[nombre].push({ mesh, idx, peso });
  const clave = mesh.uuid + ':' + idx;
  if (!vistos.has(clave)) { vistos.add(clave); _visemeSlotsUnicos.push({ mesh, idx }); }
}

function _resolverLipsyncPorVocales() {
  const porVocal = {};
  for (const v of VRM_VISEME_KEYS) porVocal[v] = _bindsDeExpresion(v);
  const conBinds = VRM_VISEME_KEYS.filter(v => porVocal[v].length);
  if (conBinds.length < 3) return 0;   // muy pocas vocales con morph propio: mejor expressionManager
  const vistos = new Set();
  for (const nombre of VISEME_NAMES) {
    for (const [vocal, peso] of _VISEMAS_POR_VOCAL[nombre] ?? []) {
      for (const b of porVocal[vocal]) _agregarSlot(nombre, b.mesh, b.idx, peso * b.peso, vistos);
    }
  }
  console.log(`[Lipsync] vocales autodetectadas por binds: ${conBinds.join(', ')}`
            + (conBinds.length < 5 ? ` (faltan: ${VRM_VISEME_KEYS.filter(v => !conBinds.includes(v)).join(', ')})` : ''));
  return VISEME_NAMES.filter(n => _visemeSlots[n].length).length;
}

function _resolverLipsyncPorPerfil(tabla) {
  const todosLosMorphsPorNombre = {};
  vrm.scene.traverse(obj => {
    if (!obj.isMesh || !obj.morphTargetDictionary) return;
    for (const [clave, idx] of Object.entries(obj.morphTargetDictionary)) {
      (todosLosMorphsPorNombre[clave] ??= []).push({ mesh: obj, idx });
    }
  });
  const vistos = new Set();
  const noEncontrados = [];
  for (const nombre of VISEME_NAMES) {
    for (const { morph, peso } of tabla[nombre] ?? []) {
      const hits = todosLosMorphsPorNombre[morph];
      if (!hits?.length) { noEncontrados.push(`${nombre} -> "${morph}"`); continue; }
      for (const { mesh, idx } of hits) _agregarSlot(nombre, mesh, idx, peso, vistos);
    }
  }
  if (noEncontrados.length) console.warn(`[Lipsync] morphs del perfil que NO existen en este VRM: ${noEncontrados.join(', ')}`);
  return VISEME_NAMES.filter(n => _visemeSlots[n].length).length;
}

// Nombres crudos de los morphs (extras.targetNames del glTF) de un Mesh de
// three, vía parser.associations — el diccionario de three no los conserva.
function _nombresMorph(gltf, mesh) {
  try {
    const a = gltf?.parser?.associations?.get(mesh);
    const m = a != null ? gltf.parser.json.meshes?.[a.meshes] : null;
    if (!m) return null;
    return m.extras?.targetNames ?? m.primitives?.[a.primitives ?? 0]?.extras?.targetNames ?? null;
  } catch { return null; }
}

// Emociones que se apagan mientras habla: las que mueven la boca. Por nombre
// del morph cuando se puede leer (MTH = boca, ALL = cara completa en VRoid,
// vrc.v_* = visemes); si no, las que comparten malla con las vocales.
function _detectarSupresionHabla(gltf) {
  if (PERFIL_MODELO.expresionesSuprimirHabla) return new Set(PERFIL_MODELO.expresionesSuprimirHabla);
  const mallasBoca = new Set(VRM_VISEME_KEYS.flatMap(v => _bindsDeExpresion(v).map(b => b.mesh)));
  const res = new Set();
  for (const clave of ['happy', 'sad', 'angry', 'surprised', 'relaxed']) {
    for (const b of _bindsDeExpresion(clave)) {
      const nombres = _nombresMorph(gltf, b.mesh);
      const n = nombres?.[b.idx];
      if (n != null ? /MTH|_ALL_|mouth|vrc\.v_/i.test(n) : mallasBoca.has(b.mesh)) { res.add(clave); break; }
    }
  }
  return res;
}

function localizarMallaFacial(gltf) {
  _visemeSlots = {};
  _visemeSlotsUnicos = [];
  for (const nombre of VISEME_NAMES) _visemeSlots[nombre] = [];

  let resueltos = 0, via = '';
  if (PERFIL_MODELO.lipsync?.visemas) {
    resueltos = _resolverLipsyncPorPerfil(PERFIL_MODELO.lipsync.visemas);
    via = 'perfil';
  }
  if (!resueltos) { resueltos = _resolverLipsyncPorVocales(); via = 'vocales'; }
  _viaLipsync = resueltos > 0 ? 'directo' : 'expressionManager';
  if (_viaLipsync === 'directo') {
    console.log(`[Lipsync] VÍA ACTIVA: directo (${via}) — ${resueltos}/${VISEME_NAMES.length} visemes, `
              + `${_visemeSlotsUnicos.length} slot(s) de morph`);
  } else {
    console.warn('[Lipsync] VÍA ACTIVA: expressionManager (aa/ee/ih/oh/ou) — sin binds de vocales usables');
  }

  _expresionesSuprimirHabla = _detectarSupresionHabla(gltf);
  console.log('[Lipsync] emociones que se apagan al hablar:', [..._expresionesSuprimirHabla].join(', ') || 'ninguna');
  diagnosticarExpressionBinds();
}

// Investigación (no toca el sistema de lipsync): para cada expresión de
// expressionManager, qué (malla, índice de morph) apunta realmente cada bind.
// Sirve para recuperar el mapeo real cuando morphTargetDictionary trae nombres
// genéricos (ej. "Bodybaked_NN") en vez de los vrc.* originales del glTF —
// los binds del VRM apuntan a (malla, índice) directo, sin pasar por el nombre.
function diagnosticarExpressionBinds() {
  if (!vrm?.expressionManager) return;
  const expresiones = vrm.expressionManager.expressions ?? [];
  console.log(`[Diag] expressionManager: ${expresiones.length} expresiones`);
  for (const expr of expresiones) {
    const binds = expr._binds ?? [];
    if (binds.length === 0) {
      console.log(`[Diag] expresión "${expr.expressionName}" — sin binds de morph target`);
      continue;
    }
    console.log(`[Diag] expresión "${expr.expressionName}" — ${binds.length} bind(s):`);
    for (const bind of binds) {
      const mallas = (bind.primitives ?? []).map(p => p.name || '<sin name>').join(', ');
      console.log(`    -> malla(s)=[${mallas}]  morph_index=${bind.index}  weight=${bind.weight}`);
    }
  }
}

// Escribe los visemes ACTIVOS de este frame (0, 1 o 2 — actual + siguiente
// durante el crossfade del timeline) resueltos vía _visemeSlots. Pone a 0
// primero TODOS los slots únicos (varios visemes canónicos pueden compartir
// el mismo morph real — ver el perfil "reducido" del modelo nuevo, donde
// dd/nn/ss/th/rr/ch comparten "ih") y después SUMA (no pisa) cada
// contribución activa, para que dos visemes que comparten morph se mezclen
// bien durante el crossfade en vez de que el segundo pise al primero.
// activos: [{nombre, peso}, ...] — nombre es un canónico de VISEME_NAMES.
function _escribirVisemes(activos) {
  for (const { mesh, idx } of _visemeSlotsUnicos) mesh.morphTargetInfluences[idx] = 0;
  for (const { nombre, peso } of activos) {
    const entradas = _visemeSlots[nombre];
    if (!entradas) continue;
    for (const { mesh, idx, peso: pesoConfig } of entradas) {
      mesh.morphTargetInfluences[idx] += peso * pesoConfig;
    }
  }
}

// Encola audio+timeline recibidos por WS; reproduce en orden, nunca solapa frases.
function encolarAudio(url, timeline) {
  _reportarVoz(true);
  _audioPlayQueue.push({ url, timeline });
  if (!_audioPlaying) _reproducirSiguienteDeCola();
}

function _reproducirSiguienteDeCola() {
  const siguiente = _audioPlayQueue.shift();
  if (!siguiente) { _audioPlaying = false; return; }
  _audioPlaying = true;

  _timeline    = siguiente.timeline || [];
  _timelineIdx = 0;
  _audioEl.src = siguiente.url;

  console.log('[Lipsync] llamando a play() para', siguiente.url);
  const promesa = _audioEl.play();
  if (promesa?.then) {
    promesa
      .then(() => console.log('[Lipsync] play() resuelto (promesa) para', siguiente.url))
      .catch(err => console.error('[Lipsync] play() rechazado para', siguiente.url,
        '- name:', err?.name, '| message:', err?.message));
  }
}

// Estado del viseme activo, calculado una vez por frame y reusado por las dos
// fases de abajo (pre/post vrm.update). null si no hay audio sonando.
let _estadoVisemeFrame = null;

function _calcularEstadoViseme() {
  if (!_audioActivo || _timeline.length === 0) return null;
  // audio.currentTime ya es la posición dentro del archivo actual — no hace
  // falta llevar un start time aparte como con Web Audio API. A 60fps sobra
  // de precisión para el lipsync.
  const t = _audioEl.currentTime;

  while (_timelineIdx < _timeline.length - 1 && _timeline[_timelineIdx + 1].t <= t) _timelineIdx++;

  const actual    = _timeline[_timelineIdx];
  const siguiente = _timeline[_timelineIdx + 1] ?? actual;

  let alpha = 0;
  if (siguiente !== actual) {
    const span = siguiente.t - actual.t;
    alpha = span > 0 ? clamp((t - actual.t) / span, 0, 1) : 1;
  }
  return { actual, siguiente, alpha };
}

// FASE 1 — ANTES de vrm.update(dt). Necesaria solo para la vía de fallback:
// expressionManager.update() (llamado dentro de vrm.update()) es lo que consume
// los pesos puestos por setValue() y escribe los morphs reales — si los
// seteamos después, vrm.update() ya pasó y no hacen efecto hasta el frame
// siguiente (mismo motivo por el que updateExpressions()/updateBlink() ya
// corrían antes de vrm.update(), más arriba en animate()).
function aplicarVisemesPreUpdate() {
  _estadoVisemeFrame = _calcularEstadoViseme();
  if (_viaLipsync !== 'expressionManager') return;

  const pesos = { aa: 0, ee: 0, ih: 0, oh: 0, ou: 0 };
  if (_estadoVisemeFrame) {
    const { actual, siguiente, alpha } = _estadoVisemeFrame;
    if (actual.viseme_vrm) pesos[actual.viseme_vrm] += actual.peso_vrm * (1 - alpha);
    if (siguiente !== actual && siguiente.viseme_vrm) pesos[siguiente.viseme_vrm] += siguiente.peso_vrm * alpha;
  }
  for (const key of VRM_VISEME_KEYS) trySetExpr(key, pesos[key]);
}

// FASE 2 — DESPUÉS de vrm.update(dt). Los morph targets vrc.* van acá porque
// expressionManager escribe cero en SUS morphs en cada update() (no toca los
// vrc.* directos, así que a esos sí hay que aplicarlos después). El jaw
// siempre va acá, en ambas vías, vía getRawBoneNode (hueso real, no el
// proxy normalizado — ver CLAUDE.md).
function aplicarVisemesPostUpdate(dt) {
  let objetivoApertura = 0;

  if (_viaLipsync !== 'expressionManager') {
    if (_estadoVisemeFrame) {
      const { actual, siguiente, alpha } = _estadoVisemeFrame;
      const activos = [{ nombre: actual.viseme, peso: 1 - alpha }];
      if (siguiente !== actual) activos.push({ nombre: siguiente.viseme, peso: alpha });
      _escribirVisemes(activos);
    } else {
      _escribirVisemes([]);
    }
  }

  if (_estadoVisemeFrame) objetivoApertura = _estadoVisemeFrame.actual.apertura ?? 0;

  _jawApertura = lerp(_jawApertura, objetivoApertura, dt * JAW_SMOOTH_SPEED);
  // Modelos sin hueso jaw (ver CONFIG.modelos / models/README.md): la
  // apertura de mandíbula simplemente no se anima por hueso — los visemes
  // (arriba) siguen moviendo la boca igual, jawB es la única fuente de esa
  // apertura extra y su ausencia no es un error.
  const jawB = vrm?.humanoid?.getRawBoneNode('jaw');
  if (jawB) jawB.rotation.x = _jawApertura * JAW_MAX_RAD;
}
