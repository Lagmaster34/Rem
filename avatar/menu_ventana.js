// avatar/menu_ventana.js — menú del clic derecho del modo VENTANA (el del
// escritorio vive en escritorio_ui.js, con más opciones). Script clásico:
// comparte el ámbito global con el resto de avatar/ (ver avatar/README.md).
//
// Solo sobre la zona 3D: dentro del panel de chat se deja el menú de WebKit
// (copiar y pegar). preventDefault() en el evento contextmenu cancela el menú
// de WebKit; el de la página se monta con las mismas clases que el del
// escritorio (avatar/escritorio.css, que ya se carga en todos los modos).
// Acciones por el WebSocket ({tipo:'app'}): las hace rem_chat.py.
"use strict";

function crearMenuVentana() {
  const raiz = document.createElement('div');
  raiz.id = 'esc-raiz';
  raiz.innerHTML = '<div id="esc-menu" class="esc-ui" hidden></div>';
  document.body.appendChild(raiz);
  const menu = raiz.querySelector('#esc-menu');
  let subAbierto = false;

  const enviar = obj => {
    if (_ws?.readyState === WebSocket.OPEN) { _ws.send(JSON.stringify({ tipo: 'app', ...obj })); return true; }
    console.warn('[Menú] sin conexión con el servidor: la acción no se manda');
    return false;
  };

  function boton(clase, texto, alPulsar, desactivado = false) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = clase;
    b.innerHTML = '<span class="esc-txt"></span>';
    b.querySelector('.esc-txt').textContent = texto;
    if (desactivado) b.disabled = true;
    else b.onclick = alPulsar;
    return b;
  }

  function pintar() {
    menu.innerHTML = '';
    const modo = boton('esc-item' + (subAbierto ? ' abierto' : ''), 'Cambiar de modo', () => { subAbierto = !subAbierto; pintar(); colocar(); });
    modo.insertAdjacentHTML('beforeend', '<span class="esc-flecha">›</span>');
    menu.appendChild(modo);
    if (subAbierto) {
      const lista = document.createElement('div');
      lista.className = 'esc-sub';
      lista.appendChild(boton('esc-item esc-subitem actual', 'Ventana (actual)', null, true));
      lista.appendChild(boton('esc-item esc-subitem', 'Escritorio', () => { cerrar(); enviar({ accion: 'modo', modo: 'escritorio' }); }));
      menu.appendChild(lista);
    }
    menu.appendChild(boton('esc-item', 'Abrir panel', () => { cerrar(); enviar({ accion: 'panel' }); }));
    menu.appendChild(Object.assign(document.createElement('div'), { className: 'esc-sep' }));
    menu.appendChild(boton('esc-item peligro', 'Cerrar', () => { cerrar(); enviar({ accion: 'cerrar' }); }));
  }

  let en = { x: 0, y: 0 };
  function colocar() {
    const W = window.innerWidth, H = window.innerHeight, w = menu.offsetWidth, h = menu.offsetHeight;
    menu.style.left = `${clamp(en.x, 6, Math.max(6, W - w - 6))}px`;
    menu.style.top = `${clamp(en.y, 6, Math.max(6, H - h - 6))}px`;
  }
  function abrir(x, y) {
    en = { x, y };
    subAbierto = false;
    pintar();
    menu.hidden = false;
    colocar();
    requestAnimationFrame(() => menu.classList.add('visible'));
  }
  function cerrar() {
    menu.classList.remove('visible');
    menu.hidden = true;
  }

  document.addEventListener('contextmenu', e => {
    if (e.target.closest?.('#chat-panel')) return;   // ahí, el de WebKit (copiar/pegar)
    e.preventDefault();
    if (e.target.closest?.('#esc-menu')) return;
    abrir(e.clientX, e.clientY);
  });
  document.addEventListener('pointerdown', e => { if (!menu.hidden && !e.target.closest?.('#esc-menu')) cerrar(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') cerrar(); });
  console.log('[Menú] menú del clic derecho (ventana) listo');
}
if (!ES_ESCRITORIO) crearMenuVentana();
