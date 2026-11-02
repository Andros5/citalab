"""Compila la memoria con Tectonic: memoria/main.tex -> memoria/build/main.pdf.

    python scripts/build_thesis.py

Tectonic descarga los paquetes de LaTeX que necesita la primera vez. Antes de compilar se pueden
regenerar las tablas de los capítulos 8 y 9 con scripts/reproduce.py.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tectonic = shutil.which("tectonic")
    if not tectonic:
        print("No se encuentra Tectonic en el PATH: https://tectonic-typesetting.github.io", file=sys.stderr)
        return 1
    build = ROOT / "memoria" / "build"
    build.mkdir(exist_ok=True)
    result = subprocess.run([tectonic, "--keep-logs", "--outdir", str(build), "main.tex"], cwd=ROOT / "memoria")
    if result.returncode == 0:
        print(f"Memoria compilada: {build / 'main.pdf'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
