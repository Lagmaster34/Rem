// avatar/chat_remoto.js — la ventana de chat aparte del modo escritorio
// (rem_chat_ventana.html): su propio WebSocket (rol "chat") y el anfitrión de
// crearPanelChat() (ver panel_chat.js). Lo que vive en la página del avatar
// (clips, modo baile, modelo cargado) se pide y se recibe por el servidor:
//   chat -> {tipo:'al_avatar', cmd:{que:'estado_get'|'baile'|'clip', ...}}
//   avatar -> {tipo:'info_avatar', que:'estado'|'sistema'|'modelo_cargado'|'baile'|'clip_lanzado', ...}
// Script clásico, sin three.js: esta página no dibuja nada en 3D.
"use strict";

const NOMBRE_PERSONAJE = new URLSearchParams(location.search).get('personaje') || 'Yoru';
document.title = `${NOMBRE_PERSONAJE} — chat`;

const _remoto = {
  ws: null,
  modelos: [],
  modeloActivo: null,
  baile: false,
  clips: [],
  reintento: 1000,
};

function _remotoEnviar(obj) {
  if (!_remoto.ws || _remoto.ws.readyState !== WebSocket.OPEN) return false;
  _remoto.ws.send(JSON.stringify(obj));
  return true;
}

function _alAvatar(cmd) { return _remotoEnviar({ tipo: 'al_avatar', cmd }); }

function anfitrionChat() {
  return {
    enviar: _remotoEnviar,
    modelos: () => _remoto.modelos,
    modeloActivo: () => _remoto.modeloActivo,
    pedirModelos() { _remotoEnviar({ tipo: 'modelos_get' }); },
    baile: () => _remoto.baile,
    setBaile(on) { if (!_alAvatar({ que: 'baile', activo: !!on })) window.__remChat?.onSistema?.('Sin conexión con el servidor.'); },
    clips: () => _remoto.clips,
    dispararClip(id) { if (!_alAvatar({ que: 'clip', nombre: id })) window.__remChat?.onSistema?.('Sin conexión con el servidor.'); },
  };
}

function _conectarChat() {
  const ws = new WebSocket('ws://localhost:18766');
  _remoto.ws = ws;
  const $estado = document.getElementById('chat-conexion');
  ws.onopen = () => {
    _remoto.reintento = 1000;
    if ($estado) $estado.hidden = true;
    ws.send(JSON.stringify({ tipo: 'hola', rol: 'chat' }));
    ws.send(JSON.stringify({ tipo: 'prefs_get' }));
    ws.send(JSON.stringify({ tipo: 'modelos_get' }));
    _alAvatar({ que: 'estado_get' });
  };
  ws.onmessage = e => {
    let d;
    try { d = JSON.parse(e.data); } catch { return; }
    const chat = window.__remChat;
    if (!chat) return;
    switch (d.tipo) {
      case 'chat_delta': chat.onDelta(d.texto ?? ''); break;
      case 'chat_done': chat.onDone(); break;
      case 'modo_actual': chat.onModoActual(d.modo); break;
      case 'voz_actual': chat.onVozActual?.(d.activa); break;
      case 'error': chat.onError(d.mensaje ?? 'error desconocido'); break;
      case 'ptt_estado': chat.onPttEstado?.(d.estado, d.motivo || d.nota || ''); break;
      case 'mic_veredicto': chat.onMicVeredicto?.(String(d.veredicto ?? ''), String(d.mensaje ?? '')); break;
      case 'conversacion': chat.onConversacion?.(!!d.activa, String(d.motivo ?? '')); break;
      case 'ptt_transcripcion': chat.onTranscripcion?.(String(d.texto ?? ''), d.ms ?? 1000); break;
      case 'accion_confirmar': chat.onAccionConfirmar?.(String(d.nombre ?? ''), String(d.descripcion ?? '')); break;
      case 'modelos_lista':
        _remoto.modelos = Array.isArray(d.modelos) ? d.modelos.filter(m => !m.error) : [];
        chat.onModelos?.();
        break;
      case 'prefs_estado':
        if (d.prefs?.modelo?.vrm) _remoto.modeloActivo = d.prefs.modelo.vrm;
        if (d.prefs?.apariencia?.tema) document.documentElement.dataset.tema = d.prefs.apariencia.tema;
        break;
      case 'prefs_actualizadas':
        if (d.seccion === 'modelo' && d.prefs?.vrm) _remoto.modeloActivo = d.prefs.vrm;
        if (d.seccion === 'apariencia' && d.prefs?.tema) document.documentElement.dataset.tema = d.prefs.tema;
        break;
      case 'prefs_error':
        if (d.seccion === 'modelo') chat.onSistema?.(`⚠ ${d.mensaje}`);
        break;
      case 'info_avatar':
        if (d.que === 'estado') {
          _remoto.baile = !!d.baile;
          _remoto.clips = Array.isArray(d.clips) ? d.clips : [];
          if (d.modelo) _remoto.modeloActivo = d.modelo;
          chat.onModoBaile?.(_remoto.baile);
        } else if (d.que === 'baile') {
          _remoto.baile = !!d.activo;
          chat.onModoBaile?.(_remoto.baile);
        } else if (d.que === 'sistema') {
          chat.onSistema?.(String(d.texto ?? ''));
        } else if (d.que === 'clip_lanzado') {
          chat.onClipLanzado?.(d.archivo, d.etiqueta);
        } else if (d.que === 'modelo_cargado') {
          _remoto.modeloActivo = d.ruta;
          chat.onModeloCargado?.(d.ruta, d.titulo, d.autor);
          _alAvatar({ que: 'estado_get' });   // el catálogo de clips no cambia, pero sí lo que carga
        }
        break;
    }
  };
  ws.onclose = () => {
    if ($estado) $estado.hidden = false;
    setTimeout(_conectarChat, _remoto.reintento);
    _remoto.reintento = Math.min(_remoto.reintento * 2, 8000);
  };
}
