"""Aplica el shim de fairseq_shim/ sobre el paquete fairseq instalado en venv/.

fairseq==0.12.2 (PyPI) no es compatible con PyTorch moderno: checkpoint_utils.py
llama a torch.load() sin weights_only=False y falla al cargar checkpoints.
Este script sobreescribe __init__.py y checkpoint_utils.py del fairseq instalado
con las versiones parcheadas del repo. Hay que ejecutarlo después de cada
`pip install fairseq` / reinstalación del venv (ver CLAUDE.md).
"""

import glob
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SHIM_DIR = PROJECT_ROOT / "fairseq_shim"
SHIM_FILES = ["__init__.py", "checkpoint_utils.py"]


def encontrar_fairseq_dir():
    patron = str(PROJECT_ROOT / "venv" / "lib" / "python3.*" / "site-packages" / "fairseq")
    candidatos = glob.glob(patron)
    if not candidatos:
        return None
    return Path(candidatos[0])


def main():
    fairseq_dir = encontrar_fairseq_dir()
    if fairseq_dir is None or not fairseq_dir.is_dir():
        print("Error: no se encontró el paquete fairseq instalado en venv/lib/python3.*/site-packages/fairseq/")
        print("Instala fairseq primero: venv/bin/python -m pip install fairseq==0.12.2")
        sys.exit(1)

    print(f"Paquete fairseq encontrado en: {fairseq_dir}")
    print()

    for nombre in SHIM_FILES:
        origen = SHIM_DIR / nombre
        destino = fairseq_dir / nombre

        if not origen.is_file():
            print(f"Error: no existe el archivo del shim {origen}")
            sys.exit(1)

        if not destino.is_file():
            print(f"Error: el destino {destino} no existe. ¿fairseq está instalado correctamente?")
            sys.exit(1)

        shutil.copy2(origen, destino)
        print(f"Reemplazado: {destino}")

    print()
    print("Shim aplicado correctamente.")


if __name__ == "__main__":
    main()
