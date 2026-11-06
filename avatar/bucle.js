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
function animate() {
  requestAnimationFrame(animate);
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

  renderer.render(scene, camera);
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
