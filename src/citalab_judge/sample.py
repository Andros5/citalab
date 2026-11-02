"""Muestra humana fijada antes del juez y sin mirar resultados.

10 condiciones del bloque principal (2 por gestión) × 6 configuraciones = 60
episodios emparejados. La selección usa solo metadatos del plan: gestión,
grupo de dependencia (cada grupo aparece dos veces) e idioma (al menos 3
condiciones en inglés si el plan las tiene). La segunda pasada es un 20 %
de la muestra con otro orden.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime

from citalab.config import OUTPUT
from citalab_judge import judge_folder
from citalab_judge.episode import load_plan, scenarios_for

SEED = 20261030
PER_OPERATION = 2
SECOND_PASS = 12
MIN_ENGLISH = 3
OPERATIONS = ("book", "query", "reschedule", "cancel", "reminder")
VERSION = "sample-v1"


def _sha(path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def choose_units(plan: list[dict], groups: dict[str, list[str]], seed: int = SEED) -> list[str]:
    units = {c["unit_id"]: c for c in plan if c["block"] == "primary"}
    group_of = {unit: name for name, members in groups.items() for unit in members}
    english = sum(1 for c in units.values() if c["family"]["language"] == "en")
    rng = random.Random(seed)
    for _ in range(20000):
        chosen: list[str] = []
        for operation in OPERATIONS:
            candidates = sorted(u for u, c in units.items() if c["family"]["operation"] == operation)
            rng.shuffle(candidates)
            picked = []
            for unit in candidates:
                if all(group_of.get(unit) != group_of.get(p) for p in picked):
                    picked.append(unit)
                if len(picked) == PER_OPERATION:
                    break
            chosen += picked
        counts = {name: sum(group_of.get(u) == name for u in chosen) for name in groups}
        enough_english = sum(units[u]["family"]["language"] == "en" for u in chosen) >= min(MIN_ENGLISH, english)
        if len(chosen) == PER_OPERATION * len(OPERATIONS) and (not groups or set(counts.values()) == {2}) \
                and enough_english:
            return sorted(chosen)
    raise RuntimeError("no-balanced-sample")


def build(campaign: str) -> dict:
    folder = OUTPUT / "evaluation" / campaign
    plan = load_plan(campaign)
    groups = scenarios_for(campaign).get("dependency_groups", {})
    units = choose_units(plan, groups)
    cells = sorted(c["cell_id"] for c in plan if c["block"] == "primary" and c["unit_id"] in units)
    rng = random.Random(SEED + 2)
    configurations = sorted({cell.split(":", 2)[0] + ":" + cell.split(":", 2)[1] for cell in cells})
    per_configuration = max(1, SECOND_PASS // max(1, len(configurations)))
    second = sorted(cell for config in configurations
                    for cell in rng.sample(sorted(c for c in cells if c.startswith(config + ":")), per_configuration))
    return {"version": VERSION, "campaign": campaign, "created_at": datetime.now(UTC).isoformat(),
            "seed": SEED,
            "rules": "Bloque principal; 2 condiciones por gestión; cada grupo de dependencia dos veces; "
                     f"al menos {MIN_ENGLISH} condiciones en inglés; todas las configuraciones de cada "
                     "condición; segunda pasada del 20 % (2 por configuración). Solo metadatos del plan, nunca resultados.",
            "plan_sha256": _sha(folder / "plan.json"), "scenarios_sha256": _sha(folder / "scenarios.json"),
            "units": units, "cells": cells, "second_pass": second}


def path(campaign: str):
    return judge_folder(campaign) / f"{VERSION}.json"


def create(campaign: str) -> dict:
    target = path(campaign)
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))  # fijada: nunca se regenera
    manifest = build(campaign)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def load(campaign: str) -> dict | None:
    target = path(campaign)
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
