// avatar/overlay_ui.js — caja de texto e indicador del modo overlay.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// UI DEL MODO OVERLAY — solo una caja de texto abajo + indicador de estado
// ═══════════════════════════════════════════════════
// Mismo protocolo WS que el panel (chat_message -> chat_delta/chat_done), y la
// misma interfaz window.__remChat que lee _ws.onmessage. La respuesta se
// escucha (y se ve a Rem hablar): acá no hay burbujas ni historial visible.
//
// La caja es LO ÚNICO que recibe el ratón. El compositor decide con la input
// region de la layer surface (la fija rem_chat.py con input_shape_combine_region),
// no con CSS — así que la página le manda a GTK el rectángulo real de la caja
// (mensaje "rem" del WebKit script message handler) al cargar y en cada cambio
// de tamaño, en vez de que Python adivine su posición.
function crearOverlayUI() {
  const raiz = document.createElement('div');
  raiz.id = 'ov-root';
  raiz.innerHTML = `
    <div id="ov-status"><span id="ov-status-txt"></span></div>
    <div id="ov-box"><input id="ov-input" type="text" placeholder="Escríbele a ${NOMBRE_PERSONAJE}…" autocomplete="off"></div>
  `;
  document.body.appendChild(raiz);

  const $status = raiz.querySelector('#ov-status');
  const $txt    = raiz.querySelector('#ov-status-txt');
  const $box    = raiz.querySelector('#ov-box');
  const $input  = raiz.querySelector('#ov-input');

  let esperandoRespuesta = false;   // hay un turno en curso (escrito o por voz)
  let mostrandoTranscripcion = false; // la caja enseña lo que entendió el STT (el turno ya arrancó)
  let pttEstado = 'idle';           // 'escuchando' | 'transcribiendo' | 'idle'
  let avisoTemporal = null;         // {texto, hasta} — errores/notas breves

  // ── región interactiva → GTK ──
  function reportarRegion() {
    const r = $box.getBoundingClientRect();
    const msg = { tipo: 'region', x: Math.floor(r.left), y: Math.floor(r.top),
                  w: Math.ceil(r.width), h: Math.ceil(r.height) };
    console.log(`[Overlay] región interactiva: ${JSON.stringify(msg)}`);
    try { window.webkit.messageHandlers.rem.postMessage(JSON.stringify(msg)); }
    catch (e) { console.warn('[Overlay] no hay message handler "rem" (¿abierto fuera de rem_chat.py?):', e.message); }
  }
  // Diagnóstico permanente (barato: solo transiciones): confirma en rem_chat.log
  // que el compositor entrega el puntero y el foco de teclado SOLO a la caja.
  // El body es pointer-events:none, así que solo la caja puede disparar esto.
  $box.addEventListener('mouseenter', () => console.log('[Overlay] ratón ENTRA en la caja'));
  $box.addEventListener('mouseleave', () => console.log('[Overlay] ratón SALE de la caja'));
  $box.addEventListener('mousedown', () => console.log('[Overlay] clic en la caja'));
  window.addEventListener('focus', () => console.log('[Overlay] foco de teclado: la superficie lo RECIBE'));
  window.addEventListener('blur',  () => console.log('[Overlay] foco de teclado: la superficie lo PIERDE'));
  // El foco de la caja de texto se le avisa a GTK: mientras se escribe la
  // superficie conserva el teclado aunque el puntero se aleje; al soltarlo
  // (Enter/Escape/clic fuera) GTK lo devuelve al escritorio (ver
  // _EntradaOverlay en rem_chat.py).
  const avisarFoco = caja => {
    try { window.webkit.messageHandlers.rem.postMessage(JSON.stringify({ tipo: 'foco', caja })); } catch (e) {}
  };
  $input.addEventListener('focus', () => { console.log('[Overlay] la caja de texto tiene el foco'); avisarFoco(true); });
  $input.addEventListener('blur',  () => { console.log('[Overlay] la caja de texto pierde el foco'); avisarFoco(false); });
  new ResizeObserver(reportarRegion).observe($box);
  window.addEventListener('resize', reportarRegion);
  reportarRegion();

  // ── indicador de estado: prioridad ptt > aviso > hablando > pensando ──
  function refrescarEstado() {
    let texto = '', clase = '';
    if (pttEstado === 'escuchando')            { texto = 'Escuchando…';    clase = 'escuchando'; }
    else if (pttEstado === 'transcribiendo')   { texto = 'Transcribiendo…'; clase = 'pensando'; }
    else if (avisoTemporal && performance.now() < avisoTemporal.hasta) { texto = avisoTemporal.texto; clase = ''; }
    else if (_audioActivo || _audioPlaying || estado === 'talking') { texto = 'Hablando…'; clase = 'hablando'; }
    else if (esperandoRespuesta || estado === 'thinking')            { texto = 'Pensando…'; clase = 'pensando'; }
    if ($txt.textContent !== texto) { $txt.textContent = texto; console.log(`[Overlay] indicador: ${texto || '(vacío)'}`); }
    $status.className = (texto ? 'visible ' : '') + clase;
  }
  setInterval(refrescarEstado, 150);

  function avisar(texto, ms = 3500) {
    avisoTemporal = { texto, hasta: performance.now() + ms };
    refrescarEstado();
  }

  function actualizarCaja() {
    $input.readOnly = mostrandoTranscripcion;
    $input.placeholder = esperandoRespuesta ? `${NOMBRE_PERSONAJE} está respondiendo…` : `Escríbele a ${NOMBRE_PERSONAJE}…`;
  }

  function enviar() {
    const texto = $input.value.trim();
    if (!texto || esperandoRespuesta || mostrandoTranscripcion) return;
    if (!_ws || _ws.readyState !== WebSocket.OPEN) { avisar('Sin conexión con Rem — reintentando…'); return; }
    _ws.send(JSON.stringify({ tipo: 'chat_message', texto }));
    $input.value = '';
    esperandoRespuesta = true;
    actualizarCaja();
    refrescarEstado();
  }

  $input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); const habia = $input.value.trim(); enviar(); if (habia) $input.blur(); }
    else if (e.key === 'Escape') { $input.value = ''; $input.blur(); }
  });

  window.__remChat = {
    onDelta() {},   // sin burbujas: el avatar habla (y `estado` ya pasa a 'talking')
    onDone() { esperandoRespuesta = false; actualizarCaja(); refrescarEstado(); },
    onError(mensaje) { esperandoRespuesta = false; actualizarCaja(); avisar(`⚠ ${mensaje}`, 5000); },
    onModoActual() {},          // el selector IA/Eco es del panel de la ventana
    onClipLanzado() {},
    onPttEstado(est, detalle) {
      pttEstado = (est === 'escuchando' || est === 'transcribiendo') ? est : 'idle';
      if (est === 'ignorado') avisar(`🎙 ${detalle}`);
      else if (est === 'idle' && detalle) avisar(`🎙 ${detalle}`);
      refrescarEstado();
    },
    onMicVeredicto(veredicto, mensaje) { if (veredicto !== 'enviar') avisar(mensaje, 4500); },
    onConversacion(activa) { if (activa) avisar('🎙 Te vuelvo a escuchar al terminar', 3000); },
    // Lo entendido se enseña en la caja durante `ms` (el turno ya arrancó a la
    // vez); mientras, la caja no acepta Enter (duplicaría el envío).
    onTranscripcion(texto, ms) {
      console.log(`[Overlay] transcripción en la caja: "${texto}" (se enseña ${ms}ms)`);
      $input.value = texto;
      $input.classList.add('transcrito');
      mostrandoTranscripcion = true;
      esperandoRespuesta = true;
      pttEstado = 'idle';   // ya transcribió: el indicador pasa a "Pensando…" mientras se enseña el texto
      actualizarCaja();
      setTimeout(() => {
        $input.value = '';
        $input.classList.remove('transcrito');
        mostrandoTranscripcion = false;
        actualizarCaja();
      }, ms);
    },
  };
  console.log('[Overlay] UI lista');
}
// Escritorio: su interfaz la monta avatar/escritorio_ui.js (el chat va aparte).
if (ES_OVERLAY) crearOverlayUI(); else if (!ES_ESCRITORIO) crearPanelChat();
