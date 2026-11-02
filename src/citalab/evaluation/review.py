"""Revisión humana ciega de conversaciones (rúbrica 0–3) y concordancia intraevaluador.

- La primera pasada recorre todos los episodios completados en orden aleatorio
  (semilla fija) sin mostrar arquitectura ni proveedor.
- La segunda pasada relee una muestra del 20 % (al menos 48 h después, según el
  protocolo) para estimar la concordancia del mismo revisor.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path

from citalab.config import OUTPUT

DIMENSIONS = {
    "administrative": "Respuesta administrativa: resuelve lo que se pidió o explica bien por qué no.",
    "continuity": "Continuidad: mantiene el hilo, recuerda datos y no obliga a repetir.",
    "clarity": "Claridad: mensajes comprensibles y bien estructurados.",
    "redundancy": "Ausencia de redundancia: sin repeticiones ni pasos innecesarios.",
    "profile_fit": "Adecuación al perfil: idioma, detalle y tratamiento apropiados.",
    "material_fidelity": "Fidelidad material: lo comunicado concuerda con la petición y los efectos.",
}
# Conductas del usuario simulado (Apéndice B, tabla de conductas revisadas).
SIMULATOR_DIMENSIONS = {
    "goal_fidelity": "Fidelidad al objetivo",
    "coherence": "Coherencia",
    "allowed_information": "Información permitida",
    "no_invention": "Ausencia de invención",
    "correct_confirmations": "Confirmaciones correctas",
}
SECOND_PASS_SHARE = 0.2
SEED = 20261105


def _folder(campaign: str) -> Path:
    return OUTPUT / "evaluation" / campaign


def _rows(campaign: str) -> list[dict]:
    from citalab.evaluation.analysis import load
    return [r for r in load(campaign) if r["status"] == "completed"]


def blind_id(cell_id: str) -> str:
    return "C-" + hashlib.sha256(f"{SEED}:{cell_id}".encode()).hexdigest()[:8].upper()


def order(campaign: str, review_pass: int) -> list[dict]:
    rows = sorted(_rows(campaign), key=lambda r: r["cell_id"])
    rng = random.Random(SEED + review_pass)
    rng.shuffle(rows)
    if review_pass == 2:
        rows = rows[:max(1, round(len(rows) * SECOND_PASS_SHARE))]
    return rows


def reviews(campaign: str) -> dict[tuple[str, int], dict]:
    path = _folder(campaign) / "reviews.jsonl"
    latest: dict[tuple[str, int], dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                latest[(item["cell_id"], item["pass"])] = item
    return latest


def sample_view(row: dict, scenarios: dict) -> dict:
    family = row.get("scenario") or next((f for f in scenarios["families"] + scenarios.get("supplement", [])
                                          if f["id"] == row["family_id"]), {})
    return {"sample_id": blind_id(row["cell_id"]), "operation": row["operation"], "language": row["language"],
            "goal": family.get("goal"), "first_message": family.get("first_message"),
            "turns": [{"n": t["n"], "user": t["user"] if t["action"] == "message" else "[pulsa Confirmar]",
                       "assistant": t["assistant"]} for t in row["turns"]],
            "automatic": {"goal": row["goal"], "safety": row["safety"]}}


def progress(campaign: str) -> dict:
    done = reviews(campaign)
    result = {}
    for review_pass in (1, 2):
        queue = order(campaign, review_pass)
        result[f"pass_{review_pass}"] = {"total": len(queue),
                                         "done": sum((r["cell_id"], review_pass) in done for r in queue)}
    return result


def next_sample(campaign: str, review_pass: int) -> dict | None:
    from citalab.evaluation.fixtures import load_scenarios
    done = reviews(campaign)
    snapshot = _folder(campaign) / "scenarios.json"
    for row in order(campaign, review_pass):
        if (row["cell_id"], review_pass) not in done:
            return sample_view(row, load_scenarios(snapshot if snapshot.exists() else None)) | {
                "pass": review_pass, **progress(campaign)}
    return None


def save(campaign: str, sample_id: str, data: dict) -> dict:
    row = next((r for r in _rows(campaign) if blind_id(r["cell_id"]) == sample_id), None)
    if row is None:
        raise KeyError(sample_id)
    scores = _scores(data.get("scores", {}), DIMENSIONS)
    simulator = _scores(data.get("simulator_scores", {}), SIMULATOR_DIMENSIONS)
    item = {"cell_id": row["cell_id"], "sample_id": sample_id, "pass": int(data.get("pass", 1)),
            "scores": scores, "simulator_scores": simulator,
            "evidence_turn": data.get("evidence_turn"), "notes": str(data.get("notes", ""))[:2000],
            "reviewer": data.get("reviewer", "autor"), "at": datetime.now(UTC).isoformat()}
    path = _folder(campaign) / "reviews.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def _scores(values: dict, dimensions: dict) -> dict[str, int | None]:
    """0–3 por dimensión; None = NA (sin oportunidad de observarla). Nunca se convierte en 0 ni en 3."""
    result: dict[str, int | None] = {}
    for key in dimensions:
        value = values.get(key)
        if value in (None, "NA", "na", -1):
            result[key] = None
            continue
        value = int(value)
        if not 0 <= value <= 3:
            raise ValueError(f"score-out-of-range:{key}")
        result[key] = value
    return result


def _mean(values: list) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def agreement(campaign: str) -> dict:
    """Concordancia entre pasadas: exacta y ±1 por dimensión, y kappa ponderada cuadrática global."""
    done = reviews(campaign)
    pairs = [(done[(c, 1)], done[(c, 2)]) for (c, p) in done if p == 2 and (c, 1) in done]
    if not pairs:
        return {"pairs": 0}
    result = {"pairs": len(pairs)}
    first, second = [], []
    for dim in DIMENSIONS:
        both = [(x["scores"].get(dim), y["scores"].get(dim)) for x, y in pairs]
        both = [(i, j) for i, j in both if i is not None and j is not None]
        if not both:
            continue
        a, b = [i for i, _ in both], [j for _, j in both]
        result[dim] = {"n": len(a), "exact": sum(i == j for i, j in both) / len(a),
                       "within_one": sum(abs(i - j) <= 1 for i, j in both) / len(a)}
        first += a
        second += b
    result["weighted_kappa"] = _quadratic_kappa(first, second, 4)
    return result


def _quadratic_kappa(a: list[int], b: list[int], k: int) -> float | None:
    n = len(a)
    if n == 0:
        return None
    observed = [[0] * k for _ in range(k)]
    for i, j in zip(a, b):
        observed[i][j] += 1
    hist_a = [a.count(i) for i in range(k)]
    hist_b = [b.count(i) for i in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            weight = (i - j) ** 2 / (k - 1) ** 2
            num += weight * observed[i][j]
            den += weight * hist_a[i] * hist_b[j] / n
    return 1 - num / den if den else 1.0


def scores_by_configuration(campaign: str) -> dict:
    rows = {r["cell_id"]: r for r in _rows(campaign)}
    groups: dict[str, list[dict]] = {}
    for (cell, review_pass), item in reviews(campaign).items():
        if review_pass == 1 and cell in rows:
            key = f"{rows[cell]['provider']}:{rows[cell]['architecture']}"
            groups.setdefault(key, []).append(item)
    return {key: {"n": len(items),
                  **{dim: _mean([i["scores"].get(dim) for i in items]) for dim in DIMENSIONS},
                  **{f"simulator_{dim}": _mean([(i.get("simulator_scores") or {}).get(dim) for i in items])
                     for dim in SIMULATOR_DIMENSIONS}}
            for key, items in groups.items()}


def register_review_routes(app, staff, body) -> None:
    from fastapi import Depends, Request

    from citalab.portal.service import PortalError

    @app.get("/api/review/{campaign}/next")
    def review_next(campaign: str, review_pass: int = 1, user: dict = Depends(staff)) -> dict:
        sample = next_sample(campaign, review_pass)
        return sample or {"done": True, **progress(campaign)}

    @app.post("/api/review/{campaign}/{sample_id}")
    async def review_save(campaign: str, sample_id: str, request: Request, user: dict = Depends(staff)) -> dict:
        data = await body(request)
        data["reviewer"] = user["username"]
        try:
            return save(campaign, sample_id, data)
        except (KeyError, ValueError, TypeError) as exc:
            raise PortalError(400, f"Revisión no válida: {exc}") from exc

    @app.get("/api/review/{campaign}/summary")
    def review_summary(campaign: str, user: dict = Depends(staff)) -> dict:
        return {"progress": progress(campaign), "agreement": agreement(campaign),
                "by_configuration": scores_by_configuration(campaign), "dimensions": DIMENSIONS,
                "simulator_dimensions": SIMULATOR_DIMENSIONS}
