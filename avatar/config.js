// avatar/config.js — modo (ventana/overlay), CONFIG centralizada y selección de modelo.
// Parte del script del avatar que antes vivía entero dentro de rem_avatar.html
// (un solo <script type="module">). Es un script CLÁSICO, no un módulo: todas
// las partes comparten el ámbito global (los let/const/function de nivel
// superior de una se ven desde las demás), igual que cuando eran secciones del
// mismo módulo. Se cargan en orden desde rem_avatar.html; three/three-vrm los
// publica antes avatar/dependencias.mjs. Ver avatar/README.md.
"use strict";


// Dos modos, elegidos por ?modo= (lo arma rem_avatar_server.url_avatar() según
// rem_chat.py --modo), nunca los dos a la vez:
//   ventana (default): ventana GTK decorada y opaca, avatar de cuerpo entero
//     sobre el suelo synthwave + panel de chat a la derecha + clips VRMA.
//   overlay: layer surface transparente y click-through (rem_chat.py --modo
//     overlay), avatar de medio cuerpo, SIN clips VRMA/gestos de reposo/suelo/
//     panel — solo lipsync, parpadeo, mirada a cámara con saccades, micro-
//     movimiento de cabeza/cuello y respiración, con los brazos en una pose de
//     reposo fija (CONFIG.brazos). Una caja de texto abajo es lo único que
//     recibe el ratón. Ver CONFIG.overlay y crearOverlayUI().
const MODO = new URLSearchParams(location.search).get('modo') === 'overlay' ? 'overlay' : 'ventana';
const ES_OVERLAY = MODO === 'overlay';
// Nombre del personaje para los textos de la interfaz: lo manda el backend en la
// URL (personalidad.NOMBRE_PERSONAJE, vía rem_avatar_server.url_avatar()).
const NOMBRE_PERSONAJE = new URLSearchParams(location.search).get('personaje') || 'Yoru';
console.log(`[Modo] ${MODO}`);

// ═══════════════════════════════════════════════════
// CONFIGURACIÓN CENTRALIZADA
// ═══════════════════════════════════════════════════
const CONFIG = {
  // z/position.y del modelo ya no son constantes fijas: recalcularEncuadre() las
  // deriva de la altura real medida del modelo (Box3) + estas anclas normalizadas.
  camera:  { fov: 28 },
  pet:     {
    anchorY: 0.55,           // altura de reposo, fracción de pantalla (0=arriba, 1=abajo)
    // anchorX es una fracción del ÁREA 3D VISIBLE (el ancho de la ventana
    // menos CONFIG.chat.anchoFrac, la parte que no tapa el panel de chat),
    // no de la ventana completa — ver fraccionAreaVisible3D()/worldX().
    anchorX: 0.5,            // centrada en su área visible
    alturaPantalla: 0.65,   // el modelo ocupa esta fracción del alto visible
  },
  // Ancho del panel de chat, como fracción del ancho total de la ventana —
  // ÚNICA fuente de verdad: tanto el CSS del panel (var(--chat-panel-width),
  // fijada desde JS al arrancar, ver crearPanelChat()) como el encuadre 3D
  // (fraccionAreaVisible3D(), más abajo) leen este mismo número, para que no
  // puedan desincronizarse.
  chat: {
    anchoFrac: 0.5,
  },
  // Suelo de cuadrícula synthwave — ver crearSueloSynthwave().
  // Nada de reflejos ni post-procesado: GPU justa (ver CLAUDE.md, calibración de VRAM).
  suelo: {
    colorLinea:     0x2be8ff,  // cian brillante
    colorHorizonte: 0x9be8ff,  // línea de horizonte, más clara que el resto de la cuadrícula
    colorFondo:     0x05000f,  // casi negro con un tinte violeta sutil
    tamano: 40,       // lado del área cuadriculada, en unidades de mundo
    divisiones: 40,
    nieblaCerca: 3.0, // arranca justo detrás de Rem — a ella no la toca
    nieblaLejos: 16,  // a partir de acá el suelo ya se perdió en el fondo
  },
  ws:      { port: 18766, retryDelay: 1500, maxRetries: 10 },
  lighting: {
    ambient: { color: 0xb0c0dd, intensity: 1.0 },
    key:     { color: 0xfff8f0, intensity: 1.4, pos: [1.5, 3, 2] },
    fill:    { color: 0x8899ff, intensity: 0.6, pos: [-2, 1, 0.5] },
    rim:     { color: 0xffffff, intensity: 0.3, pos: [0, 2, -2] },
  },
  // Brazos/antebrazos — todo en radianes. Ver "BRAZOS ACOPLADOS AL CUERPO"
  // más abajo para cómo se combinan. Pensado para poder afinarse sin leer
  // el resto del código.
  brazos: {
    separacion:        1.20,  // ángulo de reposo de ruZ/luZ — antes 1.28 (pegados al cuerpo)
    balanceoDelante:   0.14,  // inclinación hacia delante base del upperArm (ruX/luX)
    codoFlexionBase:  -0.30,  // flexión de codo en reposo — nunca brazos rectos del todo
    codoDerivaAmp:     0.05,  // amplitud del ruido que hace derivar el codo (además de la base)
    acopleRespiracion: 0.35,  // cuánto de spr.bX (torso, respiración) se filtra al balanceo del brazo
    acopleInclinacion: 0.25,  // cuánto de spr.bZ (torso, traslado de peso) se filtra al brazo
    gestoRuidoAmp:     1.6,   // cuánto empuja el envolvente de ruido la amplitud del gesto al hablar
    gestoHablaAmp:     0.5,   // cuánto empuja la energía real del habla (apertura de mandíbula)
  },
  // Dedos — 5 dedos × 3 falanges × 2 manos, todos con el mismo patrón de
  // curvatura de reposo (decrece hacia la punta) + deriva lenta. Radianes.
  dedos: {
    curlProximal:    0.55,  // falange más cercana a la palma — la que más se curva
    curlIntermedio:  0.42,
    curlDistal:      0.28,  // la punta — la que menos se curva
    curlPulgar:      0.32,  // el pulgar se curva menos que los demás dedos, y se opone (ver código)
    derivaAmp:       0.05,  // amplitud del ruido de micro-variación, para que no queden congelados
    derivaFreq:      0.025, // muy lento a propósito — es solo para que no se vean muertos
  },
  // Animación de cuerpo con clips VRMA — ver "ANIMACIÓN POR CLIPS VRMA" más
  // abajo. Los clips controlan SOLO la pose del cuerpo; respiración, parpadeo,
  // saccades, mirada a cámara y jaw se aplican siempre encima del mixer.
  animaciones: {
    // QUÉ clips hay (categoría, etiqueta, origen, medidas, giraCuerpo, fundido
    // de entrada, activoPorDefecto, estado -> clip, pose base) vive en
    // Animaciones/catalogo.json — ver "Catálogo de animaciones" en CLAUDE.md.
    // Acá queda solo el COMPORTAMIENTO: fundidos, ritmo, caché y mezcla.
    carpeta: '/Animaciones/',               // los ids del catálogo son relativos a esto
    catalogoUrl: '/Animaciones/catalogo.json',
    // Clips parseados que se guardan en memoria (LRU). Con 189 clips (58 MB) no
    // se puede precargar todo en un WebGL rasterizado por software: solo se
    // precargan los de estado y la pose base (que tampoco cuentan para el tope).
    cacheMax: 20,
    // Muchos bailes de Nerumi son una unidad de bucle (doodle 0,33 s, ankha
    // 1 s...) pensada para repetirse con la canción: como gesto de una sola vez
    // serían un parpadeo. Un baile más corto que esto se repite en bucle el
    // número de ciclos COMPLETOS que haga falta para llegar (el corte cae en
    // una frontera de ciclo). 8 s = la mediana de duración de los bailes.
    baileMinS: 8,
    // Transición clip<->clip: PUENTE DE POSE, no el crossFadeTo del mixer (ver
    // _iniciarPuente). Se fotografía la pose visible, el clip nuevo entra a
    // pleno peso y durante puenteS se hace slerp hueso por hueso desde la foto
    // hacia él — la técnica de Nerumi (DEFAULT_VRMA_BLEND_SECONDS = 0,5 s),
    // que la adoptó porque el crossfade nativo mezclaba mal la cadera.
    puenteS: 0.5,
    // Al dar la vuelta un clip en bucle, la unión casi nunca es perfecta:
    // mismo puente, cortito (Nerumi: LOOP_WRAP_BLEND_SECONDS = 0,12 s).
    puenteBucleS: 0.12,
    // Fundido procedural<->clip (el peso de mezcla, _clipPeso — ver
    // actualizarAnimacionClips). Con easing (easeInOutCubic), no lineal.
    // fadeIn: al entrar a un clip (procedural -> clip). Empieza a contar
    //   ANTES de que el clip corra a pleno peso (mismo mecanismo de siempre).
    // fadeOut: salida NATURAL — arranca en los últimos `fadeOut` segundos del
    //   clip (medidos contra su duración real), así el peso ya llega a 0
    //   justo cuando el clip termina, en vez de saltar de golpe al último
    //   frame y recién ahí empezar a desvanecer.
    // fadeOutInterrupcion: salida FORZADA (llegó audio, cambió de estado, un
    //   estado sin clip propio corta lo que hubiera) — más corta que fadeOut
    //   a propósito: "la voz manda" tiene que notarse, no arrastrarse 0,8s.
    fadeIn: 0.5,
    fadeOut: 0.8,
    fadeOutInterrupcion: 0.3,
    // Estado emocional -> clip: catalogo.json -> porEstado, {clips, modo,
    // duracionS?, enfriamiento?}. talking/idle NO tienen clip (procedurales).
    //   clips          : varios = uno al azar, sin repetir el último de ese estado.
    //   modo 'bucle'   : el clip se repite; duracionS (opcional) = tope de segundos
    //                    que controla el cuerpo, al vencer vuelve a procedural.
    //   modo 'unaVez'  : LoopOnce; al terminar vuelve a lo procedural aunque el
    //                    estado siga activo. En los dos la CARA sigue con la
    //                    emoción (la maneja updateExpressions() por 'estado').
    //   enfriamiento   : si ese clip se reprodujo por estado hace menos de
    //                    enfriamientoMin minutos, esa vez solo la cara.
    // intervaloReposo y enfriamientoMin: catalogo.json -> ajustes, y el panel
    // los pisa (ver ajusteAnim()). El intervalo se sortea CADA VEZ que termina
    // un gesto (ver _alTerminarClip/updateGestos), nunca desde que empieza: el
    // ritmo real visible es intervalo + duración del clip elegido.
    // Gestos de reposo aleatorios (solo en idle y sin audio): el repertorio es
    // el catálogo — los clips activos (ver clipActivo()) que estén en disco. Se
    // sortea primero la CATEGORÍA por su peso y después el clip dentro de ella
    // por el suyo; 'horas' [desde, hasta) restringe la franja horaria. No se
    // repite el mismo clip dos veces seguidas (ver _elegirGesto).
    // Clip de POSE BASE para idle. A diferencia de porEstado/gestos, este sería
    // la base: cede el paso a cualquier gesto o clip de estado (crossfade) y
    // vuelve a él al terminar. Todo lo procedural sigue encima (respiración,
    // saccades, mirada, dedos, traslado de peso, ruido de cabeza).
    //
    // DESACTIVADO (archivo: null) — el reposo es el idle PROCEDURAL, con los
    // brazos en CONFIG.brazos.*. Motivo: se probó con Relax.vrma y producía una
    // T-pose casi permanente. Medido sobre las pistas del .vrma (ángulo Z del
    // upperArm, ya con el espejo VRM0 que aplica clipDeVrma; el reposo
    // procedural es ±68,8° = CONFIG.brazos.separacion 1,20 rad):
    //     t=0,0s  izq +69,7°  der -60,0°   ← coincide con el reposo procedural
    //     t=0,9s  izq +12,0°  der  -8,4°
    //     t=1,8s  izq -17,1°  der  +7,0°   ← brazos en horizontal
    //     t=3,9s  izq -18,5°  der  +1,5°
    // Es decir: el clip arranca con los brazos abajo y en ~1,2s los sube a la
    // horizontal, donde se queda el 83-85% de su ciclo de 3,93s — y corre en
    // bucle, mezclado al 0,8 sobre los brazos (mezclaBrazos). Reposo real =
    // 0,8 × T-pose. NO es un bug del mixer ni del orden de la mezcla: es el
    // contenido del clip.
    //
    // Si se quiere recuperar la pose de manos/brazos del clip sin la T-pose, el
    // camino es modo:'poseFija' (congela el frame 0, que SÍ tiene los brazos
    // abajo), no modo:'bucle'. Antes de habilitar cualquier otro .vrma acá,
    // medirle el ángulo del upperArm a lo largo del clip, no solo mirar su
    // primer frame.
    //   archivo (catalogo.json -> poseBase.archivo):  null → procedural puro (el reposo por defecto, brazos en CONFIG.brazos.*).
    //             un .vrma → pose base (ver la advertencia de arriba).
    //   modo (catalogo.json -> poseBase.modo):  'bucle'    → el clip corre en loop, con timeScale variable (velMin..
    //                       velMax) para romper la periodicidad de un ciclo corto.
    //          'poseFija'  → solo el primer frame, congelado — arregla la pose sin
    //                        aportar movimiento; todo el movimiento queda procedural.
    //   mezclaBrazos: 0..1 — cuánto la pose del clip reemplaza a la procedural EN
    //                        LOS BRAZOS (hombro/upperArm/lowerArm/mano). El resto
    //                        del cuerpo queda 100% procedural: los brazos rectos
    //                        son el problema real, el resto ya se ve bien.
    //   ampProcedural: multiplica el ruido Perlin de getStatePose('idle') mientras
    //                  el clip de idle está activo (>1 rompe el patrón del bucle).
    //   velMin/velMax/velCambioS: solo 'bucle' — timeScale deriva lento entre
    //                             velMin y velMax, objetivo nuevo cada ~velCambioS s.
    idle: {
      // false: la pose base mueve el cuerpo ENTERO (lo actual). true: del clip
      // solo los brazos y el resto procedural (la mezcla vieja de mezclaBrazos).
      soloBrazos: false,
      modo: 'poseFija',       // por defecto si poseBase no dice modo
      mezclaBrazos: 0.8,
      ampProcedural: 1.5,
      velMin: 0.85,
      velMax: 1.0,
      velCambioS: 9,
    },
  },
  // Solo modo overlay (?modo=overlay). La geometría de la SUPERFICIE (ancho,
  // alto, márgenes, capa) no va acá: es de la ventana GTK y vive en config.toml
  // [overlay]. Acá, el encuadre del avatar dentro de ella.
  overlay: {
    encuadre: {
      // Medio cuerpo, medido por huesos (hips y head), en fracciones de la
      // distancia hips->head ("tramo del torso", ~0,6 u en este modelo).
      bajoCaderaFrac:  0.10,  // cuánto por DEBAJO de la cadera llega el borde inferior
      sobreCabezaFrac: 0.30,  // cuánto por ENCIMA del hueso head (pelo/adornos)
      ocupaAltoFrac:   0.93,  // fracción del alto de la superficie que ocupa ese tramo
      // El encuadre se ajusta por alto Y por ancho y manda el más restrictivo:
      // con brazos en reposo el cuerpo es más ancho que alto en una superficie
      // vertical, y ajustar solo por alto los cortaba por los costados.
      ocupaAnchoFrac:  0.96,  // fracción del ancho de la superficie que puede ocupar el cuerpo con brazos
      anchoExtraFrac:  0.34,  // margen sobre el ancho medido en huesos (mangas sueltas/volados: sin hueso propio, sobresalen de las manos)
      // El borde inferior (el corte de cadera) se apoya en el borde de abajo de
      // la superficie: el sobrante vertical queda ARRIBA (transparente), no
      // como un hueco entre Rem y la caja de texto.
      baseSobreBordeFrac: 0.0, // fracción del alto visible entre el corte y el borde inferior
      anchorX: 0.5,           // centrada horizontalmente
    },
  },
  // Presupuesto de render — la ventana comparte los 4 GB de VRAM con Ollama
  // (ver config.toml [llm.ollama].num_gpu). Bajar estos valores libera
  // VRAM para el LLM a costa de nitidez.
  render: {
    pixelRatioMax:   1.0,      // tope del devicePixelRatio (era 1.5)
    resolucionMaxPx: 1600000,  // tope de píxeles del framebuffer (w*h*ratio²).
                               // ~1,6 Mpx ≈ 1600x1000; por encima se baja el
                               // ratio y el canvas se reescala por CSS. 0 = sin tope.
  },
  // Mirada a cámara — ver "MIRADA A CÁMARA + MICRO-SACCADES" más abajo.
  mirada: {
    intensidadSeguimiento: 1.0,  // 0..1 — 1 = mirada directa a la cámara, más bajo = seguimiento más contenido
    apartarIntervaloMinS: 4,     // cada cuánto puede "apartar la mirada" un momento — mínimo, en segundos
    apartarIntervaloMaxS: 9,     // máximo
    apartarAmpYaw: 26,           // cuánto se aparta en yaw (grados)
    apartarAmpPitch: 14,         // cuánto se aparta en pitch (grados)
    apartarEntradaS: 0.35,       // segundos para entrar al desvío
    apartarSostenS: 0.8,         // segundos que se mantiene apartada
    apartarSalidaS: 0.4,         // segundos para volver a la cámara
    cabezaFraccion: 0.3,         // 0..1 — cuánto de la mirada (grados, ya convertidos a rad) gira también la cabeza/cuello
    cabezaVelocidad: 6,          // lerp/s de la cabeza hacia la mirada — más alto = menos retardo respecto a los ojos
  },
  // Cara: cuánto de una expresión que se suprime al hablar (ver
  // _expresionesSuprimirHabla) se conserva mientras suena la voz. 0 = se apaga
  // del todo (lo probado: en VRoid las emociones son Fcl_ALL_*, cara completa
  // CON boca, y pelean con los visemes).
  expresiones: {
    supresionHabla: 0,
    emocionPeso: { happy: 0.9, sad: 0.85, angry: 0.8, surprised: 0.9 }, // cara de una emoción del chat
    gestoPeso: 0.6,     // cara de un gesto de reposo con "expresion" en el catálogo
    bailePeso: 0.45,    // happy suave mientras baila (el "vibing" de Nerumi)
  },
  // ── MODELOS ──────────────────────────────────────────────────────────
  // Los VRM viven en models/vrm/ (solo locales, nunca en git) y se cambian
  // en caliente (botón 👤 del chat, /modelo, panel de control — ver
  // cambiarModelo()). Todo lo que depende del archivo se AUTODETECTA al
  // cargarlo, sin perfil a mano:
  //   - VRM 0.x o 1.0 (vrm.meta.metaVersion): orientación de la escena y el
  //     espejo de la pose procedural (ver _esVRM1).
  //   - Lipsync: los binds de las expresiones aa/ih/ou/ee/oh dicen qué morph es
  //     cada vocal (ver _resolverLipsyncPorVocales); sin ellas, expressionManager.
  //   - Qué emociones apagar al hablar: las que tocan morphs de boca o de cara
  //     completa (ver _detectarSupresionHabla).
  //   - Encuadre: por huesos, como siempre.
  // Solo si un modelo necesita algo distinto se le pone una entrada acá, con
  // la MISMA ruta que usa config.toml/preferencias:
  //   'models/vrm/x.vrm': {
  //     lipsync: { visemas: { 'vrc.v_aa': [{ morph: '<clave real de morphTargetDictionary>', peso: 1 }], ... } },
  //     expresionesSuprimirHabla: ['happy', ...],
  //   }
  modelos: {},
  modeloPorDefecto: 'models/vrm/neru.vrm',
};

// ═══════════════════════════════════════════════════
// SELECCIÓN DE MODELO — ver CONFIG.modelos más arriba
// ═══════════════════════════════════════════════════
// ?modelo=... lo arma rem_avatar_server.url_avatar() (Python) con la
// preferencia del panel o config.toml [avatar].modelo. Es `let`: cambiarModelo()
// lo reemplaza en caliente. _modeloGen sube con cada cambio e invalida todo lo
// que estuviera cargando para el modelo anterior (el VRM y los clips).
let MODELO_ACTIVO = new URLSearchParams(location.search).get('modelo') || CONFIG.modeloPorDefecto;
let PERFIL_MODELO = CONFIG.modelos[MODELO_ACTIVO] ?? {};
let _modeloGen = 0;
// VRM 1.0 mira a +Z y VRM 0.x a -Z, y sus huesos normalizados tienen X/Z
// espejados entre sí. Los clips VRMA ya lo resuelven (clipDeVrma); la pose
// procedural está escrita en la convención de VRM 0.x y se espeja para 1.0
// (ver _espejarHuesos).
let _esVRM1 = false;
console.log(`[Modelo] activo: "${MODELO_ACTIVO}"`);
