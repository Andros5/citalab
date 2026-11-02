"""Oráculo, planificación de celdas, runner y análisis."""

from __future__ import annotations

from citalab.evaluation import oracle
from citalab.evaluation.analysis import holm, paired_bootstrap, summarize, wilson
from citalab.evaluation.fixtures import build_agenda, load_scenarios
from citalab.evaluation.runner import plan_cells
from conftest import NOW


def family(effect: dict, **extra) -> dict:
    return {"id": "X", "expect": effect, **extra}


def turn(assistant: str, events=()) -> dict:
    return {"assistant": assistant, "events": list(events)}


WRITE_TURN = turn("Hecho.", [{"kind": "policy", "decision": {"rule_id": "CMP-CONFIRM-01", "allowed": True}},
                             {"kind": "write"}])


def test_scenarios_cover_five_operations_and_plan_276_cells():
    scenarios = load_scenarios()
    assert len(scenarios["families"]) == 25
    assert {f["operation"] for f in scenarios["families"]} == {"book", "query", "reschedule", "cancel", "reminder"}
    blocks = ["primary", "repeat", "counterfactual", "persona", "supplement"]
    cells = plan_cells(scenarios, ["groq", "google"], ["M5", "S1", "H"], blocks)
    assert len(cells) == 276 and len({c["cell_id"] for c in cells}) == 276
    sizes = {block: sum(1 for c in cells if c["block"] == block) for block in
             ("primary", "repeat-2", "counterfactual", "persona", "supplement")}
    assert sizes == {"primary": 150, "repeat-2": 30, "counterfactual": 30, "persona": 36, "supplement": 30}
    assert all(c["family"].get("persona_note") for c in cells if c["block"] == "persona")
    grouped = {f for members in scenarios["dependency_groups"].values() for f in members}
    assert grouped == {f["id"] for f in scenarios["families"]}  # 5 grupos × 5 familias, sin solapes


def test_oracle_book_success():
    agenda = build_agenda({}, NOW)
    before = agenda.snapshot()
    agenda.book("patient-ana", "s7-f4", None, "k")
    verdict = oracle.evaluate(family({"effect": "book", "slot": "s7-f4"}), before, agenda.snapshot(), [WRITE_TURN])
    assert verdict["success"] and verdict["safety"]


def test_oracle_detects_unconfirmed_write_and_wrong_target():
    agenda = build_agenda({}, NOW)
    before = agenda.snapshot()
    agenda.cancel("patient-ana", "apt-s7-a1", None, "k")
    verdict = oracle.evaluate(family({"effect": "cancel", "appointment": "apt-s7-a2"}), before, agenda.snapshot(),
                              [turn("Hecho.", [{"kind": "write"}])])
    assert not verdict["goal"] and not verdict["checks"]["confirmation"]["pass"]
    assert not verdict["checks"]["preservation"]["pass"]


def test_oracle_detects_false_success_claim():
    agenda = build_agenda({}, NOW)
    snap = agenda.snapshot()
    verdict = oracle.evaluate(family({"effect": "none"}), snap, snap, [turn("Tu cita ha quedado reservada.")])
    assert verdict["goal"] and not verdict["checks"]["fidelity"]["pass"] and not verdict["success"]
    ok = oracle.evaluate(family({"effect": "none"}), snap, snap, [turn("No se ha reservado nada.")])
    assert ok["success"]


def test_oracle_response_checks():
    agenda = build_agenda({}, NOW)
    snap = agenda.snapshot()
    fam = family({"effect": "none"}, response={"not_mentions": ["10:00"], "language": "es"})
    bad = oracle.evaluate(fam, snap, snap, [turn("Your appointments are at 09:00 and 10:00.")])
    assert not bad["checks"]["response"]["pass"]
    good = oracle.evaluate(fam, snap, snap, [turn("Tienes una cita el jueves a las 09:00 y otra a las 12:00.")])
    assert good["checks"]["response"]["pass"]


def _row(provider, arch, unit, success):
    return {"cell_id": f"{provider}:{arch}:{unit}:primary", "provider": provider, "architecture": arch,
            "unit_id": unit, "block": "primary", "status": "completed", "success": success, "goal": success,
            "safety": True, "preference_adherence": None, "assistant_calls": 3, "input_tokens": 10,
            "output_tokens": 5, "llm_latency_s": 1.0, "user_turns": 2, "fallback_count": 0, "operation": "book",
            "checks": {"goal": {"pass": success}}, "fallbacks": []}


def test_analysis_paired_contrasts():
    rows = [_row("groq", a, f"U{i}", a == "H" or i % 2 == 0) for i in range(10) for a in ("M5", "S1", "H")]
    summary = summarize(rows)
    assert {(e["provider"], e["architecture"]) for e in summary["table"]} == {("groq", "M5"), ("groq", "S1"), ("groq", "H")}
    contrast = paired_bootstrap(rows, "M5", "H", "groq")
    assert contrast["n_units"] == 10 and contrast["diff"] < 0
    assert holm({"a": 0.01, "b": 0.04, "c": 0.5}) == {"a": 0.03, "b": 0.08, "c": 0.5}
    low, high = wilson(5, 10)
    assert low < 0.5 < high


def _apply_expected(agenda, expect):
    effect = expect["effect"]
    if effect == "book":
        agenda.book("patient-ana", expect["slot"], None, "k")
    elif effect == "reschedule":
        agenda.reschedule("patient-ana", expect["appointment"], None, expect["slot"], None, "k")
    elif effect == "cancel":
        agenda.cancel("patient-ana", expect["appointment"], None, "k")
    elif effect == "reminder":
        agenda.set_reminder("patient-ana", expect["appointment"], expect.get("channel", "sms"),
                            expect.get("minutes", 60), "k")


def test_new_cases_are_consistent_with_their_fixture():
    """Sin LLM: aplicar el efecto esperado sobre la agenda del caso satisface el oráculo."""
    for case in load_scenarios()["supplement"]:
        agenda = build_agenda(case, NOW)
        before = agenda.snapshot()
        _apply_expected(agenda, case["expect"])
        events = [WRITE_TURN] if case["expect"]["effect"] != "none" else [turn("Listado.")]
        verdict = oracle.evaluate({**case, "response": {}}, before, agenda.snapshot(), events)
        assert verdict["goal"] and verdict["safety"], case["id"]
