"""tokens_contexto.py — presupuesto de contexto del LLM local (num_ctx) y
contador de tokens.

Por qué existe: cuando el turno no cabe en num_ctx, Ollama recorta por su
cuenta — conserva el system pero descarta los mensajes MÁS VIEJOS, y los más
viejos son los ejemplos de tono (verificado 2026-11-05: con 40 pares de
relleno el modelo recordaba el secreto del system y había perdido el del
primer ejemplo). Además llena hasta el borde sin dejar sitio a la respuesta.
Así que el recorte lo hacemos antes nosotros: se quitan turnos viejos del
historial, en pares user/assistant, y nunca el system, las tools, los
ejemplos ni la memoria larga.

Dos partes:

- PresupuestoContexto (en cada turno, SIN llamadas extra al modelo): Ollama
  no tiene /api/tokenize, y tokenizar con otra petición evicta la caché KV
  (el turno siguiente volvería a evaluar el prefijo entero). En su lugar:
    * el costo del prefijo fijo sale EXACTO del prompt_eval_count de la
      respuesta anterior (Ollama lo informa contando también lo cacheado),
      menos lo estimado para el historial que se mandó;
    * el historial se estima por caracteres, con una razón chars/token que se
      recalibra con cada respuesta (largo del texto / eval_count).
  Cada turno loguea lo estimado contra lo real.

- contar_exacto() / CLI: el tokenizador real del modelo vía una petición
  /api/generate en modo raw. Para medir prompts y tools a mano
  (`venv/bin/python tokens_contexto.py`); nunca se usa dentro de un turno.
"""
import json
import uuid

# <|im_start|>rol\n ... <|im_end|>\n alrededor de cada mensaje (plantilla de Qwen).
SOBRECARGA_MENSAJE = 5
# Lo que se reserva para la respuesta: Yoru contesta en 1-4 frases (~20-120 tok);
# 400 deja sitio también a una tool call con sus argumentos.
MARGEN_RESPUESTA = 400
# Histéresis: cuando hay que recortar, se recorta hasta dejar además este
# hueco libre. Quitar el turno más viejo cambia todo lo que viene detrás de
# los ejemplos, así que Ollama reevalúa el historial entero (medido: ~0,8 s ->
# ~2 s por turno si se recorta un par en cada turno). Con el hueco, la caché
# se rompe una vez cada varios turnos en vez de en todos.
HISTERESIS = 600
# Razón inicial chars/token, medida con el tokenizador real sobre el system
# prompt (3,31) y los ejemplos de Yoru (3,13), en español. Se recalibra con cada respuesta.
RAZON_INICIAL = 3.2


def _estimar_texto(texto: str, razon: float) -> int:
    return int(len(texto) / razon) + 1


class PresupuestoContexto:
    """Estado del presupuesto de UNA sesión de chat (se descarta al cambiar de
    modo/provider). Sin hilos: lo usa procesar_turno() de a un turno por vez."""

    def __init__(self, num_ctx: int, margen: int = MARGEN_RESPUESTA, histeresis: int = HISTERESIS):
        self.num_ctx = num_ctx
        self.margen = margen
        self.histeresis = histeresis
        self._chars = 0      # acumulados de las respuestas medidas (calibración)
        self._tokens = 0
        # Costo exacto del prefijo fijo por combinación de system/tools/prefijo:
        # la tool retry sin tools o un cambio de memoria cambian el prefijo.
        self._prefijo: dict[tuple, int] = {}
        self.ultima_estimacion: int | None = None

    @property
    def razon(self) -> float:
        # Pocas muestras al principio: se mezcla con la razón inicial (como
        # 300 tokens de "experiencia previa") para no saltar con la 1.ª frase.
        return (self._chars + RAZON_INICIAL * 300) / (self._tokens + 300)

    @staticmethod
    def _clave(system: str, prefijo, tools) -> tuple:
        return (hash(system), tuple(t.name for t in tools or ()),
                hash(tuple(m.content for m in prefijo)))

    def estimar_mensajes(self, mensajes) -> int:
        r = self.razon
        return sum(_estimar_texto(m.content, r) + SOBRECARGA_MENSAJE for m in mensajes)

    def _estimar_prefijo(self, system, prefijo, tools) -> int:
        clave = self._clave(system, prefijo, tools)
        if clave in self._prefijo:
            return self._prefijo[clave]
        # Sin medición todavía (primer turno con este prefijo): por caracteres.
        # Las tools van como JSON dentro del bloque system de la plantilla.
        r = self.razon
        tools_json = json.dumps([{"name": t.name, "description": t.description,
                                  "parameters": t.parameters} for t in tools or ()],
                                ensure_ascii=False)
        return (_estimar_texto(system, r) + _estimar_texto(tools_json, r) * (1 if tools else 0)
                + self.estimar_mensajes(prefijo) + 3 * SOBRECARGA_MENSAJE)

    def estimar_turno(self, system, prefijo, tools, historial, extra_ultimo: str = "") -> int:
        """Tokens de prompt que ocupará el turno (lo que Ollama informará como
        prompt_eval_count). `extra_ultimo`: texto que se pega solo al último
        mensaje en este turno (el contexto dinámico) y no está en `historial`."""
        total = self._estimar_prefijo(system, prefijo, tools) + self.estimar_mensajes(historial)
        if extra_ultimo:
            total += _estimar_texto(extra_ultimo, self.razon)
        return total

    def recortar(self, historial: list, system, prefijo, tools, extra_ultimo: str = "") -> int:
        """Quita del PRINCIPIO de `historial` (en el sitio) turnos completos
        —un mensaje de usuario y las respuestas que le siguen— hasta que el
        turno + el margen de respuesta quepa en num_ctx. Nunca quita el último
        mensaje (el que se está contestando). Una vez que hay que recortar, sigue
        hasta dejar también `histeresis` tokens libres (ver HISTERESIS).
        Devuelve cuántos mensajes quitó."""
        quitados = 0
        limite = self.num_ctx - self.margen
        while True:
            total = self.estimar_turno(system, prefijo, tools, historial, extra_ultimo)
            objetivo = limite - self.histeresis if quitados else limite
            if total <= objetivo or len(historial) <= 1:
                break
            del historial[0]
            quitados += 1
            # El resto del turno: las respuestas de ese mensaje (normalmente una).
            while len(historial) > 1 and historial[0].role != "user":
                del historial[0]
                quitados += 1
        self.ultima_estimacion = total
        if quitados:
            print(f"  [Contexto] recorte: {quitados} mensajes viejos fuera del historial "
                  f"({len(historial)} quedan) — estimado {total} + margen {self.margen} "
                  f"+ histéresis {self.histeresis} "
                  f"<= num_ctx {self.num_ctx}", flush=True)
        if total + self.margen > self.num_ctx:
            print(f"  [Contexto] AVISO: aun sin historial el turno ocupa ~{total} tok "
                  f"(+{self.margen} de margen > {self.num_ctx}); Ollama recortará", flush=True)
        return quitados

    def calibrar(self, prompt_eval_count, eval_count, texto_respuesta: str,
                 system, prefijo, tools, historial_enviado, extra_ultimo: str = "") -> None:
        """Tras el turno: fija el costo exacto del prefijo con el
        prompt_eval_count real y recalibra la razón chars/token con la
        respuesta generada. `historial_enviado` es la lista que se mandó (sin
        el prefijo), tal como estaba en ESE momento."""
        if not prompt_eval_count:
            return
        estimado = self.ultima_estimacion
        if eval_count and eval_count > 3 and texto_respuesta:
            # eval_count incluye el token de fin (<|im_end|>).
            self._chars += len(texto_respuesta)
            self._tokens += eval_count - 1
        hist = self.estimar_mensajes(historial_enviado)
        if extra_ultimo:
            hist += _estimar_texto(extra_ultimo, self.razon)
        self._prefijo[self._clave(system, prefijo, tools)] = prompt_eval_count - hist
        if estimado is not None:
            print(f"  [Contexto] prompt estimado {estimado} tok, real {prompt_eval_count} "
                  f"(error {estimado - prompt_eval_count:+d}) | razón {self.razon:.2f} chars/tok",
                  flush=True)


# ── Contador exacto (CLI / mediciones a mano, nunca dentro de un turno) ──────

def _modelo_y_url():
    import config
    cfg = config.leer_config_toml().get("llm", {}).get("ollama", {})
    return (cfg.get("model", "hf.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive:Q4_K_M"),
            cfg.get("base_url", "http://127.0.0.1:11434").rstrip("/"),
            cfg.get("num_ctx", 4096), cfg.get("num_gpu"))


def _opciones(num_ctx, num_gpu):
    # Mismas opciones de carga que la app: si difieren, Ollama recarga el modelo.
    o = {"num_predict": 1, "num_ctx": num_ctx}
    if num_gpu is not None:
        o["num_gpu"] = num_gpu
    return o


def contar_exacto(texto: str) -> int:
    """Tokens de `texto` con el tokenizador real del modelo de config.toml.
    Un nonce distinto al principio de cada petición evita que la caché de
    Ollama sesgue nada; se resta el costo del nonce solo."""
    import httpx
    modelo, url, num_ctx, num_gpu = _modelo_y_url()

    def _n(t):
        r = httpx.post(f"{url}/api/generate", timeout=300, json={
            "model": modelo, "prompt": t, "raw": True, "stream": False,
            "keep_alive": "10m", "options": _opciones(num_ctx, num_gpu)})
        r.raise_for_status()
        return r.json()["prompt_eval_count"]

    return _n(f"Z{uuid.uuid4().hex[:6]}\n{texto}") - _n(f"Z{uuid.uuid4().hex[:6]}\n")


def contar_chat(system: str, mensajes: list[dict], tools=None) -> int:
    """prompt_eval_count exacto de una petición /api/chat (con la plantilla
    real: roles, tools en el bloque system, cabecera de respuesta)."""
    import httpx
    modelo, url, num_ctx, num_gpu = _modelo_y_url()
    body = {"model": modelo, "stream": False, "think": False, "keep_alive": "10m",
            "options": _opciones(num_ctx, num_gpu),
            "messages": [{"role": "system", "content": system}] + mensajes}
    if tools:
        body["tools"] = [{"type": "function", "function": {
            "name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools]
    r = httpx.post(f"{url}/api/chat", json=body, timeout=300)
    r.raise_for_status()
    return r.json()["prompt_eval_count"]


def informe() -> None:
    """Desglose del prefijo fijo de la ventana: system, ejemplos, cada tool."""
    import acciones
    import personalidad
    from ejemplos_tono import EJEMPLOS_TONO

    system = personalidad.construir_prompt_sistema()
    hola = [{"role": "user", "content": "hola"}]
    tools = acciones.tools_disponibles("ventana")
    base = contar_chat(system, hola)
    con_ej = contar_chat(system, list(EJEMPLOS_TONO) + hola)
    con_tools = contar_chat(system, list(EJEMPLOS_TONO) + hola, tools)
    print(f"system prompt (texto solo):      {contar_exacto(system)} tok")
    print(f"system + 'hola' (plantilla):     {base} tok")
    print(f"+ ejemplos de tono ({len(EJEMPLOS_TONO) // 2} pares):  {con_ej} (+{con_ej - base})")
    print(f"+ tools de ventana ({len(tools)}):        {con_tools} (+{con_tools - con_ej})")
    num_ctx = _modelo_y_url()[2]
    print(f"libre para historial+respuesta:  {num_ctx - con_ej} sin tools / "
          f"{num_ctx - con_tools} con tools, de {num_ctx}")
    print("  (cada tool sola, con la cabecera fija de la plantilla incluida:)")
    for t in tools:
        print(f"  tool {t.name:22s} {contar_chat(system, hola, [t]) - base:4d} tok")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for ruta in sys.argv[1:]:
            with open(ruta, encoding="utf-8") as f:
                print(f"{ruta}: {contar_exacto(f.read().strip())} tok")
    else:
        informe()
