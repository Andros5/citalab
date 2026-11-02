"""Comprobaciones puntuales con los modelos, posteriores a la campaña final (capítulos 8 y 9).

No forman parte de la campaña: no modifican sus resultados ni el código evaluado. Repiten un paso
concreto con los mismos modelos, temperatura e instrucciones, y una variante corregida definida aquí:

  A. Idioma de S1: primer turno de los episodios en inglés, tal como se evaluó y detectando el idioma
     del mensaje, como ya hacen M5 y H.
  B. «Otra hora»: el agente de contexto ante el primer mensaje de N-R02, con sus instrucciones y con
     una indicación añadida, y cuatro reservas legítimas como control.
  C. Explicación del orden (solo Groq): la redacción del primer turno de N-B02, N-UC-B02 y N-R02, con
     sus instrucciones y con una indicación añadida.

Los resultados se añaden a `derived/comprobaciones-modelos.jsonl` y se pueden reanudar. La opción
`--report` genera la tabla de la memoria a partir de ese registro, sin llamar a los modelos.

    PYTHONPATH=src python scripts/check_fixes_with_models.py --provider google --dry-run
    PYTHONPATH=src python scripts/check_fixes_with_models.py --provider google
    PYTHONPATH=src python scripts/check_fixes_with_models.py --report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from citalab.assistant import prompts
from citalab.assistant.engine import Assistant
from citalab.assistant.schemas import Draft, Interpretation
from citalab.config import load_settings
from citalab.domain.policy import Auth
from citalab.domain.text import detect_language
from citalab.evaluation.analysis import load
from citalab.evaluation.fixtures import build_agenda, build_profiles, load_scenarios, reference_time
from citalab.llm.client import ChatClient, LLMError, RequestGate, TraceSink

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "final-independent-v1"
FOLDER = ROOT / "output" / "evaluation" / CAMPAIGN
RESULTS = FOLDER / "derived" / "comprobaciones-modelos.jsonl"
PATIENT = "patient-ana"
INTERVAL = {"google": 4.5, "groq": 1.0}

CONTEXT_HINT = ("\n- Si own_appointments ya incluye una cita del servicio que pide y la persona habla de «otra "
                "hora», «otro día» o de cambiarla, sin decir que quiere una cita adicional, la intent es "
                "reschedule y appointment_id es esa cita.")
WRITER_HINT = ("\n- Si un plan explica por qué se ordenan las opciones (por ejemplo, según la preferencia "
               "guardada), conserva esa explicación.")
CONTROLS = ["N-B01", "N-B02", "N-B04", "N-SUP-B"]
EXPLANATION = re.compile(r"preferen|tardes|mañanas|afternoons?|mornings?", re.IGNORECASE)


class DetectingS1(Assistant):
    """S1 con la corrección: detecta el idioma del mensaje antes de construir sus instrucciones."""

    def _run_s1(self, message: str):
        if len(message.split()) >= 3:
            self.state.language = detect_language(message) or self.state.language
        return super()._run_s1(message)


def trace(row: dict) -> list[dict]:
    return json.loads((FOLDER / row["traces_file"].replace("\\", "/")).read_text(encoding="utf-8"))


def first_call(row: dict, agents: tuple[str, ...]) -> dict:
    return next(c for c in trace(row) if c["agent"] in agents and c["status"] == "success")


def usage(calls: list[dict]) -> dict:
    return {"calls": len(calls), "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
            "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
            "failed": sum(1 for c in calls if c.get("status") == "error")}


def plan(provider: str, rows: list[dict]) -> list[dict]:
    by_cell = {r["cell_id"]: r for r in rows}
    tasks = []
    seen = set()
    for row in rows:
        if row["provider"] != provider or row["architecture"] != "S1" or row["language"] != "en":
            continue
        first = row["scenario"]["first_message"]
        if detect_language(first) != "en" or first in seen:
            continue
        seen.add(first)
        for variant in ("evaluada", "idioma detectado"):
            tasks.append({"experiment": "A", "provider": provider, "variant": variant, "unit": row["unit_id"],
                          "cell": row["cell_id"], "rep": 1})
    for unit, block, reps in [("N-R02", "primary", 5)] + [(u, "supplement" if "SUP" in u else "primary", 2)
                                                          for u in CONTROLS]:
        cell = f"{provider}:H:{unit}:{block}"
        for variant in ("evaluada", "con indicación"):
            for rep in range(1, reps + 1):
                tasks.append({"experiment": "B", "provider": provider, "variant": variant, "unit": unit,
                              "cell": cell, "rep": rep})
    if provider == "groq":
        for cell in ("groq:H:N-B02:primary", "groq:H:N-UC-B02:persona", "groq:M5:N-UC-B02:persona",
                     "groq:H:N-R02:primary"):
            for variant in ("evaluada", "con indicación"):
                for rep in range(1, 4):
                    tasks.append({"experiment": "C", "provider": provider, "variant": variant,
                                  "unit": by_cell[cell]["unit_id"], "cell": cell, "rep": rep})
    return tasks


def run_a(task: dict, row: dict, client: ChatClient, scenarios: dict) -> dict:
    now = reference_time(scenarios)
    family = row["scenario"]
    agenda = build_agenda(family, now, scenarios.get("agenda"))
    profiles = build_profiles(family.get("profile", {}), now)
    cls = DetectingS1 if task["variant"] == "idioma detectado" else Assistant
    assistant = cls("S1", client, agenda, profiles, Auth(PATIENT, PATIENT))
    result = assistant.turn("message", family["first_message"])
    stored = first_call(row, ("single",))["system_prompt"]
    return {"response_language": detect_language(result.response), "fallbacks": result.fallbacks,
            "response": result.response[:400], "evaluated_language": detect_language(row["turns"][0]["assistant"]),
            "same_instructions": stored.startswith(prompts.prompt("single")), **usage(result.calls)}


def run_b(task: dict, row: dict, client: ChatClient) -> dict:
    call = first_call(row, ("context",))
    system = call["system_prompt"] + (CONTEXT_HINT if task["variant"] == "con indicación" else "")
    sink = TraceSink()
    interp = client.with_sink(sink).structured("context", system, call["input"], Interpretation, prompts.VERSION)
    evaluated = json.loads(call["output"]["content"])
    return {"intent": interp.intent, "appointment_id": interp.appointment_id,
            "evaluated_intent": evaluated.get("intent"), "message": call["input"]["message"], **usage(sink.calls)}


def run_c(task: dict, row: dict, client: ChatClient) -> dict:
    call = first_call(row, ("writer", "personalization"))
    system = call["system_prompt"] + (WRITER_HINT if task["variant"] == "con indicación" else "")
    sink = TraceSink()
    draft = client.with_sink(sink).structured(call["agent"], system, call["input"], Draft, prompts.VERSION)
    anchors = [a for p in call["input"]["plans"] for a in p.get("anchors") or []]
    evaluated = json.loads(call["output"]["content"])["text"]
    return {"kept_explanation": bool(EXPLANATION.search(draft.text)), "anchors_kept": all(a in draft.text for a in anchors),
            "evaluated_kept": bool(EXPLANATION.search(evaluated)), "text": draft.text[:400], **usage(sink.calls)}


def done_keys() -> set[tuple]:
    if not RESULTS.exists():
        return set()
    keys = set()
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if item.get("status") == "ok":
                keys.add((item["experiment"], item["provider"], item["variant"], item["cell"], item["rep"]))
    return keys


def report() -> dict:
    """Tabla de la memoria con los resultados, sin nuevas llamadas."""
    items = [json.loads(line) for line in RESULTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    items = [i for i in items if i["status"] == "ok"]
    model = {"google": "Gemini", "groq": "Groq"}
    rows, summary = [], {}

    def count(experiment: str, provider: str, variant: str, test, units=None) -> tuple[int, int]:
        group = [i for i in items if i["experiment"] == experiment and i["provider"] == provider
                 and i["variant"] == variant and (units is None or i["unit"] in units)]
        return sum(1 for i in group if test(i)), len(group)

    checks = [
        ("A", "S1 responde en inglés en el primer turno de los episodios en inglés", "idioma detectado",
         lambda i: i["response_language"] == "en", None, ("google", "groq")),
        ("B", "El agente de contexto interpreta el primer mensaje de N-R02 como un cambio", "con indicación",
         lambda i: i["intent"] == "reschedule", {"N-R02"}, ("google", "groq")),
        ("B", "Las reservas legítimas de control siguen interpretándose como reservas", "con indicación",
         lambda i: i["intent"] == "book", set(CONTROLS), ("google", "groq")),
        ("C", "La redacción conserva la explicación del orden de los huecos", "con indicación",
         lambda i: i["kept_explanation"], None, ("groq",)),
    ]
    for experiment, label, fixed, test, units, providers in checks:
        for n, provider in enumerate(providers):
            before = count(experiment, provider, "evaluada", test, units)
            after = count(experiment, provider, fixed, test, units)
            summary[f"{experiment}:{label}:{provider}"] = {"evaluated": before, "fixed": after}
            first = label if n == 0 else ""
            rows.append(f"{first} & {model[provider]} & {before[0]}/{before[1]} & {after[0]}/{after[1]} \\\\")
        rows.append("\\addlinespace")
    lines = ["\\begin{tabularx}{\\textwidth}{Ylcc}\\toprule",
             "Comprobación & Modelo & Tal como se evaluó & Con la corrección \\\\ \\midrule", *rows[:-1],
             "\\bottomrule\\end{tabularx}"]
    out = ROOT / "memoria" / "generated" / "campana-comprobaciones.tex"
    out.write_text("% Generado por scripts/check_fixes_with_models.py --report. No editar a mano.\n"
                   + "\n".join(lines) + "\n", encoding="utf-8")
    consumption = {}
    for provider in ("google", "groq"):
        group = [i for i in items if i["provider"] == provider]
        consumption[provider] = {k: sum(i.get(k, 0) or 0 for i in group) for k in ("calls", "input_tokens", "output_tokens")}
    summary["consumption"] = consumption
    (RESULTS.parent / "comprobaciones-modelos-resumen.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("google", "groq"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", action="store_true", help="genera la tabla de la memoria sin llamar a los modelos")
    args = parser.parse_args(argv)
    if args.report:
        print(json.dumps(report(), indent=2, ensure_ascii=False))
        return 0
    if not args.provider:
        parser.error("indica --provider o --report")
    rows = load(CAMPAIGN)
    by_cell = {r["cell_id"]: r for r in rows}
    tasks = plan(args.provider, rows)
    done = done_keys()
    pending = [t for t in tasks if (t["experiment"], t["provider"], t["variant"], t["cell"], t["rep"]) not in done]
    print(f"{len(tasks)} tareas, {len(pending)} pendientes "
          f"(A {sum(t['experiment'] == 'A' for t in pending)}, B {sum(t['experiment'] == 'B' for t in pending)}, "
          f"C {sum(t['experiment'] == 'C' for t in pending)})")
    if args.dry_run:
        for t in pending:
            print("  ", t["experiment"], t["variant"], t["cell"], t["rep"])
        return 0
    settings = load_settings()
    client = ChatClient(settings.providers[args.provider], settings,
                        gate=RequestGate(INTERVAL[args.provider], pause_on_quota=False))
    scenarios = load_scenarios(FOLDER / "scenarios.json")
    RESULTS.parent.mkdir(exist_ok=True)
    totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    with RESULTS.open("a", encoding="utf-8") as handle:
        for task in pending:
            row = by_cell[task["cell"]]
            try:
                if task["experiment"] == "A":
                    outcome = run_a(task, row, client, scenarios)
                elif task["experiment"] == "B":
                    outcome = run_b(task, row, client)
                else:
                    outcome = run_c(task, row, client)
                status = "ok"
            except LLMError as exc:
                outcome, status = {"error": exc.code}, "error"
            item = {**task, "status": status, "model": client.model, "at": datetime.now(UTC).isoformat(), **outcome}
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            handle.flush()
            for key in totals:
                totals[key] += outcome.get(key, 0) or 0
            brief = {k: outcome.get(k) for k in ("response_language", "intent", "kept_explanation", "error") if k in outcome}
            print(task["experiment"], task["variant"], task["cell"], task["rep"], brief, flush=True)
    print("Consumo:", totals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
