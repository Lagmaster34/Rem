// avatar/bucle.js — bucle principal animate() y resize.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// LOOP PRINCIPAL
// ═══════════════════════════════════════════════════
// El cuerpo del frame va en un try/catch: un error se registra con su pila
// (como mucho uno por segundo, para no inundar el log) y el bucle sigue. La
// cadena de requestAnimationFrame no depende de esto (es la primera línea).
// Latido "[Bucle] vivo" cada 10 s con los frames dibujados: si deja de salir
// en el log, la página dejó de recibir frames (ver el latido de Python, que
// dice si el que se colgó fue el proceso de la interfaz).
const _bucleDiag = { frames: 0, errores: 0, seguidos: 0, ultimoError: 0, latido: performance.now(),
                     ultimoFrame: performance.now(), sinFramesAvisado: false };
const ERRORES_SEGUIDOS_MAX = 30;   // ~0,5 s fallando en cada frame: se descarta la animación
function animate() {
  requestAnimationFrame(animate);
  _bucleDiag.frames++;
  _bucleDiag.ultimoFrame = performance.now();
  try {
    _frame();
    _bucleDiag.seguidos = 0;
  } catch (e) {
    _bucleDiag.errores++;
    _bucleDiag.seguidos++;
    if (_bucleDiag.ultimoFrame - _bucleDiag.ultimoError > 1000) {
      _bucleDiag.ultimoError = _bucleDiag.ultimoFrame;
      console.error(`[Bucle] error en el frame (${_bucleDiag.errores} en total): ${e?.message ?? e}\n${e?.stack ?? ''}`);
    }
    if (_bucleDiag.seguidos === ERRORES_SEGUIDOS_MAX) _descartarAnimacion();
  }
  if (_bucleDiag.ultimoFrame - _bucleDiag.latido >= 10000) {
    const s = (_bucleDiag.ultimoFrame - _bucleDiag.latido) / 1000;
    console.log(`[Bucle] vivo: ${(_bucleDiag.frames / s).toFixed(1)} fps, ${_bucleDiag.errores} errores, `
              + `clip ${_accionActual?._clip?.name ?? _accionActual?.getClip?.().name ?? 'ninguno'} (peso ${(_clipPeso ?? 0).toFixed(2)})`);
    _bucleDiag.frames = 0;
    _bucleDiag.latido = _bucleDiag.ultimoFrame;
    _ws?.readyState === WebSocket.OPEN && _ws.send(JSON.stringify({ tipo: 'latido_pagina' }));
  }
}

// El mismo fallo en cada frame (p. ej. un clip que rompe la mezcla): se para
// el mixer, se suelta el gesto y el cuerpo vuelve a lo procedural, que no
// depende de ningún clip.
function _descartarAnimacion() {
  console.error(`[Bucle] ${ERRORES_SEGUIDOS_MAX} frames seguidos con error: se descarta la animación `
              + `"${_accionActual?.getClip?.()?.name ?? '?'}" y se vuelve al reposo procedural`);
  try {
    ++_tokenClip;
    _mixer?.stopAllAction();
    _accionActual = _accionAnterior = null;
    _clipPeso = _clipPesoObjetivo = 0;
    _puente = null;
    _gestoActivo = _bailando = _siguienteBaile = false;
    _caraGesto = null;
    vrm?.humanoid?.resetNormalizedPose();
  } catch (e) {
    console.error(`[Bucle] no se pudo descartar la animación: ${e?.message ?? e}`);
  }
}

// Errores fuera del bucle (callbacks, promesas sin catch): al log, con su pila.
window.addEventListener('error', e => console.error(`[Página] error: ${e.message} (${e.filename}:${e.lineno})\n${e.error?.stack ?? ''}`));
window.addEventListener('unhandledrejection', e => console.error(`[Página] promesa rechazada sin catch: ${e.reason?.message ?? e.reason}\n${e.reason?.stack ?? ''}`));

// Las otras dos hipótesis de un congelamiento: el contexto WebGL perdido y la
// página oculta o sin frames (el compositor deja de mandar frame callbacks).
renderer.domElement.addEventListener('webglcontextlost', e => {
  e.preventDefault();   // permite que se restaure
  console.error('[Bucle] webglcontextlost: el contexto WebGL se perdió');
});
renderer.domElement.addEventListener('webglcontextrestored', () => console.warn('[Bucle] webglcontextrestored'));
document.addEventListener('visibilitychange', () => console.warn(`[Bucle] visibilidad: ${document.visibilityState}`));
// Un temporizador NO depende de los frames: si salta y el último frame es de
// hace más de 3 s, la página está viva pero no recibe frames (hipótesis b).
// En el modo escritorio además se le avisa a Python (una vez por episodio),
// que intenta desatascar la superficie forzando un redibujado (escritorio.py).
setInterval(() => {
  const hace = performance.now() - _bucleDiag.ultimoFrame;
  if (hace > 3000) {
    console.warn(`[Bucle] sin frames desde hace ${(hace / 1000).toFixed(1)} s (la página sí está viva: lo dice este temporizador)`);
    if (!_bucleDiag.sinFramesAvisado && !_renderPausado && _ws?.readyState === WebSocket.OPEN) {
      _bucleDiag.sinFramesAvisado = true;
      _ws.send(JSON.stringify({ tipo: 'escritorio', datos: { tipo: 'sin_frames', s: Math.round(hace / 1000) } }));
    }
  } else if (_bucleDiag.sinFramesAvisado) {
    _bucleDiag.sinFramesAvisado = false;
    console.warn('[Bucle] vuelven a llegar frames');
  }
}, 3000);

function _frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  if (_modeloCambioPendiente && !hayVozSonando()) cambiarModelo(_modeloCambioPendiente);
  if (!vrm) { renderer.render(scene, camera); return; }

  const t = clock.getElapsedTime();

  // Detectar cambio de estado
  if (estado !== prevEstado) {
    if (estado === 'surprised') surprisedSnap = 1.0;
    applySpringConfig();
    sincronizarClipConEstado(); // mapea estado -> clip VRMA (o crossfade a procedural)
    prevEstado = estado;
    // Segunda salida para el clip en espera, además de _avanzarCola(): con la
    // voz del panel apagada NO hay audio, pero el backend igual manda
    // estado='talking' con el primer delta — sin esto, un clip encolado por
    // "está hablando" se quedaba encolado para siempre, porque _avanzarCola()
    // nunca llega a correr. _intentarLanzarClipEnEspera() revalida que no haya
    // voz sonando antes de soltarlo, así que llamarlo de más es inofensivo.
    if (estado !== 'talking') _intentarLanzarClipEnEspera();
  }

  // Decaer snap de sorpresa
  if (surprisedSnap > 0) surprisedSnap = Math.max(0, surprisedSnap - dt * 1.8);

  // ── Sistemas de expresión / parpadeo / mirada / saccades ──
  updateExpressions(dt);
  updateBlink(dt);
  aplicarVisemesPreUpdate(); // vía fallback: expressionManager necesita el valor ANTES de vrm.update()
  updateLook(dt, t);
  updateSaccades(dt);
  // _jawApertura es del frame anterior acá (se recalcula al final de este
  // mismo animate(), en aplicarVisemesPostUpdate) — un frame de atraso es
  // imperceptible para algo tan lento como _hablaEnergia.
  actualizarHablaEnergia(dt);

  // ── Pose de cuerpo: clip VRMA, procedural, o mezcla de los dos ──
  // Reemplaza el bloque de pose procedural inline + el giro de bailarina a
  // mano. Ver "ANIMACIÓN POR CLIPS VRMA" más arriba: cuando hay un clip
  // activo lo aplica el mixer y la respiración/mirada van encima; si no,
  // corre aplicarCuerpoProcedural() tal cual antes.
  actualizarAnimacionClips(dt, t);

  // Escritorio: inclinación al arrastrar (antes de vrm.update, así el pelo y
  // la falda reaccionan al vaivén), región de clic y botones/burbuja.
  if (ES_ESCRITORIO) actualizarEscritorio(dt);

  vrm.update(dt); // spring bones + morphs internos del VRM — después de posar los huesos

  // Remedir con huesos ahora que el modelo ya se posó al menos un frame
  // (no en el mismo frame de la carga, donde el esqueleto podía no reflejar
  // la pose real todavía).
  if (_medirHuesosPendiente) {
    _medirHuesosPendiente = false;
    vrm.scene.updateMatrixWorld(true); // asegurar matrices de mundo frescas para getWorldPosition
    const medida = ES_OVERLAY ? medirMedioCuerpo() : medirAlturaHuesos();
    if (medida) {
      console.log(`[Encuadre] altura Box3=${_modeloAlturaBox3.toFixed(3)}u  `
                + `altura ${ES_OVERLAY ? 'medio cuerpo' : 'huesos'}=${medida.altura.toFixed(3)}u`);
      _modeloAlturaLocal = medida.altura;
      _modeloCentroLocal = medida.centro;
      _modeloAnchoLocal = medida.ancho ?? 0;
      recalcularEncuadre(); // vuelve a fijar z/position.y — su propio log muestra el z resultante
    }
    // Overlay: recién ahora, con la pose de reposo aplicada y el encuadre
    // definitivo, se muestra el modelo (nace oculto, ver la carga del VRM).
    vrm.scene.visible = true;
  }

  // Visemes (vía vrc.*) + jaw: DESPUÉS de vrm.update(), porque expressionManager
  // escribe cero en SUS morphs en cada update() y borraría lo que hubiéramos
  // puesto ahí (por eso la vía de fallback se aplica ANTES, ver aplicarVisemesPreUpdate).
  aplicarVisemesPostUpdate(dt);

  if (!_renderPausado) renderer.render(scene, camera);
}
animate();

// ═══════════════════════════════════════════════════
// RESIZE
// ═══════════════════════════════════════════════════
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  aplicarTamanoRender();
  // anchorX/anchorY son fracciones normalizadas — se preservan solas. Solo hay
  // que recalcular a qué coordenada de mundo corresponden con el nuevo aspect
  // (y reposicionar el suelo synthwave si está activo).
  recalcularEncuadre();
});
