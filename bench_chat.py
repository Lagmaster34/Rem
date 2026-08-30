#!/usr/bin/env python3
"""bench_chat.py — REPL async nativo para la capa LLM (llm/) y para probar
lipsync/RVC/avatar, sin Tkinter ni GUI. No importa Rem.py (no se puede: el
Python 3.10.14 del venv se compiló sin _tkinter, y Tkinter va a desaparecer
del proyecto de todos modos) — es autocontenido, reusa lipsync.py y
rem_avatar_server.py directo.

Antes existía bench.py aparte para probar voz/lipsync/avatar con una frase
suelta, sin pasar por ningún LLM — el modo eco (ver más abajo) cubre
exactamente ese caso y más, así que bench.py se eliminó (ver CLAUDE.md,
"bench.py eliminado, absorbido por bench_chat.py + modo eco").

Es el precursor del backend que va a reemplazar a Tkinter: consume
provider.stream_chat() directo con `async for`, sin el puente sync->async de
_drenar_stream_llm() en Rem.py (ese puente existe solo porque responder() hoy
corre en un hilo nuevo por turno — acá no hace falta, todo el REPL vive en un
único asyncio.run()).

    venv/bin/python bench_chat.py
    venv/bin/python bench_chat.py --no-rvc      # 'voz' sin conversión RVC
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

El pipeline de voz (TTS -> RVC -> enviar_audio) vive en habla.py, compartido
con el panel de chat de rem_chat.py (vía rem_avatar_server.py) — no hay una
copia propia acá. Lo mismo el turno de LLM en sí (chat_sesion.procesar_turno()):
_chat(), más abajo, es apenas un envoltorio que imprime en consola sobre esa
función compartida.
"""

import argparse
import asyncio
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import config
import habla
import rem_avatar_server
from chat_sesion import procesar_turno
from rem_avatar_server import (
    HTTP_PORT, iniciar_avatar, cerrar_avatar,
    enviar_estado, ESTADOS_VALIDOS,
)

URL_AVATAR = f"http://localhost:{HTTP_PORT}/rem_avatar.html"
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
    """Envoltorio de consola sobre chat_sesion.procesar_turno(): imprime cada
    fragmento en stdout a medida que llega (on_delta), muestra las tool_calls
    que aparezcan, y al final el resumen ([done] + tiempo de respuesta si
    hubo voz) — el turno en sí (historial, contexto dinámico, sentence-
    splitting hacia voz) lo hace la función compartida con el panel de chat
    de rem_chat.py, no una copia propia acá."""
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


async def repl(args):
    _imprimir_ayuda()
    # Sesión COMPARTIDA con el panel de chat de rem_chat.py (si algo más en
    # este proceso lo levanta) — no una SesionChat propia del REPL. Misma
    # razón para la memoria: un snapshot al arrancar, igual que Rem.py, pero
    # el MISMO snapshot que usaría el panel, no una copia aparte.
    sesion, memoria_larga, memoria_sistema = rem_avatar_server.obtener_sesion_chat()
    voz_activa = False
    loop = asyncio.get_running_loop()

    # Cola persistente para toda la sesión: un solo worker la consume en
    # orden, así que "voz on/off" solo decide si _chat() encola algo, sin
    # tener que arrancar/parar el worker en cada toggle. Cola/worker PROPIOS
    # del REPL — el panel de chat de rem_chat.py tiene los suyos (ver
    # rem_avatar_server.py), no se comparten (cada uno habla lo que se le
    # pidió a ÉL, ver CLAUDE.md "Voz en la ventana de chat").
    cola_habla: asyncio.Queue = asyncio.Queue()
    worker_habla = asyncio.create_task(habla.worker_habla(cola_habla, not args.no_rvc))

    try:
        while True:
            try:
                linea = (await loop.run_in_executor(None, input, "bench_chat> ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not linea:
                continue

            comando, _, resto = linea.partition(" ")
            comando = comando.lower()
            resto = resto.strip()

            if comando == "quit":
                break

            elif comando == "chat":
                if not resto:
                    log("uso: chat <texto>")
                    continue
                # En modo eco no hay LLM que necesite el contexto dinámico
                # (fecha/hora/estado de la PC) — incluirlo igual solo hace
                # que Rem lo repita en voz alta. --depurar-contexto-eco lo
                # fuerza de vuelta si hace falta ver ese bloque sin gastar
                # tokens de un LLM real.
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
                    # cambiar_modo_chat() (no sesion.cambiar_modo() directo):
                    # además de cambiar el modo, avisa por WebSocket a
                    # cualquier panel de chat conectado — así el selector del
                    # panel queda sincronizado con lo que se escribe acá.
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
                enviar_estado(estado)
                log(f"estado -> {estado}")

            elif comando == "open":
                _abrir_navegador()

            else:
                log(f"comando desconocido: {comando!r} (usa chat / modo / voz / reset / state / open / quit)")
    finally:
        # Deja que las oraciones ya encoladas terminen de hablarse (hasta 5s)
        # en vez de cortarlas a mitad de camino al salir.
        cola_habla.put_nowait(None)
        try:
            await asyncio.wait_for(worker_habla, timeout=5.0)
        except asyncio.TimeoutError:
            worker_habla.cancel()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-rvc", action="store_true", help="'voz' salta la conversión RVC (más rápido)")
    p.add_argument("--open", action="store_true", help="abre el navegador automáticamente al arrancar")
    p.add_argument("--depurar-contexto-eco", action="store_true",
                    help="incluye el contexto dinámico (fecha/hora/estado de la PC) también en "
                         "modo eco — apagado por defecto, solo para depurar ese bloque sin gastar "
                         "tokens de un LLM real")
    args = p.parse_args()

    if not sys.executable.replace("\\", "/").endswith("venv/bin/python"):
        log("ADVERTENCIA: ejecuta con venv/bin/python bench_chat.py")

    config.cargar_dotenv()

    if not args.no_rvc:
        # Lanzada antes de iniciar_avatar() (HTTP/WS/overlay) para solaparse
        # con ese arranque en vez de sumarse después — para cuando el REPL
        # queda listo para el primer 'chat', RVC ya suele estar cargado y
        # calentado (ver CLAUDE.md, "Precarga de RVC y fin de la recarga del .pth en cada frase").
        threading.Thread(target=habla.precargar_rvc, daemon=True).start()

    print("Iniciando avatar (HTTP :18765, WS :18766, overlay GTK)...")
    iniciar_avatar()

    if args.open:
        _abrir_navegador()

    try:
        asyncio.run(repl(args))
    finally:
        print()
        print("Cerrando...")
        cerrar_avatar()


if __name__ == "__main__":
    main()
