"""stt/analisis.py — cuándo hay voz en el micrófono: fin de frase en vivo,
veredicto de una grabación y filtro de frases que Whisper se inventa.

Todo trabaja con niveles en dBFS por TRAMA de 20 ms (RMS de la trama). Nada de
umbrales absolutos para decidir qué es voz: el umbral es el PISO DE RUIDO de la
propia grabación + `voz_sobre_ruido_db` (12 dB), con un mínimo absoluto
(`voz_min_dbfs`) para que un micrófono digitalmente mudo no convierta cualquier
ruidito en voz.

El piso es "la mediana del ruido", medida como la MÍNIMA mediana de ventanas de
0,4 s (`VENTANA_PISO_S`): basta un trozo tranquilo (antes de hablar, una pausa,
el final) para fijarlo, y no sube nunca aunque se hable mucho rato. Se probó
antes la mediana del 30 % de tramas más bajas: con voz continua (más del 70 %
de la grabación) ese 30 % ya era voz y el umbral quedaba por encima de la
propia voz (la frase se cortaba a los 4 s de un discurso de 15).

Los tiempos fijos (gracia, silencio que cierra la frase, tope, micrófono muerto,
mínimo de voz para no ser una alucinación) vienen de config.toml [stt.voz], ver
`ConfigVoz.desde_config()`. Sin numpy pesado: unas cuantas operaciones por
bloque de audio, cabe en el hilo de PortAudio.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np

TRAMA_S = 0.02
VENTANA_PISO_S = 0.4      # el piso es la mínima mediana de ventanas de este largo
PISO_DB = -120.0          # nivel de una trama en silencio digital


@dataclass
class ConfigVoz:
    gracia_s: float = 0.65            # al empezar a hablar, no cuenta silencio todavía
    silencio_s: float = 1.0           # silencio seguido tras la voz que cierra la frase
    max_voz_s: float = 15.0           # tope desde que empieza la voz
    voz_sobre_ruido_db: float = 12.0  # voz = trama por encima del piso + esto
    voz_min_dbfs: float = -45.0       # ...y nunca por debajo de esto
    voz_inicio_tramas: int = 3        # tramas seguidas sobre el umbral para dar la voz por empezada
    muerto_dbfs: float = -80.0        # pico por debajo de esto = no llega audio
    muerto_temprano_s: float = 4.0    # en vivo: cortar si en este tiempo no llegó nada
    muerto_min_s: float = 1.5         # veredicto: "muerto" (≥) o "silencio" (<)
    alucinacion_max_voz_ms: float = 120.0
    frases_inventadas: list[str] = field(default_factory=list)

    @classmethod
    def desde_config(cls) -> "ConfigVoz":
        import config as _config
        cfg = _config.leer_config_toml().get("stt", {}).get("voz", {})
        base = cls()
        valores = {}
        for nombre in ("gracia_s", "silencio_s", "max_voz_s", "voz_sobre_ruido_db", "voz_min_dbfs",
                       "muerto_dbfs", "muerto_temprano_s", "muerto_min_s", "alucinacion_max_voz_ms"):
            try:
                valores[nombre] = float(cfg.get(nombre, getattr(base, nombre)))
            except (TypeError, ValueError):
                valores[nombre] = getattr(base, nombre)
        try:
            valores["voz_inicio_tramas"] = max(1, int(cfg.get("voz_inicio_tramas", base.voz_inicio_tramas)))
        except (TypeError, ValueError):
            pass
        frases = cfg.get("frases_inventadas", [])
        valores["frases_inventadas"] = [str(f) for f in frases] if isinstance(frases, list) else []
        return cls(**valores)


def niveles_db(audio: np.ndarray, sr: int) -> np.ndarray:
    """dBFS (RMS) de cada trama completa de 20 ms."""
    n = int(sr * TRAMA_S)
    if len(audio) < n:
        return np.zeros(0)
    tramas = np.asarray(audio[: len(audio) // n * n], dtype=np.float64).reshape(-1, n)
    rms = np.sqrt(np.mean(tramas * tramas, axis=1))
    return np.maximum(20 * np.log10(np.maximum(rms, 1e-12)), PISO_DB)


_TRAMAS_VENTANA = int(round(VENTANA_PISO_S / TRAMA_S))


def piso_ruido(niveles: np.ndarray) -> float:
    """La mediana del ruido: la mínima mediana de las ventanas de 0,4 s (con
    menos tramas que eso, la mediana de todas)."""
    if len(niveles) == 0:
        return PISO_DB
    if len(niveles) <= _TRAMAS_VENTANA:
        return float(np.median(niveles))
    ventanas = np.lib.stride_tricks.sliding_window_view(niveles, _TRAMAS_VENTANA)
    return float(np.median(ventanas, axis=1).min())


def umbral_voz(piso: float, cfg: ConfigVoz) -> float:
    return max(piso + cfg.voz_sobre_ruido_db, cfg.voz_min_dbfs)


class FinDeFrase:
    """Detector en vivo. alimentar(bloque) con cada bloque del micrófono;
    devuelve None mientras siga, o el motivo para cortar:
      "fin"     tras la voz, `silencio_s` seguidos por debajo del umbral
      "tope"    `max_voz_s` desde que empezó la voz
      "muerto"  `muerto_temprano_s` sin un solo pico por encima de muerto_dbfs
      "espera"  `espera_voz_s` sin que empiece la voz (modo conversación)
    Cada bloque recalcula el piso sobre todo lo grabado y, si la voz aún no
    había empezado, la busca HACIA ATRÁS con el umbral nuevo: si se habla desde
    el primer instante, el piso es nivel de voz hasta que llega el primer
    silencio, y ahí se descubre que la voz empezó al principio."""

    def __init__(self, sr: int, cfg: ConfigVoz, espera_voz_s: float | None = None):
        self.sr, self.cfg = sr, cfg
        self.espera_voz_s = espera_voz_s
        self._n = int(sr * TRAMA_S)
        self._resto = np.zeros(0, np.float32)
        self._niveles = np.zeros(0)
        self.voz_desde: float | None = None     # s desde el inicio
        self.fin_voz_s: float | None = None     # fin de la última trama de voz
        self.silencio_s = 0.0
        self.pico_db = PISO_DB

    @property
    def t(self) -> float:
        return len(self._niveles) * TRAMA_S

    def alimentar(self, bloque: np.ndarray) -> str | None:
        datos = np.concatenate([self._resto, np.asarray(bloque, np.float32)])
        enteras = len(datos) // self._n * self._n
        self._resto = datos[enteras:]
        if not enteras:
            return None
        nuevos = niveles_db(datos[:enteras], self.sr)
        self._niveles = np.concatenate([self._niveles, nuevos])
        self.pico_db = max(self.pico_db, float(nuevos.max()))
        sobre = self._niveles > umbral_voz(piso_ruido(self._niveles), self.cfg)

        if self.voz_desde is None:
            # Primera racha de voz_inicio_tramas tramas seguidas sobre el umbral.
            k = self.cfg.voz_inicio_tramas
            racha = np.convolve(sobre.astype(np.int32), np.ones(k, np.int32), mode="valid")
            hits = np.flatnonzero(racha >= k)
            if len(hits):
                self.voz_desde = hits[0] * TRAMA_S
        t = self.t
        if self.voz_desde is not None:
            ultimo = np.flatnonzero(sobre)
            self.fin_voz_s = (ultimo[-1] + 1) * TRAMA_S if len(ultimo) else self.voz_desde
            self.silencio_s = t - self.fin_voz_s
            if t - self.voz_desde > self.cfg.gracia_s and self.silencio_s >= self.cfg.silencio_s:
                return "fin"
            if t - self.voz_desde >= self.cfg.max_voz_s:
                return "tope"
            return None
        if t >= self.cfg.muerto_temprano_s and self.pico_db < self.cfg.muerto_dbfs:
            return "muerto"
        if self.espera_voz_s is not None and t >= self.espera_voz_s:
            return "espera"
        return None


@dataclass
class Veredicto:
    """"enviar" | "sin_voz" | "silencio" | "muerto" (y el STT puede añadir
    "inventada"). voz_ms: tramas por encima del umbral × 20 ms."""
    tipo: str
    dur_s: float
    voz_ms: float
    pico_db: float
    piso_db: float
    umbral_db: float

    def resumen(self) -> str:
        return (f"{self.tipo}: {self.dur_s:.2f}s, voz {self.voz_ms:.0f} ms, pico {self.pico_db:.1f} dBFS, "
                f"piso {self.piso_db:.1f}, umbral {self.umbral_db:.1f}")


def veredicto(audio: np.ndarray, sr: int, cfg: ConfigVoz) -> Veredicto:
    niveles = niveles_db(audio, sr)
    dur = len(audio) / sr if sr else 0.0
    pico = float(niveles.max()) if len(niveles) else PISO_DB
    piso = piso_ruido(niveles)
    umbral = umbral_voz(piso, cfg)
    voz_ms = float(np.count_nonzero(niveles > umbral)) * TRAMA_S * 1000
    if pico < cfg.muerto_dbfs:
        tipo = "muerto" if dur >= cfg.muerto_min_s else "silencio"
    elif voz_ms == 0:
        tipo = "sin_voz"
    else:
        tipo = "enviar"
    return Veredicto(tipo, dur, voz_ms, pico, piso, umbral)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")   # sin tildes
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", t).split())         # sin signos


def es_inventada(texto: str, voz_ms: float, cfg: ConfigVoz) -> bool:
    """Whisper rellena el silencio con frases de subtítulos ("Gracias.",
    "Subtítulos realizados por la comunidad de Amara.org"...). Se descarta si
    el texto es una de esas Y la grabación casi no tuvo voz: con voz de verdad,
    un "gracias" del usuario se respeta."""
    if voz_ms >= cfg.alucinacion_max_voz_ms:
        return False
    t = _normalizar(texto)
    return bool(t) and any(t == _normalizar(f) for f in cfg.frases_inventadas)
