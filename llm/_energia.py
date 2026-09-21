"""Estado de energía de la máquina y de la GPU, para acompañar cada medición
de tok/s. Motivo (medido, ver CLAUDE.md, "Precarga de Ollama…"): con el
portátil en batería la GPU cae a P5 con la memoria a 810 MHz y Ollama pasa de
~15-20 a ~6,6 tok/s. Una cifra de tok/s sin este dato no se puede comparar con
otra, así que el log de cada turno lo lleva siempre.

Todo es de mejor esfuerzo: si /sys o nvidia-smi no están, devuelve None y el
log dice "n/d" en vez de romper el turno."""
import glob
import subprocess


def estado_alimentacion() -> str:
    """"AC", "batería 29% (descargando)", "AC (batería 80% cargando)"... o "n/d"."""
    try:
        ac, bateria = None, None
        for d in glob.glob("/sys/class/power_supply/*"):
            tipo = open(f"{d}/type").read().strip()
            if tipo == "Mains":
                ac = open(f"{d}/online").read().strip() == "1"
            elif tipo == "Battery":
                estado = open(f"{d}/status").read().strip().lower()
                estado = {"discharging": "descargando", "charging": "cargando", "full": "llena",
                          "not charging": "sin cargar"}.get(estado, estado)
                bateria = f"{open(f'{d}/capacity').read().strip()}% {estado}"
        if ac is None and bateria is None:
            return "n/d"
        if bateria is None:
            return "AC" if ac else "sin AC"
        return f"AC (batería {bateria})" if ac else f"batería {bateria}"
    except Exception:
        return "n/d"


def estado_gpu() -> dict | None:
    """{"pstate": "P5", "mem_mhz": 810, "sm_mhz": 1717} de la primera GPU NVIDIA, o None."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=pstate,clocks.mem,clocks.sm", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3).stdout.strip().splitlines()[0]
        pstate, mem, sm = [x.strip() for x in out.split(",")]
        return {"pstate": pstate, "mem_mhz": int(mem), "sm_mhz": int(sm)}
    except Exception:
        return None


def formatear_gpu(al_empezar: dict | None, al_terminar: dict | None) -> str:
    """"GPU P3→P5 (mem 810 MHz)" — el estado al llegar el primer token y al
    terminar (la GPU sube a P3 un par de segundos y luego cae a P5: mirar solo
    uno de los dos engaña)."""
    if not al_empezar and not al_terminar:
        return "GPU n/d"
    a = al_empezar or al_terminar
    b = al_terminar or al_empezar
    return f"GPU {a['pstate']}→{b['pstate']} (mem {b['mem_mhz']} MHz)"
