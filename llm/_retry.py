"""Retry con backoff exponencial compartido por los providers.

El backoff estaba ocultando la excepción original: solo se logueaba str(e) en
cada intento, y al agotar los reintentos se relanzaba el último error tal
cual, sin dejar explícito que se trataba de un fallo tras N intentos. Acá se
loguea tipo + causa (__cause__) de cada intento, y al agotar los reintentos se
envuelve en un RuntimeError encadenado (`raise ... from`) para que el
traceback completo — incluida la causa raíz — quede visible en vez de perderse
detrás de un "error de conexión" genérico.
"""
import asyncio


async def reintentar_con_backoff(intentar, max_intentos: int, etiqueta: str):
    """`intentar` es una función async sin argumentos (ej. un lambda que hace
    la llamada de red). Reintenta hasta `max_intentos` veces con backoff
    exponencial (1s, 2s, 4s...). Si todos los intentos fallan, lanza
    RuntimeError encadenado al último error real."""
    ultimo_error = None
    for intento in range(max_intentos):
        try:
            return await intentar()
        except Exception as e:
            ultimo_error = e
            causa = f" (causa: {type(e.__cause__).__name__}: {e.__cause__})" if e.__cause__ else ""
            if intento < max_intentos - 1:
                espera = 2 ** intento
                print(f"[{etiqueta}] Intento {intento + 1}/{max_intentos} falló: "
                      f"{type(e).__name__}: {e}{causa}. Reintentando en {espera}s...")
                await asyncio.sleep(espera)
            else:
                print(f"[{etiqueta}] Intento {intento + 1}/{max_intentos} falló: "
                      f"{type(e).__name__}: {e}{causa}. Reintentos agotados.")

    raise RuntimeError(
        f"[{etiqueta}] Se agotaron los {max_intentos} intentos. "
        f"Último error: {type(ultimo_error).__name__}: {ultimo_error}"
    ) from ultimo_error
