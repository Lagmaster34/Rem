// avatar/ws.js — WebSocket con el servidor (rem_avatar_server.py).
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// WEBSOCKET — con límite de reintentos
// ═══════════════════════════════════════════════════
let _wsRetries = 0;
let _ws = null;
let _modelosLista = [];   // modelos_lista del servidor (models/vrm/)

(function conectar() {
  if (_wsRetries >= CONFIG.ws.maxRetries) {
    console.warn('[WS] Máximo de reintentos alcanzado, deteniendo reconexión');
    return;
  }
  _ws = new WebSocket(`ws://localhost:${CONFIG.ws.port}`);
  _ws.onopen = () => {
    console.log('[WS] conectado');
    // Rol para el servidor: solo los avatares cuentan como destinatarios del
    // estado/audio (ver ROLES_WS en rem_avatar_server.py).
    _ws.send(JSON.stringify({ tipo: 'hola', rol: 'avatar' }));
    // Preferencias del panel (repertorio de animaciones): llegan en prefs_estado.
    _ws.send(JSON.stringify({ tipo: 'prefs_get' }));
    _ws.send(JSON.stringify({ tipo: 'modelos_get' }));
    _wsRetries = 0;
  };
  _ws.onmessage = e => {
    try {
      const d = JSON.parse(e.data);
      if (d.tipo === 'audio') {
        console.log('[Lipsync] mensaje de audio recibido, url=', d.url, '| eventos de timeline:', d.timeline?.length);
        encolarAudio(d.url, d.timeline);
      } else if (d.tipo === 'chat_delta') {
        window.__remChat?.onDelta(d.texto ?? '');
      } else if (d.tipo === 'chat_done') {
        window.__remChat?.onDone();
      } else if (d.tipo === 'modo_actual') {
        window.__remChat?.onModoActual(d.modo);
      } else if (d.tipo === 'historial') {
        // La conversación del modo anterior (cambio ventana <-> escritorio).
        window.__remChat?.onHistorial?.(Array.isArray(d.mensajes) ? d.mensajes : []);
      } else if (d.tipo === 'error') {
        window.__remChat?.onError(d.mensaje ?? 'error desconocido', String(d.frase ?? ''));
      } else if (d.tipo === 'prefs_estado') {
        for (const [sec, v] of Object.entries(d.prefs ?? {})) aplicarPrefsGenerales(sec, v);
        aplicarPrefsAnim(d.prefs?.animaciones);
        if (d.prefs?.modelo?.vrm) cambiarModelo(d.prefs.modelo.vrm);
      } else if (d.tipo === 'prefs_actualizadas') {
        aplicarPrefsGenerales(d.seccion, d.prefs);
        if (d.seccion === 'animaciones') aplicarPrefsAnim(d.prefs);
        if (d.seccion === 'modelo' && d.prefs?.vrm) cambiarModelo(d.prefs.vrm);
      } else if (d.tipo === 'prefs_error') {
        if (d.seccion === 'modelo') window.__remChat?.onSistema?.(`⚠ ${d.mensaje}`);
      } else if (d.tipo === 'modelos_lista') {
        _modelosLista = Array.isArray(d.modelos) ? d.modelos.filter(m => !m.error) : [];
        window.__remChat?.onModelos?.();
      } else if (d.tipo === 'emocion') {
        recibirEmocion(String(d.emocion ?? ''));
      } else if (d.tipo === 'debug_clip') {
        window.dispararClipDebug?.(String(d.nombre ?? ''));
      } else if (d.tipo === 'ptt_estado') {
        // Escuchando: estado local 'listening' (pose atenta; corta el baile).
        if (d.estado === 'escuchando' || d.estado === 'transcribiendo') { if (estado === 'idle') estado = 'listening'; }
        else if (estado === 'listening') estado = 'idle';
        window.__remChat?.onPttEstado?.(d.estado, d.motivo || d.nota || '');
      } else if (d.tipo === 'mic_veredicto') {
        window.__remChat?.onMicVeredicto?.(String(d.veredicto ?? ''), String(d.mensaje ?? ''), String(d.frase ?? ''));
      } else if (d.tipo === 'conversacion') {
        window.__remChat?.onConversacion?.(!!d.activa, String(d.motivo ?? ''));
      } else if (d.tipo === 'ptt_transcripcion') {
        window.__remChat?.onTranscripcion?.(String(d.texto ?? ''), d.ms ?? 1000);
      } else if (d.tipo === 'accion_confirmar') {
        window.__remChat?.onAccionConfirmar?.(String(d.nombre ?? ''), String(d.descripcion ?? ''), String(d.frase ?? ''));
      } else if (d.tipo === 'sonido') {
        tocarSonido(String(d.nombre ?? ''), String(d.id ?? ''));
      } else if (d.tipo === 'voz_actual') {
        window.__remChat?.onVozActual?.(d.activa);
      } else if (d.tipo === 'cmd_avatar') {
        // De la ventana de chat aparte (modo escritorio), vía el servidor.
        window.__remCmdAvatar?.(d);
      } else if (d.tipo === 'info_avatar') {
        // Para la ventana de chat; la página del avatar no lo usa.
      } else if (d.estado) {
        estado = d.estado;
      }
    } catch (err) {
      console.warn('[WS] JSON inválido:', err);
    }
  };
  _ws.onclose = () => {
    _wsRetries++;
    setTimeout(conectar, CONFIG.ws.retryDelay);
  };
  _ws.onerror = e => console.warn('[WS] Error de conexión:', e.type);
})();

window.setEstado = s => { estado = s; };

// Preferencias que valen en cualquier modo (tema, volumen); las del avatar de
// escritorio las recoge escritorio_ui.js por window.__remPrefs.
function aplicarPrefsGenerales(seccion, valores) {
  if (!valores) return;
  if (seccion === 'apariencia' && valores.tema) document.documentElement.dataset.tema = valores.tema;
  if (seccion === 'voz' && typeof valores.volumen === 'number') _audioEl.volume = _sonidoEl.volume = clamp(valores.volumen, 0, 1);
  window.__remPrefs?.(seccion, valores);
}

// La página del avatar le cuenta algo a la(s) ventana(s) de chat aparte.
function enviarAlChat(info) {
  if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send(JSON.stringify({ tipo: 'del_avatar', info }));
}
