// avatar/cuerpo.js — mirada, springs, pose procedural, ruido Perlin, peso, saccades, dedos y pose de cuerpo.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// SISTEMA DE MIRADA POR ESTADO
// ═══════════════════════════════════════════════════
const lookCur = { x: 0, y: 0 };
let lookDrift = { x: 0, y: 0 };
let lookChangeTimer = 2 + Math.random() * 3;

function updateLook(dt, t) {
  lookChangeTimer -= dt;
  const est = estadoCorporal();
  if (lookChangeTimer <= 0 && (est === 'idle' || est === 'happy' || est === 'sad')) {
    lookDrift.x = (Math.random() - 0.5) * 0.22;
    lookDrift.y = (Math.random() - 0.5) * 0.10;
    lookChangeTimer = 2.5 + Math.random() * 3.5;
  }

  let tgtX, tgtY, lerpSpd;
  switch (est) {
    case 'thinking':
      tgtX = -0.18; tgtY = 0.12; lerpSpd = 1.2; // arriba-izquierda
      break;
    case 'talking':
      tgtX = Math.sin(t * 0.12) * 0.04; tgtY = Math.sin(t * 0.09) * 0.03; lerpSpd = 2.5;
      break;
    default:
      tgtX = lookDrift.x; tgtY = lookDrift.y; lerpSpd = 1.3;
  }
  lookCur.x = lerp(lookCur.x, tgtX, dt * lerpSpd);
  lookCur.y = lerp(lookCur.y, tgtY, dt * lerpSpd);
}

// ═══════════════════════════════════════════════════
// SISTEMA DE SPRINGS (AMORTIGUADORES)
// ═══════════════════════════════════════════════════
class Spring {
  constructor(init = 0, k = 20, d = 6) { this.v = init; this.vel = 0; this.k = k; this.d = d; }
  step(target, dt) {
    const f = -this.k * (this.v - target) - this.d * this.vel;
    this.vel += f * dt; this.v += this.vel * dt; return this.v;
  }
  tune(k, d) { this.k = k; this.d = d; }
}

const spr = {
  hX: new Spring(0,    18, 5.5),
  hY: new Spring(0,    18, 5.5),
  hZ: new Spring(-0.04,18, 5.5),
  bZ: new Spring(0,    14, 4.5),
  bX: new Spring(0,    12, 4.0),
  ruZ: new Spring(-1.28, 22, 7.0),
  luZ: new Spring( 1.28, 22, 7.0),
  ruX: new Spring(0.05,  16, 5.0),
  luX: new Spring(0.05,  16, 5.0),
  // Antebrazos (flexión de codo) — un poco más blandas que ruX/luX a
  // propósito: el antebrazo "va detrás" del hombro, un retardo sobre otro
  // retardo (ver "BRAZOS ACOPLADOS AL CUERPO" en animate()).
  rlX: new Spring(-0.30, 14, 5.5),
  llX: new Spring(-0.30, 14, 5.5),
};

// Perfiles de stiffness/damping por estado
const SPRING_CFG = {
  idle:      [18, 5.5, 14, 4.5],
  talking:   [20, 5.0, 16, 4.0],
  thinking:  [14, 6.0, 10, 5.0],
  listening: [16, 6.0, 12, 5.0],
  happy:     [22, 4.5, 18, 3.5],
  sad:       [10, 7.0,  8, 6.0],
  angry:     [26, 3.0, 22, 2.8], // menos damping = más brusco
  surprised: [30, 4.0, 25, 3.5],
};

function applySpringConfig() {
  const [hk, hd, bk, bd] = SPRING_CFG[estado] ?? SPRING_CFG.idle;
  spr.hX.tune(hk, hd); spr.hY.tune(hk, hd); spr.hZ.tune(hk, hd);
  spr.bZ.tune(bk, bd); spr.bX.tune(bk, bd);
}

// ═══════════════════════════════════════════════════
// POSE PROCEDURAL POR ESTADO
// ═══════════════════════════════════════════════════
let surprisedSnap = 0;

// Estado que gobierna el CUERPO y la mirada. En overlay es siempre 'idle': los
// brazos quedan en la pose de reposo fija (CONFIG.brazos), sin gesticular al
// hablar ni la pose de 'thinking', y la mirada siempre va a cámara. El resto
// del avatar (cara, parpadeo, lipsync) sí sigue leyendo `estado`.
const estadoCorporal = () => ES_OVERLAY ? 'idle' : estado;

// Canales hX/hY/hZ/bZ/ruZ/luZ/ruX/luX: ruido Perlin, no senos (ver más abajo,
// "RUIDO PERLIN 1D" — un producto de senos sigue siendo periódico, aunque no
// lo parezca a simple vista; el ruido no lo es). bX (respiración) sigue con
// un seno limpio a propósito: la respiración real SÍ es rítmica, eso no es
// lo que hacía ver a Rem como un robot.
function getStatePose(t) {
  // Velocidades de animación por estado
  const SPEEDS = { idle:1.0, talking:1.8, thinking:0.5, listening:0.7, happy:1.5, sad:0.4, angry:1.3, surprised:2.0 };
  const est = estadoCorporal();
  const sp = SPEEDS[est] ?? 1.0;
  const ts = t * sp; // tiempo escalado por emoción

  // Respiración siempre presente
  const breath = Math.sin(ts * 0.8 / sp) * 0.018;

  switch (est) {

    case 'idle': {
      const S = CONFIG.brazos;
      // _idleAmpMult (>1) amplifica el ruido cuando hay clip de pose base de
      // idle activo — el clip fija la pose, el ruido rompe la periodicidad del
      // bucle. Vale 1 en procedural puro (ver actualizarAnimacionClips).
      const A = _idleAmpMult;
      return {
        hX: ruido(10, 0.15, ts) * 0.028 * A,
        hY: ruido(20, 0.12, ts) * 0.020 * A,
        hZ: -0.04 + ruido(30, 0.13, ts) * 0.016 * A,
        bZ: ruido(40, 0.10, ts) * 0.009 * A,
        bX: breath,
        ruZ: -S.separacion + ruido(50, 0.07, ts) * 0.02 * A,
        luZ:  S.separacion + ruido(51, 0.07, ts) * 0.02 * A,
        ruX:  S.balanceoDelante + ruido(60, 0.08, ts) * 0.02 * A,
        luX:  S.balanceoDelante + ruido(61, 0.08, ts) * 0.02 * A,
      };
    }

    case 'talking': {
      // Gesticulación con ruido, no senos: cada brazo con su propia fase y
      // amplitud generosa, para que se lea como alguien hablando con las
      // manos, no como un metrónomo. gestoAmp combina dos señales (ver
      // "BRAZOS ACOPLADOS AL CUERPO" más abajo para _hablaEnergia): un
      // envolvente de ruido lento (Math.max(0,...) pasa ~la mitad del
      // tiempo en 0 — eso es lo que crea pausas de verdad, no solo menos
      // amplitud) más la energía real del habla (apertura de mandíbula
      // suavizada). Con gestoAmp≈0 los brazos vuelven al mismo reposo que
      // en idle — "gestos que van y vuelven", no oscilación continua.
      const S = CONFIG.brazos;
      const envolvente = Math.max(0, ruido(200, 0.18, ts));
      const gestoAmp = clamp(envolvente * S.gestoRuidoAmp + _hablaEnergia * S.gestoHablaAmp, 0, 1);
      return {
        hX: ruido(10, 0.55, ts) * 0.09,
        hY: ruido(20, 0.48, ts) * 0.12,
        hZ: ruido(30, 0.60, ts) * 0.13,
        bZ: ruido(40, 0.65, ts) * 0.024,
        bX: breath,
        ruZ: -S.separacion + ruido(50, 0.30, ts) * 0.10 * gestoAmp,
        luZ:  S.separacion + ruido(51, 0.35, ts) * 0.16 * gestoAmp,
        ruX:  S.balanceoDelante + ruido(60, 0.40, ts) * 0.14 * gestoAmp,
        luX:  S.balanceoDelante + ruido(61, 0.45, ts) * 0.20 * gestoAmp,
      };
    }

    case 'thinking': {
      // Pose distinta y reconocible a propósito: mirada arriba a un lado
      // (ver también updateLook()/updateSaccades()), mano derecha elevada
      // hacia la cara (upperArm MÁS levantado que antes + codo MÁS
      // flexionado que la base universal, rlX propio en vez del genérico
      // de CONFIG.brazos.codoFlexionBase — ver animate()), movimiento más
      // lento que cualquier otro estado.
      const S = CONFIG.brazos;
      return {
        hX:  0.18 + ruido(10, 0.045, ts) * 0.016,
        hY:  0.15 + ruido(20, 0.040, ts) * 0.012,
        hZ: -0.22 + ruido(30, 0.050, ts) * 0.012,
        bZ: ruido(40, 0.045, ts) * 0.005,
        bX: breath * 0.7,
        ruZ: -0.85 + ruido(50, 0.03, ts) * 0.02, // brazo derecho bien elevado, hacia la cara
        luZ: S.separacion,
        ruX:  0.35 + ruido(60, 0.035, ts) * 0.02, // codo adelantado, no solo el hombro
        luX: S.balanceoDelante,
        rlX: -0.95 + ruido(65, 0.03, ts) * 0.03,  // codo bien flexionado — la mano llega a la cara
      };
    }

    case 'listening': {
      // Escuchando el push-to-talk (estado local, ver WEBSOCKET/ptt_estado):
      // cabeza ladeada hacia la cámara y un poco adelante, torso inclinado
      // hacia el que habla, brazos quietos. Movimiento lento y contenido.
      const S = CONFIG.brazos;
      return {
        hX:  0.06 + ruido(10, 0.10, ts) * 0.012,
        hY:  ruido(20, 0.08, ts) * 0.015,
        hZ:  0.13 + ruido(30, 0.09, ts) * 0.012,
        bZ:  ruido(40, 0.06, ts) * 0.005,
        bX:  0.035 + breath * 0.8,
        ruZ: -S.separacion, luZ: S.separacion,
        ruX:  S.balanceoDelante, luX: S.balanceoDelante,
      };
    }

    case 'happy': {
      const bob = ruido(5, 1.1, ts) * 0.018; // pequeño rebote de cabeza
      return {
        hX: bob + ruido(10, 0.5, ts) * 0.03,
        hY: ruido(20, 0.6, ts) * 0.045,
        hZ: ruido(30, 0.7, ts) * 0.055,
        bZ: ruido(40, 0.7, ts) * 0.02,
        bX: breath * 1.2,
        ruZ: -1.15 + ruido(50, 0.3, ts) * 0.03, luZ: 1.15 + ruido(51, 0.3, ts) * 0.03,
        ruX:  0.09 + ruido(60, 0.3, ts) * 0.02, luX: 0.09 + ruido(61, 0.3, ts) * 0.02,
      };
    }

    case 'sad':
      return {
        hX:  0.25 + ruido(10, 0.06, ts) * 0.012, // cabeza caída
        hY:  ruido(20, 0.05, ts) * 0.008,
        hZ:  0.05 + ruido(30, 0.05, ts) * 0.006,
        bZ:  ruido(40, 0.05, ts) * 0.004,
        bX:  0.05 + breath * 0.5, // spine ligeramente inclinada
        ruZ: -1.30, luZ: 1.30,
        ruX: 0.02, luX: 0.02,
      };

    case 'angry': {
      // Ruido a frecuencia alta en vez de sign(sin())*sin(): igual de
      // brusco/entrecortado a la vista, pero no forma un patrón que se
      // repita exacto — antes SÍ era periódico, solo que con un período
      // largo que lo disimulaba a corto plazo.
      return {
        hX: 0.06 + ruido(10, 1.5, ts) * 0.02,
        hY: ruido(20, 3.5, ts) * 0.014,
        hZ: ruido(30, 4.0, ts) * 0.020,
        bZ: ruido(40, 0.6, ts) * 0.018,
        bX: 0.02,
        ruZ: -1.24, luZ: 1.24,
        ruX: 0.08, luX: 0.08,
      };
    }

    case 'surprised': {
      const snap = clamp(surprisedSnap, 0, 1);
      return {
        hX: -0.20 * snap + ruido(10, 0.12, ts) * 0.018 * (1 - snap),
        hY:  ruido(20, 0.09, ts) * 0.015,
        hZ:  ruido(30, 0.15, ts) * 0.010,
        bZ: -0.04 * snap,
        bX: -0.03 * snap + breath,
        ruZ: -1.28 - 0.12 * snap,
        luZ:  1.28 + 0.12 * snap,
        ruX: 0.12, luX: 0.12,
      };
    }

    default:
      return { hX:0, hY:0, hZ:-0.04, bZ:0, bX:0,
               ruZ:-CONFIG.brazos.separacion, luZ:CONFIG.brazos.separacion,
               ruX:CONFIG.brazos.balanceoDelante, luX:CONFIG.brazos.balanceoDelante };
  }
}

// ═══════════════════════════════════════════════════
// RUIDO PERLIN 1D — reemplaza los Math.sin() de getStatePose()
// ═══════════════════════════════════════════════════
// El ojo detecta la periodicidad de sumas/productos de senos en pocos
// segundos (se lee como robot, no como alguien vivo) por más frecuencias
// que se combinen — siguen siendo, técnicamente, funciones periódicas. El
// ruido Perlin no lo es: es la misma técnica que "flow noise" para
// animación procedural de idle en personajes 3D. Implementación chica,
// clásica (Ken Perlin, tabla de permutación de 256 valores), sin
// dependencias externas — 1D alcanza: cada canal (cabeza X, cabeza Y, brazo
// derecho...) es noise1D(t * frecuencia + fase), con una fase fija propia
// por canal para que no se muevan todos en sincronía.
const _PERLIN_PERM = (() => {
  const p = new Uint8Array(256);
  for (let i = 0; i < 256; i++) p[i] = i;
  // Barajado con un PRNG determinístico (LCG) — no importa cuál en
  // particular, solo que la permutación sea siempre la misma entre cargas
  // de la página (si no, cada recarga tendría una "personalidad" de ruido
  // distinta, sin que eso aporte nada).
  let seed = 1337;
  const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    const tmp = p[i]; p[i] = p[j]; p[j] = tmp;
  }
  const perm = new Uint8Array(512);
  for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
  return perm;
})();

const _fade = t => t * t * t * (t * (t * 6 - 15) + 10);
const _gradiente1D = (hash, x) => ((hash & 1) === 0 ? x : -x);

// Devuelve un valor suave en, aproximadamente, [-1, 1].
function noise1D(x) {
  const xi = Math.floor(x) & 255;
  const xf = x - Math.floor(x);
  const u  = _fade(xf);
  const a  = _PERLIN_PERM[xi], b = _PERLIN_PERM[xi + 1];
  return lerp(_gradiente1D(a, xf), _gradiente1D(b, xf - 1), u);
}

// Un canal de ruido con su propia fase (frecuencia baja = movimiento lento).
const ruido = (fase, freq, t) => noise1D(t * freq + fase);

// ═══════════════════════════════════════════════════
// TRASLADO DE PESO — cadera lenta de un pie a otro, sin caminar
// ═══════════════════════════════════════════════════
// Reemplaza el bob/rock de la caminata eliminada: Rem se queda fija en su
// sitio (sin desplazamiento en X), pero una cadera muerta se ve tan
// artificial como una cabeza inmóvil. Frecuencia muy baja (periodo ~20s) a
// propósito — un traslado de peso real es lento y ocasional, no un tic.
// Devuelve {rock} además de mutar hips/spine — hombros y brazos lo reusan
// para "acompañar" el traslado de peso (ver BRAZOS ACOPLADOS AL CUERPO en
// animate()), en vez de tener su propia señal de ruido desconectada.
function updateTrasladoPeso(dt, t) {
  const rock = ruido(500, 0.05, t) * 0.035;
  const lean = ruido(510, 0.05, t) * 0.012; // leve inclinación de vuelta, para el balance
  const hipB = getB('hips');
  if (hipB) { hipB.rotation.z = rock; hipB.rotation.x = ruido(520, 0.04, t) * 0.01; }
  const spineB = getB('spine');
  if (spineB) spineB.rotation.z += -rock * 0.35 + lean;
  return { rock };
}

// ═══════════════════════════════════════════════════
// MIRADA A CÁMARA + MICRO-SACCADES — ojos, vía vrm.lookAt (huesos leftEye/rightEye)
// ═══════════════════════════════════════════════════
// Antes las saccades eran TODO el control de los ojos: saltos aleatorios
// alrededor de un centro fijo (0,0) en grados, sin relación con dónde está
// el usuario. Ahora hay una base real (_miradaBase(), justo abajo) — sigue
// a la cámara de verdad vía vrm.lookAt.lookAt(posición de la cámara), el
// mismo método que usaría el auto-tracking de three-vrm si target/autoUpdate
// estuvieran en el modo automático (ver el callback de carga del VRM, más
// arriba: se dejan target=camera + autoUpdate=false a propósito, así este
// código controla CUÁNDO se recalcula y puede sumarle encima saccades y
// apartar-la-mirada antes de que vrm.update() aplique el resultado a los
// huesos). Las saccades (rápidas, 20-40ms) y el apartar-la-mirada (más
// lento, con sostén) son DESVIACIONES sobre esa base, no un centro fijo —
// updateSaccades() sigue siendo el punto de entrada llamado desde animate().
let _saccadeYaw = 0, _saccadePitch = 0;                 // desvío actual (relativo a la base), no un ángulo absoluto
let _saccadeYawIni = 0, _saccadePitchIni = 0;           // punto de partida del salto en curso
let _saccadeYawObjetivo = 0, _saccadePitchObjetivo = 0; // punto de llegada del salto en curso
let _saccadeT = 1, _saccadeDur = 0.03;                  // progreso 0..1 del salto actual, y su duración
let _saccadeTimer = 0.5 + Math.random() * 1.5;

// Versión con retardo de la mirada final (base + saccade), para que la
// cabeza/cuello la sigan detrás de los ojos — ver "cabeza acompaña a la
// mirada" más abajo (usado en animate(), no acá).
let _cabezaMiradaYaw = 0, _cabezaMiradaPitch = 0;

let _miradaLogTimer = 2; // diagnóstico: cada cuántos segundos se loguea el yaw/pitch pedido

const _miradaCamPos = new THREE.Vector3(); // reusado cada frame, evita basura de GC

let _miradaFase = 'siguiendo';  // 'siguiendo' | 'apartando'
let _miradaTimer = CONFIG.mirada.apartarIntervaloMinS
                  + Math.random() * (CONFIG.mirada.apartarIntervaloMaxS - CONFIG.mirada.apartarIntervaloMinS);
let _miradaT = 0;
let _miradaOffsetYaw = 0, _miradaOffsetPitch = 0;

// Envolvente de "apartar la mirada": entra (fade), se sostiene plana, sale
// (fade) — no es un pulso simétrico tipo seno (necesita el sostén en el
// medio), así que se arma a mano con _fade() en los dos tramos.
function _envolventeApartar(p) {
  const M = CONFIG.mirada;
  const dur = M.apartarEntradaS + M.apartarSostenS + M.apartarSalidaS;
  const fEntrada = M.apartarEntradaS / dur, fSalida = M.apartarSalidaS / dur;
  if (p < fEntrada) return _fade(p / fEntrada);
  if (p > 1 - fSalida) return _fade((1 - p) / fSalida);
  return 1;
}

// Base de la mirada (antes de sumarle las saccades): sigue a la cámara con
// vrm.lookAt.lookAt(), salvo en 'thinking' (mismo punto fijo arriba-a-un-
// lado de siempre — Rem está pensando, no mirando al usuario, y las
// saccades de esa pose ya orbitaban ese punto). "Apartar la mirada" se
// superpone encima del seguimiento normal, nunca durante 'thinking' (que ya
// tiene su propio desvío). Devuelve {yaw, pitch} en grados.
function _miradaBase(dt) {
  const M = CONFIG.mirada;

  if (estadoCorporal() === 'thinking') return { yaw: -10, pitch: 8 };

  let yaw = 0, pitch = 0;
  if (vrm?.lookAt) {
    vrm.lookAt.lookAt(camera.getWorldPosition(_miradaCamPos));
    yaw   = vrm.lookAt.yaw   * M.intensidadSeguimiento;
    pitch = vrm.lookAt.pitch * M.intensidadSeguimiento;
  }
  // Modo escritorio: además hacia el cursor (avatar/escritorio_ui.js).
  if (ES_ESCRITORIO) {
    const c = miradaCursorEscritorio(dt);
    yaw += c.yaw;
    pitch += c.pitch;
  }

  _miradaTimer -= dt;
  if (_miradaFase === 'siguiendo' && _miradaTimer <= 0) {
    _miradaFase = 'apartando';
    _miradaT = 0;
    const angulo = Math.random() * Math.PI * 2; // dirección al azar, no siempre "hacia el mismo lado"
    _miradaOffsetYaw   = Math.cos(angulo) * M.apartarAmpYaw;
    _miradaOffsetPitch = Math.sin(angulo) * M.apartarAmpPitch;
    console.log(`[Mirada] apartando (yaw=${_miradaOffsetYaw.toFixed(1)}, pitch=${_miradaOffsetPitch.toFixed(1)})`);
  }
  if (_miradaFase === 'apartando') {
    const dur = M.apartarEntradaS + M.apartarSostenS + M.apartarSalidaS;
    _miradaT += dt;
    const p = Math.min(1, _miradaT / dur);
    const env = _envolventeApartar(p);
    yaw   += _miradaOffsetYaw   * env;
    pitch += _miradaOffsetPitch * env;
    if (p >= 1) {
      _miradaFase = 'siguiendo';
      _miradaTimer = M.apartarIntervaloMinS + Math.random() * (M.apartarIntervaloMaxS - M.apartarIntervaloMinS);
      console.log(`[Mirada] de vuelta a cámara, próximo apartado en ~${_miradaTimer.toFixed(1)}s`);
    }
  }

  return { yaw, pitch };
}

function updateSaccades(dt) {
  const { yaw: yawBase, pitch: pitchBase } = _miradaBase(dt);

  _saccadeTimer -= dt;
  if (_saccadeTimer <= 0) {
    _saccadeYawIni = _saccadeYaw;
    _saccadePitchIni = _saccadePitch;
    // Relativo a la base (ya no a un centro fijo): un salto pequeño desde
    // donde sea que esté mirando en este momento (cámara, o apartada).
    _saccadeYawObjetivo   = (Math.random() - 0.5) * 14;
    _saccadePitchObjetivo = (Math.random() - 0.5) * 8;
    _saccadeDur   = 0.02 + Math.random() * 0.02;  // 20-40ms, como pide la especificación
    _saccadeT     = 0;
    _saccadeTimer = 0.5 + Math.random() * 1.5;    // próxima saccade en 0,5-2s
  }
  if (_saccadeT < 1) {
    _saccadeT = Math.min(1, _saccadeT + dt / _saccadeDur);
    const u = _fade(_saccadeT); // mismo suavizado que el ruido — un salto, no un tirón lineal
    _saccadeYaw   = lerp(_saccadeYawIni,   _saccadeYawObjetivo,   u);
    _saccadePitch = lerp(_saccadePitchIni, _saccadePitchObjetivo, u);
  }

  // Se escribe SIEMPRE, no solo mientras hay un salto en curso: a diferencia
  // de la versión vieja (centro fijo, no hacía falta reescribir entre
  // saltos), la base ahora se mueve todo el tiempo (sigue a la cámara/la
  // cabeza) y hay que reaplicarla cada frame o los ojos se quedan pegados al
  // último valor hasta la próxima saccade.
  const yawFinal = yawBase + _saccadeYaw;
  const pitchFinal = pitchBase + _saccadePitch;
  if (vrm?.lookAt) {
    vrm.lookAt.yaw   = yawFinal;
    vrm.lookAt.pitch = pitchFinal;
  }

  // La cabeza (y el cuello, ver animate()) siguen una fracción de ESTA
  // MISMA mirada final (base de cámara + saccade + apartar, ya combinados
  // arriba) — pero con un retardo propio: un lerp más lento que la
  // respuesta instantánea de los ojos (que ya se escribieron sin demora,
  // arriba), así que la cabeza "llega después". CONFIG.mirada.cabezaVelocidad
  // más alto = menos retardo. Se actualiza siempre, incluso en 'thinking'
  // (donde yawFinal/pitchFinal son el punto fijo -10/8 más saccades) — es
  // animate() quien decide NO aplicar esta contribución en 'thinking',
  // porque ese estado ya tiene su propio desvío de cabeza fijo vía
  // updateLook() y sumar los dos duplicaría el giro.
  _cabezaMiradaYaw   = lerp(_cabezaMiradaYaw,   yawFinal,   dt * CONFIG.mirada.cabezaVelocidad);
  _cabezaMiradaPitch = lerp(_cabezaMiradaPitch, pitchFinal, dt * CONFIG.mirada.cabezaVelocidad);

  // Diagnóstico pedido explícitamente: el yaw/pitch que se le pide a los
  // ojos cada 2s, para poder ver a simple vista si se está saturando contra
  // el rango real del modelo (ver el log de rangos al cargar el VRM, más
  // arriba — con xRange=90/yRange=10 en las cuatro curvas, un pedido de
  // 20-30° ya se recorta a apenas 2-3° reales).
  _miradaLogTimer -= dt;
  if (_miradaLogTimer <= 0) {
    _miradaLogTimer = 2;
    console.log(`[Mirada] pedido yaw=${yawFinal.toFixed(1)}° pitch=${pitchFinal.toFixed(1)}°`);
  }
}

// ═══════════════════════════════════════════════════
// DEDOS — curvatura de reposo (30 huesos, 5 dedos × 3 falanges × 2 manos)
// ═══════════════════════════════════════════════════
// Sin esto las manos quedan completamente abiertas y rectas — una de las
// señales más claras de "muñeco" en un modelo por lo demás bien animado.
// Curvatura decreciente hacia la punta (proximal > intermedio > distal,
// ver CONFIG.dedos) + una única deriva de ruido muy lenta por mano (no una
// por dedo — con una alcanza para que no se vean congeladas, sin que cada
// dedo se mueva por su cuenta como una araña). Eje de curvado: rotation.z,
// con signo espejado entre manos (confirmado en vivo con captura de
// pantalla — si algún día el modelo cambia y las manos se ven mal, es acá
// donde revisar el signo).
const _DEDOS_NOMBRE = ['Index', 'Middle', 'Ring', 'Little'];
const _FALANGES = ['Proximal', 'Intermediate', 'Distal'];

function aplicarCurvaturaDedos(t) {
  const D = CONFIG.dedos;
  const curls = { Proximal: D.curlProximal, Intermediate: D.curlIntermedio, Distal: D.curlDistal };
  for (const lado of ['left', 'right']) {
    const signo = lado === 'left' ? -1 : 1;
    const deriva = ruido(lado === 'left' ? 900 : 901, D.derivaFreq, t) * D.derivaAmp;
    for (const dedo of _DEDOS_NOMBRE) {
      for (const falange of _FALANGES) {
        const bone = getB(`${lado}${dedo}${falange}`);
        if (bone) bone.rotation.z = signo * (curls[falange] + deriva);
      }
    }
    // Pulgar: se curva menos que el resto (curlPulgar < curlProximal) y se
    // opone — rotation.y extra, para que no quede en el mismo plano que
    // los demás dedos.
    const derivaPulgar = deriva * 0.6;
    for (const falange of _FALANGES) {
      const bone = getB(`${lado}Thumb${falange}`);
      if (bone) {
        bone.rotation.z = signo * (D.curlPulgar + derivaPulgar);
        bone.rotation.y = -signo * 0.25;
      }
    }
  }
}

// ═══════════════════════════════════════════════════
// POSE PROCEDURAL DE CUERPO — pose por estado (getStatePose) + springs
// ═══════════════════════════════════════════════════
// Antes vivía inline en animate(). Se extrajo a una función porque ahora es
// uno de los dos caminos de pose de cuerpo: se usa cuando NO hay clip VRMA
// activo, y como fuente de la mezcla durante un crossfade procedural<->clip
// (ver "ANIMACIÓN POR CLIPS VRMA" abajo). Lógica sin cambios respecto de
// cuando era inline. Escribe .rotation en los huesos normalizados.
// ── ESPEJO VRM 1.0 ────────────────────────────────────────────────────
// Todo lo procedural (poses, springs, dedos, traslado de peso, respiración y
// cabeza encima del clip) está escrito en la convención de ejes de VRM 0.x:
// ahí los huesos normalizados tienen X/Z al revés que en VRM 1.0 (el modelo
// mira a -Z). Pasar una rotación de una convención a la otra es conjugarla
// por un giro de 180° en Y, o sea negar x y z del cuaternión (lo mismo que
// clipDeVrma hace con las pistas de un VRMA). Se espeja ANTES de escribir
// (la pose actual pasa a convención 0.x, así los ejes que el código no toca
// quedan coherentes) y DESPUÉS (vuelta a 1.0). En VRM 0.x no hace nada.
const _HUESOS_PROC = [
  'hips', 'spine', 'chest', 'upperChest', 'neck', 'head',
  'leftShoulder', 'rightShoulder', 'leftUpperArm', 'rightUpperArm', 'leftLowerArm', 'rightLowerArm',
  ...['left', 'right'].flatMap(l => ['Thumb', 'Index', 'Middle', 'Ring', 'Little']
    .flatMap(d => ['Proximal', 'Intermediate', 'Distal'].map(f => `${l}${d}${f}`))),
];
let _nodosProc = [], _nodosProcGen = -1;
function _espejarHuesos() {
  if (!_esVRM1 || !vrm) return;
  if (_nodosProcGen !== _modeloGen) {
    _nodosProc = _HUESOS_PROC.map(getB).filter(Boolean);
    _nodosProcGen = _modeloGen;
  }
  for (const b of _nodosProc) { const q = b.quaternion; q.set(-q.x, q.y, -q.z, q.w); }
}

function aplicarCuerpoProcedural(t, dt) {
  _espejarHuesos();
  _aplicarCuerpoProcedural(t, dt);
  _espejarHuesos();
}

function _aplicarCuerpoProcedural(t, dt) {
  const pose = getStatePose(t);

  // Cabeza: pose base + drift de updateLook() + "sigue la mirada" (fracción
  // de hacia dónde miran los ojos — base de cámara + saccade + apartar, ya
  // con el retardo propio calculado en updateSaccades()) + spring. En
  // 'thinking' NO se suma la mirada acá: ese estado ya tiene su propio
  // desvío de cabeza fijo vía lookCur (arriba, en updateLook()) apuntando
  // al mismo punto que usa _miradaBase() para los ojos — sumar los dos
  // duplicaría el giro.
  const S_MIRADA = CONFIG.mirada;
  const cabezaSigueMirada = estadoCorporal() !== 'thinking';
  const miradaYawRad   = cabezaSigueMirada ? (_cabezaMiradaYaw   * Math.PI / 180) * S_MIRADA.cabezaFraccion : 0;
  const miradaPitchRad = cabezaSigueMirada ? (_cabezaMiradaPitch * Math.PI / 180) * S_MIRADA.cabezaFraccion : 0;

  const tHX = pose.hX - lookCur.y * 0.32 - miradaPitchRad;
  const tHY = pose.hY - lookCur.x * 0.26 + miradaYawRad;
  const tHZ = pose.hZ + lookCur.x * 0.48;

  // headB.rotation.{x,y,z} recibe el spring completo; neckB recibe una
  // fracción del MISMO spring ya resuelto (spr.hX.v/etc., más abajo) — así
  // el giro se reparte entre cabeza y cuello (no todo cargado en la
  // cabeza) automáticamente, para CUALQUIER fuente que alimente tHX/tHY/tHZ
  // (drift de reposo, mirada nueva, lo que sea) sin necesidad de un reparto
  // aparte por cada una.
  const headB = getB('head'), neckB = getB('neck');
  if (headB) {
    headB.rotation.x = spr.hX.step(tHX, dt);
    headB.rotation.y = spr.hY.step(tHY, dt);
    headB.rotation.z = spr.hZ.step(tHZ, dt);
  }
  if (neckB) {
    neckB.rotation.x = spr.hX.v * 0.38;
    neckB.rotation.y = spr.hY.v * 0.30;
    neckB.rotation.z = spr.hZ.v * 0.28;
  }

  // Cuerpo
  const spineB = getB('spine'), chestB = getB('upperChest') ?? getB('chest');
  const bZ = spr.bZ.step(pose.bZ, dt);
  const bX = spr.bX.step(pose.bX, dt);
  if (spineB) { spineB.rotation.z = bZ; spineB.rotation.x = bX; }

  // Traslado de peso PRIMERO: hombros y brazos lo necesitan para
  // acompañarlo (ver más abajo) — reemplaza el bob/rock que aportaba la
  // caminata eliminada, para que la cadera no se vea muerta estando quieta.
  const { rock: pesoRock } = updateTrasladoPeso(dt, t);

  // Respiración visible en pecho y hombros — mismo seno base (breath, ver
  // getStatePose). Los hombros también acompañan el traslado de peso: el
  // lado que "pesa más" baja un poco, como alguien real recargado de un
  // costado — no solo suben con la inhalación (Math.max(0,...), no bajan
  // de la base, para que se lea como elevación real y no una oscilación
  // simétrica).
  const respFase = Math.sin(t * 0.8);
  if (chestB) chestB.rotation.x = respFase * 0.018;
  const lShoulderB = getB('leftShoulder'), rShoulderB = getB('rightShoulder');
  if (lShoulderB) lShoulderB.rotation.z =  Math.max(0, respFase) * 0.013 - pesoRock * 0.4;
  if (rShoulderB) rShoulderB.rotation.z = -Math.max(0, respFase) * 0.013 - pesoRock * 0.4;

  // ── BRAZOS ACOPLADOS AL CUERPO ──────────────────────────────────────
  // No son ruido independiente: el target del upperArm suma una fracción
  // de spr.bX.v/spr.bZ.v (el TORSO ya resuelto por su propio spring, que
  // ya tiene su propio retardo) — así, cuando el cuerpo se inclina, el
  // brazo lo sigue con un retardo sobre otro retardo (el suyo propio, al
  // pasar de nuevo por spr.ruX/luX). Rangos en CONFIG.brazos.
  const S = CONFIG.brazos;
  const acopleCuerpo = spr.bX.v * S.acopleRespiracion + spr.bZ.v * S.acopleInclinacion;

  const rua = getB('rightUpperArm'), lua = getB('leftUpperArm');
  const rla = getB('rightLowerArm'), lla = getB('leftLowerArm');
  if (rua) {
    rua.rotation.z = spr.ruZ.step(pose.ruZ, dt);
    rua.rotation.x = spr.ruX.step(pose.ruX + acopleCuerpo, dt);
  }
  if (lua) {
    lua.rotation.z = spr.luZ.step(pose.luZ, dt);
    lua.rotation.x = spr.luX.step(pose.luX + acopleCuerpo, dt);
  }

  // Antebrazos: flexión base (nunca brazos rectos) + deriva de ruido, con
  // el mismo acoplamiento al cuerpo (a la mitad de fuerza que el upperArm).
  // pose.rlX/llX (solo 'thinking' los define, ver getStatePose) reemplazan
  // la base universal cuando el estado necesita algo distinto — la mano
  // hacia la cara, en ese caso.
  const codoR = pose.rlX ?? (S.codoFlexionBase + ruido(70, 0.09, t) * S.codoDerivaAmp);
  const codoL = pose.llX ?? (S.codoFlexionBase + ruido(72, 0.09, t) * S.codoDerivaAmp);
  if (rla) {
    rla.rotation.x = spr.rlX.step(codoR + acopleCuerpo * 0.5, dt);
    rla.rotation.z = -0.08 + ruido(71, 0.07, t) * 0.02;
  }
  if (lla) {
    lla.rotation.x = spr.llX.step(codoL + acopleCuerpo * 0.5, dt);
    lla.rotation.z =  0.08 + ruido(73, 0.07, t) * 0.02;
  }

  aplicarCurvaturaDedos(t);
}
