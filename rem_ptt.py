#!/usr/bin/env python3
"""Push-to-talk de Rem: manda ptt_start / ptt_stop al servidor WS de rem_chat.py.

Pensado para atarse a una tecla mantenida (ver "Voz de entrada" en CLAUDE.md
para las líneas de hyprland.conf):

    venv/bin/python rem_ptt.py start    # al PRESIONAR: abre el micrófono
    venv/bin/python rem_ptt.py stop     # al SOLTAR: cierra, transcribe y responde

Cada invocación es un proceso corto: se conecta, manda el comando, espera la
confirmación del servidor (ptt_estado / error, hasta ESPERA_S) y sale. Todo
lo que pasa después (transcripción, respuesta de Rem) lo ve la ventana; acá
solo se imprime la confirmación. Códigos de salida: 0 = aceptado, 1 = Rem no
está corriendo / sin respuesta, 2 = el servidor lo ignoró (p.ej. Rem está
hablando — ver la decisión documentada en rem_avatar_server.py).
"""
import json
import sys

WS_URL   = "ws://127.0.0.1:18766"
ESPERA_S = 2.0


def main(argv):
    if len(argv) != 2 or argv[1] not in ("start", "stop"):
        print("uso: rem_ptt.py start|stop", file=sys.stderr)
        return 1
    accion = argv[1]

    from websockets.sync.client import connect
    try:
        ws = connect(WS_URL, open_timeout=1.0)
    except OSError as e:
        print(f"[ptt] no se pudo conectar con Rem en {WS_URL} ({e}) — ¿está corriendo rem_chat.py?",
              file=sys.stderr)
        return 1

    with ws:
        ws.send(json.dumps({"tipo": f"ptt_{accion}"}))
        while True:
            try:
                msg = json.loads(ws.recv(timeout=ESPERA_S))
            except TimeoutError:
                print(f"[ptt] {accion}: el servidor no confirmó en {ESPERA_S:.0f}s", file=sys.stderr)
                return 1
            if msg.get("tipo") == "error":
                print(f"[ptt] {accion}: error — {msg.get('mensaje')}", file=sys.stderr)
                return 1
            if msg.get("tipo") == "ptt_estado":
                detalle = msg.get("motivo") or msg.get("nota") or ""
                print(f"[ptt] {accion}: {msg['estado']}" + (f" ({detalle})" if detalle else ""))
                return 2 if msg["estado"] == "ignorado" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
