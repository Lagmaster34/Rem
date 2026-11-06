// avatar/chat_local.js — anfitrión del panel de chat cuando el panel vive en la
// MISMA página que el avatar (modo ventana), y el disparo manual de clips, que
// usan también la ventana de chat aparte del modo escritorio (vía cmd_avatar,
// ver escritorio_ui.js). Script clásico: comparte el ámbito global con el resto
// de avatar/ (ver avatar/README.md).
"use strict";

// Dispara un clip a mano. Regla: los que giran el cuerpo (giraCuerpo, ver
// catalogo.json, medido) sacan al avatar de cámara, así que mientras haya voz
// sonando NO se disparan — quedan en espera y salen al vaciarse la cola de
// audio. Los demás salen al momento, aunque esté hablando.
// `avisar(texto)`: dónde contarlo (burbuja de sistema del chat que lo pidió).
function dispararClipManual(archivo, avisar) {
  const etiqueta = etiquetaClip(archivo);
  if (clipGiraCuerpo(archivo) && hayVozSonando()) {
    ponerClipEnEspera(archivo);   // reemplaza al anterior; solo se guarda uno
    avisar(`⏳ ${etiqueta} — en espera: gira el cuerpo y ${NOMBRE_PERSONAJE} está hablando`);
    return;
  }
  // El disparo manual corre el temporizador de gestos espontáneos, para que
  // no se encadene uno automático encima del que se acaba de pedir.
  _gestoTimer = _sortearIntervaloGesto();
  window.dispararClipDebug(archivo);   // MISMA función que el handler WS debug_clip
  avisar(`▶ ${etiqueta}`);
}

function _wsAbierto() { return !!_ws && _ws.readyState === WebSocket.OPEN; }

// Anfitrión de crearPanelChat() (ver la cabecera de panel_chat.js).
function anfitrionChat() {
  return {
    enviar(obj) {
      if (!_wsAbierto()) return false;
      _ws.send(JSON.stringify(obj));
      return true;
    },
    modelos: () => _modelosLista,
    modeloActivo: () => MODELO_ACTIVO,
    pedirModelos() { if (_wsAbierto()) _ws.send(JSON.stringify({ tipo: 'modelos_get' })); },
    baile: () => _modoBaile,
    setBaile: on => setModoBaile(on),
    clips: () => clipsDisponibles(),
    dispararClip: id => dispararClipManual(id, t => window.__remChat?.onSistema?.(t)),
  };
}
