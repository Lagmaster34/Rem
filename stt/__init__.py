"""Capa de abstracción de voz a texto (STT): contrato común (base.py) + un
provider por backend (local.py = faster-whisper, groq.py). get_stt_provider()
decide cuál instanciar según configuración — mismo esquema que llm/."""
import os
import threading

import config as _config

from .base import SAMPLE_RATE, STTProvider

__all__ = ["SAMPLE_RATE", "STTProvider", "get_stt_provider", "obtener_stt",
           "leer_config_stt", "precargar_stt"]


def leer_config_stt() -> dict:
    """[stt] de config.toml con defaults (los tiempos de push-to-talk; la
    config de cada provider se lee en get_stt_provider())."""
    cfg = _config.leer_config_toml().get("stt", {})
    return {
        "max_grabacion_s": float(cfg.get("max_grabacion_s", 30)),
        "min_grabacion_s": float(cfg.get("min_grabacion_s", 0.4)),
        "mostrar_transcripcion_s": float(cfg.get("mostrar_transcripcion_s", 1.0)),
        "espera_tras_habla_s": float(cfg.get("espera_tras_habla_s", 0.5)),
        "dispositivo_entrada": _dispositivo_entrada(cfg),
    }


def _dispositivo_entrada(cfg):
    """Dispositivo de captura para sounddevice: REM_MIC_DEVICE (env) >
    [stt].dispositivo_entrada > None (el predeterminado del sistema). Acepta el
    índice o el nombre (p. ej. "pulse", para elegir la fuente con PULSE_SOURCE)."""
    valor = os.environ.get("REM_MIC_DEVICE", "").strip() or str(cfg.get("dispositivo_entrada", "")).strip()
    if not valor:
        return None
    return int(valor) if valor.isdigit() else valor


def get_stt_provider() -> STTProvider:
    """Precedencia: REM_STT_PROVIDER (env) > [stt].provider en config.toml >
    "local". Falla acá si falta la API key del provider elegido (mismo
    criterio que llm.get_provider())."""
    stt_config = dict(_config.leer_config_toml().get("stt", {}))
    proveedor = (
        os.environ.get("REM_STT_PROVIDER", "").strip().lower()
        or str(stt_config.get("provider", "local")).strip().lower()
    )

    if proveedor == "local":
        from .local import LocalSTTProvider
        c = dict(stt_config.get("local", {}))
        return LocalSTTProvider(
            model=str(c.get("model", "small")),
            compute_type=str(c.get("compute_type", "int8")),
            device=str(c.get("device", "cpu")),
            language=str(c.get("language", "es")),
            beam_size=int(c.get("beam_size", 1)),
            cpu_threads=int(c.get("cpu_threads", 0)),
            initial_prompt=str(c.get("initial_prompt", "")) or None,
        )

    if proveedor == "groq":
        from .groq import GroqSTTProvider
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Proveedor STT 'groq' seleccionado pero falta GROQ_API_KEY en el "
                "entorno (revisá tu .env)."
            )
        c = dict(stt_config.get("groq", {}))
        return GroqSTTProvider(
            api_key=api_key,
            model=str(c.get("model", "whisper-large-v3-turbo")),
            language=str(c.get("language", "es")),
        )

    raise ValueError(f"Proveedor de STT desconocido: '{proveedor}'. Implementados: 'local', 'groq'.")


_compartido = None
_compartido_lock = threading.Lock()


def obtener_stt() -> STTProvider:
    """La instancia única del proceso (la usan el hilo de precarga y
    rem_avatar_server al transcribir): así el modelo se carga una sola vez."""
    global _compartido
    with _compartido_lock:
        if _compartido is None:
            _compartido = get_stt_provider()
        return _compartido


def precargar_stt() -> None:
    """Carga (y calienta) el modelo en el hilo que lo llame — lanzada en un
    hilo de fondo al arrancar por rem_chat.py, igual que habla.precargar_rvc().
    No bloqueante: si falla (falta la API key, no hay red para bajar el modelo
    la primera vez...) solo lo loguea; el error real volverá a aparecer,
    visible, en el primer push-to-talk."""
    try:
        obtener_stt().precargar()
    except Exception as e:
        print(f"  [STT] precarga falló, no bloqueante ({e})", flush=True)
