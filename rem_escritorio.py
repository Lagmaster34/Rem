#!/usr/bin/env python3
"""Muestra u oculta el avatar del modo escritorio (rem_chat.py --modo escritorio).

    venv/bin/python rem_escritorio.py mostrar|ocultar|alternar

Pensado para un atajo de Hyprland y para el lanzador «Yoru» (que lo
usa en vez de abrir una segunda instancia). Se conecta al WebSocket de Rem, manda
la acción y sale: 0 = enviada, 1 = Rem no está corriendo.
"""
import json
import sys

WS_URL = "ws://127.0.0.1:18766"


def main(argv):
    if len(argv) != 2 or argv[1] not in ("mostrar", "ocultar", "alternar"):
        print("uso: rem_escritorio.py mostrar|ocultar|alternar", file=sys.stderr)
        return 1
    from websockets.sync.client import connect
    try:
        with connect(WS_URL, open_timeout=1.0) as ws:
            ws.send(json.dumps({"tipo": "escritorio", "datos": {"tipo": "accion", "accion": argv[1]}}))
    except OSError as e:
        print(f"[escritorio] no se pudo conectar con Rem en {WS_URL} ({e}) — ¿está corriendo?",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
