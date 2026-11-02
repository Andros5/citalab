"""Campaña de evaluación: familias × arquitecturas × proveedores.

Principios (aprendidos de la versión anterior):
- Un incidente se conserva; una cuota agotada pausa solo la cola afectada.
- Reanudable: las celdas ya registradas se omiten; los incidentes se repiten
  solo con `--retry-incidents` y quedan marcados como reintento.
- El estado de cada episodio es aislado; nada se comparte entre celdas.

Uso:
    python -m citalab.evaluation.runner --campaign final --providers groq,google
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import threading
import time
import traceback
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from citalab.assistant import prompts
from citalab.assistant.engine import Assistant
from citalab.assistant.respond import plan_proposal
from citalab.config import OUTPUT, ROOT, load_settings
from citalab.domain.policy import Auth
from citalab.evaluation import oracle
from citalab.evaluation.fixtures import SCENARIOS_FILE, build_agenda, build_profiles, load_scenarios, reference_time
from citalab.evaluation.simulator import UserSimulator
from citalab.llm.client import ChatClient, LLMError, RequestGate, TraceSink

ARCHITECTURES = ("M5", "S1", "H")


def plan_cells(scenarios: dict, providers: list[str], archs: list[str], blocks: list[str],
               families: list[str] | None = None) -> list[dict]:
    by_id = {f["id"]: f for f in scenarios["families"]}
    units: list[tuple[str, dict, str]] = []
    if "primary" in blocks:
        units += [(f["id"], f, "primary") for f in scenarios["families"]]
    if "repeat" in blocks:
        units += [(fid, by_id[fid], "repeat-2") for fid in scenarios["repeats"]]
    if "counterfactual" in blocks:
        for cf in scenarios["counterfactuals"]:
            base = dict(by_id[cf["base"]])
            base["profile"] = {**base.get("profile", {}), **cf["profile"]}
            for key in ("expect", "preference_target"):
                if key in cf:
                    base[key] = cf[key]
            units.append((cf["id"], base, "counterfactual"))
    if "persona" in blocks:
        for contrast in scenarios.get("persona_contrasts", []):
            base = dict(by_id[contrast["base"]])
            base["persona_note"] = contrast["persona_note"][base["language"]]
            units.append((contrast["id"], base, "persona"))
    if "supplement" in blocks:
        units += [(case["id"], case, "supplement") for case in scenarios.get("supplement", [])]
    cells = []
    for unit_id, family, block in units:
        if families and unit_id not in families and family["id"] not in families:
            continue
        for provider in providers:
            for arch in archs:
                cells.append({"cell_id": f"{provider}:{arch}:{unit_id}:{block}", "provider": provider,
                              "architecture": arch, "unit_id": unit_id, "family_id": family["id"],
                              "block": block, "family": family})
    return cells


def _compact_call(call: dict) -> dict:
    keys = ("agent", "status", "http_status", "input_tokens", "output_tokens", "total_tokens",
            "cached_input_tokens", "latency_ms", "attempt_index", "error_type", "error_code", "model",
            "terminal_error", "quota_kind", "provider", "provider_request_sent")
    return {k: call.get(k) for k in keys}


def infrastructure_failure(fallbacks: list[str]) -> str | None:
    for reason in fallbacks:
        code = reason.split(":", 1)[-1]
        if code.startswith(("provider-", "http-", "missing-api-key")):
            return code
    return None


def run_episode(cell: dict, settings, scenarios: dict, simulator_client: ChatClient,
                gate: RequestGate | None = None) -> tuple[dict[str, Any], list[dict]]:
    family = cell["family"]
    now = reference_time(scenarios)
    agenda = build_agenda(family, now, scenarios.get("agenda"))
    profiles = build_profiles(family.get("profile", {}), now)
    before = agenda.snapshot()
    client = ChatClient(settings.providers[cell["provider"]], settings, gate=gate)
    assistant = Assistant(cell["architecture"], client, agenda, profiles, Auth("patient-ana", "patient-ana"))
    simulator_sink = TraceSink()
    simulator = UserSimulator(simulator_client.with_sink(simulator_sink))
    persona = scenarios["personas"][family["persona"]][family["language"]]
    if family.get("persona_note"):
        persona = f"{persona} {family['persona_note']}"
    external = family.get("external_occupy_after_proposal")
    external_fired = False
    transcript: list[dict] = []
    turns: list[dict] = []
    traces: list[dict] = []
    action, message = "message", family["first_message"]
    end_reason = "max-turns"
    confirm_without_card = 0
    simulator_messages: list[str] = []
    started = time.perf_counter()
    incident = None
    incident_provider = None
    for number in range(1, scenarios["max_user_turns"] + 1):
        clock = time.perf_counter()
        result = assistant.turn(action, message)
        latency = time.perf_counter() - clock
        traces.extend(result.calls)
        turns.append({"n": number, "action": action, "user": message, "assistant": result.response,
                      "status": result.status, "plans": result.plans, "events": result.events,
                      "fallbacks": result.fallbacks, "latency_s": round(latency, 2),
                      "calls": [_compact_call(c) for c in result.calls]})
        transcript += [{"role": "user", "text": message if action == "message" else "[pulsa Confirmar]"},
                       {"role": "assistant", "text": result.response}]
        incident = infrastructure_failure(result.fallbacks)
        if incident:
            incident_provider = cell["provider"]
            end_reason = "infrastructure-interrupted"
            break
        proposal = assistant.state.proposal
        if external and not external_fired and proposal and proposal.slot_id == external:
            agenda.occupy_slot(external)
            external_fired = True
        if result.status == "ESCALATED":
            end_reason = "escalated"
            break
        pending = None
        if proposal:
            card = plan_proposal({"proposal": assistant.tools.describe_proposal(proposal)}, family["language"])
            pending = card.facts[0]
        try:
            user = simulator.next(family, persona, transcript, pending)
        except LLMError as exc:
            incident = f"simulator:{exc.code}"
            incident_provider = simulator_client.provider.name
            end_reason = "simulator-interrupted"
            break
        if user.action == "end":
            end_reason = f"user-end:{user.goal_status}"
            if user.message.strip():
                transcript.append({"role": "user", "text": user.message})
            break
        # El botón Confirmar solo existe si hay una propuesta en pantalla.
        if user.action == "confirm" and not proposal:
            confirm_without_card += 1
        if user.message.strip():
            simulator_messages.append(user.message)
        action = "confirm" if user.action == "confirm" and proposal else "message"
        fallback_yes = "Sí, confirmo." if family["language"] == "es" else "Yes, I confirm."
        message = "" if action == "confirm" else (user.message.strip() or fallback_yes)
    after = agenda.snapshot()
    verdict = oracle.evaluate(family, before, after, turns)
    if family["expect"]["effect"].startswith("conflict-"):
        verdict["checks"]["conflict_trigger"] = {"pass": external_fired,
                                                   "reason": "ocupación externa tras propuesta visible"}
        verdict["success"] = verdict["success"] and external_fired
        verdict["goal"] = verdict["goal"] and external_fired
    simulator = oracle.simulator_checks(family, end_reason, verdict["goal"], confirm_without_card,
                                        simulator_messages)
    calls = [c for t in turns for c in t["calls"]]
    fallbacks = [f for t in turns for f in t["fallbacks"]]
    client.close()
    return {
        "cell_id": cell["cell_id"], "provider": cell["provider"], "model": client.model,
        "architecture": cell["architecture"], "unit_id": cell["unit_id"], "family_id": cell["family_id"],
        "operation": family["operation"], "block": cell["block"], "language": family["language"],
        "status": "incident" if incident else "completed", "end_reason": end_reason,
        "incident_reason": incident, "incident_provider": incident_provider, "retryable": bool(incident),
        "external_event_fired": external_fired,
        **{k: verdict[k] for k in ("success", "goal", "safety", "preference_adherence")},
        "checks": verdict["checks"], "effects": verdict["effects"],
        "simulator_valid": simulator["valid"], "simulator_flags": simulator["flags"],
        "user_turns": len(turns), "assistant_calls": len(calls),
        "provider_errors": sum(1 for c in calls if c["status"] != "success"),
        "input_tokens": sum(c["input_tokens"] or 0 for c in calls),
        "output_tokens": sum(c["output_tokens"] or 0 for c in calls),
        "llm_latency_s": round(sum((c["latency_ms"] or 0) for c in calls) / 1000, 2),
        "active_seconds": round(time.perf_counter() - started, 2),
        "fallbacks": fallbacks, "fallback_count": len(fallbacks),
        "infra_degraded": bool(incident),
        "observed_success": verdict["success"],
        "final_status": turns[-1]["status"] if turns else None,
        "transcript": transcript, "turns": turns,
        "scenario": family,
        "simulator_calls": len(simulator_sink.calls),
        "initial_state": before, "final_state": after,
        **({"success": None} if incident else {}),
        "finished_at": datetime.now(UTC).isoformat(),
    }, traces + simulator_sink.calls


def _manifest(args, settings) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "src", "data"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", True
    prompt_hash = hashlib.sha256(json.dumps(prompts.DEFAULTS, sort_keys=True).encode()).hexdigest()
    sources = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((ROOT / "src" / "citalab").rglob("*.py"))}
    from citalab.evaluation.fixtures import PROFILES_FILE
    sources[PROFILES_FILE.relative_to(ROOT).as_posix()] = hashlib.sha256(PROFILES_FILE.read_bytes()).hexdigest()
    for name in ("prepare_independent_corpus.py", "run_independent_campaign.py"):
        script = ROOT / "scripts" / name
        sources[script.relative_to(ROOT).as_posix()] = hashlib.sha256(script.read_bytes()).hexdigest()
    return {"campaign": args.campaign, "created_at": datetime.now(UTC).isoformat(), "git_commit": commit,
            "git_dirty": dirty, "prompt_version": prompts.VERSION, "prompt_sha256": prompt_hash,
            "scenarios_path": str(args.scenarios.resolve()),
            "scenarios_sha256": hashlib.sha256(args.scenarios.read_bytes()).hexdigest(),
            "sources": sources, "families": args.families,
            "workers_per_provider": args.workers_per_provider,
            "request_intervals": {p: float(os.getenv(f"{p.upper()}_MIN_INTERVAL_SECONDS", default))
                                  for p, default in (("google", "4.5"), ("groq", "0"), ("simulator", "0"))},
            "models": {name: p.model for name, p in settings.providers.items()},
            "simulator_model": settings.simulator.model, "temperature": settings.temperature,
            "max_output_tokens": settings.max_output_tokens, "max_attempts": settings.max_attempts,
            "timeout_seconds": settings.timeout_seconds, "blocks": args.blocks.split(","),
            "providers": args.providers.split(","), "architectures": args.archs.split(",")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Campaña de evaluación CitaLab")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--providers", default="groq,google")
    parser.add_argument("--archs", default="M5,S1,H")
    parser.add_argument("--blocks", default="primary,repeat,counterfactual,persona,supplement")
    parser.add_argument("--families", default="")
    parser.add_argument("--workers-per-provider", type=int, default=1)
    parser.add_argument("--retry-incidents", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--scenarios", type=Path, default=SCENARIOS_FILE)
    parser.add_argument("--dry-run", action="store_true", help="valida y congela el plan sin llamar a las API")
    args = parser.parse_args(argv)

    settings = load_settings()
    if not args.dry_run:
        missing = [p for p in args.providers.split(",") if not settings.providers[p].available]
        if not settings.simulator.available:
            missing.append("simulator")
        if missing:
            parser.error(f"Faltan claves para: {', '.join(missing)}")
    if args.workers_per_provider < 1:
        parser.error("--workers-per-provider debe ser al menos 1")
    scenarios = load_scenarios(args.scenarios)
    out = OUTPUT / "evaluation" / args.campaign
    (out / "traces").mkdir(parents=True, exist_ok=True)
    results_file = out / "results.jsonl"
    manifest_file = out / "manifest.json"
    manifest = _manifest(args, settings)
    if manifest_file.exists():
        previous = json.loads(manifest_file.read_text(encoding="utf-8"))
        keys = ("prompt_sha256", "scenarios_sha256", "sources", "families", "models", "simulator_model",
                "temperature", "max_output_tokens", "max_attempts", "timeout_seconds", "blocks",
                "providers", "architectures", "workers_per_provider", "request_intervals")
        changed = [k for k in keys if previous.get(k) != manifest[k]]
        if changed:
            parser.error(f"El freeze no coincide ({', '.join(changed)}); usa otra campaña, conserva la anterior")
        snapshot = out / "scenarios.json"
        if not snapshot.exists() or hashlib.sha256(snapshot.read_bytes()).hexdigest() != manifest["scenarios_sha256"]:
            parser.error("La copia congelada de escenarios no coincide con el manifiesto")
    else:
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (out / "scenarios.json").write_bytes(args.scenarios.read_bytes())

    done: dict[str, dict] = {}
    if results_file.exists():
        for line in results_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["cell_id"]] = row
    families = [f for f in args.families.split(",") if f] or None
    cells = plan_cells(scenarios, args.providers.split(","), args.archs.split(","), args.blocks.split(","), families)
    plan_file = out / "plan.json"
    if not plan_file.exists():
        plan_file.write_text(json.dumps(cells, ensure_ascii=False, indent=2), encoding="utf-8")
    elif json.loads(plan_file.read_text(encoding="utf-8")) != cells:
        parser.error("El plan persistido no coincide con el corpus congelado")
    todo = [c for c in cells if c["cell_id"] not in done
            or (args.retry_incidents and done[c["cell_id"]]["status"] == "incident")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[{args.campaign}] {len(cells)} celdas planificadas, {len(cells) - len(todo)} ya hechas, {len(todo)} por ejecutar",
          flush=True)
    if args.dry_run:
        return 0

    # Un bloqueo del sistema operativo se libera también si el proceso muere.
    process_lock = (out / "runner.lock").open("a+b")
    process_lock.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            if process_lock.read(1) == b"":
                process_lock.write(b"0")
                process_lock.flush()
            process_lock.seek(0)
            msvcrt.locking(process_lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        process_lock.close()
        parser.error("Ya hay un runner activo para esta campaña")
    # Releer bajo el bloqueo evita duplicar celdas si otro runner acaba de terminar.
    if results_file.exists():
        for line in results_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["cell_id"]] = row
        todo = [c for c in todo if c["cell_id"] not in done or
                (args.retry_incidents and done[c["cell_id"]]["status"] == "incident")]

    lock = threading.Lock()
    queues: dict[str, list[dict]] = defaultdict(list)
    for cell in todo:
        queues[cell["provider"]].append(cell)
    counter = {"n": 0}
    gates = {p: RequestGate(float(os.getenv(f"{p.upper()}_MIN_INTERVAL_SECONDS", "4.5" if p == "google" else "0")))
             for p in args.providers.split(",")}
    sim_gate = RequestGate(float(os.getenv("SIMULATOR_MIN_INTERVAL_SECONDS", "0")))
    paused = {}

    def progress(state: str) -> None:
        latest = {**done}
        completed = sum(r["status"] == "completed" for r in latest.values())
        incidents = sum(r["status"] == "incident" for r in latest.values())
        payload = {"campaign": args.campaign, "state": state, "pid": os.getpid(), "planned": len(cells),
                   "completed": completed, "incidents": incidents, "not_started": len(cells) - len(latest),
                   "by_provider": {p: {"planned": sum(c["provider"] == p for c in cells),
                                       "completed": sum(r["provider"] == p and r["status"] == "completed"
                                                        for r in latest.values()),
                                       "incidents": sum(r["provider"] == p and r["status"] == "incident"
                                                        for r in latest.values())} for p in gates},
                   "paused_providers": dict(paused), "updated_at": datetime.now(UTC).isoformat()}
        temp = out / "progress.tmp"
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(out / "progress.json")

    progress("running")

    def record(row: dict, traces: list[dict]) -> None:
        with lock:
            attempt_id = uuid.uuid4().hex
            row["attempt_id"] = attempt_id
            row["attempt_number"] = done.get(row["cell_id"], {}).get("attempt_number", 0) + 1
            safe = row["cell_id"].replace(":", "_")
            trace_path = out / "traces" / f"{safe}-{attempt_id}.json"
            row["traces_file"] = str(trace_path.relative_to(out))
            trace_path.write_text(json.dumps(traces, ensure_ascii=False, default=str), encoding="utf-8")
            with results_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            done[row["cell_id"]] = row
            # Alias para el inspector existente; cada intento tiene además su fichero inmutable.
            (out / "traces" / f"{safe}.json").write_text(json.dumps(traces, ensure_ascii=False, default=str),
                                                         encoding="utf-8")
            progress("running")
            counter["n"] += 1
            mark = "OK " if row.get("success") else ("INC" if row["status"] == "incident" else "-- ")
            print(f"{counter['n']:>4}/{len(todo)} {mark} {row['cell_id']:<38} turns={row.get('user_turns', 0):>2} "
                  f"calls={row.get('assistant_calls', 0):>3} fb={row.get('fallback_count', 0)} "
                  f"{row.get('end_reason', row.get('error', ''))[:60]}", flush=True)

    def worker(cells_for_provider: list[dict]) -> None:
        simulator_client = ChatClient(settings.simulator, settings, TraceSink())
        simulator_client.gate = sim_gate
        for cell in cells_for_provider:
            gate = gates[cell["provider"]]
            if gate.pause_code or sim_gate.pause_code:
                with lock:
                    paused[cell["provider"]] = gate.pause_code or f"simulator:{sim_gate.pause_code}"
                    progress("running")
                break
            retry_of = done.get(cell["cell_id"], {}).get("status") == "incident"
            try:
                row, traces = run_episode(cell, settings, scenarios, simulator_client, gate)
            except Exception as exc:  # noqa: BLE001 -- frontera del arnés: conservar incidente y continuar
                row = {"cell_id": cell["cell_id"], "provider": cell["provider"],
                       "architecture": cell["architecture"], "unit_id": cell["unit_id"],
                       "family_id": cell["family_id"], "operation": cell["family"]["operation"],
                       "block": cell["block"], "status": "incident", "success": None,
                       "retryable": True,
                       "error": f"{type(exc).__name__}: {exc}"[:500],
                       "traceback": traceback.format_exc()[-3000:],
                       "finished_at": datetime.now(UTC).isoformat()}
                traces = []
            if retry_of:
                row["retry_of_incident"] = True
            record(row, traces)
        simulator_client.close()

    groups: list[list[dict]] = []
    for provider_cells in queues.values():
        size = max(1, args.workers_per_provider)
        groups += [provider_cells[i::size] for i in range(size)]
    try:
        with ThreadPoolExecutor(max_workers=max(1, len(groups))) as pool:
            list(pool.map(worker, groups))
        for p, gate in gates.items():
            if gate.pause_code or sim_gate.pause_code:
                paused[p] = gate.pause_code or f"simulator:{sim_gate.pause_code}"
        progress("paused" if paused else ("finished-with-incidents" if any(
            r["status"] == "incident" for r in done.values()) else "finished"))
    finally:
        process_lock.close()
    print(f"[{args.campaign}] terminado. Resultados en {results_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
