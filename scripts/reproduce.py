"""Comprobación completa de la campaña final sin claves ni coste.

    python scripts/reproduce.py            # código evaluado, tablas de la memoria e informe del jurado
    python scripts/reproduce.py --tests    # además, las pruebas automáticas

1. Código y corpus: cada fichero que fija el manifiesto de la campaña tiene el mismo hash, y también
   las instrucciones de los agentes.
2. Tablas: se regeneran las tablas de los capítulos 8 y 9 de la memoria y los resúmenes derivados,
   y se comparan con los publicados.
3. Jurado y revisión humana: se recalcula el informe de concordancia y se compara con el publicado.

Ninguna comprobación llama a un modelo. Los ficheros regenerados se comparan sin tener en cuenta
los finales de línea y, si coinciden, se dejan exactamente como estaban.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "final-independent-v1"
FOLDER = ROOT / "output" / "evaluation" / CAMPAIGN
# Ficheros que regeneran los pasos 2 y 3.
GENERATED = [ROOT / "memoria" / "generated", FOLDER / "derived", FOLDER / "judge"]
STEPS = [
    ("Tablas de la campaña", [sys.executable, "scripts/derive_thesis_tables.py"]),
    ("Fallos y correcciones sin modelos", [sys.executable, "scripts/replay_fixes.py"]),
    ("Comprobaciones con modelos (sin llamadas)", [sys.executable, "scripts/check_fixes_with_models.py", "--report"]),
    ("Informe del jurado y de la revisión humana", [sys.executable, "-m", "citalab_judge", "report",
                                                     "--campaign", CAMPAIGN]),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_sources() -> list[str]:
    manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))
    errors = [rel for rel, digest in manifest["sources"].items()
              if not (ROOT / rel).is_file() or sha256(ROOT / rel) != digest]
    for rel in ("data/evaluation/independent-final-v1.json", f"output/evaluation/{CAMPAIGN}/scenarios.json"):
        if sha256(ROOT / rel) != manifest["scenarios_sha256"]:
            errors.append(rel)
    sys.path.insert(0, str(ROOT / "src"))
    from citalab.assistant import prompts

    digest = hashlib.sha256(json.dumps(prompts.DEFAULTS, sort_keys=True).encode()).hexdigest()
    if digest != manifest["prompt_sha256"] or prompts.VERSION != manifest["prompt_version"]:
        errors.append("src/citalab/assistant/prompts.py (instrucciones de los agentes)")
    print(f"  {len(manifest['sources'])} ficheros de código y datos, corpus e instrucciones")
    return errors


def snapshot() -> dict[Path, bytes]:
    return {p: p.read_bytes() for folder in GENERATED for p in folder.rglob("*") if p.is_file()}


def compare(before: dict[Path, bytes]) -> list[str]:
    differences = []
    after = snapshot()
    for path, data in after.items():
        old = before.get(path)
        if old is None:
            differences.append(f"{path.relative_to(ROOT).as_posix()} (nuevo)")
        elif old.replace(b"\r\n", b"\n") == data.replace(b"\r\n", b"\n"):
            if old != data:
                path.write_bytes(old)  # mismo contenido: se conservan los bytes publicados
        else:
            differences.append(path.relative_to(ROOT).as_posix())
    differences += [f"{p.relative_to(ROOT).as_posix()} (desaparecido)" for p in before if p not in after]
    return differences


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", line_buffering=True)
    parser = argparse.ArgumentParser(description="Comprobación de la campaña final sin llamadas a modelos")
    parser.add_argument("--tests", action="store_true", help="ejecuta también las pruebas automáticas")
    args = parser.parse_args()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    failed = False

    print("1. Código evaluado frente al manifiesto de la campaña")
    errors = check_sources()
    for rel in errors:
        print(f"  DISTINTO  {rel}")
    print("  OK" if not errors else f"  FALLO: {len(errors)} ficheros no coinciden")
    failed |= bool(errors)

    print("2-3. Tablas de la memoria e informe del jurado")
    before = snapshot()
    for label, command in STEPS:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        print(f"  {'OK   ' if result.returncode == 0 else 'FALLO'}  {label}")
        if result.returncode != 0:
            print(result.stdout[-2000:] + result.stderr[-2000:])
            failed = True
    differences = compare(before)
    for rel in differences:
        print(f"  DISTINTO  {rel}")
    print(f"  {len(before)} ficheros regenerados" + (" idénticos a los publicados" if not differences
                                                    else f", {len(differences)} distintos"))
    failed |= bool(differences)

    if args.tests:
        print("4. Pruebas automáticas")
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, env=env)
        failed |= result.returncode != 0

    print("\nResultado:", "FALLO" if failed else "todo coincide con lo publicado")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
