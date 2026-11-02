"""Inicio y reanudación del primer día; el mismo comando continúa lo pendiente."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
# Se fijan antes de cargar .env. El ritmo se comparte entre los hilos del modelo.
os.environ.setdefault("GOOGLE_MIN_INTERVAL_SECONDS", "4.5")
os.environ.setdefault("SIMULATOR_MIN_INTERVAL_SECONDS", "2.1")

from citalab.evaluation import analysis, runner

if __name__ == "__main__":
    arguments = ["--campaign", "final-independent-v1-20261029", "--scenarios",
                 str(ROOT / "data/evaluation/independent-final-v1.json"), "--providers", "groq,google",
                 "--workers-per-provider", "1", "--retry-incidents", *sys.argv[1:]]
    status = runner.main(arguments)
    # No se ejecuta análisis ni inferencia durante el dry-run.
    if "--dry-run" not in arguments:
        campaign = arguments[arguments.index("--campaign") + 1]
        # argparse acepta una última opción repetida: conservar ese mismo criterio.
        for index, argument in enumerate(arguments[:-1]):
            if argument == "--campaign":
                campaign = arguments[index + 1]
        analysis.main(["--campaign", campaign])
    raise SystemExit(status)
