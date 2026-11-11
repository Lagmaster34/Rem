// avatar/overlay_ui.js — la caja de texto del escritorio FIJADO en la esquina
// (el antiguo modo overlay, fusionado con el de escritorio el 2026-11-10).
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// CAJA DE TEXTO (escritorio fijado) + indicador de estado
// ═══════════════════════════════════════════════════
// Mismo protocolo WS que el panel (chat_message -> chat_delta/chat_done). La
// respuesta se escucha (y se ve a Yoru hablar): aquí no hay burbujas de chat.
// La monta escritorio_ui.js y le pasa los mensajes del WS (onDone, onError,
// onPttEstado, onTranscripcion); se ve solo con <html class="fijado">.
//
// Ratón y teclado los decide escritorio.py: la caja entra en la región de clic
// junto al cuerpo (_actualizarRegion de escritorio_ui.js), y el teclado se toma
// solo con el puntero encima o escribiendo — la página avisa con
// {tipo:'teclado', encima, foco} por el WebSocket (no por messageHandlers de
// WebKit: con JSCValue en Python la app llegó a colgarse, ver escritorio.py).
function crearCajaTexto(aPython) {
  const raiz = document.createElement('div');
  raiz.id = 'ov-root';
  raiz.innerHTML = `
    <div id="ov-status"><span id="ov-status-txt"></span></div>
    <div id="ov-box" class="esc-ui"><input id="ov-input" type="text" placeholder="Escríbele a ${NOMBRE_PERSONAJE}…" autocomplete="off"></div>
  `;
  document.body.appendChild(raiz);

  const $status = raiz.querySelector('#ov-status');
  const $txt    = raiz.querySelector('#ov-status-txt');
  const $box    = raiz.querySelector('#ov-box');
  const $input  = raiz.querySelector('#ov-input');

  let esperandoRespuesta = false;   // hay un turno en curso (escrito o por voz)
  let mostrandoTranscripcion = false; // la caja enseña lo que entendió el STT (el turno ya arrancó)
  let pttEstado = 'idle';           // 'escuchando' | 'transcribiendo' | 'idle'
  const teclado = { encima: false, foco: false };

  // El teclado: a escritorio.py, que lo toma (ON_DEMAND) o lo suelta (NONE).
  function avisarTeclado(cambio) {
    Object.assign(teclado, cambio);
    console.log(`[Caja] teclado: encima=${teclado.encima} foco=${teclado.foco}`);
    aPython({ tipo: 'teclado', ...teclado });
  }
  $box.addEventListener('mouseenter', () => avisarTeclado({ encima: true }));
  $box.addEventListener('mouseleave', () => avisarTeclado({ encima: false }));
  $input.addEventListener('focus', () => avisarTeclado({ foco: true }));
  $input.addEventListener('blur',  () => avisarTeclado({ foco: false }));

  // ── indicador de estado: prioridad ptt > hablando > pensando (los avisos
  //    van a la burbuja de escritorio_ui.js) ──
  function refrescarEstado() {
    if (!FIJADO) return;
    let texto = '', clase = '';
    if (pttEstado === 'escuchando')            { texto = 'Escuchando…';    clase = 'escuchando'; }
    else if (pttEstado === 'transcribiendo')   { texto = 'Transcribiendo…'; clase = 'pensando'; }
    else if (_audioActivo || _audioPlaying || estado === 'talking') { texto = 'Hablando…'; clase = 'hablando'; }
    else if (esperandoRespuesta || estado === 'thinking')            { texto = 'Pensando…'; clase = 'pensando'; }
    if ($txt.textContent !== texto) $txt.textContent = texto;
    $status.className = (texto ? 'visible ' : '') + clase;
  }
  setInterval(refrescarEstado, 150);

  function actualizarCaja() {
    $input.readOnly = mostrandoTranscripcion;
    $input.placeholder = esperandoRespuesta ? `${NOMBRE_PERSONAJE} está respondiendo…` : `Escríbele a ${NOMBRE_PERSONAJE}…`;
  }

  function enviar() {
    const texto = $input.value.trim();
    if (!texto || esperandoRespuesta || mostrandoTranscripcion) return false;
    if (!_ws || _ws.readyState !== WebSocket.OPEN) return false;
    _ws.send(JSON.stringify({ tipo: 'chat_message', texto }));
    $input.value = '';
    esperandoRespuesta = true;
    actualizarCaja();
    refrescarEstado();
    return true;
  }

  $input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (enviar()) $input.blur(); }
    else if (e.key === 'Escape') { $input.value = ''; $input.blur(); }
  });

  console.log('[Caja] lista');
  return {
    elemento: $box,
    turnoTerminado() { esperandoRespuesta = false; actualizarCaja(); refrescarEstado(); },
    ptt(est) { pttEstado = (est === 'escuchando' || est === 'transcribiendo') ? est : 'idle'; refrescarEstado(); },
    // Lo entendido se enseña en la caja durante `ms` (el turno ya arrancó a la
    // vez); mientras, la caja no acepta Enter (duplicaría el envío).
    transcripcion(texto, ms) {
      $input.value = texto;
      $input.classList.add('transcrito');
      mostrandoTranscripcion = true;
      esperandoRespuesta = true;
      pttEstado = 'idle';
      actualizarCaja();
      setTimeout(() => {
        $input.value = '';
        $input.classList.remove('transcrito');
        mostrandoTranscripcion = false;
        actualizarCaja();
      }, ms);
    },
    // El puntero salió de la superficie (lo avisa escritorio.py, que ya soltó
    // el teclado): sin mouseleave en ese caso, el "encima" quedaría caducado y
    // se reenviaría con el próximo cambio de foco.
    punteroFuera() { teclado.encima = false; },
    // Al soltar el fijado: fuera el foco y el teclado.
    soltar() {
      if (document.activeElement === $input) $input.blur();
      if (teclado.encima || teclado.foco) avisarTeclado({ encima: false, foco: false });
    },
  };
}
// Ventana: el panel de chat de siempre. Escritorio: su interfaz (con esta caja)
// la monta avatar/escritorio_ui.js; el chat completo va en una ventana aparte.
if (!ES_ESCRITORIO) crearPanelChat();
