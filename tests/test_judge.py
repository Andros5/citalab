"""Evaluación mixta (citalab_judge): vista ciega, validación, reanudación, muestra, kappa y PPI. Sin red."""

from __future__ import annotations

import json
import random

import pytest

from citalab.evaluation.review import DIMENSIONS, SIMULATOR_DIMENSIONS
from citalab_judge import agreement, episode, judge, sample
from citalab_judge.judge import CallResult, JudgeFailure, UsageLimit

SCENARIOS = {"reference_time": "2026-11-02T08:00:00Z", "personas": {"direct": {"es": "Escribes breve."}},
             "dependency_groups": {}}


def row(cell_id: str = "groq:M5:N-B01:primary", text: str = "Su cita ha quedado reservada.") -> dict:
    return {"cell_id": cell_id, "provider": cell_id.split(":")[0], "architecture": cell_id.split(":")[1],
            "status": "completed", "language": "es",
            "scenario": {"id": "N-B01", "language": "es", "persona": "direct", "goal": "Reservar enfermería.",
                         "script": ["Confirma la propuesta coincidente."], "profile": {}},
            "transcript": [{"role": "user", "text": "Quiero enfermería el miércoles a las 09:20."},
                           {"role": "assistant", "text": text},
                           {"role": "user", "text": "Gracias."}],
            "effects": {"created": [], "cancelled": [], "moved": [], "reminders": []},
            "initial_state": {}, "final_state": {}, "success": True, "goal": True}


def payload(score: str = "3", quote: str = "ha quedado reservada", evidence=(2,)) -> dict:
    item = {"evidence": list(evidence), "quote": quote, "justification": "Correcto.", "score": score}
    na = {"evidence": [], "quote": "", "justification": "Sin oportunidad.", "score": "NA"}
    return {"assistant": {k: dict(item) for k in DIMENSIONS},
            "simulator": {k: dict(na) for k in SIMULATOR_DIMENSIONS}}


def test_blind_view_hides_configuration_and_oracle():
    view = episode.build(row(), SCENARIOS)
    text = episode.render(view)
    assert episode.leaks(view) == []
    assert "M5" not in text and "groq" not in text.casefold() and "success" not in json.dumps(view)
    assert "[2] asistente: Su cita ha quedado reservada." in text
    assert "Ningún cambio en la agenda." in text  # efecto observado, no el veredicto


def test_leak_detector_flags_identifying_strings():
    view = episode.build(row(text="Soy el coordinador de M5."), SCENARIOS)
    assert "M5" in episode.leaks(view)


def test_quote_must_exist_in_cited_messages():
    view = episode.build(row(), SCENARIOS)
    scores, errors = judge.validate(payload(), view)
    assert errors == [] and scores["assistant"]["clarity"]["score"] == 3
    assert scores["simulator"]["coherence"]["score"] is None  # NA nunca se convierte en 0
    _, errors = judge.validate(payload(quote="la cita fue cancelada"), view)
    assert errors and "no aparece literalmente" in errors[0]
    _, errors = judge.validate(payload(evidence=(9,)), view)
    assert errors and "mensajes existentes" in errors[0]
    assert judge.quote_found("«Su cita… reservada»", ["Su cita ha quedado reservada."])


def test_schema_is_strict_for_both_clis():
    schema = judge.output_schema()
    dim = schema["properties"]["assistant"]["properties"]["clarity"]
    assert schema["additionalProperties"] is False and dim["additionalProperties"] is False
    assert set(dim["required"]) == set(dim["properties"]) and "NA" in dim["properties"]["score"]["enum"]


class FakeJudge(judge.CliJudge):
    def __init__(self, outputs):
        super().__init__("fake", "fake-model", "high")
        self.outputs = list(outputs)
        self.calls = []

    def preflight(self):
        self.version = "fake 1.0"

    def call(self, system, text, schema):
        self.calls.append(text)
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return CallResult(item, {"input_tokens": 10})


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    rows = [row(f"groq:{arch}:N-B0{i}:primary") for arch in ("M5", "S1", "H") for i in (1, 2)]
    monkeypatch.setattr(judge, "judge_folder", lambda c: tmp_path)
    monkeypatch.setattr(judge, "campaign_rows", lambda c: rows)
    monkeypatch.setattr(judge, "scenarios_for", lambda c: SCENARIOS)
    monkeypatch.setattr(judge, "load_plan", lambda c: [{"cell_id": r["cell_id"]} for r in rows])
    return rows


def test_repair_once_then_invalid_never_zero(campaign):
    fake = FakeJudge([payload(quote="inventada"), payload()])
    outcome = judge.judge_one(fake, episode.build(campaign[0], SCENARIOS), "s", {})
    assert outcome["status"] == "valid" and outcome["attempts"] == 2
    assert "no era válida" in fake.calls[1]
    fake = FakeJudge([payload(quote="inventada"), None])
    outcome = judge.judge_one(fake, episode.build(campaign[0], SCENARIOS), "s", {})
    assert outcome["status"] == "invalid" and "scores" not in outcome


def test_run_is_resumable_and_stops_on_usage_limit(campaign, tmp_path):
    fake = FakeJudge([payload(), payload(), UsageLimit("fake")])
    counts = judge.run("c", fake, repetitions=False, log=lambda *_: None)
    assert counts["valid"] == 2 and counts["stopped"] == "usage-limit"
    fake = FakeJudge([payload()] * 10)
    counts = judge.run("c", fake, repetitions=False, log=lambda *_: None)
    assert counts["skipped"] == 2 and counts["valid"] == 4 and len(fake.calls) == 4
    lines = (tmp_path / "judgments-fake-v1.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6 and all(json.loads(x)["status"] == "valid" for x in lines)


def test_judge_failures_are_incidents_and_stop_after_three(campaign):
    fake = FakeJudge([JudgeFailure("timeout")] * 3)
    counts = judge.run("c", fake, repetitions=False, log=lambda *_: None)
    assert counts["incident"] == 3 and counts["stopped"].startswith("incidents")


def test_repetitions_add_ten_percent(campaign):
    queue = judge._queue("c", campaign, repetitions=True)
    assert sum(1 for _, rep in queue if rep == 1) == 1  # 10 % de 6 celdas, redondeado


def _plan():
    plan = []
    for op, letter in (("book", "B"), ("query", "Q"), ("reschedule", "R"), ("cancel", "C"), ("reminder", "M")):
        for i in range(1, 6):
            unit = f"N-{letter}0{i}"
            family = {"operation": op, "language": "en" if i == 3 else "es"}
            for provider in ("groq", "google"):
                for arch in ("M5", "S1", "H"):
                    plan.append({"cell_id": f"{provider}:{arch}:{unit}:primary", "unit_id": unit,
                                 "block": "primary", "family": family})
    groups = {f"G{g}": [f"N-{letter}0{(g + k) % 5 + 1}" for k, letter in enumerate("BQRCM")] for g in range(5)}
    return plan, groups


def test_sample_is_balanced_and_independent_of_results():
    plan, groups = _plan()
    units = sample.choose_units(plan, groups)
    assert len(units) == 10
    group_of = {u: g for g, members in groups.items() for u in members}
    assert sorted(list(map(group_of.get, units)).count(g) for g in groups) == [2] * 5
    shuffled = [dict(c, success=random.random() < 0.5) for c in plan]  # los resultados no intervienen
    assert sample.choose_units(shuffled, groups) == units


def test_kappa_and_comparison():
    a = {f"c{i}": {d: i % 4 for d in agreement.DIMS} for i in range(20)}
    same = agreement.compare(a, a)
    assert same["clarity"]["kappa"] == pytest.approx(1.0) and same["clarity"]["bias"] == 0
    shifted = {c: {d: min(3, v + 1) for d, v in s.items()} for c, s in a.items()}
    stats = agreement.compare(a, shifted)["clarity"]
    assert stats["bias"] > 0 and stats["within_one"] == 1.0 and stats["kappa"] < 1


def test_ppi_corrects_constant_judge_bias():
    rng = random.Random(7)
    truth = [rng.choice([1, 2, 3]) for _ in range(400)]
    judge_scores = [min(3.0, t + 0.5) for t in truth]  # el juez puntúa medio punto de más
    labeled = list(zip(truth[:40], judge_scores[:40]))
    result = agreement.ppi_mean(labeled, judge_scores[40:])
    real = sum(truth) / len(truth)
    assert result["ci"][0] <= real <= result["ci"][1]
    assert abs(result["estimate"] - real) < abs(result["judge_only"] - real)


def test_review_api_serves_portal_origin_only(monkeypatch):
    from fastapi.testclient import TestClient

    from citalab_judge import review_app
    monkeypatch.setattr(review_app, "state", lambda c: {p: {"total": 1, "done": 0, "available": ["x"], "pending_results": 0}
                                                         for p in (1, 2)})
    client = TestClient(review_app.create_app("c"))
    status = client.get("/api/status", headers={"Origin": "http://127.0.0.1:8765"})
    assert status.json()["campaign"] == "c" and status.json()["progress"]["1"]["available"] == 1
    assert status.headers["access-control-allow-origin"] == "http://127.0.0.1:8765"
    other = client.options("/api/save", headers={"Origin": "https://example.org", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in other.headers
    assert client.post("/api/save", content="sample_id=x", headers={"Content-Type": "text/plain"}).status_code == 415


def test_review_api_saves_json(monkeypatch):
    from fastapi.testclient import TestClient

    from citalab_judge import review_app
    saved = []
    monkeypatch.setattr(review_app, "save", lambda c, data: saved.append(data) or {"saved": True})
    client = TestClient(review_app.create_app("c"))
    response = client.post("/api/save", json={"sample_id": "C-1", "pass": 1})
    assert response.status_code == 200 and saved == [{"sample_id": "C-1", "pass": 1}]
