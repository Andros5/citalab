"""Fallos del transporte y reanudación: ninguna llamada real a proveedores."""

import json
from dataclasses import replace

import httpx
import pytest
from conftest import draft, interp
from test_evaluation import WRITE_TURN, _apply_expected

from citalab.config import DATA, ProviderConfig, Settings
from citalab.evaluation import analysis, runner
from citalab.evaluation.fixtures import build_agenda, load_scenarios, reference_time
from citalab.llm.client import ChatClient, LLMError, RequestGate, quota_kind

INDEPENDENT = DATA / "evaluation/independent-final-v1.json"


def settings():
    providers = {p: ProviderConfig(p, "https://test.invalid", "test-key", p) for p in ("groq", "google")}
    return Settings(providers=providers, simulator=replace(providers["groq"], model="simulator"), max_attempts=2)


def client(responses, provider="google", gate=None):
    config = settings()
    result = ChatClient(config.providers[provider], config, sleep=lambda _: None, gate=gate)
    calls = []

    def request(req):
        calls.append(req)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    result._http.close()
    result._http = httpx.Client(transport=httpx.MockTransport(request))
    return result, calls


def post(c):
    return c._post("test", {}, {}, "", None, "test")


@pytest.mark.parametrize("body", [
    {"error": {"message": "Quota exceeded: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}},
    [{"error": {"message": "requests_per_day exhausted", "code": 429}}],
    {"error": {"message": "Daily token limit exceeded"}},
])
def test_daily_quota_opens_shared_circuit_without_retries(body):
    gate = RequestGate()
    c, sent = client([httpx.Response(429, json=body)], gate=gate)
    with pytest.raises(LLMError, match="provider-daily-quota"):
        post(c)
    other, other_sent = client([], gate=gate)
    with pytest.raises(LLMError, match="provider-daily-quota"):
        post(other)
    assert len(sent) == 1 and not other_sent
    assert c.sink.calls[0]["retry_scheduled"] is False
    assert c.sink.calls[0]["terminal_error"] == "provider-daily-quota"
    c.close()
    other.close()


def test_unknown_429_pauses_only_after_retry_budget_without_calling_it_daily():
    c, sent = client([httpx.Response(429, json={"error": {"message": "RESOURCE_EXHAUSTED"}}) for _ in range(2)],
                     gate=RequestGate())
    with pytest.raises(LLMError, match="provider-rate-limit-exhausted"):
        post(c)
    assert len(sent) == 2 and c.gate.pause_code == "provider-rate-limit-exhausted"
    assert quota_kind(429, "requests per minute") == "rate-limit"
    assert quota_kind(503, "daily") is None
    c.close()


@pytest.mark.parametrize("failure", [httpx.Response(429, text="per minute"), httpx.Response(503), httpx.ReadTimeout("test")])
def test_recovered_transient_does_not_pause_or_invalidate(failure):
    success = httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})
    c, sent = client([failure, success])
    assert post(c)["choices"][0]["message"]["content"] == "ok"
    assert len(sent) == 2 and c.gate.pause_code is None
    assert not any(t.get("terminal_error") for t in c.sink.calls)
    c.close()


def test_provider_failure_preserves_partial_episode_and_excludes_it_from_scores(monkeypatch):
    scenarios = load_scenarios(INDEPENDENT)
    cell = runner.plan_cells(scenarios, ["google"], ["H"], ["primary"])[0]
    real, sent = client([httpx.Response(429, text="GenerateRequestsPerDay")])
    monkeypatch.setattr(runner, "ChatClient", lambda *a, **k: real)
    simulator, sim_sent = client([])
    row, traces = runner.run_episode(cell, settings(), scenarios, simulator)
    assert row["status"] == "incident" and row["retryable"] and row["success"] is None
    assert row["incident_reason"] == "provider-daily-quota"
    assert row["turns"] and row["transcript"] and row["initial_state"] == row["final_state"]
    assert len(sent) == 1 and not sim_sent and traces[0]["http_status"] == 429
    summary = analysis.summarize([row])
    assert summary["completed"] == 0 and summary["table"][0]["incidents"] == 1
    simulator.close()


def test_simulator_failure_keeps_assistant_transcript_and_simulator_traces(monkeypatch):
    from citalab.llm.client import ScriptedClient
    scenarios = load_scenarios(INDEPENDENT)
    cell = runner.plan_cells(scenarios, ["groq"], ["H"], ["primary"], ["N-Q01"])[0]
    fake = ScriptedClient({"context": [interp("query")], "writer": [draft("Tienes dos citas.")]})
    fake.close = lambda: None
    monkeypatch.setattr(runner, "ChatClient", lambda *a, **k: fake)
    simulator, sent = client([httpx.Response(503), httpx.Response(503)], provider="groq")
    row, traces = runner.run_episode(cell, settings(), scenarios, simulator)
    assert row["status"] == "incident" and row["incident_reason"] == "simulator:provider-unavailable"
    assert row["transcript"] and row["simulator_calls"] == 2 and len(sent) == 2
    assert any(t["agent"] == "user-simulator" and t["http_status"] == 503 for t in traces)
    simulator.close()


def test_full_independent_plan_has_new_messages_new_agenda_and_consistent_effects():
    from citalab.evaluation import oracle
    old, new = load_scenarios(), load_scenarios(INDEPENDENT)
    cells = runner.plan_cells(new, ["groq", "google"], ["M5", "S1", "H"],
                              ["primary", "repeat", "counterfactual", "persona", "supplement"])
    assert len(cells) == len({c["cell_id"] for c in cells}) == 276
    assert {b: sum(c["block"] == b for c in cells) for b in ("primary", "repeat-2", "counterfactual", "persona", "supplement")} == {
        "primary": 150, "repeat-2": 30, "counterfactual": 30, "persona": 36, "supplement": 30}
    assert {f["first_message"] for f in new["families"] + new["supplement"]}.isdisjoint(
        f["first_message"] for f in old["families"] + old["supplement"])
    assert len({f["first_message"] for f in new["families"] + new["supplement"]}) == 30
    assert {f["id"] for f in new["families"]} == {f for g in new["dependency_groups"].values() for f in g}
    now = reference_time(new)
    for cell in cells[::6]:
        family = cell["family"]
        agenda = build_agenda(family, now, new["agenda"])
        assert all(s["start"] > now.isoformat() for s in agenda.resources["Slot"].values())
        before = agenda.snapshot()
        if family.get("external_occupy_after_proposal"):
            agenda.occupy_slot(family["external_occupy_after_proposal"])
        else:
            expected = dict(family["expect"])
            if expected["effect"] in ("book", "reschedule") and "slot" not in expected:
                constraints = {**expected, **family.get("preference_target", {})}
                compatible = [s for s in agenda.free_slots() if oracle._matches(
                    {**s, "slot": [{"reference": f"Slot/{s['id']}"}]}, constraints)]
                assert compatible, cell["cell_id"]
                expected["slot"] = compatible[0]["id"]
            _apply_expected(agenda, expected)
        verdict = oracle.evaluate({**family, "response": {}}, before, agenda.snapshot(), [WRITE_TURN])
        assert verdict["goal"] and verdict["safety"], cell["cell_id"]


def test_conflict_cannot_pass_with_an_unrequested_alternative_booking():
    from citalab.evaluation import oracle
    scenarios = load_scenarios(INDEPENDENT)
    family = next(f for f in scenarios["families"] if f["id"] == "N-B03")
    agenda = build_agenda(family, reference_time(scenarios), scenarios["agenda"])
    before = agenda.snapshot()
    agenda.book("patient-ana", "ind-p3", None, "alternative")
    assert not oracle.evaluate(family, before, agenda.snapshot(), [WRITE_TURN])["goal"]


def test_conflict_cannot_pass_if_the_race_was_never_exercised(monkeypatch):
    from citalab.llm.client import ScriptedClient
    scenarios = load_scenarios(INDEPENDENT)
    cell = runner.plan_cells(scenarios, ["groq"], ["H"], ["primary"], ["N-B03"])[0]
    fake = ScriptedClient({"context": [interp("query")], "writer": [draft("Here are your appointments.")]})
    fake.close = lambda: None
    monkeypatch.setattr(runner, "ChatClient", lambda *a, **k: fake)
    simulator = ScriptedClient({"user-simulator": [{"action": "end", "message": "Thanks", "goal_status": "not_possible"}]})
    row, _ = runner.run_episode(cell, settings(), scenarios, simulator)
    assert row["status"] == "completed" and not row["success"]
    assert row["checks"]["conflict_trigger"]["pass"] is False


def test_pause_resume_is_append_only_and_keeps_other_provider_running(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)
    monkeypatch.setattr(runner, "load_settings", settings)
    executions = []

    def episode(cell, config, scenarios, simulator, gate):
        executions.append(cell["cell_id"])
        row = {k: cell[k] for k in ("cell_id", "provider", "architecture", "unit_id", "family_id", "block")}
        row.update(status="completed", success=True)
        if cell["provider"] == "google":
            gate.pause("provider-daily-quota")
            row.update(status="incident", success=None)
        return row, [{"status": "error" if row["status"] == "incident" else "success"}]

    monkeypatch.setattr(runner, "run_episode", episode)
    args = ["--campaign", "recovery", "--scenarios", str(INDEPENDENT), "--blocks", "primary",
            "--families", "N-B01,N-Q01", "--archs", "H"]
    assert runner.main(args) == 0
    folder = tmp_path / "evaluation/recovery"
    progress = json.loads((folder / "progress.json").read_text())
    assert progress["completed"] == 2 and progress["incidents"] == 1 and progress["not_started"] == 1
    assert progress["paused_providers"] == {"google": "provider-daily-quota"}
    first_results = (folder / "results.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in first_results.splitlines()]
    old_traces = {r["traces_file"]: (folder / r["traces_file"]).read_bytes() for r in rows}
    executions.clear()

    def recovered(cell, *rest):
        executions.append(cell["cell_id"])
        return {**{k: cell[k] for k in ("cell_id", "provider", "architecture", "unit_id", "family_id", "block")},
                "status": "completed", "success": True}, []

    monkeypatch.setattr(runner, "run_episode", recovered)
    assert runner.main(args + ["--retry-incidents"]) == 0
    assert len(executions) == 2 and all(x.startswith("google:") for x in executions)
    results = (folder / "results.jsonl").read_text(encoding="utf-8")
    assert results.startswith(first_results) and len(results.splitlines()) == 5
    assert all((folder / name).read_bytes() == content for name, content in old_traces.items())
    progress = json.loads((folder / "progress.json").read_text())
    assert progress["completed"] == 4 and progress["incidents"] == 0 and progress["state"] == "finished"
    assert json.loads(results.splitlines()[-2])["retry_of_incident"]


def test_resume_rejects_changed_corpus_and_source_freeze(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "OUTPUT", tmp_path)
    monkeypatch.setattr(runner, "load_settings", settings)
    source = tmp_path / "input.json"
    source.write_bytes(INDEPENDENT.read_bytes())
    args = ["--campaign", "frozen", "--scenarios", str(source), "--dry-run"]
    assert runner.main(args) == 0
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        runner.main(args)
    source.write_bytes(INDEPENDENT.read_bytes())
    manifest = tmp_path / "evaluation/frozen/manifest.json"
    data = json.loads(manifest.read_text())
    data["sources"]["src/citalab/llm/client.py"] = "changed"
    manifest.write_text(json.dumps(data))
    with pytest.raises(SystemExit):
        runner.main(args)


def test_analysis_uses_campaign_dependency_groups(monkeypatch, tmp_path):
    monkeypatch.setattr(analysis, "OUTPUT", tmp_path)
    folder = tmp_path / "evaluation/new"
    folder.mkdir(parents=True)
    (folder / "scenarios.json").write_bytes(INDEPENDENT.read_bytes())
    assert analysis._dependency_groups("new") == load_scenarios(INDEPENDENT)["dependency_groups"]


def test_interactive_client_can_recover_after_quota_without_restarting():
    c, sent = client([httpx.Response(429, text="daily quota"),
                     httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})])
    with pytest.raises(LLMError):
        post(c)
    assert c.gate.pause_code is None
    assert post(c)["choices"][0]["message"]["content"] == "ok" and len(sent) == 2
    c.close()


def test_new_corpus_goals_available_in_blind_review(monkeypatch, tmp_path):
    from citalab.evaluation import review
    monkeypatch.setattr(review, "OUTPUT", tmp_path)
    scenarios = load_scenarios(INDEPENDENT)
    folder = tmp_path / "evaluation/independent"
    folder.mkdir(parents=True)
    (folder / "scenarios.json").write_bytes(INDEPENDENT.read_bytes())
    family = scenarios["supplement"][0]
    row = {"cell_id": "google:H:N-SUP-B:supplement", "family_id": family["id"],
           "operation": family["operation"], "language": family["language"], "turns": [],
           "status": "completed", "goal": True, "safety": True}
    monkeypatch.setattr(review, "order", lambda *a: [row])
    sample = review.next_sample("independent", 1)
    assert sample["goal"] == family["goal"] and sample["first_message"] == family["first_message"]
    assert "provider" not in sample and "architecture" not in sample
