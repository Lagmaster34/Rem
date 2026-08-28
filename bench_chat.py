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
"""

import argparse
import asyncio
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import numpy as np
import soundfile as sf
import sounddevice as sd
from scipy import signal as sps

import config
import lipsync
import personalidad
from llm import Done, Message, TextDelta, ToolCallChunk, dividir_en_oraciones, get_provider
from llm.echo import EchoProvider
from rem_avatar_server import (
    HTTP_PORT, TMP_AUDIO_DIR, iniciar_avatar, cerrar_avatar, enviar_audio,
    enviar_estado, ESTADOS_VALIDOS,
)

BASE = os.path.dirname(os.path.abspath(__file__))
URL_AVATAR = f"http://localhost:{HTTP_PORT}/rem_avatar.html"

ESPERA_CLIENTE_S = 8.0  # tiempo máximo para que un cliente WS conecte antes del fallback local
ESPERA_HTTP_S = 5.0     # tiempo máximo para que el servidor HTTP responda antes de --open

_rvc_cache = None
# Protege tanto la carga de RVC (_obtener_rvc) como cada conversión
# (generate_from_cache): BaseLoader no es thread-safe entre llamadas
# concurrentes — self.cache_model/self.model_vc/self.model_pitch_estimator se
# leen y escriben sin lock propio, así que dos conversiones a la vez (el hilo
# de precarga y un turno con voz llegando antes de que termine) pueden verse
# ambas con el cache todavía vacío y recargar el .pth y el rmvpe por
# duplicado — visto en vivo antes de agregar este lock.
_rvc_lock = threading.Lock()


def log(msg):
    print(f"  {msg}", flush=True)


def cargar_rvc(pitch=4, index_influence=0.75):
    from infer_rvc_python import BaseLoader
    dispositivo = config.leer_dispositivo_rvc()
    rmvpe = os.path.join(BASE, "rmvpe.pt")
    rvc = BaseLoader(only_cpu=(dispositivo == "cpu"), rmvpe_path=rmvpe)
    rvc.apply_conf(
        tag="rem",
        file_model=os.path.join(BASE, "models", "Rem_600e_6600s", "Rem_600e_6600s.pth"),
        pitch_algo="rmvpe",
        pitch_lvl=pitch,
        file_index=os.path.join(BASE, "models", "Rem_600e_6600s", "Rem.index"),
        index_influence=index_influence,
        respiration_median_filtering=3,
        envelope_ratio=0.25,
        consonant_breath_protection=0.33,
        resample_sr=0,
    )
    return rvc, dispositivo


def _obtener_rvc():
    """Carga RVC si hace falta y devuelve la instancia cacheada. Con lock
    porque ahora hay dos llamadores concurrentes posibles: el hilo de
    precarga (_precargar_rvc, lanzado al arrancar) y _decir() si el usuario
    llega a pedir voz antes de que la precarga termine — sin el lock, ambos
    podrían ver _rvc_cache en None a la vez y cargar el modelo dos veces."""
    global _rvc_cache
    with _rvc_lock:
        if _rvc_cache is None:
            log("cargando RVC...")
            t0 = time.perf_counter()
            _rvc_cache = cargar_rvc()
            rvc, dispositivo = _rvc_cache
            log(f"RVC listo en {time.perf_counter() - t0:.1f}s ({dispositivo})")
        return _rvc_cache


def _convertir_rvc(rvc, tmp_wav):
    """generate_from_cache() bajo el mismo lock que _obtener_rvc() — ver el
    comentario de _rvc_lock más arriba sobre por qué hace falta serializar
    también las conversiones, no solo la carga inicial."""
    with _rvc_lock:
        return rvc.generate_from_cache(audio_data=tmp_wav, tag="rem")


def _preparar_wav_16k(audio_mp3, tmp_mp3, tmp_wav):
    """mp3 de edge-tts -> wav mono 16kHz, el formato que espera RVC. Comparte
    esta conversión _decir() (una oración real) y _precargar_rvc() (la
    oración de calentamiento) para no duplicarla."""
    with open(tmp_mp3, "wb") as f:
        f.write(audio_mp3)
    audio, sr_ = sf.read(tmp_mp3)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr_ != 16000:
        audio = sps.resample(audio, int(round(len(audio) * 16000 / sr_)))
        sr_ = 16000
    sf.write(tmp_wav, audio.astype(np.float32), sr_)


def _precargar_rvc():
    """Carga RVC y lo deja "caliente" con una conversión de calentamiento
    descartada, en un hilo de fondo lanzado al arrancar (ver main()) — para
    que el primer 'chat'/'say' real no pague ni la carga del modelo (~4-6s)
    ni el costo extra de la primera conversión en frío (kernels CUDA sin
    compilar/cachear todavía). Todo lo que toca (log/print, nada de estado
    compartido con el REPL) es seguro de llamar desde un hilo aparte."""
    tmp_mp3 = os.path.join(TMP_AUDIO_DIR, "_precarga_rvc.mp3")
    tmp_wav = os.path.join(TMP_AUDIO_DIR, "_precarga_rvc.wav")
    try:
        rvc, dispositivo = _obtener_rvc()
        t0 = time.perf_counter()
        audio_mp3, _ = asyncio.run(lipsync.sintetizar_con_timings("Hola."))
        _preparar_wav_16k(audio_mp3, tmp_mp3, tmp_wav)
        _convertir_rvc(rvc, tmp_wav)
        log(f"calentamiento RVC listo en {time.perf_counter() - t0:.2f}s ({dispositivo}) — RVC caliente para el primer chat")
    except Exception as e:
        log(f"precarga de RVC falló, no bloqueante ({e})")
    finally:
        for tmp in (tmp_mp3, tmp_wav):
            try:
                os.remove(tmp)
            except OSError:
                pass


async def _decir(texto, usar_rvc):
    """Sintetiza una oración y la manda al avatar — mismo pipeline que
    bench.py (lipsync -> RVC opcional -> enviar_audio, con fallback local a
    sounddevice si no hay cliente WS conectado). La conversión RVC corre en
    un hilo aparte (asyncio.to_thread): es una llamada bloqueante, y si
    corriera en el loop principal frenaría también al productor (_chat()
    consumiendo el stream del LLM para la siguiente oración) — justo lo que
    se quiere solapar. Devuelve True si el audio se entregó (por WS o local),
    para que el llamador pueda medir "tiempo hasta el primer audio"."""
    log(f'hablando: "{texto}"')
    audio_mp3, palabras = await lipsync.sintetizar_con_timings(texto)
    timeline = lipsync.construir_timeline(palabras)

    uid = int(time.time() * 1000)
    tmp_mp3 = os.path.join(TMP_AUDIO_DIR, f"bench_chat_tmp_{uid}.mp3")
    tmp_wav = os.path.join(TMP_AUDIO_DIR, f"bench_chat_tmp_{uid}.wav")
    tmp_wav_rvc = os.path.join(TMP_AUDIO_DIR, f"bench_chat_tmp_{uid}_rvc.wav")
    ruta_final = tmp_wav
    entregado = False

    try:
        _preparar_wav_16k(audio_mp3, tmp_mp3, tmp_wav)

        if usar_rvc:
            rvc, dispositivo = _obtener_rvc()
            t_rvc = time.perf_counter()
            try:
                # generate_from_cache() reusa net_g/index/pipe ya cargados en
                # la instancia (self.model_vc) en vez de releer el .pth y el
                # .index de disco en cada llamada, como sí hace __call__ (ver
                # CLAUDE.md, "Precarga de RVC y fin de la recarga del .pth en cada frase"). Además corre
                # infer() en el hilo actual (el de asyncio.to_thread), no en
                # un hilo interno que __call__ solo joinea sin propagar sus
                # excepciones — así que un fallo real de RVC (p.ej. un OOM de
                # CUDA) llega acá como excepción, en vez de volver una lista
                # vacía en silencio.
                audio_opt, sr_rvc = await asyncio.to_thread(_convertir_rvc, rvc, tmp_wav)
                sf.write(tmp_wav_rvc, audio_opt, sr_rvc)
                ruta_final = tmp_wav_rvc
                log(f"conversión RVC ({dispositivo}): {time.perf_counter() - t_rvc:.2f}s")
            except Exception as e:
                log(f"RVC falló ({e}) — hablando sin convertir (voz cruda de edge-tts)")

        enviado = enviar_audio(ruta_final, timeline)
        if not enviado:
            log(f"esperando cliente WS conectado (máx {ESPERA_CLIENTE_S:.0f}s)...")
            t_limite = time.time() + ESPERA_CLIENTE_S
            while time.time() < t_limite and not enviado:
                await asyncio.sleep(0.3)
                enviado = enviar_audio(ruta_final, timeline)

        if enviado:
            log("enviado por WebSocket — el avatar reproduce por su cuenta")
            entregado = True
        else:
            log("nadie conectado al WS — reproduciendo localmente con sounddevice")
            data, sr2 = sf.read(ruta_final)
            try:
                sd.play(data, sr2)
                sd.wait()
                entregado = True
            except sd.PortAudioError as e:
                log(f"no se pudo reproducir localmente ({e}) — revisa el dispositivo de audio por defecto")
    finally:
        for tmp in {tmp_mp3, tmp_wav, tmp_wav_rvc}:
            try:
                os.remove(tmp)
            except OSError:
                pass

    return entregado


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


class _TurnoHabla:
    """Timing de un turno con voz activada: cuánto tarda en sonar la primera
    oración frente a cuánto tarda la respuesta completa — la comparación que
    justifica solapar TTS+RVC con la generación en vez de esperar todo el
    texto antes de hablar."""
    def __init__(self):
        self.t_inicio = time.perf_counter()
        self.t_primer_audio = None

    def marcar_primer_audio(self):
        if self.t_primer_audio is None:
            self.t_primer_audio = time.perf_counter()
            log(f"primer audio enviado a los {self.t_primer_audio - self.t_inicio:.2f}s")


async def _pasar_por(chunks, on_chunk):
    """Deja pasar cada chunk tal cual, pero además llama on_chunk(chunk) al
    vuelo. Los async generators son de un solo consumidor — esto es lo que
    permite que _chat() imprima texto y registre Done/tool_calls mientras
    dividir_en_oraciones() consume el MISMO stream para extraer oraciones,
    sin tener que bifurcarlo de verdad."""
    async for chunk in chunks:
        on_chunk(chunk)
        yield chunk


async def _worker_habla(cola, usar_rvc):
    """Consume la cola de oraciones en orden, una por vez. Como _chat() encola
    cada oración en cuanto dividir_en_oraciones() la completa (sin esperar el
    resto de la respuesta), la conversión de la oración N+1 arranca apenas
    termina la N — mientras esa N ya está sonando en el frontend
    (enviar_audio() no espera a que termine de reproducirse, solo despacha).
    `None` en la cola es la señal de cierre."""
    while True:
        item = await cola.get()
        if item is None:
            cola.task_done()
            break
        oracion, estado = item
        try:
            entregado = await _decir(oracion, usar_rvc)
            if entregado and estado is not None:
                estado.marcar_primer_audio()
        except Exception as e:
            log(f"error hablando oración: {e}")
        cola.task_done()


MODOS_VALIDOS = ("ia", "eco")


class SesionChat:
    """Estado de una conversación: modo activo, provider y su historial.

    Agrupados acá (en vez de variables sueltas en repl(), como estaban antes)
    para que cambiar_modo() sea una función limpia y reusable — es el mismo
    mecanismo que va a usar el botón de la futura ventana de chat en React
    para alternar entre hablar con la IA de verdad y con el eco de prueba,
    no lógica pegada a este REPL en particular. repl() es el único que sabe
    de input()/print(); esta clase no.
    """

    def __init__(self, modo_inicial="ia"):
        self.modo = None
        self.provider = None
        self.historial: list[Message] = []
        self.cambiar_modo(modo_inicial)

    def cambiar_modo(self, modo):
        """Cambia el provider activo en caliente, sin reiniciar el proceso.
        Devuelve True si hubo un cambio real, False si ya estaba en ese modo
        (no-op: no pierde el historial por las dudas de un "modo ia"
        repetido — el llamador puede usar el valor de vuelta para no decir
        "historial limpiado" cuando no limpió nada). El historial no se
        mezcla entre modos: se limpia al cambiar — más simple que mantener
        dos historiales en paralelo, y evita que un modo arranque con
        contexto real de una conversación que tuvo el otro."""
        if modo not in MODOS_VALIDOS:
            raise ValueError(f"modo debe ser uno de {MODOS_VALIDOS}, no {modo!r}")
        if modo == self.modo:
            return False
        # get_provider() puede lanzar (p.ej. falta la API key del provider
        # configurado, ver llm/__init__.py) — se arma el provider nuevo ANTES
        # de tocar self.modo/self.historial, así que si falla la sesión queda
        # exactamente como estaba, no a mitad de cambio.
        nuevo_provider = EchoProvider() if modo == "eco" else get_provider()
        self.modo = modo
        self.provider = nuevo_provider
        self.historial = []
        return True


async def _chat(historial, texto, provider, memoria_larga, memoria_sistema, cola_habla=None,
                 incluir_contexto=True):
    """Manda `texto` al LLM vía stream_chat() y lo consume directo con
    `async for` — sin puente sync->async, ese es justo el punto de este
    script. Usa el mismo system prompt + contexto dinámico que preguntar_groq()
    en Rem.py (personalidad.py, compartido) — antes mandaba una personalidad
    de relleno inventada, no la real. Imprime TextDelta a medida que llegan y
    muestra las ToolCall que aparezcan.

    Si `cola_habla` no es None (voz activada), cada oración completa se
    encola para hablar (TTS+RVC+envío) apenas dividir_en_oraciones() la
    detecta — no se espera a que termine el resto de la respuesta.

    `incluir_contexto=False` (usado en modo eco, ver repl()) omite el bloque
    de fecha/hora/estado de la PC: ese bloque existe para informarle al LLM,
    y en modo eco no hay LLM — anteponerlo igual solo hace que Rem lea en
    voz alta el porcentaje de CPU, que no es lo que pide el modo eco (repetir
    tal cual lo que se escribió). El default sigue siendo True porque en modo
    ia el contexto real sí hace falta."""
    if incluir_contexto:
        contexto = personalidad.construir_contexto_dinamico(memoria_sistema)
        historial.append(Message(role="user", content=f"{contexto}\n{texto}"))
    else:
        historial.append(Message(role="user", content=texto))

    system = personalidad.construir_prompt_sistema(memoria_larga)
    estado = _TurnoHabla() if cola_habla is not None else None

    partes = []
    done_chunk = None

    def _on_chunk(chunk):
        nonlocal done_chunk
        if isinstance(chunk, TextDelta):
            print(chunk.text, end="", flush=True)
            partes.append(chunk.text)
        elif isinstance(chunk, ToolCallChunk):
            print(f"\n  [tool_call] {chunk.call.name}({chunk.call.arguments}) id={chunk.call.id}")
        elif isinstance(chunk, Done):
            done_chunk = chunk

    print("Rem> ", end="", flush=True)
    stream = provider.stream_chat(system, historial)
    async for oracion in dividir_en_oraciones(_pasar_por(stream, _on_chunk)):
        if cola_habla is not None:
            cola_habla.put_nowait((oracion, estado))

    print()
    if done_chunk:
        print(f"  [done] reason={done_chunk.reason} usage={done_chunk.usage}")
    if estado is not None:
        log(f"tiempo total de la respuesta (hasta el done): {time.perf_counter() - estado.t_inicio:.2f}s")

    texto_completo = "".join(partes)
    historial.append(Message(role="assistant", content=texto_completo))
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
    sesion = SesionChat(modo_inicial="ia")
    voz_activa = False
    loop = asyncio.get_running_loop()

    # Snapshot al arrancar, igual que Rem.py al iniciar — no se actualiza
    # durante la sesión (bench_chat.py no tiene extraer_memoria_importante()),
    # pero da el mismo contexto real de personalidad/memoria que tiene Rem.
    memoria_larga = personalidad.cargar_memoria_larga()
    memoria_sistema = personalidad.cargar_memoria_sistema()

    # Cola persistente para toda la sesión: un solo worker la consume en
    # orden, así que "voz on/off" solo decide si _chat() encola algo, sin
    # tener que arrancar/parar el worker en cada toggle.
    cola_habla: asyncio.Queue = asyncio.Queue()
    worker_habla = asyncio.create_task(_worker_habla(cola_habla, not args.no_rvc))

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
                        sesion.historial, resto, sesion.provider, memoria_larga, memoria_sistema,
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
                    if sesion.cambiar_modo(valor):
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
        threading.Thread(target=_precargar_rvc, daemon=True).start()

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
