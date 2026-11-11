// avatar/escritorio_ui.js — interfaz del modo escritorio (?modo=escritorio,
// rem_chat.py --modo escritorio; la parte GTK está en escritorio.py).
// Script clásico: comparte el ámbito global con el resto de avatar/ (ver
// avatar/README.md). Solo hace algo si ES_ESCRITORIO.
//
// Reparto con Python (escritorio.py):
//   - El ARRASTRE lo lleva Python (posición desde el cursor global de
//     Hyprland). Aquí llega como arrastreInicio(x, y) / posicion(gx, gy) /
//     arrastreFin(), y de eso sale la inclinación (muelle amortiguado hacia un
//     ángulo proporcional a la velocidad, pivotando en el punto agarrado).
//   - Un CLIC sin arrastre llega como clic(x, y): reacción (cara, vaivén,
//     burbuja), y con muchos seguidos se enoja.
//   - La REGIÓN DE CLIC la calcula esta página: cajas alrededor de los huesos
//     proyectados (sigue al cuerpo también durante un clip o inclinado) más los
//     botones y el menú cuando están a la vista. Se manda {tipo:'region'}.
//   - Pulsar sobre el cuerpo se avisa ({tipo:'presion'}): sin eso Python no
//     arrastra (así los botones y el menú no mueven el avatar).
//   - Clic derecho: menú propio (HTML, dentro de la superficie).
//   - Botones al pasar el ratón: chat, menú y ocultar.
// La ventana de chat aparte habla con esta página por el servidor
// (cmd_avatar / del_avatar, ver chat_remoto.js).
"use strict";

const _esc = {
  // inclinación (rad) y su velocidad angular
  tz: 0, tx: 0, wz: 0, wx: 0,
  // velocidad del arrastre (px/s), filtrada, y la instantánea más reciente
  vx: 0, vy: 0, vxObj: 0, vyObj: 0, ultima: null,
  arrastrando: false,
  pivote: new THREE.Vector3(), hayPivote: false,
  qTilt: new THREE.Quaternion(), qBase: new THREE.Quaternion(),
  euler: new THREE.Euler(), ejeY: new THREE.Vector3(0, 1, 0), tmp: new THREE.Vector3(),
  // interfaz
  punteroDentro: false, ocultarBotonesEn: 0, botonesVisibles: false,
  menuAbierto: false, menuCierraEn: 0,
  burbuja: null,          // {texto, hasta}
  clics: [], enojoHasta: 0,
  ptt: 'idle', esperando: false, vozActiva: true,
  regionClave: '', regionT: 0,
  cabezaPx: null,          // {x, y, r} de la última región, para colocar botones y burbuja
  oculto: false,
  modo: 'ia',              // ia | eco (modo_actual del servidor)
  maxTz: 0, maxVx: 0,      // diagnóstico por arrastre (se loguea al soltar)
  // mirada al cursor: posición en px de superficie, cuándo cambió y el ángulo suavizado
  cursor: null, cursorT: 0, miraYaw: 0, miraPitch: 0,
};

// A escritorio.py, por el WebSocket del servidor (mismo proceso). No por
// window.webkit.messageHandlers: ver establecer_oyente_escritorio en
// rem_avatar_server.py (los JSCValue en Python colgaban el bucle de GTK).
function _aPython(obj) {
  if (!_ws || _ws.readyState !== WebSocket.OPEN) return false;
  _ws.send(JSON.stringify({ tipo: 'escritorio', datos: obj }));
  return true;
}

const _azar = lista => lista[Math.floor(Math.random() * lista.length)];

// Preferencias de las pestañas Avatar y Escritorio del panel (ws.js las pasa por
// window.__remPrefs; los valores por defecto son los de preferencias.py).
let _prefsAvatar = { mirarCursor: true, mirarPeso: 0.6, inclinacion: 1, reacciones: true, clicsEnojo: 5, frasesVoz: true };
let _prefsEscritorio = { capa: 'top', respetarBarras: true, tamano: 100 };

// Frases de reacción: texto de interfaz, sin LLM (nada de llamadas al modelo
// sin que el usuario escriba o hable; ver CLAUDE.md). Viven en
// frases_escritorio.json: el servidor las tiene ya sintetizadas (frases_voz.py)
// y suenan al instante con lipsync.
let FRASES_ESCRITORIO = {};
fetch('/frases_escritorio.json', { cache: 'no-cache' })
  .then(r => r.json()).then(d => { FRASES_ESCRITORIO = d; })
  .catch(e => console.warn('[Escritorio] sin frases_escritorio.json:', e));
// «sirviente» nunca en dos reacciones seguidas: si la anterior lo llevaba, se
// elige entre las que no (si queda alguna en esa lista).
let _ultimaConSirviente = false;
function _frase(clave) {
  const l = FRASES_ESCRITORIO[clave];
  if (!Array.isArray(l) || !l.length) return '';
  const tiene = t => /sirviente/i.test(t);
  const sin = _ultimaConSirviente ? l.filter(t => !tiene(t)) : [];
  const t = _azar(sin.length ? sin : l);
  _ultimaConSirviente = tiene(t);
  return t;
}

// ═══════════════════════════════════════════════════
// PROYECCIÓN Y REGIÓN DE CLIC
// ═══════════════════════════════════════════════════
const _HUESOS_REGION = {
  torso: ['hips', 'spine', 'chest', 'upperChest', 'neck'],
  brazoI: ['leftUpperArm', 'leftLowerArm', 'leftHand'],
  brazoD: ['rightUpperArm', 'rightLowerArm', 'rightHand'],
  piernaI: ['leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'leftToes'],
  piernaD: ['rightUpperLeg', 'rightLowerLeg', 'rightFoot', 'rightToes'],
};

function _proyectar(v) {
  const p = _esc.tmp.copy(v).project(camera);
  return { x: (p.x + 1) / 2 * window.innerWidth, y: (1 - p.y) / 2 * window.innerHeight };
}

function _posHueso(nombre) {
  const b = vrm?.humanoid?.getRawBoneNode(nombre);
  return b ? b.getWorldPosition(new THREE.Vector3()) : null;
}

// Cajas (px de superficie) que cubren el cuerpo: círculos a lo largo de cada
// cadena de huesos, del radio de CONFIG.escritorio.region, como cuadrados.
function _cajasCuerpo() {
  const R = CONFIG.escritorio.region;
  const pxU = window.innerHeight / (_alturaVisible || 1);   // px por unidad en el plano del modelo
  const cajas = [];
  const caja = (c, r) => cajas.push([c.x - r, c.y - r, 2 * r, 2 * r]);
  const cadena = (nombres, rU) => {
    const pts = nombres.map(_posHueso).filter(Boolean).map(_proyectar);
    const r = rU * pxU + R.margenPx;
    for (let i = 0; i < pts.length; i++) {
      caja(pts[i], r);
      if (i === 0) continue;
      const a = pts[i - 1], b = pts[i];
      const n = Math.min(8, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / r));
      for (let k = 1; k < n; k++) caja({ x: a.x + (b.x - a.x) * k / n, y: a.y + (b.y - a.y) * k / n }, r);
    }
    return pts;
  };
  cadena(_HUESOS_REGION.torso, R.radioTorso);
  cadena(_HUESOS_REGION.brazoI, R.radioBrazo);
  cadena(_HUESOS_REGION.brazoD, R.radioBrazo);
  cadena(_HUESOS_REGION.piernaI, R.radioPierna);
  cadena(_HUESOS_REGION.piernaD, R.radioPierna);
  // Cabeza: el hueso head está en la base del cráneo; el centro, algo más arriba.
  const head = _posHueso('head');
  if (head) {
    head.y += 0.08;
    const c = _proyectar(head);
    const r = R.radioCabeza * pxU + R.margenPx;
    caja(c, r);
    _esc.cabezaPx = { x: c.x, y: c.y, r };
  }
  return cajas;
}

function _cajaDe(el) {
  if (!el || el.hidden || getComputedStyle(el).display === 'none') return null;
  const r = el.getBoundingClientRect();
  return r.width > 0 ? [r.left, r.top, r.width, r.height] : null;
}

function _actualizarRegion(forzar) {
  const ahora = performance.now();
  if (!forzar && ahora - _esc.regionT < CONFIG.escritorio.region.cadaMs) return;
  _esc.regionT = ahora;
  if (!vrm || !vrm.scene.visible || _esc.oculto) return;
  const cajas = _cajasCuerpo();
  if (_esc.botonesVisibles) { const c = _cajaDe(_ui.botones); if (c) cajas.push(c); }
  if (_esc.menuAbierto) { const c = _cajaDe(_ui.menu); if (c) cajas.push(c); }
  const W = window.innerWidth, H = window.innerHeight;
  const rects = [];
  for (const [x, y, w, h] of cajas) {
    const x0 = Math.max(0, Math.floor(x)), y0 = Math.max(0, Math.floor(y));
    const x1 = Math.min(W, Math.ceil(x + w)), y1 = Math.min(H, Math.ceil(y + h));
    if (x1 > x0 && y1 > y0) rects.push([x0, y0, x1 - x0, y1 - y0]);
  }
  // Solo si cambió de verdad (cuantizado a 3 px): cada envío reaplica la región en GTK.
  const clave = rects.map(r => r.map(v => Math.round(v / 3)).join(',')).join(';');
  if (clave === _esc.regionClave) return;
  if (_aPython({ tipo: 'region', rects })) _esc.regionClave = clave;   // sin WS, se reintenta
}

// ═══════════════════════════════════════════════════
// INCLINACIÓN AL ARRASTRAR
// ═══════════════════════════════════════════════════
// Punto de la superficie (px) → punto del plano z=0 del modelo (mundo).
function _puntoEnPlano(x, y) {
  const ndc = new THREE.Vector3(x / window.innerWidth * 2 - 1, -(y / window.innerHeight * 2 - 1), 0.5);
  const dir = ndc.unproject(camera).sub(camera.position).normalize();
  if (Math.abs(dir.z) < 1e-6) return null;
  return camera.position.clone().addScaledVector(dir, -camera.position.z / dir.z);
}

function _fijarPivote(x, y) {
  const p = _puntoEnPlano(x, y);
  if (!p) return;
  // Acotado al cuerpo: agarrar por el aire junto a ella no la hace girar raro.
  const pie = _modeloPositionY + _modeloCentroLocal - _modeloAlturaLocal / 2;
  p.y = clamp(p.y, pie, pie + _modeloAlturaLocal);
  _esc.pivote.copy(p);
  _esc.hayPivote = true;
}

function _actualizarInclinacion(dt) {
  const I = CONFIG.escritorio.inclinacion;
  // La velocidad la calcula escritorio.py con sus propias marcas de tiempo (las
  // llamadas a la página pueden llegar a ráfagas); aquí solo se suaviza.
  if (!_esc.arrastrando) _esc.vxObj = _esc.vyObj = 0;
  const a = 1 - Math.exp(-dt / I.suavizadoVel);
  _esc.vx += (_esc.vxObj - _esc.vx) * a;
  _esc.vy += (_esc.vyObj - _esc.vy) * a;
  const k = _prefsAvatar.inclinacion;   // multiplicador del panel (0 = sin inclinación)
  const objZ = clamp(-_esc.vx * I.porVelX * k, -I.maxZ * k, I.maxZ * k);
  const objX = clamp(-_esc.vy * I.porVelY * k, -I.maxX * k, I.maxX * k);
  // Muelle semi-implícito en dos subpasos (estable con dt de hasta 50 ms).
  for (let i = 0; i < 2; i++) {
    const h = dt / 2;
    _esc.wz += (I.rigidez * (objZ - _esc.tz) - I.amortiguacion * _esc.wz) * h;
    _esc.wx += (I.rigidez * (objX - _esc.tx) - I.amortiguacion * _esc.wx) * h;
    _esc.tz += _esc.wz * h;
    _esc.tx += _esc.wx * h;
  }
  if (!_esc.arrastrando && Math.abs(_esc.tz) + Math.abs(_esc.tx) + Math.abs(_esc.wz) + Math.abs(_esc.wx) < 1e-4) {
    _esc.tz = _esc.tx = _esc.wz = _esc.wx = 0;
  }
  if (_esc.arrastrando) {
    _esc.maxTz = Math.max(_esc.maxTz, Math.abs(_esc.tz));
    _esc.maxVx = Math.max(_esc.maxVx, Math.abs(_esc.vx));
  }
}

// ═══════════════════════════════════════════════════
// COLGADA: la pose mientras la llevas agarrada
// ═══════════════════════════════════════════════════
// Procedural (ningún clip del catálogo sirve: los de sentarse, de frente, se
// leen como sentada en el aire, y "flotar en el agua" casi no se distingue de
// estar de pie). Piernas colgando que se balancean con la inercia (un muelle
// propio, más lento que el de la inclinación: van detrás), pataleo suave, pies
// en punta y brazos algo abiertos agitándose. Se mezcla ENCIMA de lo que haga
// el cuerpo (clip o procedural) con un peso que entra y sale con fundido.
// Ángulos en la convención de la pose procedural (VRM 0.x), espejados para 1.0.
const _colg = { peso: 0, pz: 0, wpz: 0, px: 0, wpx: 0, q: new THREE.Quaternion(), e: new THREE.Euler() };

function _poseColgada(nombre, x, y, z, peso) {
  const b = getB(nombre);
  if (!b) return;
  _colg.e.set(x, y, z, 'XYZ');
  _colg.q.setFromEuler(_colg.e);
  if (_esVRM1) _colg.q.set(-_colg.q.x, _colg.q.y, -_colg.q.z, _colg.q.w);
  b.quaternion.slerp(_colg.q, peso);
}

function _actualizarColgada(dt) {
  const C = CONFIG.escritorio.colgada;
  const objetivo = _esc.arrastrando ? 1 : 0;
  const paso = dt / (objetivo > _colg.peso ? C.entradaS : C.salidaS);
  _colg.peso = objetivo > _colg.peso ? Math.min(1, _colg.peso + paso) : Math.max(0, _colg.peso - paso);
  // Péndulo de las piernas: hacia atrás del movimiento (lateral y adelante-atrás).
  // (signo medido en vivo: con -vx las piernas se iban hacia donde se movía)
  const objZ = clamp(_esc.vx * C.inercia, -C.maxBalanceo, C.maxBalanceo);
  const objX = clamp(_esc.vy * C.inercia * 0.6, -C.maxBalanceo, C.maxBalanceo);
  _colg.wpz += (C.rigidez * (objZ - _colg.pz) - C.amortiguacion * _colg.wpz) * dt;
  _colg.wpx += (C.rigidez * (objX - _colg.px) - C.amortiguacion * _colg.wpx) * dt;
  _colg.pz += _colg.wpz * dt;
  _colg.px += _colg.wpx * dt;
  if (_colg.peso <= 0) return;
  const w = _colg.peso * _colg.peso * (3 - 2 * _colg.peso);   // smoothstep
  const t = performance.now() / 1000;
  const pat = Math.sin(t * Math.PI * 2 * C.pataleoHz) * C.pataleo;
  const ag = Math.sin(t * Math.PI * 2 * C.agitarHz);
  const ag2 = Math.sin(t * Math.PI * 2 * C.agitarHz * 1.13 + 1.7);
  const sL = C.signoLado;   // +1/-1 según hacia dónde abre la pierna izquierda (convención del modelo)
  _poseColgada('leftUpperLeg',  C.caderas + _colg.px + pat, 0,  sL * C.abrirPiernas + _colg.pz, w);
  _poseColgada('rightUpperLeg', C.caderas + _colg.px - pat, 0, -sL * C.abrirPiernas + _colg.pz, w);
  _poseColgada('leftLowerLeg',  C.rodillas + Math.max(0, -pat) * 1.6, 0, 0, w);
  _poseColgada('rightLowerLeg', C.rodillas + Math.max(0,  pat) * 1.6, 0, 0, w);
  _poseColgada('leftFoot',  C.pies, 0, 0, w);
  _poseColgada('rightFoot', C.pies, 0, 0, w);
  _poseColgada('leftUpperArm',  C.brazosAdelante, 0,  C.brazos + ag * C.agitar, w);
  _poseColgada('rightUpperArm', C.brazosAdelante, 0, -C.brazos + ag2 * C.agitar, w);
  _poseColgada('leftLowerArm',  0, -C.codos, 0, w);
  _poseColgada('rightLowerArm', 0,  C.codos, 0, w);
}

// ═══════════════════════════════════════════════════
// MIRADA AL CURSOR
// ═══════════════════════════════════════════════════
// escritorio.py manda la posición del cursor (px de la superficie, puede estar
// fuera) cada vez que cambia. Se suma a la base de la mirada (ver _miradaBase
// en cuerpo.js): los ojos lo siguen y la cabeza un poco (CONFIG.mirada.
// cabezaFraccion de lo que miran los ojos, más el peso de aquí). Sin mover el
// ratón unos segundos, vuelve al frente.
// Signo de yaw/pitch de vrm.lookAt para un punto a la derecha (+X) y arriba
// (+Y) de la cabeza: depende del modelo (VRM 0.x/1.0), así que se le pregunta a
// three-vrm una vez por modelo en vez de suponerlo.
let _signosMirada = null;
function _signosLookAt() {
  if (_signosMirada?.gen === _modeloGen) return _signosMirada;
  const h = _posHueso('head');
  if (!h || !vrm?.lookAt) return { x: 1, y: 1 };
  vrm.lookAt.lookAt(h.clone().add(new THREE.Vector3(0.5, 0, 1)));
  const x = Math.sign(vrm.lookAt.yaw) || 1;
  vrm.lookAt.lookAt(h.clone().add(new THREE.Vector3(0, 0.5, 1)));
  const y = Math.sign(vrm.lookAt.pitch) || 1;
  _signosMirada = { gen: _modeloGen, x, y };
  console.log(`[Escritorio] signos de la mirada al cursor: yaw ${x}, pitch ${y}`);
  return _signosMirada;
}

function miradaCursorEscritorio(dt) {
  const M = CONFIG.escritorio.mirarCursor;
  let yaw = 0, pitch = 0;
  const c = _esc.cabezaPx, p = _esc.cursor;
  if (c && p && _prefsAvatar.mirarCursor && !_esc.arrastrando && !_esc.oculto
      && performance.now() - _esc.cursorT < M.volverTrasS * 1000) {
    const g = 180 / Math.PI, s = _signosLookAt();
    // Pantalla: x a la derecha = +X del mundo; y hacia abajo = -Y.
    const peso = _prefsAvatar.mirarPeso;
    yaw = clamp(Math.atan2(p.x - c.x, M.distanciaPx) * g * peso * s.x, -M.maxYaw, M.maxYaw);
    pitch = clamp(Math.atan2(c.y - p.y, M.distanciaPx) * g * peso * s.y, -M.maxPitch, M.maxPitch);
  }
  const a = 1 - Math.exp(-dt * M.suavizado);
  _esc.miraYaw += (yaw - _esc.miraYaw) * a;
  _esc.miraPitch += (pitch - _esc.miraPitch) * a;
  return { yaw: _esc.miraYaw, pitch: _esc.miraPitch };
}

// Rotación de la escena del VRM = inclinación (en mundo) × su orientación base
// (VRM 0.x mira a -Z y se gira 180°, ver modelo.js), alrededor del pivote.
function _aplicarInclinacion() {
  const s = vrm.scene;
  _esc.qBase.setFromAxisAngle(_esc.ejeY, _esVRM1 ? 0 : Math.PI);
  _esc.euler.set(_esc.tx, 0, _esc.tz, 'XYZ');
  _esc.qTilt.setFromEuler(_esc.euler);
  s.quaternion.copy(_esc.qTilt).multiply(_esc.qBase);
  // Posición base: la del encuadre (recalcularEncuadre deja la cámara en su X).
  s.position.set(camera.position.x, _modeloPositionY, 0);
  if (_esc.hayPivote && (_esc.tz || _esc.tx)) {
    const d = s.position.clone().sub(_esc.pivote).applyQuaternion(_esc.qTilt);
    s.position.copy(_esc.pivote).add(d);
  }
}

// Llamada desde animate() (bucle.js) antes de vrm.update(): así los spring
// bones (pelo, falda) reaccionan al vaivén.
function actualizarEscritorio(dt) {
  if (!vrm) return;
  _actualizarInclinacion(dt);
  _actualizarColgada(dt);
  if (!_medirHuesosPendiente) _aplicarInclinacion();
  _actualizarRegion(false);
  _actualizarInterfaz();
}

// ═══════════════════════════════════════════════════
// REACCIONES
// ═══════════════════════════════════════════════════
// Cara de una emoción durante `ms` (el director la pinta, ver _caraObjetivo).
function _caraUnRato(nombre, ms) { _emocion = { nombre, hasta: performance.now() + ms }; }

// Burbuja; con voz=true además se pide decirla en voz alta (frase fija ya
// sintetizada). Si ya está hablando no se pide: una reacción nunca corta una
// respuesta (el servidor lo vuelve a comprobar, y también la voz apagada y el
// micrófono abierto).
function _decir(texto, ms = CONFIG.escritorio.burbujaMs, voz = false) {
  if (!texto) return;
  _esc.burbuja = { texto, hasta: performance.now() + ms };
  if (voz && _prefsAvatar.frasesVoz && _esc.vozActiva && !hayVozSonando() && /\p{L}/u.test(texto) && _ws?.readyState === WebSocket.OPEN) {
    _ws.send(JSON.stringify({ tipo: 'decir_frase', texto }));
  }
}

function _reaccionarClic(x, y) {
  if (!_prefsAvatar.reacciones) return;
  // Umbrales: el de enfado sale del panel; el de "molesta", 3/5 de ese.
  const C = { ...CONFIG.escritorio.clics, enojadaDesde: _prefsAvatar.clicsEnojo,
              molestaDesde: Math.max(2, Math.round(_prefsAvatar.clicsEnojo * 0.6)) };
  const ahora = performance.now();
  _fijarPivote(x, y);
  // Un golpecito: vaivén pequeño alrededor de donde se tocó.
  _esc.wz += (x < (_esc.cabezaPx?.x ?? window.innerWidth / 2) ? -1 : 1) * 1.1;
  if (ahora < _esc.enojoHasta) { _decir(_frase('enojo'), 1500, true); return; }
  _esc.clics = _esc.clics.filter(t => ahora - t < C.ventanaS * 1000);
  _esc.clics.push(ahora);
  const n = _esc.clics.length;
  console.log(`[Escritorio] clic (${n} en ${C.ventanaS}s)`);
  if (n >= C.enojadaDesde) {
    _esc.clics = [];
    _esc.enojoHasta = ahora + C.enojoS * 1000;
    recibirEmocion('angry');                 // cara + su clip (con su enfriamiento)
    _emocion = { nombre: 'angry', hasta: _esc.enojoHasta };
    _decir(_frase('enojada'), 3500, true);
  } else if (n >= C.molestaDesde) {
    _caraUnRato('angry', 1800);
    _decir(_frase('molesta'), undefined, true);
  } else {
    _caraUnRato(_azar(['surprised', 'happy']), 1300);
    if (Math.random() < 0.45) _decir(_frase('leve'), undefined, true);
  }
}

// ═══════════════════════════════════════════════════
// INTERFAZ: botones, menú, burbuja
// ═══════════════════════════════════════════════════
const _ui = {};

function _crearInterfazEscritorio() {
  const raiz = document.createElement('div');
  raiz.id = 'esc-raiz';
  raiz.innerHTML = `
    <div id="esc-burbuja" class="esc-oculto"><span></span></div>
    <div id="esc-botones" class="esc-ui esc-oculto">
      <button type="button" data-accion="chat" title="Chat">${_ICONOS.chat}</button>
      <button type="button" data-accion="menu" title="Más">${_ICONOS.mas}</button>
      <button type="button" data-accion="ocultar" title="Ocultar">${_ICONOS.ocultar}</button>
    </div>
    <div id="esc-menu" class="esc-ui" hidden></div>`;
  document.body.appendChild(raiz);
  _ui.burbuja = raiz.querySelector('#esc-burbuja');
  _ui.burbujaTxt = _ui.burbuja.querySelector('span');
  _ui.botones = raiz.querySelector('#esc-botones');
  _ui.menu = raiz.querySelector('#esc-menu');

  _ui.botones.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    const acc = b.dataset.accion;
    if (acc === 'menu') {
      const r = b.getBoundingClientRect();
      _abrirMenu(r.left, r.bottom + 6);
    } else {
      _accionEscritorio(acc);
    }
  });

  // Pulsar en el cuerpo (no en botones ni menú) arma el arrastre en Python.
  document.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    const enUI = e.target.closest?.('.esc-ui');
    if (_esc.menuAbierto && !e.target.closest?.('#esc-menu')) _cerrarMenu();
    if (!enUI) _aPython({ tipo: 'presion' });
  });
  document.addEventListener('contextmenu', e => {
    e.preventDefault();
    if (e.target.closest?.('#esc-menu')) return;
    _abrirMenu(e.clientX, e.clientY);
  });
  document.addEventListener('mousemove', () => _punteroEncima(true));
  document.addEventListener('mouseout', e => { if (!e.relatedTarget) _punteroEncima(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') _cerrarMenu(); });
}

// Iconos propios en SVG de trazo (heredan el color del botón).
const _svg = d => `<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const _ICONOS = {
  chat: _svg('<path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-4.5 3.2V17H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/>'),
  mas: _svg('<circle cx="6" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18" cy="12" r="1.2"/>'),
  ocultar: _svg('<path d="M3 3l18 18"/><path d="M10.6 6.1A9.8 9.8 0 0 1 12 6c5 0 8.5 4.2 9.5 6-.4.8-1.3 2-2.6 3.2M6.5 7.6C4.6 8.9 3.2 10.7 2.5 12c1 1.8 4.5 6 9.5 6 1.5 0 2.9-.4 4.1-1"/><path d="M9.9 10a3 3 0 0 0 4.1 4.1"/>'),
  nota: _svg('<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>'),
  vozOn: _svg('<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>'),
  vozOff: _svg('<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M17 9l5 6M22 9l-5 6"/>'),
  modelo: _svg('<circle cx="12" cy="8" r="4"/><path d="M4 21c1.2-4 4.3-6 8-6s6.8 2 8 6"/>'),
  ajustes: _svg('<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>'),
  salir: _svg('<path d="M6 6l12 12M18 6L6 18"/>'),
  chip: _svg('<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>'),
  mano: _svg('<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10V4.5a1.5 1.5 0 0 1 3 0V11M14 10.5V6a1.5 1.5 0 0 1 3 0v8a6 6 0 0 1-6 6h-.5A5.5 5.5 0 0 1 5 15l-1.4-3a1.5 1.5 0 0 1 2.6-1.4L8 13"/>'),
  posicion: _svg('<path d="M12 21s-6-5.6-6-11a6 6 0 0 1 12 0c0 5.4-6 11-6 11z"/><circle cx="12" cy="10" r="2.2"/>'),
  capas: _svg('<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>'),
};

function _punteroEncima(dentro) {
  if (dentro) {
    _esc.punteroDentro = true;
    _esc.ocultarBotonesEn = 0;
  } else if (_esc.punteroDentro) {
    _esc.punteroDentro = false;
    _esc.ocultarBotonesEn = performance.now() + CONFIG.escritorio.botonesOcultarMs;
    if (_esc.menuAbierto) _esc.menuCierraEn = performance.now() + 1200;
  }
}

// Pestañas del panel de control que el menú puede abrir directamente.
const PESTANAS_AJUSTES = [
  ['apariencia', 'Apariencia'], ['avatar', 'Avatar'], ['escritorio', 'Escritorio'],
  ['animaciones', 'Animaciones'], ['voz', 'Voz'], ['microfono', 'Micrófono'], ['chat', 'Chat'],
  ['personalidad', 'Personalidad'],
];

function _enviarWS(obj) {
  if (_ws?.readyState === WebSocket.OPEN) { _ws.send(JSON.stringify(obj)); return true; }
  return false;
}

function _accionEscritorio(acc, arg) {
  _cerrarMenu();
  if (acc === 'voz') {
    const activa = !_esc.vozActiva;
    _enviarWS({ tipo: 'voz', activa });
    _esc.vozActiva = activa;   // el servidor lo confirma con voz_actual
    // Apagada: solo texto (el servidor ya no la dice). Encendida: se dice.
    _decir(_frase(activa ? 'vozOn' : 'vozOff'), 2000, activa);
  } else if (acc === 'modo') {
    _enviarWS({ tipo: 'cambiar_modo', modo: _esc.modo === 'eco' ? 'ia' : 'eco' });
  } else if (acc === 'bailar') {
    setModoBaile(!_modoBaile);
  } else if (acc === 'modelo') {
    if (arg && arg !== MODELO_ACTIVO) _enviarWS({ tipo: 'prefs_set', seccion: 'modelo', cambios: { vrm: arg } });
  } else if (acc === 'saludar') {
    if (_catalogo && !_bailando) _dispararSaludo();
  } else if (acc === 'gesto') {
    if (_catalogo && !_bailando) _dispararIdleVrma();
  } else if (acc === 'encima') {
    // "Encima de pantalla completa" = capa overlay; quitarlo vuelve a top.
    _enviarWS({ tipo: 'prefs_set', seccion: 'escritorio',
                cambios: { capa: _prefsEscritorio.capa === 'overlay' ? 'top' : 'overlay' } });
  } else if (acc === 'ajustes') {
    _aPython({ tipo: 'accion', accion: 'ajustes', pestana: arg });
  } else {
    _aPython({ tipo: 'accion', accion: acc });   // chat, posicion_inicial, ocultar, salir
  }
}

// El menú: ítems simples y cuatro con submenú desplegable en el sitio (no hay
// sitio para submenús laterales en una superficie de 380 px).
function _itemsMenu() {
  return [
    { accion: 'chat', texto: 'Chat', icono: _ICONOS.chat },
    { accion: 'modo', texto: _esc.modo === 'eco' ? 'Modo: Eco (pasar a IA)' : 'Modo: IA (pasar a Eco)', icono: _ICONOS.chip },
    { accion: 'voz', texto: _esc.vozActiva ? 'Silenciar la voz' : 'Activar la voz', icono: _esc.vozActiva ? _ICONOS.vozOff : _ICONOS.vozOn },
    { accion: 'bailar', texto: _modoBaile ? 'Dejar de bailar' : 'Bailar', icono: _ICONOS.nota },
    { sub: 'modelos', texto: 'Modelo', icono: _ICONOS.modelo },
    { sub: 'gestos', texto: 'Gesto', icono: _ICONOS.mano },
    { sub: 'posicion', texto: 'Posición', icono: _ICONOS.posicion },
    { accion: 'encima', texto: 'Encima de pantalla completa', icono: _ICONOS.capas, marcado: _prefsEscritorio.capa === 'overlay' },
    { sub: 'ajustes', texto: 'Ajustes', icono: _ICONOS.ajustes },
    { sep: true },
    { accion: 'ocultar', texto: 'Ocultar', icono: _ICONOS.ocultar },
    { accion: 'salir', texto: 'Salir', icono: _ICONOS.salir, peligro: true },
  ];
}

function _itemsSubmenu(sub) {
  if (sub === 'modelos') {
    if (!_modelosLista.length) return [{ vacio: 'No hay modelos en models/vrm/.' }];
    return _modelosLista.map(m => ({ accion: 'modelo', arg: m.ruta, texto: m.titulo,
                                     title: `${m.autor} · ${m.ruta}`, actual: m.ruta === MODELO_ACTIVO }));
  }
  if (sub === 'gestos') return [{ accion: 'saludar', texto: 'Saludar' }, { accion: 'gesto', texto: 'Un gesto al azar' }];
  if (sub === 'posicion') return [{ accion: 'posicion_inicial', texto: 'Volver a la esquina inicial' }];
  if (sub === 'ajustes') return PESTANAS_AJUSTES.map(([id, t]) => ({ accion: 'ajustes', arg: id, texto: t }));
  return [];
}

let _menuSub = null;   // submenú desplegado, o null
function _pintarMenu(sub = null) {
  _menuSub = sub;
  const m = _ui.menu;
  m.innerHTML = '';
  const boton = (clase, html) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = clase;
    b.innerHTML = html;
    return b;
  };
  for (const it of _itemsMenu()) {
    if (it.sep) { m.appendChild(Object.assign(document.createElement('div'), { className: 'esc-sep' })); continue; }
    const abierto = it.sub && it.sub === sub;
    const b = boton('esc-item' + (it.peligro ? ' peligro' : '') + (abierto ? ' abierto' : ''),
      `<span class="esc-ico"></span><span class="esc-txt"></span>${it.sub ? '<span class="esc-flecha">›</span>' : ''}`
      + (it.marcado !== undefined ? `<span class="esc-marca${it.marcado ? ' si' : ''}"></span>` : ''));
    b.querySelector('.esc-ico').innerHTML = it.icono;   // SVG propio de _ICONOS
    b.querySelector('.esc-txt').textContent = it.texto;
    b.onclick = () => {
      if (it.sub) {
        _pintarMenu(abierto ? null : it.sub);
        if (it.sub === 'modelos' && !abierto) _enviarWS({ tipo: 'modelos_get' });
        _colocarMenu();
      } else _accionEscritorio(it.accion);
    };
    m.appendChild(b);
    if (abierto) {
      const lista = document.createElement('div');
      lista.className = 'esc-sub';
      for (const s of _itemsSubmenu(sub)) {
        if (s.vacio) { lista.appendChild(Object.assign(document.createElement('div'), { textContent: s.vacio })); continue; }
        const sb = boton('esc-item esc-subitem' + (s.actual ? ' actual' : ''), '');
        sb.textContent = s.texto;
        if (s.title) sb.title = s.title;
        sb.onclick = () => _accionEscritorio(s.accion, s.arg);
        lista.appendChild(sb);
      }
      m.appendChild(lista);
    }
  }
}

let _menuEn = { x: 0, y: 0 };
function _colocarMenu() {
  const m = _ui.menu, W = window.innerWidth, H = window.innerHeight;
  const w = m.offsetWidth, h = m.offsetHeight;
  m.style.left = `${clamp(_menuEn.x, 6, Math.max(6, W - w - 6))}px`;
  m.style.top = `${clamp(_menuEn.y, 6, Math.max(6, H - h - 6))}px`;
  _actualizarRegion(true);
}

function _abrirMenu(x, y) {
  _menuEn = { x, y };
  // Se abrió con el puntero encima: cuenta como dentro aunque GTK mande un
  // "salir" al cambiar la región de clic (si no, con el ratón quieto el menú
  // se cerraba solo a los 1,2 s).
  _esc.punteroDentro = true;
  _pintarMenu(null);
  _ui.menu.hidden = false;
  _esc.menuAbierto = true;
  _esc.menuCierraEn = performance.now() + 12000;
  _colocarMenu();
  requestAnimationFrame(() => _ui.menu.classList.add('visible'));
}

function _cerrarMenu() {
  if (!_esc.menuAbierto) return;
  _esc.menuAbierto = false;
  _ui.menu.classList.remove('visible');
  _ui.menu.hidden = true;
  _actualizarRegion(true);
}

function _actualizarInterfaz() {
  if (!_ui.botones) return;
  const ahora = performance.now();
  // Botones: a la vista mientras el puntero está sobre el cuerpo (y un poco después).
  const verBotones = !_esc.arrastrando && !_esc.menuAbierto
    && (_esc.punteroDentro || ahora < _esc.ocultarBotonesEn) && !!_esc.cabezaPx;
  if (verBotones !== _esc.botonesVisibles) {
    _esc.botonesVisibles = verBotones;
    _ui.botones.classList.toggle('esc-oculto', !verBotones);
    _actualizarRegion(true);
  }
  const c = _esc.cabezaPx;
  if (c && verBotones) {
    const bw = _ui.botones.offsetWidth, bh = _ui.botones.offsetHeight;
    const x = clamp(c.x + c.r + 8, 4, window.innerWidth - bw - 4);
    const y = clamp(c.y - bh / 2 + c.r * 0.6, 4, window.innerHeight - bh - 4);
    _ui.botones.style.transform = `translate(${x.toFixed(0)}px, ${y.toFixed(0)}px)`;
  }
  if (_esc.menuAbierto && ahora > _esc.menuCierraEn && !_esc.punteroDentro) _cerrarMenu();

  // Burbuja: reacción > escuchando > pensando.
  let texto = '';
  if (_esc.burbuja && ahora < _esc.burbuja.hasta) texto = _esc.burbuja.texto;
  else if (_esc.ptt === 'escuchando') texto = '🎙 Te escucho…';
  else if (_esc.ptt === 'transcribiendo' || ((_esc.esperando || estado === 'thinking') && !hayVozSonando())) texto = '…';
  if (_ui.burbujaTxt.textContent !== texto && texto) _ui.burbujaTxt.textContent = texto;
  _ui.burbuja.classList.toggle('esc-oculto', !texto);
  if (texto && c) {
    const bw = _ui.burbuja.offsetWidth, bh = _ui.burbuja.offsetHeight;
    const x = clamp(c.x - bw / 2, 4, window.innerWidth - bw - 4);
    const y = Math.max(4, c.y - c.r - bh - 6);
    _ui.burbuja.style.transform = `translate(${x.toFixed(0)}px, ${y.toFixed(0)}px)`;
    _ui.burbuja.style.setProperty('--cola-x', `${clamp(c.x - x, 14, bw - 14).toFixed(0)}px`);
  }
}

// ═══════════════════════════════════════════════════
// ENLACES: Python, WebSocket y la ventana de chat
// ═══════════════════════════════════════════════════
function crearEscritorioUI() {
  _crearInterfazEscritorio();

  window.__remPrefs = (seccion, v) => {
    if (seccion === 'avatar') _prefsAvatar = { ..._prefsAvatar, ...v };
    else if (seccion === 'escritorio') _prefsEscritorio = { ..._prefsEscritorio, ...v };
    else if (seccion === 'voz' && typeof v.activa === 'boolean') _esc.vozActiva = v.activa;
    else return;
    if (_esc.menuAbierto) _pintarMenu(_menuSub);
  };

  // Lo que llama escritorio.py (evaluate_javascript).
  window.__remEscritorio = {
    arrastreInicio(x, y) {
      _esc.arrastrando = true;
      _esc.ultima = null;
      _esc.maxTz = _esc.maxVx = 0;
      _fijarPivote(x, y);
      _cerrarMenu();
      _emocion = { nombre: 'surprised', hasta: Infinity };
      if (Math.random() < 0.35) _decir(_frase('agarre'), 2200, true);
      console.log('[Escritorio] arrastre: inicio');
    },
    // (gx, gy): esquina de la superficie en el escritorio; (vx, vy): su
    // velocidad en px/s, ya suavizada por escritorio.py.
    posicion(gx, gy, vx, vy) {
      _esc.ultima = { x: gx, y: gy, t: performance.now() };
      _esc.vxObj = vx ?? 0;
      _esc.vyObj = vy ?? 0;
    },
    arrastreFin() {
      _esc.arrastrando = false;
      console.log(`[Escritorio] arrastre: inclinación máx ${(_esc.maxTz * 180 / Math.PI).toFixed(1)}° `
                + `con ${_esc.maxVx.toFixed(0)} px/s`);
      if (_emocion?.nombre === 'surprised' && _emocion.hasta === Infinity) _emocion.hasta = performance.now() + 700;
      console.log('[Escritorio] arrastre: fin');
    },
    clic(x, y) { _reaccionarClic(x, y); },
    puntero(dentro) { _punteroEncima(dentro); },
    cursor(x, y) {
      if (!_esc.cursor || Math.hypot(x - _esc.cursor.x, y - _esc.cursor.y) > 2) _esc.cursorT = performance.now();
      _esc.cursor = { x, y };
    },
    // Ocultar sin desmapear la capa (ver escritorio.py): no se dibuja nada.
    ocultar(si) {
      _esc.oculto = !!si;
      _renderPausado = _esc.oculto;
      document.body.style.visibility = si ? 'hidden' : '';
      if (si) _cerrarMenu();
      _esc.regionClave = '';
      if (!si) renderer.render(scene, camera);
    },
  };

  // Mensajes del WebSocket que esta página atiende (ver ws.js).
  window.__remChat = {
    onDelta() {},
    onDone() { _esc.esperando = false; },
    // Con frase (aviso de Yoru, el servidor ya la dice con voz si puede), la
    // burbuja la enseña a ella; el mensaje técnico queda en el chat.
    onError(mensaje, frase) { _esc.esperando = false; _decir(frase || `⚠ ${mensaje}`, 4000); },
    onModoActual(modo) { _esc.modo = modo; if (_esc.menuAbierto) _pintarMenu(_menuSub); },
    onVozActual(activa) { _esc.vozActiva = !!activa; },
    onSistema(texto) { enviarAlChat({ que: 'sistema', texto }); },
    onModeloCargado(ruta, titulo, autor) {
      enviarAlChat({ que: 'modelo_cargado', ruta, titulo, autor });
      if (_esc.menuAbierto) { _pintarMenu(_menuSub); _colocarMenu(); }
    },
    onModelos() { if (_esc.menuAbierto && _menuSub === 'modelos') { _pintarMenu('modelos'); _colocarMenu(); } },
    onModoBaile(on) { enviarAlChat({ que: 'baile', activo: on }); },
    onClipLanzado(archivo) { enviarAlChat({ que: 'clip_lanzado', archivo, etiqueta: etiquetaClip(archivo) }); },
    onPttEstado(est, detalle) {
      _esc.ptt = (est === 'escuchando' || est === 'transcribiendo') ? est : 'idle';
      if (est === 'ignorado') _decir(`🎙 No te escuché: ${detalle}`, 4000);
    },
    // Veredicto del micrófono: en la burbuja la frase de Yoru (la voz la pone
    // el servidor, con el micrófono ya cerrado) o, sin ella, el mensaje.
    onMicVeredicto(veredicto, mensaje, frase) { if (veredicto !== 'enviar') _decir(frase || mensaje, 4500); },
    onConversacion() {},
    onTranscripcion(texto, ms) { _esc.esperando = true; _decir(`«${texto}»`, Math.max(1500, ms + 600)); },
    // Una acción espera confirmación: se contesta en la ventana de chat, que
    // se abre si estaba cerrada (el servidor le reenvía el pedido al conectar).
    onAccionConfirmar(_nombre, _descripcion, frase) {
      _aPython({ tipo: 'accion', accion: 'chat_abrir' });
      _decir(frase || _frase('confirmar'), 4000);   // la voz la pone el servidor
    },
  };

  // Pedidos de la ventana de chat aparte (servidor -> cmd_avatar).
  window.__remCmdAvatar = d => {
    if (d.que === 'estado_get') {
      _catalogoListo.then(() => enviarAlChat({ que: 'estado', baile: _modoBaile, clips: clipsDisponibles(), modelo: MODELO_ACTIVO }));
    } else if (d.que === 'baile') {
      setModoBaile(!!d.activo);
    } else if (d.que === 'saludar' || d.que === 'gesto') {
      _accionEscritorio(d.que);   // lo mismo que Gesto ▸ del menú
    } else if (d.que === 'clip') {
      const id = resolverClip(String(d.nombre ?? ''));
      if (!id) { enviarAlChat({ que: 'sistema', texto: `No hay ninguna animación "${d.nombre}".` }); return; }
      dispararClipManual(id, texto => enviarAlChat({ que: 'sistema', texto }));
    }
  };
  console.log('[Escritorio] interfaz lista');
}
if (ES_ESCRITORIO) crearEscritorioUI();
