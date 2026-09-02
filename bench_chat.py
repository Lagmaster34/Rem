#!/usr/bin/env python3
"""bench_chat.py — REPL de depuración para la capa LLM (llm/) y el pipeline de
voz/lipsync/avatar, sin GUI. No importa Rem.py (no se puede: el Python
3.10.14 del venv se compiló sin _tkinter).

La APLICACIÓN es rem_chat.py (levanta el servidor HTTP/WS y abre la ventana).
bench_chat.py es una herramienta de depuración que se adapta:

  * Si detecta el servidor del avatar ya levantado (rem_chat.py corriendo, u
    otra instancia), se conecta como CLIENTE WebSocket y manda sus 'state',
    'chat', 'modo', 'voz' y 'reset' por ahí — el servidor los procesa y la
    ventana los ve. (modo cliente)

  * Si no hay servidor, lo levanta él mismo y funciona autocontenido: consume
    provider.stream_chat() directo, con su propio worker de voz. (modo standalone)

En ninguno de los dos casos falla en silencio: si un mensaje no tiene a quién
llegar, lo dice en consola.

    venv/bin/python bench_chat.py
    venv/bin/python bench_chat.py --no-rvc      # 'voz' sin conversión RVC (solo standalone)
    venv/bin/python bench_chat.py --open        # abre el navegador al arrancar
    venv/bin/python bench_chat.py --depurar-contexto-eco  # ver más abajo

Comandos dentro del REPL:
    chat <texto>       — manda <texto> al modo activo, imprime la respuesta en streaming
    modo                — muestra el modo activo (ia/eco)
    modo ia|eco          — cambia de modo en caliente, sin reiniciar (ver SesionChat)
    voz on|off          — activa/desactiva hablar la respuesta (lipsync+RVC+avatar)
    reset                — limpia el historial de la conversación
    state <estado>      — manda ese estado al avatar (idle/talking/thinking/happy/sad/angry/surprised)
    open                 — abre el avatar en el navegador por defecto
    quit                 — cierra limpiamente (o Ctrl+D / Ctrl+C)

Modo "ia" habla con el provider configurado (llm.get_provider() — Claude,
Groq u Ollama según .env/config.toml), con el contexto dinámico real
(fecha/hora/estado de la PC) antepuesto a cada mensaje. Modo "eco"
(llm.echo.EchoProvider) no llama a ningún modelo: repite tal cual el último
mensaje, sin ese contexto — el modo eco existe para que Rem diga
exactamente lo que se escribió (probar TTS/RVC/lipsync/avatar de punta a
punta sin gastar tokens ni depender de que haya red o API key), así que
anteponerlo por defecto contradiría el propósito. --depurar-contexto-eco
lo fuerza de vuelta si hace falta ver ese bloque sin gastar tokens de un
LLM real.

El pipeline de voz (TTS -> RVC -> enviar_audio) vive en habla.py y el turno
de LLM en chat_sesion.procesar_turno() — compartidos con el panel de chat de
rem_chat.py (vía rem_avatar_server.py). _chat(), más abajo, es apenas un
envoltorio que imprime en consola sobre esa función compartida (solo modo
standalone; en modo cliente el turno lo corre el servidor).
"""

import argparse
import asyncio
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import config
import rem_avatar_server
from rem_avatar_server import HTTP_PORT, WS_PORT, ESTADOS_VALIDOS

URL_AVATAR = f"http://localhost:{HTTP_PORT}/rem_avatar.html"
WS_URI = f"ws://127.0.0.1:{WS_PORT}"
ESPERA_HTTP_S = 5.0     # tiempo máximo para que el servidor HTTP responda antes de --open


def log(msg):
    print(f"  {msg}", flush=True)


def _esperar_http(timeout=ESPERA_HTTP_S):
    t_limite = time.time() + timeout
    while time.time() < t_limite:
        try:
            urllib.request.urlopen(URL_AVATAR, timeout=1.0)
            return True
        except urllib.error.URLError:
            time.sleep(0.2)
    return False


def _abrir_navegador():
    if not _esperar_http():
        log(f"el servidor HTTP no respondió a tiempo — igual intento abrir {URL_AVATAR}")
    webbrowser.open(URL_AVATAR)
    log(f"abriendo {URL_AVATAR} en el navegador por defecto")


# SesionChat/MODOS_VALIDOS/procesar_turno() viven en chat_sesion.py —
# compartidos con el panel de chat de rem_chat.py (vía
# rem_avatar_server.obtener_sesion_chat()), ver ese módulo para el porqué.
# El REPL usa la sesión COMPARTIDA (ver repl()), no una instancia propia —
# así "modo ia|eco" acá y el selector del panel HTML actualizan el mismo
# estado, sin importar cuál de los dos lo disparó.


async def _chat(sesion, texto, memoria_larga, memoria_sistema, cola_habla=None,
                 incluir_contexto=True):
    """Envoltorio de consola sobre chat_sesion.procesar_turno() (SOLO modo
    standalone): imprime cada fragmento en stdout a medida que llega
    (on_delta), muestra las tool_calls que aparezcan, y al final el resumen
    ([done] + tiempo de respuesta si hubo voz) — el turno en sí (historial,
    contexto dinámico, sentence-splitting hacia voz) lo hace la función
    compartida con el panel de chat de rem_chat.py, no una copia propia acá."""
    from chat_sesion import procesar_turno
    print("Rem> ", end="", flush=True)

    def _imprimir(fragmento):
        print(fragmento, end="", flush=True)

    def _imprimir_tool_call(call):
        print(f"\n  [tool_call] {call.name}({call.arguments}) id={call.id}")

    texto_completo, done_chunk, turno_habla = await procesar_turno(
        sesion, texto, memoria_larga, memoria_sistema,
        on_delta=_imprimir, on_tool_call=_imprimir_tool_call,
        cola_habla=cola_habla, incluir_contexto=incluir_contexto,
    )

    print()
    if done_chunk:
        print(f"  [done] reason={done_chunk.reason} usage={done_chunk.usage}")
    if turno_habla is not None:
        log(f"tiempo total de la respuesta (hasta el done): {time.perf_counter() - turno_habla.t_inicio:.2f}s")

    return texto_completo


def _imprimir_ayuda():
    print()
    print(f"  Abrí {URL_AVATAR} en un navegador normal para ver el avatar (o usá el comando 'open').")
    print()
    print("  Comandos:")
    print("    chat <texto>       — manda <texto> al modo activo, respuesta en streaming")
    print("    modo                — muestra el modo activo (ia/eco)")
    print("    modo ia|eco          — cambia de modo en caliente, sin reiniciar")
    print("    voz on|off          — activa/desactiva hablar la respuesta (lipsync+RVC+avatar)")
    print("    reset                — limpia el historial de la conversación")
    print(f"    state <estado>    — manda ese estado ({'/'.join(sorted(ESTADOS_VALIDOS))})")
    print("    open               — abre el avatar en el navegador por defecto")
    print("    quit                 — cierra limpiamente (o Ctrl+D / Ctrl+C)")
    print()


async def _leer_linea(prompt):
    loop = asyncio.get_running_loop()
    return (await loop.run_in_executor(None, input, prompt)).strip()


# ─── Modo STANDALONE: bench_chat.py levantó el servidor él mismo ──────
async def repl_standalone(args):
    import habla  # solo hace falta acá — el modo cliente no toca RVC/TTS
    _imprimir_ayuda()
    # Sesión COMPARTIDA con el panel de chat de rem_chat.py (si algo más en
    # este proceso lo levanta) — no una SesionChat propia del REPL. Misma
    # razón para la memoria: un snapshot al arrancar, el MISMO que usaría el panel.
    sesion, memoria_larga, memoria_sistema = rem_avatar_server.obtener_sesion_chat()
    voz_activa = False

    # Cola/worker de voz PROPIOS del REPL — el panel de chat de rem_chat.py
    # tiene los suyos (ver rem_avatar_server.py), no se comparten (cada uno
    # habla lo que se le pidió a ÉL, ver CLAUDE.md "Voz en la ventana de chat").
    cola_habla: asyncio.Queue = asyncio.Queue()
    worker_habla = asyncio.create_task(habla.worker_habla(cola_habla, not args.no_rvc))

    try:
        while True:
            try:
                linea = await _leer_linea("bench_chat> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not linea:
                continue
            comando, _, resto = linea.partition(" ")
            comando, resto = comando.lower(), resto.strip()

            if comando == "quit":
                break

            elif comando == "chat":
                if not resto:
                    log("uso: chat <texto>")
                    continue
                # En modo eco no hace falta el contexto dinámico (Rem lo
                # repetiría en voz alta). --depurar-contexto-eco lo fuerza.
                incluir_contexto = sesion.modo != "eco" or args.depurar_contexto_eco
                try:
                    await _chat(
                        sesion, resto, memoria_larga, memoria_sistema,
                        cola_habla=cola_habla if voz_activa else None,
                        incluir_contexto=incluir_contexto,
                    )
                except Exception as e:
                    log(f"error: {e}")

            elif comando == "modo":
                valor = resto.lower()
                if not valor:
                    log(f"modo activo: {sesion.modo}")
                    continue
                try:
                    # cambiar_modo_chat() avisa por WebSocket a cualquier panel
                    # conectado — así el selector del panel queda sincronizado.
                    if rem_avatar_server.cambiar_modo_chat(valor):
                        log(f"modo -> {sesion.modo} (historial limpiado)")
                    else:
                        log(f"ya estaba en modo {sesion.modo}")
                except ValueError as e:
                    log(f"{e} (uso: modo ia|eco)")
                except Exception as e:
                    log(f"no se pudo cambiar a modo {valor!r}: {e}")

            elif comando == "voz":
                valor = resto.lower()
                if valor not in ("on", "off"):
                    log("uso: voz on|off")
                    continue
                voz_activa = (valor == "on")
                log(f"voz -> {'activada' if voz_activa else 'desactivada'}")

            elif comando == "reset":
                sesion.historial.clear()
                log("historial limpiado")

            elif comando == "state":
                estado = resto.lower()
                if estado not in ESTADOS_VALIDOS:
                    log(f"estado inválido. usar uno de: {', '.join(sorted(ESTADOS_VALIDOS))}")
                    continue
                enviar_estado_o_avisa(estado)

            elif comando == "open":
                _abrir_navegador()

            else:
                log(f"comando desconocido: {comando!r} (usa chat / modo / voz / reset / state / open / quit)")
    finally:
        cola_habla.put_nowait(None)  # deja terminar lo ya encolado (hasta 5s)
        try:
            await asyncio.wait_for(worker_habla, timeout=5.0)
        except asyncio.TimeoutError:
            worker_habla.cancel()


def enviar_estado_o_avisa(estado):
    """enviar_estado() con aviso explícito si no llegó a nadie — modo standalone,
    donde el avatar puede no estar abierto (rem_avatar_server ya loguea, pero
    esto lo pone también en el prompt del REPL). Devuelve el nº de clientes, o
    None si fueron 0."""
    n = rem_avatar_server.enviar_estado(estado)
    if n:
        log(f"estado -> {estado}  ({n} cliente{'s' if n != 1 else ''})")
        return n
    log(f"estado -> {estado}  — NADIE conectado al avatar (abrí rem_chat.py para verlo)")
    return None


# ─── Modo CLIENTE: ya hay un servidor; bench_chat.py se conecta por WS ──
async def repl_cliente(args):
    import websockets
    _imprimir_ayuda()
    log(f"servidor de avatar detectado — conectando como cliente WS a {WS_URI}")
    try:
        ws = await websockets.connect(WS_URI, open_timeout=5)
    except Exception as e:
        log(f"no se pudo conectar al WebSocket ({e}) — ¿el servidor sigue vivo?")
        return
    log("conectado. 'chat', 'state', 'modo', 'voz' y 'reset' van al servidor "
        "(la ventana de rem_chat.py los ve).")

    modo_actual = ["(desconocido)"]
    turno_hecho = asyncio.Event()
    turno_hecho.set()

    async def _escuchar():
        try:
            async for crudo in ws:
                try:
                    d = json.loads(crudo)
                except (json.JSONDecodeError, TypeError):
                    continue
                t = d.get("tipo") if isinstance(d, dict) else None
                if t == "chat_delta":
                    print(d.get("texto", ""), end="", flush=True)
                elif t == "chat_done":
                    print()
                    turno_hecho.set()
                elif t == "error":
                    print()
                    log(f"error del servidor: {d.get('mensaje')}")
                    turno_hecho.set()
                elif t == "modo_actual":
                    modo_actual[0] = d.get("modo", "?")
                    log(f"modo -> {modo_actual[0]}")
                # 'estado'/'audio' se ignoran: es el REPL, no un renderer
        except websockets.ConnectionClosed:
            pass
        finally:
            turno_hecho.set()

    listener = asyncio.create_task(_escuchar())

    async def _enviar(payload):
        try:
            await ws.send(json.dumps(payload))
            return True
        except websockets.ConnectionClosed:
            log("la conexión con el servidor se cerró — el mensaje no se envió")
            return False

    try:
        while True:
            try:
                linea = await _leer_linea("bench_chat(cliente)> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not linea:
                continue
            if listener.done():
                log("el servidor cerró la conexión — saliendo")
                break
            comando, _, resto = linea.partition(" ")
            comando, resto = comando.lower(), resto.strip()

            if comando == "quit":
                break

            elif comando == "chat":
                if not resto:
                    log("uso: chat <texto>")
                    continue
                turno_hecho.clear()
                if await _enviar({"tipo": "chat_message", "texto": resto}):
                    print("Rem> ", end="", flush=True)
                    try:
                        await asyncio.wait_for(turno_hecho.wait(), timeout=120)
                    except asyncio.TimeoutError:
                        print()
                        log("timeout esperando la respuesta del servidor")

            elif comando == "modo":
                if not resto:
                    log(f"modo activo (según el servidor): {modo_actual[0]}")
                    continue
                await _enviar({"tipo": "cambiar_modo", "modo": resto.lower()})

            elif comando == "voz":
                valor = resto.lower()
                if valor not in ("on", "off"):
                    log("uso: voz on|off")
                    continue
                if await _enviar({"tipo": "voz", "activa": valor == "on"}):
                    log(f"voz del panel -> {valor}")

            elif comando == "reset":
                if await _enviar({"tipo": "reset"}):
                    log("reset enviado al servidor")

            elif comando == "state":
                estado = resto.lower()
                if estado not in ESTADOS_VALIDOS:
                    log(f"estado inválido. usar uno de: {', '.join(sorted(ESTADOS_VALIDOS))}")
                    continue
                if await _enviar({"tipo": "estado", "estado": estado}):
                    log(f"estado -> {estado}  (enviado al servidor)")

            elif comando == "open":
                _abrir_navegador()

            else:
                log(f"comando desconocido: {comando!r} (usa chat / modo / voz / reset / state / open / quit)")
    finally:
        listener.cancel()
        try:
            await ws.close()
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-rvc", action="store_true", help="'voz' salta la conversión RVC (solo modo standalone)")
    p.add_argument("--open", action="store_true", help="abre el navegador automáticamente al arrancar")
    p.add_argument("--depurar-contexto-eco", action="store_true",
                    help="incluye el contexto dinámico (fecha/hora/estado de la PC) también en "
                         "modo eco — apagado por defecto, solo para depurar ese bloque sin gastar "
                         "tokens de un LLM real")
    args = p.parse_args()

    if not sys.executable.replace("\\", "/").endswith("venv/bin/python"):
        log("ADVERTENCIA: ejecuta con venv/bin/python bench_chat.py")

    config.cargar_dotenv()

    # ¿Ya hay un servidor de avatar corriendo (rem_chat.py, u otra instancia)?
    # Se prueba el puerto HTTP, no el WS: el ThreadingHTTPServer tolera un
    # connect pelado sin quejarse, el server de websockets loguea un traceback
    # feo por cada probe. Si el HTTP está, el WS también (van juntos).
    if rem_avatar_server._puerto_activo("127.0.0.1", HTTP_PORT):
        print("Servidor de avatar ya corriendo — bench_chat.py arranca en modo CLIENTE.")
        if args.open:
            _abrir_navegador()
        try:
            asyncio.run(repl_cliente(args))
        finally:
            print("\nCerrando...")
        return

    # No hay servidor: lo levanta este proceso y corre autocontenido.
    print("No hay servidor de avatar — bench_chat.py arranca en modo STANDALONE.")
    if not args.no_rvc:
        # Antes de levantar el servidor, para solaparse con ese arranque (ver
        # CLAUDE.md, "Precarga de RVC y fin de la recarga del .pth en cada frase").
        import habla
        threading.Thread(target=habla.precargar_rvc, daemon=True).start()

    print("Levantando servidor del avatar (HTTP :18765, WS :18766)...")
    rem_avatar_server.iniciar_servidor_avatar()

    if args.open:
        _abrir_navegador()

    try:
        asyncio.run(repl_standalone(args))
    finally:
        print("\nCerrando...")


if __name__ == "__main__":
    main()
