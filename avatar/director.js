// avatar/director.js — director de animación: ruleta de reposo, bailes, saludo, emoción, clip en espera.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// DIRECTOR DE ANIMACIÓN — qué hace el cuerpo (inspirado en Nerumi)
// ═══════════════════════════════════════════════════
// Prioridad, de arriba abajo, cada frame:
//   1. Clip manual o de emoción en curso: se respeta hasta que termine.
//   2. Modo baile (/bailar o 💃), salvo escuchando: bailes de una bolsa sin
//      repetición, encadenados; habla y piensa bailando (el lipsync va aparte).
//   3. Saludo pendiente (al abrir y al cambiar de modelo), en reposo y callada.
//   4. Gesto de reposo en curso: lo corta el audio o un estado que no sea idle.
//   5. Ruleta de reposo: cada 60–120 s un intento; si está ocupada pierde el
//      turno. Un idle VRMA: grupo raro 20 % / común 80 %, sin repetir el último.
// El cuerpo se mueve SOLO con clips: entre gestos, la pose base (catálogo ->
// poseBase, Respirar en bucle) — también hablando; thinking y listening
// tienen su propio clip (porEstado). Lo procedural queda como respaldo
// mientras carga el primer clip.
// Los números salen de catalogo.json -> ajustes (probRaro,
// probSuperRaro, intervaloReposo), pisables desde el panel.
let _modoBaile = (() => { try { return localStorage.getItem('rem_modo_baile') === '1'; } catch { return false; } })();
let _bailando = false;          // un baile del director controla el cuerpo
let _siguienteBaile = false;    // el baile actual terminó: sacar el siguiente
let _cargandoBaile = false;
let _ultimoBaile = null;
let _saludoPendiente = false;
let _emocion = null;            // {nombre, hasta: ms | null (= hasta que termine de hablar)}
let _caraGesto = null;          // {happy: 0.6, ...} del gesto de reposo en curso, o null

function _reiniciarDirector() {
  _gestoActivo = false;
  _bailando = _siguienteBaile = _cargandoBaile = false;
  _caraGesto = null;
  _clipEnEspera = null;
  _gestoTimer = _sortearIntervaloGesto();
}

function setModoBaile(on) {
  _modoBaile = !!on;
  try { localStorage.setItem('rem_modo_baile', _modoBaile ? '1' : '0'); } catch {}
  console.log(`[Baile] modo baile ${_modoBaile ? 'ON' : 'OFF'}`);
  window.__remChat?.onModoBaile?.(_modoBaile);
}
window.setModoBaile = setModoBaile;

// ── Bolsas de bailes (muestreo sin reemplazo, como drawFromShuffleBag) ────
// Cada baile sale UNA vez antes de que se repita cualquiera, y el último que
// sonó nunca abre la ronda siguiente. Dos bolsas: regular y súper raro (los
// "raro" de la categoría dance; un 3 % de las veces). Se guardan entre
// sesiones (localStorage). Lo desactivado o faltante se filtra al sacar.
const _bolsas = (() => {
  try { return JSON.parse(localStorage.getItem('rem_bolsas_baile')) ?? {}; } catch { return {}; }
})();
function _bailesDisponibles(superRaro) {
  if (!_catalogo) return [];
  return Object.entries(_catalogo.clips)
    .filter(([id, c]) => c.categoria === 'dance' && clipUsable(id) && clipActivo(id) && clipAptoFijo(id) && (c.raro === true) === superRaro)
    .map(([id]) => id);
}
function _barajar(a) {
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}
function _sacarDeBolsa(tipo, pool) {
  const ok = new Set(pool);
  let bolsa = (_bolsas[tipo] ?? []).filter(id => ok.has(id));
  if (!bolsa.length) {
    bolsa = _barajar([...pool]);
    // pop() saca del final: el último que sonó, si cae ahí, va al principio.
    if (bolsa.length > 1 && bolsa[bolsa.length - 1] === _ultimoBaile) [bolsa[0], bolsa[bolsa.length - 1]] = [bolsa[bolsa.length - 1], bolsa[0]];
  }
  const id = bolsa.pop() ?? null;
  _bolsas[tipo] = bolsa;
  try { localStorage.setItem('rem_bolsas_baile', JSON.stringify(_bolsas)); } catch {}
  return id;
}
function _elegirBaile() {
  const normales = _bailesDisponibles(false), raros = _bailesDisponibles(true);
  const pRaro = ajusteAnim('probSuperRaro', 0.03);
  if (raros.length && (Math.random() < pRaro || !normales.length)) return _sacarDeBolsa('superRaro', raros);
  if (normales.length) return _sacarDeBolsa('regular', normales);
  return null;
}

function _arrancarBaile() {
  const id = _elegirBaile();
  _siguienteBaile = false;
  if (!id) { _bailando = false; return; }
  _cargandoBaile = true;
  _gestoActivo = false;
  const tok = ++_tokenClip;
  obtenerClip(id).then(entry => {
    _cargandoBaile = false;
    if (tok !== _tokenClip || !_modoBaile) return;
    if (entry.error || !entry.clip) { _siguienteBaile = true; return; }   // probar con otro
    _ultimoBaile = id;
    _bailando = true;
    // Si el baile no arranca, se prueba otro (sin quedar "bailando" sin clip).
    if (!reproducirSeguro(entry, _opcionesGesto(id, entry, { esBaile: true }), 'baile')) _siguienteBaile = true;
  }).catch(e => {
    _cargandoBaile = false;
    console.error(`[Anim] baile: error en la carga de "${id}": ${e?.message ?? e}`);
    if (tok === _tokenClip) _siguienteBaile = true;
  });
}

// ── Ruleta de reposo: idle VRMA ────────────────────────────────────────────
// Candidatos: clips usables y activos fuera de 'dance' (esos son del modo
// baile), en su franja 'horas'. raro (catálogo) = grupo raro. Si el grupo
// sorteado está vacío se usa el otro (menos idles, no cero). Dentro, por peso
// de categoría × peso del clip, sin repetir el último.
function _elegirGesto(excluir) {
  if (!_catalogo) return null;
  const hora = new Date().getHours();
  const raros = [], comunes = [];
  for (const [id, c] of Object.entries(_catalogo.clips)) {
    if (c.categoria === 'dance' || !clipUsable(id) || !clipActivo(id) || !clipAptoFijo(id) || !(c.peso > 0)) continue;
    if (c.horas && !(hora >= c.horas[0] && hora < c.horas[1])) continue;
    (c.raro ? raros : comunes).push({ id, peso: c.peso * pesoCategoria(c.categoria) });
  }
  let pool = Math.random() < ajusteAnim('probRaro', 0.2) ? raros : comunes;
  if (!pool.length) pool = pool === raros ? comunes : raros;
  if (pool.length > 1) pool = pool.filter(x => x.id !== excluir);
  return _sorteoPonderado(pool)?.id ?? null;
}

function _dispararIdleVrma() {
  const g = _elegirGesto(_ultimoGestoDisparado);
  if (!g) return false;
  _gestoActivo = true;
  const tok = ++_tokenClip;
  obtenerClip(g).then(entry => {
    if (tok !== _tokenClip || estado !== 'idle' || _audioActivo || entry.error || !entry.clip) {
      _logGesto(`cancelado antes de reproducir "${g}"` + (entry.error ? ` (${entry.error.message})` : ''));
      if (tok === _tokenClip) _gestoActivo = false;
      return;
    }
    _ultimoGestoDisparado = g;
    const expr = infoClip(g)?.expresion;
    _caraGesto = expr ? { [expr]: CONFIG.expresiones.gestoPeso } : null;
    _logGesto(`idle VRMA "${g}"${infoClip(g)?.raro ? ' (raro)' : ''}`);
    reproducirSeguro(entry, _opcionesGesto(g, entry, { esGesto: true }), 'gesto');
  }).catch(errorDeCarga(tok, 'gesto'));
  return true;
}

// ── Saludo (al abrir y al cambiar de modelo) ──────────────────────────────
// Los clips con "saludo": true, uniforme y sin repetir el anterior, que se
// recuerda POR MODELO (como avatar-greetings.js de Nerumi).
function _dispararSaludo() {
  _saludoPendiente = false;
  if (!_catalogo) return;
  const clave = 'rem_ultimo_saludo:' + MODELO_ACTIVO;
  let anterior = null;
  try { anterior = localStorage.getItem(clave); } catch {}
  let ids = Object.entries(_catalogo.clips).filter(([id, c]) => c.saludo && clipUsable(id) && clipAptoFijo(id)).map(([id]) => id);
  if (ids.length > 1) ids = ids.filter(id => id !== anterior);
  if (!ids.length) return;
  const id = ids[Math.floor(Math.random() * ids.length)];
  try { localStorage.setItem(clave, id); } catch {}
  _gestoActivo = true;
  const tok = ++_tokenClip;
  obtenerClip(id).then(entry => {
    if (tok !== _tokenClip || estado !== 'idle' || _audioActivo || entry.error || !entry.clip) {
      _logGesto(`saludo "${id}" cancelado (${tok !== _tokenClip ? 'otro clip ganó mientras cargaba'
                : estado !== 'idle' ? `estado ${estado}` : _audioActivo ? 'está hablando'
                : `no carga: ${entry.error?.message ?? 'sin clip'}`})`);
      if (tok === _tokenClip) _gestoActivo = false;
      return;
    }
    _caraGesto = { happy: CONFIG.expresiones.gestoPeso };
    _logGesto(`saludo "${id}"`);
    reproducirSeguro(entry, { modo: 'unaVez', esGesto: true }, 'saludo');
  }).catch(errorDeCarga(tok, 'saludo'));
}

// ── Emoción del chat ──────────────────────────────────────────────────────
// Llega por WS ({tipo:'emocion'}) apenas el modelo abre la respuesta con su
// etiqueta (ver chat_sesion.py). Cara: la de la emoción mientras viva —
// surprised es breve (emocionBreveS); las demás duran hasta que termine de
// hablar + emocionTrasHablarS (en Nerumi, "hasta que se oculta la burbuja").
// Cuerpo: el clip de esa emoción (catálogo -> porEstado), si no está en
// enfriamiento, no está bailando y no gira el cuerpo mientras habla.
function recibirEmocion(nombre) {
  const breve = nombre === 'surprised';
  _emocion = { nombre, hasta: breve ? performance.now() + ajusteAnim('emocionBreveS', 5) * 1000 : null };
  console.log(`[Emoción] ${nombre}${breve ? ' (breve)' : ''}`);
  if (!_mixer || _bailando || hayClipManual()) return;
  const m = porEstadoEfectivo(nombre);
  const id = m ? _elegirClipDeEstado(nombre, m) : null;
  if (!id || (clipGiraCuerpo(id) && hayVozSonando())) return;
  const tok = ++_tokenClip;
  _gestoActivo = false;
  obtenerClip(id).then(entry => {
    if (tok !== _tokenClip || _bailando || entry.error || !entry.clip) return;
    _ultimoClipEstado.set(nombre, id);
    if (m.enfriamiento) _ultimoUsoClipEstado.set(id, performance.now());
    reproducirSeguro(entry, { modo: 'unaVez', esEmocion: true }, `emoción ${nombre}`);
  }).catch(errorDeCarga(tok, `emoción ${nombre}`));
}
window.recibirEmocion = recibirEmocion;

function _actualizarEmocion() {
  if (!_emocion) return;
  const ahora = performance.now();
  if (_emocion.hasta == null) {
    if (!hayVozSonando() && estado !== 'thinking') _emocion.hasta = ahora + ajusteAnim('emocionTrasHablarS', 4) * 1000;
  } else if (ahora > _emocion.hasta) {
    console.log(`[Emoción] ${_emocion.nombre} terminó`);
    _emocion = null;
  }
}

// Tiempo máximo de seguridad de un gesto: lo que dura su clip + este margen
// (o GESTO_MAX_S si no se sabe). Pasado eso, aunque algo lo pisara o se
// perdiera el evento de fin, se libera el control y se vuelve al reposo.
const GESTO_MARGEN_S = 8, GESTO_MAX_S = 30;
let _gestoDesde = 0;

function _vigilarGesto() {
  if (!_gestoActivo) { _gestoDesde = 0; return; }
  const ahora = performance.now();
  if (!_gestoDesde) { _gestoDesde = ahora; return; }
  const dur = _accionActual?.getClip?.()?.duration;
  const tope = Number.isFinite(dur) && _accionActual?._esGesto ? dur + GESTO_MARGEN_S : GESTO_MAX_S;
  if ((ahora - _gestoDesde) / 1000 > tope) {
    _gestoDesde = 0;
    ++_tokenClip;   // cualquier carga pendiente de ese gesto queda obsoleta
    abortarGesto(`seguía activo a los ${tope.toFixed(0)} s (tiempo máximo de seguridad)`);
  }
}

function updateDirector(dt) {
  _vigilarGesto();
  _actualizarEmocion();
  _gestoTimer -= dt;   // la ruleta corre siempre; ver paso 5

  // 1. Manual / emoción: se respetan.
  if (hayClipManual() || _accionActual?._esEmocion) return;

  // 2. Baile.
  const quiereBailar = _modoBaile && estado !== 'listening';
  if (quiereBailar) {
    if ((!_bailando || _siguienteBaile) && !_cargandoBaile) _arrancarBaile();
    return;
  }
  if (_bailando || _cargandoBaile) {
    _bailando = _siguienteBaile = _cargandoBaile = false;
    ++_tokenClip;
    volverABaseIdle(false);     // salida de un baile: a la pose base
    _gestoTimer = _sortearIntervaloGesto();
    return;
  }

  // 3. Saludo.
  if (_saludoPendiente && !_medirHuesosPendiente && vrm?.scene.visible && _catalogo
      && estado === 'idle' && !_audioActivo && !_gestoActivo) {
    _dispararSaludo();
    return;
  }

  // 4. Gesto de reposo en curso (VRMA o procedural).
  if (_gestoActivo) {
    if (estado !== 'idle' || _audioActivo) {
      _logGesto(`interrumpido (motivo: ${estado !== 'idle' ? `estado=${estado}` : 'audio'})`);
      volverABaseIdle(true);
      _gestoActivo = false;
      _caraGesto = null;
      _gestoTimer = _sortearIntervaloGesto();
    }
    return;
  }

  // 5. Ruleta.
  if (_gestoTimer > 0) return;
  _gestoTimer = _sortearIntervaloGesto();
  if (estado !== 'idle' || _audioActivo || porEstadoEfectivo(estado)) {
    _logGesto(`turno perdido (ocupada: ${estado !== 'idle' ? estado : 'audio'})`);
    return;
  }
  _dispararIdleVrma();
}


// Depuración: dispara un clip por nombre bajo demanda, como si fuera un gesto
// de reposo (unaVez + vuelta a la base con crossfade) — para grabar un clip
// concreto sin esperar al sorteo de updateGestos(). Acepta el id del catálogo
// o el nombre de archivo con o sin ".vrma" (resolverClip). Sirve cualquier clip
// del catálogo, activo o no. Llega por WebSocket ({tipo:'debug_clip', nombre:'VRMA_05'}, ver
// rem_avatar_server._ws_handler) o a mano desde la consola del inspector.
// Se comporta como cualquier gesto: si entra audio o cambia el estado, se
// interrumpe con crossfade (la voz manda).
window.dispararClipDebug = function (nombre) {
  const archivo = resolverClip(nombre);
  if (!archivo) { console.warn(`[Anim] debug_clip "${nombre}": no está en el catálogo — no se dispara`); return; }
  const tok = ++_tokenClip;
  _gestoActivo = true;   // ya acá, para que updateGestos() no sortee otro mientras carga
  obtenerClip(archivo).then(entry => {
    // Otro clip/estado ganó mientras cargaba. Se libera _gestoActivo igual que
    // hace updateGestos() en su misma rama: si el ganador es otro gesto, ya lo
    // puso en true por su cuenta; lo que NO puede pasar es que quede en true sin
    // dueño (un .vrma lento + un cambio de estado dejaría los gestos muertos).
    if (tok !== _tokenClip) { _gestoActivo = false; return; }
    if (entry.error || !entry.clip) {
      console.warn(`[Anim] debug_clip "${archivo}": no disponible — no se dispara`);
      _gestoActivo = false;
      return;
    }
    _gestoTimer = _sortearIntervaloGesto();
    console.log(`[Anim] debug_clip -> "${archivo}"`);
    reproducirSeguro(entry, _opcionesGesto(archivo, entry, { esManual: true }), 'clip manual');
  }).catch(errorDeCarga(tok, 'clip manual'));
};

// ── CLIP EN ESPERA (solo los de giraCuerpo) ──────────────────────────────
// Un clip que gira el cuerpo mientras Rem habla la saca de cámara a mitad de
// frase, así que no se dispara: queda acá y sale al vaciarse la cola de audio
// (_avanzarCola, más arriba). Solo se guarda UNO: un pedido nuevo reemplaza al
// anterior en vez de encolarse detrás.
//
// _gestoActivo NO se toca al encolar — se pone recién en dispararClipDebug, en
// el momento del disparo real. Un clip que queda en espera y nunca llega a
// dispararse (lo reemplaza otro, o la ventana se cierra) no deja nada colgado.
let _clipEnEspera = null;     // nombre de archivo, o null
let _clipEsperaTimer = null;  // setTimeout del rebote, o null

// Con voz por oraciones (ver SentenceSplitter en CLAUDE.md) la cola se vacía un
// instante ENTRE dos frases de la misma respuesta. Por eso no se dispara en el
// acto: se espera un poco y se vuelve a comprobar que no haya arrancado otro
// audio, para no soltar el giro en mitad de la respuesta.
const _ESPERA_TRAS_AUDIO_MS = 700;

function hayVozSonando() {
  return _audioActivo || _audioPlaying || _audioPlayQueue.length > 0 || estado === 'talking';
}

function ponerClipEnEspera(archivo) { _clipEnEspera = archivo; }

// Llamada desde _avanzarCola() cuando la cola de audio queda vacía.
function _intentarLanzarClipEnEspera() {
  if (!_clipEnEspera || _clipEsperaTimer !== null) return;
  _clipEsperaTimer = setTimeout(() => {
    _clipEsperaTimer = null;
    const archivo = _clipEnEspera;
    if (!archivo) return;                 // lo cancelaron mientras esperaba
    if (hayVozSonando()) return;          // llegó otra frase: sigue en espera
    _clipEnEspera = null;
    _gestoTimer = _sortearIntervaloGesto();
    window.dispararClipDebug(archivo);
    window.__remChat?.onClipLanzado?.(archivo);
  }, _ESPERA_TRAS_AUDIO_MS);
}

// Respiración encima del clip — aditiva (+=), suave. La respiración real es
// rítmica (seno limpio), no es lo que hacía ver a Rem como un robot. Se escala
// por k (= _clipPeso): cuando lo procedural domina la mezcla ya trae su propia
// respiración; cuando el clip domina, esta la reemplaza. Sin doble conteo en
// la transición.
function aplicarRespiracionEncima(t, k) {
  _espejarHuesos();
  _respiracionEncima(t, k);
  _espejarHuesos();
}
function _respiracionEncima(t, k) {
  const respFase = Math.sin(t * 0.8) * k;
  const chestB = getB('upperChest') ?? getB('chest');
  if (chestB) chestB.rotation.x += respFase * 0.018;
  const spineB = getB('spine');
  if (spineB) spineB.rotation.x += respFase * 0.009;
  const lS = getB('leftShoulder'), rS = getB('rightShoulder');
  if (lS) lS.rotation.z +=  Math.max(0, respFase) * 0.013;
  if (rS) rS.rotation.z += -Math.max(0, respFase) * 0.013;
}

// La cabeza sigue la mirada también durante un clip, pero más contenida (el
// clip ya posa la cabeza) — mitad de CONFIG.mirada.cabezaFraccion, y escalada
// por k (= _clipPeso) para no doblar el aporte procedural en la transición.
// _cabezaMirada* lo actualiza updateSaccades() cada frame, antes de esto.
function aplicarCabezaSigueMiradaEncima(k) {
  const f = CONFIG.mirada.cabezaFraccion * 0.5 * k;
  const headB = getB('head');
  if (!headB) return;
  _espejarHuesos();
  headB.rotation.y += (_cabezaMiradaYaw   * Math.PI / 180) * f;
  headB.rotation.x -= (_cabezaMiradaPitch * Math.PI / 180) * f;
  _espejarHuesos();
}

// Llamada desde animate() en lugar del bloque de pose de cuerpo. Decide entre
// procedural puro, clip puro, o la mezcla de los dos durante un crossfade.
function actualizarAnimacionClips(dt, t) {
  if (!_mixer) { _idleAmpMult = 1; aplicarCuerpoProcedural(t, dt); return; } // aún no cargó el VRM
  updateDirector(dt);

  // Salida NATURAL de un clip 'bucle' con tope (baile corto, duracionS): arranca
  // el fundido en los últimos fadeOut segundos del tope, no de golpe al llegar
  // a 0 — mismo criterio que el chequeo de abajo para clips 'unaVez'. Un baile
  // no se funde: al vencer el tope el director encadena el siguiente (puente).
  if (_clipTopeTimer != null) {
    _clipTopeTimer -= dt;
    if (_accionActual?._esBaile) {
      if (_clipTopeTimer <= 0) { _clipTopeTimer = null; _siguienteBaile = true; }
    } else if (_clipTopeTimer <= CONFIG.animaciones.fadeOut) { _clipTopeTimer = null; volverABaseIdle(false); }
  }

  // Salida NATURAL de un clip 'unaVez' (gesto, o surprised/happy): arranca el
  // fundido en los últimos fadeOut segundos de SU PROPIA duración —medida
  // contra el reloj interno del clip (accion.time), no contra el evento
  // 'finished' del mixer, que solo dispara recién al terminar del todo. Así
  // el peso ya está en (o cerca de) 0 cuando el clip realmente termina, en
  // vez de saltar del último frame a la pose procedural y ahí SÍ empezar a
  // desvanecer. Si ya se disparó un corte forzado este mismo frame (arriba,
  // en updateGestos), _clipPesoObjetivo ya es 0 y esto no hace nada.
  if (_accionActual && !_accionActual._esBaile && _accionActual.loop === THREE.LoopOnce && !_accionActual.paused && _clipPesoObjetivo === 1) {
    const dur = _accionActual.getClip().duration;
    const restante = isFinite(dur) ? (dur - _accionActual.time) / Math.abs(_accionActual.timeScale || 1) : Infinity;
    if (restante <= CONFIG.animaciones.fadeOut) {
      volverABaseIdle(false);
    }
  }

  // Rampa de _clipPeso (progreso LINEAL 0..1) con duración distinta según la
  // dirección: fadeIn al entrar, fadeOut/fadeOutInterrupcion al salir (el que
  // corresponda, fijado en volverAProcedural/volverABaseIdle). La curva de
  // easing se aplica solo al PESO DE MEZCLA (pesoBlend, más abajo) — los
  // umbrales de acá (0.001/0.999/0.5) siguen leyendo el progreso lineal.
  {
    const subiendo = _clipPesoObjetivo > _clipPeso;
    const dur = subiendo ? (_clipFadeEntradaS ?? CONFIG.animaciones.fadeIn) : (_clipFadeSalidaS ?? CONFIG.animaciones.fadeOut);
    _clipPeso += clamp(_clipPesoObjetivo - _clipPeso, -dt / dur, dt / dur);
  }
  const pesoBlend = easeInOutCubic(clamp(_clipPeso, 0, 1));

  const esIdleClip = _accionActual?._esIdle === true;
  // Ruido procedural amplificado solo mientras el clip de idle domina la mezcla.
  _idleAmpMult = (esIdleClip && _clipPeso > 0.5) ? (CONFIG.animaciones.idle.ampProcedural ?? 1) : 1;

  if (_clipPeso <= 0.001) {
    _clipPeso = 0;
    if (_accionActual || _accionAnterior) {
      const eraGesto = _accionActual?._esGesto === true;
      _mixer.stopAllAction();
      _accionActual = _accionAnterior = null;
      vrm.humanoid.resetNormalizedPose(); // huesos que el clip movió y el procedural no toca (piernas, hips.position)
      // El gesto se da por terminado recién ACÁ (peso realmente en 0), no en
      // 'finished' ni al disparar el fundido — ver _alTerminarClip/updateGestos.
      if (eraGesto && _gestoActivo) {
        _logGesto('fundido de salida completo — libre para el próximo');
        _gestoActivo = false;
        _gestoTimer = _sortearIntervaloGesto();
      }
      if (eraGesto) _caraGesto = null;
    }
    _puente = null;
    _qPrevValido = false;
    _clipFadeSalidaS = null;
    _idleAmpMult = 1;
    aplicarCuerpoProcedural(t, dt);
    return;
  }

  // Idle a pleno peso: mezcla ESPECIAL — del clip solo se toman los brazos
  // (hombro/upperArm/lowerArm/mano), el resto del cuerpo queda 100% procedural
  // (getStatePose('idle') ya con ampProcedural). Durante el crossfade
  // (mezclando) todavía se mezclan todos los huesos por _clipPeso.
  const idleBrazos = esIdleClip && _clipPeso >= 0.999 && CONFIG.animaciones.idle.soloBrazos;
  const mezclando  = _clipPeso < 0.999;

  if (mezclando || idleBrazos) {
    aplicarCuerpoProcedural(t, dt);                          // escribe .rotation (pose procedural)
    for (const h of _huesosNorm) h.q.copy(h.node.quaternion); // snapshot procedural
    if (_hipsNode) _hipsPosProc.copy(_hipsNode.position);
  }

  if (esIdleClip && poseBaseModo() === 'bucle') _actualizarVelIdle(dt);
  // A pleno peso, lo que hay ahora en los huesos es la pose visible del frame
  // anterior: se guarda por si este update da la vuelta a un bucle ('loop').
  _qPrevValido = !mezclando && !idleBrazos;
  if (_qPrevValido) for (const h of _huesosNorm) h.qPrev.copy(h.node.quaternion);
  _mixer.update(dt);                                          // el clip escribe .quaternion

  if (idleBrazos) {
    const m = CONFIG.animaciones.idle.mezclaBrazos ?? 0.8;
    for (const h of _huesosNorm) {
      if (_HUESOS_BRAZO_IDLE.has(h.nombre)) {
        _qClipTmp.copy(h.node.quaternion);
        h.node.quaternion.slerpQuaternions(h.q, _qClipTmp, m);
      } else {
        h.node.quaternion.copy(h.q);   // resto: 100% procedural
      }
    }
    if (_hipsNode) _hipsNode.position.copy(_hipsPosProc);
    _aplicarPuente(dt);
    // aplicarCuerpoProcedural ya puso respiración/mirada para todo el cuerpo;
    // NO se suman de nuevo (sería doble). La mínima pérdida de respiración en
    // hombros (mezclados 0.8 al clip) no se nota.
    return;
  }

  if (mezclando) {
    for (const h of _huesosNorm) {
      _qClipTmp.copy(h.node.quaternion);
      h.node.quaternion.slerpQuaternions(h.q, _qClipTmp, pesoBlend);
    }
    if (_hipsNode) {
      _vClipTmp.copy(_hipsNode.position);
      _hipsNode.position.lerpVectors(_hipsPosProc, _vClipTmp, pesoBlend);
    }
  }

  _aplicarPuente(dt);
  // Sin respiración por código encima: los clips ya respiran. Solo la cabeza
  // acompaña un poco a la mirada (los ojos siguen a la cámara).
  if (estado !== 'thinking') aplicarCabezaSigueMiradaEncima(pesoBlend);
}
