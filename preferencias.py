"""preferencias.py — preferencias editables en vivo desde el panel de control.

Capa encima de config.toml: preferencias.json (ignorado por git) guarda SOLO
lo que se cambió en el panel; lo que no está ahí sale de config.toml, y lo que
tampoco está ahí, del default del código. Prioridad:

    preferencias.json  >  config.toml  >  default del código

Se lee por sección (`obtener("voz")`) y se escribe por parche
(`aplicar("voz", {"rate": "-10%"})`), validado contra ESQUEMA: un parche con
una clave desconocida o un valor inválido se rechaza ENTERO, sin tocar nada
(mismo criterio de atomicidad que SesionChat.cambiar_modo()). Un valor `None`
en el parche borra la preferencia y la sección vuelve al valor de config.toml.
Un valor igual al de config.toml tampoco se guarda: el JSON queda con lo que de
verdad difiere.

Lo leen varios hilos (worker de voz, precargas, loop del WS) y puede leerlo
otro proceso (bench_chat.py standalone): la cache del JSON se invalida por
mtime, y la escritura es atómica (tmp + os.replace) bajo un lock.

Quién aplica cada cambio: los consumidores que leen la preferencia en cada uso
(p. ej. habla.decir() vía config.leer_config_voz(), por frase) no necesitan
nada más. Los que hay que avisar (recargar el avatar, reconfigurar RVC...) se
registran con al_cambiar(seccion, callback).
"""
import copy
import json
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable

import config

ARCHIVO = os.path.join(config.BASE_DIR, "preferencias.json")


class PreferenciaInvalida(ValueError):
    """Parche rechazado: sección/clave desconocida o valor fuera de rango. El
    mensaje está pensado para mostrarse tal cual en el panel."""


# ── Validadores ─────────────────────────────────────────────────────────
_RE_VOZ = re.compile(r"^[a-z]{2,3}-[A-Z]{2}-[A-Za-z]+Neural$")
_RE_RATE = re.compile(r"^([+-])(\d{1,3})%$")


def _validar_voz(v):
    if not isinstance(v, str) or not _RE_VOZ.match(v):
        raise PreferenciaInvalida(f"voz inválida: {v!r} (formato es-VE-PaolaNeural)")
    return v


def _validar_rate(v):
    m = _RE_RATE.match(v) if isinstance(v, str) else None
    if not m or int(m.group(2)) > 50:
        raise PreferenciaInvalida(f"rate inválido: {v!r} (entre -50% y +50%, p. ej. -8%)")
    return v


def _validar_vrm(v):
    """Ruta relativa a la raíz del proyecto, a un .vrm que exista y no se salga
    de ella (el HTTP sirve BASE_DIR entero, pero esta ruta además se escribe en
    disco y se le pasa al avatar: nada de '..' ni rutas absolutas)."""
    if not isinstance(v, str) or not v.lower().endswith(".vrm") or os.path.isabs(v):
        raise PreferenciaInvalida(f"modelo inválido: {v!r} (ruta relativa a un .vrm)")
    real = os.path.realpath(os.path.join(config.BASE_DIR, v))
    if os.path.commonpath([real, config.BASE_DIR]) != config.BASE_DIR:
        raise PreferenciaInvalida(f"modelo fuera del proyecto: {v!r}")
    if not os.path.isfile(real):
        raise PreferenciaInvalida(f"no existe el modelo: {v!r}")
    return v


@dataclass(frozen=True)
class Campo:
    validar: Callable[[Any], Any]
    base: Callable[[], Any]   # valor de config.toml (o default del código)


def _lipsync():
    import lipsync  # perezoso: arrastra edge_tts
    return lipsync


def _toml(seccion, clave, default):
    valor = config.leer_config_toml().get(seccion, {}).get(clave, default)
    return str(valor).strip() or default


# Cada pestaña del panel añade aquí su sección cuando se implemente. Las bases
# leen config.toml directo, no los config.leer_*() — esos ya devuelven el valor
# EFECTIVO (con estas preferencias encima) y sería circular.
ESQUEMA: dict[str, dict[str, Campo]] = {
    "voz": {
        "voz": Campo(_validar_voz, lambda: _toml("voz", "voz", _lipsync().VOZ_DEFAULT)),
        "rate": Campo(_validar_rate, lambda: _toml("voz", "rate", _lipsync().RATE_DEFAULT)),
    },
    "modelo": {
        "vrm": Campo(_validar_vrm, lambda: _toml("avatar", "modelo", "rem.vrm")),
    },
}


# ── Estado: el contenido de preferencias.json, cacheado por mtime ───────
_lock = threading.Lock()
_cache: dict = {}
_cache_mtime: float | None = None
_oyentes: dict[str, list[Callable[[dict], None]]] = {}


def _cargar() -> dict:
    """Contenido de preferencias.json (solo las claves del ESQUEMA). Llamar con
    _lock tomado. Un JSON corrupto o con valores que ya no validan (p. ej. un
    .vrm que se borró) no tumba la app: se ignora lo inválido y se avisa."""
    global _cache, _cache_mtime
    try:
        mtime = os.path.getmtime(ARCHIVO)
    except OSError:
        _cache, _cache_mtime = {}, None
        return _cache
    if mtime == _cache_mtime:
        return _cache
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            crudo = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[Prefs] {ARCHIVO} ilegible ({e}) — se usa config.toml")
        crudo = {}
    limpio = {}
    for seccion, valores in (crudo.items() if isinstance(crudo, dict) else ()):
        campos = ESQUEMA.get(seccion)
        if not campos or not isinstance(valores, dict):
            continue
        for clave, valor in valores.items():
            if clave not in campos:
                continue
            try:
                limpio.setdefault(seccion, {})[clave] = campos[clave].validar(valor)
            except PreferenciaInvalida as e:
                print(f"[Prefs] se ignora {seccion}.{clave}: {e}")
    _cache, _cache_mtime = limpio, mtime
    return _cache


def _guardar(datos: dict) -> None:
    """Escritura atómica: un lector (este proceso u otro) ve el JSON viejo o el
    nuevo, nunca uno a medio escribir. Llamar con _lock tomado."""
    global _cache, _cache_mtime
    tmp = ARCHIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, ARCHIVO)
    _cache, _cache_mtime = datos, os.path.getmtime(ARCHIVO)


# ── API ─────────────────────────────────────────────────────────────────
def obtener(seccion: str) -> dict:
    """Valores efectivos de la sección (preferencia > config.toml > default)."""
    campos = ESQUEMA.get(seccion)
    if campos is None:
        raise PreferenciaInvalida(f"sección desconocida: {seccion!r}")
    with _lock:
        propias = dict(_cargar().get(seccion, {}))
    return {clave: propias.get(clave, campo.base()) for clave, campo in campos.items()}


def todas() -> dict:
    return {seccion: obtener(seccion) for seccion in ESQUEMA}


def propias() -> dict:
    """Las claves que vienen de preferencias.json (cambiadas desde el panel),
    por sección: {"voz": ["rate"], ...}. El panel las marca y ofrece volver a
    config.toml; el resto sale de config.toml o del default."""
    with _lock:
        datos = _cargar()
        return {seccion: sorted(datos.get(seccion, {})) for seccion in ESQUEMA}


def aplicar(seccion: str, cambios: dict) -> dict:
    """Valida el parche entero, lo guarda y avisa a los oyentes de la sección.
    Devuelve los valores efectivos resultantes. Lanza PreferenciaInvalida sin
    haber tocado nada si alguna clave o valor no vale."""
    campos = ESQUEMA.get(seccion)
    if campos is None:
        raise PreferenciaInvalida(f"sección desconocida: {seccion!r}")
    if not isinstance(cambios, dict) or not cambios:
        raise PreferenciaInvalida("'cambios' tiene que ser un objeto no vacío")
    validados = {}
    for clave, valor in cambios.items():
        if clave not in campos:
            raise PreferenciaInvalida(f"{seccion}: clave desconocida {clave!r}")
        validados[clave] = None if valor is None else campos[clave].validar(valor)

    with _lock:
        datos = copy.deepcopy(_cargar())
        propias = datos.setdefault(seccion, {})
        for clave, valor in validados.items():
            if valor is None or valor == campos[clave].base():
                propias.pop(clave, None)
            else:
                propias[clave] = valor
        if not propias:
            datos.pop(seccion)
        _guardar(datos)

    efectivos = obtener(seccion)
    print(f"[Prefs] {seccion} <- {validados} => {efectivos}")
    for callback in list(_oyentes.get(seccion, ())):
        try:
            callback(efectivos)
        except Exception as e:  # un oyente roto no deshace lo ya guardado
            print(f"[Prefs] oyente de {seccion!r} falló: {type(e).__name__}: {e}")
    return efectivos


def al_cambiar(seccion: str, callback: Callable[[dict], None]) -> None:
    """Registra `callback(valores_efectivos)`, llamado tras cada aplicar() de la
    sección, en el hilo de quien aplicó (el loop del WS): que sea rápido, o que
    despache su trabajo a otro hilo."""
    if seccion not in ESQUEMA:
        raise PreferenciaInvalida(f"sección desconocida: {seccion!r}")
    _oyentes.setdefault(seccion, []).append(callback)
