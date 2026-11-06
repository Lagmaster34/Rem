// avatar/panel_chat.js — panel de chat del modo ventana.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";

// ═══════════════════════════════════════════════════
// PANEL DE CHAT (ver también el CSS en <head>)
// ═══════════════════════════════════════════════════
// HTML/CSS/JS vanilla, sin frameworks ni dependencias externas. El envío usa
// _ws directo (declarado más abajo, en WEBSOCKET) — los handlers de click
// solo lo LEEN al momento del click, mucho después de que el módulo entero
// ya terminó de evaluarse, así que el orden de declaración no importa acá.
// La recepción es al revés: window.__remChat se define ACÁ (antes de la
// sección WEBSOCKET) para que _ws.onmessage, más abajo, ya lo encuentre
// armado desde el primer mensaje que llegue.
function crearPanelChat() {

  // Única fuente de verdad para el ancho del panel: CONFIG.chat.anchoFrac.
  // fraccionAreaVisible3D() (encuadre 3D) lee ese mismo número directo de
  // CONFIG; el CSS del <head> no puede leer CONFIG (vive en el JS de acá
  // abajo), así que un custom property es el único puente entre los dos —
  // fijado acá, antes de crear el panel, para que ambos queden atados al
  // mismo valor sin poder desincronizarse.
  document.documentElement.style.setProperty('--chat-panel-width', `${CONFIG.chat.anchoFrac * 100}%`);

  const panel = document.createElement('div');
  panel.id = 'chat-panel';
  panel.innerHTML = `
    <div id="chat-header">
      <div id="chat-modeselect">
        <button data-modo="ia" class="activo" type="button">IA</button>
        <button data-modo="eco" type="button">Eco</button>
      </div>
      <div id="chat-header-actions">
        <button id="chat-modelo" class="chat-btn-texto" type="button" title="Elegir el modelo del avatar">Modelo ▾</button>
        <button id="chat-baile" class="chat-btn-texto" type="button" title="Activar o desactivar el modo baile">Bailar</button>
        <button id="chat-voz" type="button" title="Silenciar voz">🔊</button>
        <button id="chat-reset" type="button" title="Limpiar conversación">🗑</button>
      </div>
    </div>
    <div id="chat-modelos" hidden></div>
    <div id="chat-messages"></div>
    <div id="chat-status"></div>
    <div id="chat-inputbar">
      <div id="chat-paleta"></div>
      <input id="chat-input" type="text" placeholder="Escríbele algo a ${NOMBRE_PERSONAJE}... (/ para comandos)" autocomplete="off">
      <button id="chat-send" type="button" title="Enviar">➤</button>
    </div>
  `;
  document.body.appendChild(panel);

  const $mensajes = panel.querySelector('#chat-messages');
  const $status   = panel.querySelector('#chat-status');
  const $input    = panel.querySelector('#chat-input');
  const $send     = panel.querySelector('#chat-send');
  const $voz      = panel.querySelector('#chat-voz');
  const $reset    = panel.querySelector('#chat-reset');
  const $modoBtns = panel.querySelectorAll('#chat-modeselect button');
  const $paleta   = panel.querySelector('#chat-paleta');
  const $btnModelo = panel.querySelector('#chat-modelo');
  const $btnBaile  = panel.querySelector('#chat-baile');
  const $modelos   = panel.querySelector('#chat-modelos');

  // ── Selector de modelo y modo baile ──
  function pedirModelo(ruta) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) { agregarSistema('Sin conexión con el servidor.'); return; }
    _ws.send(JSON.stringify({ tipo: 'prefs_set', seccion: 'modelo', cambios: { vrm: ruta } }));
    $modelos.hidden = true;
    $btnModelo.classList.remove('activo');
  }
  function pintarModelos() {
    $modelos.innerHTML = '';
    if (!_modelosLista.length) { $modelos.textContent = 'No hay modelos en models/vrm/.'; return; }
    for (const m of _modelosLista) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'modelo-item' + (m.ruta === MODELO_ACTIVO ? ' activo' : '');
      b.textContent = `${m.titulo} — ${m.autor}${m.credito ? ' (crédito)' : ''} · VRM ${m.version ?? '?'}`;
      b.title = m.ruta;
      b.onclick = () => pedirModelo(m.ruta);
      $modelos.appendChild(b);
    }
  }
  $btnModelo.addEventListener('click', () => {
    $modelos.hidden = !$modelos.hidden;
    $btnModelo.classList.toggle('activo', !$modelos.hidden);
    if (!$modelos.hidden) { pintarModelos(); _ws?.send(JSON.stringify({ tipo: 'modelos_get' })); }
  });
  $btnBaile.addEventListener('click', () => setModoBaile(!_modoBaile));
  $btnBaile.classList.toggle('activo', _modoBaile);

  let modoActivo = 'ia';
  let esperandoRespuesta = false;
  let burbujaRemActual = null; // <div> de la respuesta en curso (streaming), o null
  // Arranca en true — el backend también arranca con la voz activa por
  // defecto (ver rem_avatar_server._chat_voz_activa), este botón es para
  // silenciarla, no para tener que prenderla primero. Puramente local: a
  // diferencia del modo, no hay confirmación del backend ni sincronización
  // con el REPL — "voz on|off" del REPL controla SUS PROPIOS turnos, este
  // botón los del panel (ver CLAUDE.md, "Voz en la ventana de chat").
  let vozActiva = true;

  function alFondo() { $mensajes.scrollTop = $mensajes.scrollHeight; }

  function agregarBurbuja(texto, clase) {
    const div = document.createElement('div');
    div.className = `msg ${clase}`;
    div.textContent = texto;
    $mensajes.appendChild(div);
    alFondo();
    return div;
  }

  function agregarSistema(texto) {
    agregarBurbuja(texto, 'sistema');
  }

  // Confirmación de una acción que la requiere (ver acciones.py,
  // TOOLS_QUE_CONFIRMAN — hoy solo apagar_pc). Burbuja de sistema con dos
  // botones; al elegir cualquiera se deshabilitan los dos (no se puede
  // responder dos veces al mismo pedido) y se manda accion_confirmar_resp.
  // Si expira del lado del servidor (_CONFIRMACION_TIMEOUT_S) el turno ya se
  // canceló solo — esta burbuja queda inerte, sin nada que limpiarla, pero
  // tampoco hace daño: un click tardío ya no tiene a quién llegarle
  // (_confirmacion_pendiente ya no existe del lado de Python).
  function agregarConfirmacion(nombre, descripcion) {
    const div = document.createElement('div');
    div.className = 'msg sistema';
    const p = document.createElement('div');
    p.textContent = descripcion;
    div.appendChild(p);
    const btns = document.createElement('div');
    btns.style.marginTop = '6px';
    const responder = (ok) => {
      btnSi.disabled = true;
      btnNo.disabled = true;
      _ws.send(JSON.stringify({ tipo: 'accion_confirmar_resp', ok }));
    };
    const btnSi = document.createElement('button');
    btnSi.textContent = 'Sí';
    btnSi.onclick = () => responder(true);
    const btnNo = document.createElement('button');
    btnNo.textContent = 'No';
    btnNo.style.marginLeft = '8px';
    btnNo.onclick = () => responder(false);
    btns.appendChild(btnSi);
    btns.appendChild(btnNo);
    div.appendChild(btns);
    $mensajes.appendChild(div);
    alFondo();
  }

  function setEstadoUI(texto, clase) {
    $status.textContent = texto || '';
    $status.className = clase || '';
  }

  function actualizarInputHabilitado() {
    $input.disabled = esperandoRespuesta;
    $send.disabled = esperandoRespuesta;
  }

  // ═══════════════════════════════════════════════════
  // COMANDOS "/" — se resuelven ENTEROS en el frontend
  // ═══════════════════════════════════════════════════
  // Nunca salen por el WebSocket: el registro de clips solo lo conoce esta
  // página, así que un comando no genera chat_message ni turno del LLM.
  //
  // Cada comando: {descripcion, listar()?, ejecutar(arg)}. listar() (opcional)
  // es lo que hace que la paleta tenga un segundo nivel — devuelve
  // [{valor, titulo, desc}]. Un solo argumento posicional a propósito: no hace
  // falta un parser genérico de flags para lo que se necesita acá.

  // Dispara un clip a mano. Regla: los que giran el cuerpo (giraCuerpo, ver
  // catalogo.json, medido) sacan a Rem de cámara, así que mientras haya
  // voz sonando NO se disparan — quedan en espera y salen al vaciarse la cola
  // de audio. Los demás salen al momento, aunque esté hablando.
  function dispararClipManual(archivo) {
    const etiqueta = etiquetaClip(archivo);
    if (clipGiraCuerpo(archivo) && hayVozSonando()) {
      ponerClipEnEspera(archivo);   // reemplaza al anterior; solo se guarda uno
      agregarSistema(`⏳ ${etiqueta} — en espera: gira el cuerpo y ${NOMBRE_PERSONAJE} está hablando`);
      return;
    }
    // El disparo manual corre el temporizador de gestos espontáneos, para que
    // no se encadene uno automático encima del que se acaba de pedir.
    _gestoTimer = _sortearIntervaloGesto();
    window.dispararClipDebug(archivo);   // MISMA función que el handler WS debug_clip
    agregarSistema(`▶ ${etiqueta}`);
  }

  const COMANDOS = {
    modelo: {
      descripcion: 'Cambiar de modelo VRM',
      listar() {
        return _modelosLista.map(m => ({ valor: m.ruta, titulo: m.titulo, desc: m.autor + (m.ruta === MODELO_ACTIVO ? ' · actual' : '') }));
      },
      ejecutar(arg) {
        const f = (arg || '').trim().toLowerCase();
        const hit = _modelosLista.find(m => m.ruta.toLowerCase() === f || m.titulo.toLowerCase() === f || m.archivo.toLowerCase().startsWith(f));
        if (!f || !hit) { agregarSistema(`Modelos: ${_modelosLista.map(m => m.archivo).join(', ') || 'ninguno'}`); return; }
        pedirModelo(hit.ruta);
      },
    },
    bailar: {
      descripcion: 'Activar/desactivar el modo baile',
      ejecutar() { setModoBaile(!_modoBaile); },
    },
    animaciones: {
      descripcion: 'Disparar un clip de animación',
      listar() {
        return clipsDisponibles().map(c => ({
          valor: c.nombre,
          titulo: c.etiqueta,
          grupo: c.grupo,
          desc: c.giraCuerpo ? 'gira el cuerpo' : '',
        }));
      },
      ejecutar(arg) {
        const disponibles = clipsDisponibles();
        if (disponibles.length === 0) {
          agregarSistema('No hay clips de animación cargados.');
          return;
        }
        const f = (arg || '').trim().toLowerCase();
        if (!f) { agregarSistema('Uso: /animaciones <nombre>'); return; }
        const hit = disponibles.find(c => c.nombre.toLowerCase() === f)
                 ?? disponibles.find(c => c.etiqueta.toLowerCase() === f)
                 ?? disponibles.find(c => c.etiqueta.toLowerCase().includes(f));
        if (!hit) { agregarSistema(`No hay ninguna animación que coincida con "${arg}".`); return; }
        dispararClipManual(hit.nombre);
      },
    },
  };

  // ── Paleta ────────────────────────────────────────────────────────────
  let palAbierta = false;
  let palItems = [];      // [{valor, titulo, desc}]
  let palSel = 0;
  let palNivel = 'raiz';  // 'raiz' o el nombre del comando cuyo argumento se elige

  // "/" SOLO como primer carácter: "a/b" no abre nada. Devuelve null si el
  // texto no es un comando.
  function parsearEntrada(v) {
    if (!v.startsWith('/')) return null;
    const m = v.match(/^\/([^\s]*)(\s([\s\S]*))?$/);
    if (!m) return null;
    return { comando: m[1], tieneArg: m[2] !== undefined, arg: m[3] ?? '' };
  }

  function cerrarPaleta() {
    palAbierta = false;
    palItems = [];
    $paleta.style.display = 'none';
    $paleta.innerHTML = '';
  }

  function pintarPaleta() {
    $paleta.innerHTML = '';
    if (palItems.length === 0) {
      const v = document.createElement('div');
      v.className = 'pal-vacio';
      v.textContent = 'Sin coincidencias';
      $paleta.appendChild(v);
      return;
    }
    palItems.forEach((it, i) => {
      // Cabecera de grupo (categoría) al cambiar: no es un ítem, no se selecciona.
      if (it.grupo && it.grupo !== palItems[i - 1]?.grupo) {
        const g = document.createElement('div');
        g.className = 'pal-grupo';
        g.textContent = it.grupo;
        $paleta.appendChild(g);
      }
      const fila = document.createElement('div');
      fila.className = 'pal-item' + (i === palSel ? ' sel' : '');
      const n = document.createElement('span');
      n.className = 'pal-nombre';
      n.textContent = it.titulo;
      fila.appendChild(n);
      if (it.desc) {
        const d = document.createElement('span');
        d.className = 'pal-desc';
        d.textContent = it.desc;
        fila.appendChild(d);
      }
      // mousedown, no click: preventDefault evita que el input pierda el foco,
      // así el flujo de dos niveles sigue siendo tecleable sin volver a clickear.
      fila.addEventListener('mousedown', e => { e.preventDefault(); elegir(i); });
      $paleta.appendChild(fila);
    });
    const sel = $paleta.querySelector('.pal-item.sel');
    if (sel) sel.scrollIntoView({ block: 'nearest' });
  }

  function actualizarPaleta() {
    const p = parsearEntrada($input.value);
    if (!p) { cerrarPaleta(); return; }
    const cmd = COMANDOS[p.comando];
    if (p.tieneArg && cmd && cmd.listar) {
      palNivel = p.comando;
      const f = p.arg.trim().toLowerCase();
      palItems = cmd.listar().filter(i =>
        !f || i.titulo.toLowerCase().includes(f) || i.valor.toLowerCase().includes(f)
           || (i.grupo ?? '').toLowerCase().includes(f));
    } else {
      palNivel = 'raiz';
      const f = p.comando.toLowerCase();
      palItems = Object.entries(COMANDOS)
        .filter(([n]) => n.toLowerCase().startsWith(f))
        .map(([n, c]) => ({ valor: n, titulo: '/' + n, desc: c.descripcion }));
    }
    palSel = 0;
    palAbierta = true;
    $paleta.style.display = '';
    pintarPaleta();
  }

  function elegir(i) {
    const it = palItems[i];
    if (!it) return;
    if (palNivel === 'raiz') {
      // Primer nivel: deja el comando escrito y pasa a listar sus argumentos.
      $input.value = `/${it.valor} `;
      $input.focus();
      if (COMANDOS[it.valor]?.listar) actualizarPaleta();
      else cerrarPaleta();
      return;
    }
    COMANDOS[palNivel]?.ejecutar(it.valor);
    $input.value = '';
    cerrarPaleta();
    $input.focus();
  }

  // Texto que empieza por "/" — se resuelve acá y NUNCA se manda al backend.
  function ejecutarComandoTexto(texto) {
    const p = parsearEntrada(texto);
    const cmd = p && COMANDOS[p.comando];
    if (!cmd) { agregarSistema(`Comando desconocido: ${texto}`); return; }
    cmd.ejecutar(p.arg);
  }

  $input.addEventListener('input', actualizarPaleta);

  function enviarMensaje() {
    const texto = $input.value.trim();
    if (!texto || esperandoRespuesta) return;
    // Un comando "/" se resuelve entero en el frontend: ni chat_message ni
    // turno del LLM. Va antes del chequeo de WS a propósito — /animaciones
    // funciona aunque el socket esté caído, no necesita backend.
    if (texto.startsWith('/')) {
      ejecutarComandoTexto(texto);
      $input.value = '';
      cerrarPaleta();
      return;
    }
    if (!_ws || _ws.readyState !== WebSocket.OPEN) {
      agregarSistema('Sin conexión con Rem — reintentando...');
      return;
    }
    agregarBurbuja(texto, 'user');
    _ws.send(JSON.stringify({ tipo: 'chat_message', texto }));
    $input.value = '';
    esperandoRespuesta = true;
    burbujaRemActual = null;
    actualizarInputHabilitado();
    setEstadoUI(`${NOMBRE_PERSONAJE} está pensando…`, 'pensando');
  }

  $send.addEventListener('click', enviarMensaje);
  $input.addEventListener('keydown', e => {
    // La paleta se atiende PRIMERO y en el MISMO listener que el envío: así
    // el preventDefault de Enter llega seguro antes de enviarMensaje(), sin
    // depender del orden en que se hayan registrado los handlers.
    if (palAbierta) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (palItems.length) { palSel = (palSel + 1) % palItems.length; pintarPaleta(); }
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (palItems.length) { palSel = (palSel - 1 + palItems.length) % palItems.length; pintarPaleta(); }
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        // Con la paleta abierta Enter SELECCIONA, nunca envía — ni siquiera
        // cuando no hay coincidencias (si no, un "/anim" a medio escribir se
        // le mandaría al LLM).
        e.preventDefault();
        elegir(palSel);
        return;
      }
      if (e.key === 'Escape') { e.preventDefault(); cerrarPaleta(); return; }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviarMensaje(); }
  });

  $modoBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const modo = btn.dataset.modo;
      if (modo === modoActivo || !_ws || _ws.readyState !== WebSocket.OPEN) return;
      _ws.send(JSON.stringify({ tipo: 'cambiar_modo', modo }));
    });
  });

  // Interruptor de voz — equivalente a "voz on|off" del REPL, para poder
  // silenciar el panel sin cerrar la ventana. Optimista (no espera
  // confirmación del backend, a diferencia del modo): un simple on/off no
  // puede fallar, y esto es puramente local al panel — no hay "voz_actual"
  // que sincronizar con nadie más.
  $voz.addEventListener('click', () => {
    vozActiva = !vozActiva;
    $voz.textContent = vozActiva ? '🔊' : '🔇';
    $voz.title = vozActiva ? 'Silenciar voz' : 'Activar voz';
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ tipo: 'voz', activa: vozActiva }));
    }
  });

  $reset.addEventListener('click', () => {
    if (_ws && _ws.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify({ tipo: 'reset' }));
    }
    $mensajes.innerHTML = '';
    burbujaRemActual = null;
    esperandoRespuesta = false;
    actualizarInputHabilitado();
    setEstadoUI('', '');
  });

  // Llamado desde _ws.onmessage (ver WEBSOCKET más abajo) — traduce los
  // tipos del protocolo de chat a cambios concretos del panel.
  window.__remChat = {
    onDelta(fragmento) {
      if (!burbujaRemActual) {
        burbujaRemActual = agregarBurbuja('', 'rem');
        setEstadoUI(`${NOMBRE_PERSONAJE} está hablando…`, 'hablando');
      }
      burbujaRemActual.textContent += fragmento;
      alFondo();
    },
    onDone() {
      esperandoRespuesta = false;
      burbujaRemActual = null;
      actualizarInputHabilitado();
      setEstadoUI('', '');
    },
    onError(mensaje) {
      esperandoRespuesta = false;
      burbujaRemActual = null;
      actualizarInputHabilitado();
      setEstadoUI('', '');
      agregarSistema(`⚠ ${mensaje}`);
    },
    onModoActual(modo) {
      const cambioReal = modo !== modoActivo;
      modoActivo = modo;
      $modoBtns.forEach(b => b.classList.toggle('activo', b.dataset.modo === modo));
      if (cambioReal) {
        $mensajes.innerHTML = '';
        agregarSistema(`Modo: ${modo === 'ia' ? 'IA' : 'Eco'}`);
      }
    },
    // Lo llama _intentarLanzarClipEnEspera() cuando por fin sale un clip que
    // estaba esperando a que Rem terminara de hablar.
    onSistema(texto) { agregarSistema(texto); },
    onModeloCargado(ruta, titulo, autor) {
      agregarSistema(`Modelo: ${titulo}${autor ? ` — ${autor}` : ''}`);
      if (!$modelos.hidden) pintarModelos();
    },
    onModelos() { if (!$modelos.hidden) pintarModelos(); },
    onModoBaile(on) { $btnBaile.classList.toggle('activo', on); },
    onClipLanzado(archivo) {
      agregarSistema(`▶ ${etiquetaClip(archivo)}`);
    },
    // Push-to-talk (ver rem_avatar_server, "Push-to-talk"). La transcripción
    // entra como un mensaje del usuario y el turno arranca solo ~1s después.
    onPttEstado(est, detalle) {
      if (est === 'escuchando')          setEstadoUI('🎙 Escuchando…', 'pensando');
      else if (est === 'transcribiendo') setEstadoUI('Transcribiendo…', 'pensando');
      else if (est === 'ignorado')       { setEstadoUI('', ''); agregarSistema(`🎙 Ignorado: ${detalle}`); }
      else {
        if (!esperandoRespuesta) setEstadoUI('', '');
        // Un "stop" sin grabación (p. ej. el bindrt de soltar Super) no es noticia.
        if (detalle && detalle !== 'no estaba grabando') agregarSistema(`🎙 ${detalle}`);
      }
    },
    onTranscripcion(texto) {
      agregarBurbuja(texto, 'user');
      esperandoRespuesta = true;
      burbujaRemActual = null;
      actualizarInputHabilitado();
      setEstadoUI(`${NOMBRE_PERSONAJE} está pensando…`, 'pensando');
    },
    // Una tool que requiere confirmación (ver acciones.py) está esperando
    // sí/no del panel antes de ejecutarse — ver _pedir_confirmacion_accion
    // en rem_avatar_server.py.
    onAccionConfirmar(nombre, descripcion) {
      agregarConfirmacion(nombre, descripcion);
    },
  };

  cerrarPaleta();   // arranca oculta
  $input.focus();
}
