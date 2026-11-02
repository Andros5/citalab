"""Reproducción determinista de los fallos y de sus correcciones (capítulos 8 y 9 de la memoria).

No llama a ningún modelo ni modifica el código evaluado. Toma de las trazas de la campaña final las
interpretaciones y los argumentos que se registraron, ejecuta el componente tal como se evaluó y una
variante corregida definida en este script, y compara el resultado del paso que falló. También
clasifica los borradores que la comprobación de la redacción tomó por anuncios de efectos.

    PYTHONPATH=src python scripts/replay_fixes.py
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from citalab.assistant.engine import Assistant
from citalab.assistant.respond import unsupported_claim
from citalab.assistant.schemas import Interpretation
from citalab.assistant.state import ConversationState, Task
from citalab.assistant.tools import Toolbox, parse_day
from citalab.domain.agenda import Agenda, patient_of, service_of
from citalab.domain.policy import Auth
from citalab.domain.text import detect_language, local
from citalab.evaluation.analysis import load
from citalab.evaluation.fixtures import build_profiles

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "final-independent-v1"
FOLDER = ROOT / "output" / "evaluation" / CAMPAIGN
NOW = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
PATIENT = "patient-ana"

# Clasificación manual de los borradores marcados como anuncio, tras leerlos uno a uno.
# Los que no aparecen aquí eran correctos.
REAL_EFFECT = {
    ("groq:H:N-B04:primary", 2): "Da por confirmada una reserva antes de confirmarla",
    ("groq:H:N-M04:primary", 1): "Promete un recordatorio que no se ha propuesto",
    ("groq:M5:N-M04:primary", 1): "Promete un recordatorio que no se ha propuesto",
}
OTHER_DEFECT = {
    ("groq:M5:N-R05:primary", 3): "Escrito con la voz del usuario",
    ("groq:S1:N-M05:primary", 1): "Presenta como real un recordatorio simulado",
}


def trace(row: dict) -> list[dict]:
    return json.loads((FOLDER / row["traces_file"].replace("\\", "/")).read_text(encoding="utf-8"))


def interpretations(row: dict) -> list[Interpretation]:
    result = []
    for call in trace(row):
        if call["agent"] == "context" and call["status"] == "success":
            data = json.loads(call["output"]["content"])
            data = {k: (None if v == "null" else v) for k, v in data.items()}
            result.append(Interpretation.model_validate(data))
    return result


def toolbox(row: dict) -> Toolbox:
    agenda = Agenda(copy.deepcopy(row["initial_state"]), now=lambda: NOW)
    profiles = build_profiles(row["scenario"].get("profile", {}), NOW)
    state = ConversationState(subject_id=PATIENT, actor_id=PATIENT)
    return Toolbox(agenda, profiles, Auth(PATIENT, PATIENT), state)


# ------------------------------------------------------------- correcciones
def merge_evaluated(state: ConversationState, interp: Interpretation) -> Task:
    return Assistant._merge_task(SimpleNamespace(state=state), interp)


def merge_fixed(state: ConversationState, interp: Interpretation) -> Task:
    """Corrección: en una consulta, cada mensaje fija sus filtros y no hereda los anteriores."""
    if interp.intent == "query":
        values = {"service": interp.service, "date_from": interp.date_from,
                  "date_to": interp.date_to or interp.date_from, "appointment_id": interp.appointment_id}
        state.task = Task(operation="query", **{k: v for k, v in values.items() if v is not None})
        return state.task
    return merge_evaluated(state, interp)


def list_fixed(tools: Toolbox, service: str | None, date_from: str | None, date_to: str | None) -> list[dict]:
    """Corrección: una fecha final ausente significa sin límite, no el mismo día."""
    start, end = parse_day(date_from), parse_day(date_to)
    return [a for a in tools.own_appointments()
            if not (service and service_of(a) != service)
            and not (start and local(a["start"]).date() < start)
            and not (end and local(a["start"]).date() > end)]


# ------------------------------------------------------------- análisis
def carried_filter(rows: dict) -> list[dict]:
    result = []
    for config in ("groq:M5", "groq:H", "google:M5", "google:H"):
        row = rows[f"{config}:N-SUP-Q:supplement"]
        interps = interpretations(row)
        outcome = {}
        for name, merge in (("evaluated", merge_evaluated), ("fixed", merge_fixed)):
            state = ConversationState(subject_id=PATIENT, actor_id=PATIENT)
            merge(state, interps[0])
            task = merge(state, interps[1])
            tools = toolbox(row)
            listed = tools.list_appointments(task.service, task.date_from, task.date_to)["appointments"]
            outcome[name] = {"service_filter": task.service, "appointments": len(listed),
                             "hours": sorted(item["when"][-5:] for item in listed)}
        result.append({"cell": row["cell_id"], "second_interpretation_service": interps[1].service, **outcome})
    return result


def open_end(rows: dict) -> dict:
    row = rows["groq:S1:N-SUP-Q:supplement"]
    arguments = next(e["arguments"] for e in row["turns"][1]["events"]
                     if e.get("kind") == "tool" and e.get("name") == "list_appointments")
    tools = toolbox(row)
    evaluated = tools.list_appointments(arguments.get("service"), arguments.get("date_from"),
                                        arguments.get("date_to"))["appointments"]
    fixed = list_fixed(tools, arguments.get("service"), arguments.get("date_from"), arguments.get("date_to"))
    return {"cell": row["cell_id"], "arguments": arguments, "evaluated": len(evaluated), "fixed": len(fixed)}


def clarification_rule(rows: list[dict]) -> dict:
    """Regla: antes de proponer una reserva, preguntar si ya hay una cita pendiente del mismo servicio."""
    triggered = []
    for row in rows:
        own = [a for a in row["initial_state"]["Appointment"].values()
               if patient_of(a) == PATIENT and a["status"] == "booked"]
        for turn in row["turns"]:
            for event in turn.get("events", []):
                proposal = event.get("proposal") if event.get("kind") == "proposal" else None
                if not proposal or proposal["operation"] != "book":
                    continue
                slot = row["initial_state"]["Slot"].get(proposal["slot_id"])
                if slot and any(service_of(a) == service_of(slot) for a in own):
                    triggered.append(row)
                    break
            else:
                continue
            break
    failures = [r for r in triggered if not r["success"]]
    legit = [r for r in triggered if r["success"]]
    return {"triggered": len(triggered), "failures": sorted(r["cell_id"] for r in failures),
            "legitimate": sorted(r["cell_id"] for r in legit),
            "legitimate_units": sorted({r["unit_id"] for r in legit}),
            "booking_episodes": sum(1 for r in rows if r["operation"] == "book")}


def language(rows: list[dict]) -> dict:
    result = {}
    for arch in ("M5", "S1", "H"):
        counts = Counter()
        for row in rows:
            if row["architecture"] != arch or row["language"] != "en":
                continue
            for turn in row["turns"]:
                text = turn.get("assistant") or ""
                if len(text.split()) >= 4:
                    counts[detect_language(text)] += 1
                user = turn.get("user") or ""
                if len(user.split()) >= 3:
                    counts["user:" + detect_language(user)] += 1
        result[arch] = dict(counts)
    return result


def drafts(rows: list[dict]) -> dict:
    items = []
    for row in rows:
        for number, turn in enumerate(row["turns"], 1):
            for event in turn.get("events", []):
                detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
                if event.get("kind") != "agent" or "rejected_draft" not in detail:
                    continue
                if "unsupported-success-claim" not in detail["problems"]:
                    continue
                key = (row["cell_id"], number)
                kinds = sorted({p.get("kind") for p in turn.get("plans") or []})
                if key in REAL_EFFECT:
                    label, note = "real-effect", REAL_EFFECT[key]
                elif key in OTHER_DEFECT:
                    label, note = "other-defect", OTHER_DEFECT[key]
                elif set(kinds) & {"proposal", "confirm_needed"}:
                    label, note = "correct-proposal", ""
                else:
                    label, note = "correct-existing", ""
                items.append({"cell": row["cell_id"], "turn": number, "plans": kinds, "label": label, "note": note,
                              "first_problem": detail["problems"][0] == "unsupported-success-claim",
                              "trigger": unsupported_claim(detail["rejected_draft"]),
                              "draft": detail["rejected_draft"]})
    return {"total": len(items), "by_label": dict(Counter(i["label"] for i in items)),
            "first_problem": sum(i["first_problem"] for i in items),
            "triggers": dict(Counter((i["trigger"] or "").lower() for i in items).most_common()),
            "items": items}


# ------------------------------------------------------------- tablas
def write(path: Path, lines: list[str]) -> None:
    header = "% Generado por scripts/replay_fixes.py a partir de la campaña final. No editar a mano.\n"
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def table_drafts(data: dict, out: Path) -> None:
    labels = [("real-effect", "Anunciaba o prometía un efecto que no existía"),
              ("other-defect", "Tenía otro defecto real"),
              ("correct-existing", "Describía correctamente una cita existente o su conservación"),
              ("correct-proposal", "Mencionaba correctamente una propuesta o cómo confirmar")]
    lines = ["\\begin{tabular}{lr}\\toprule", "Contenido del borrador sustituido & Borradores \\\\ \\midrule"]
    for code, label in labels:
        lines.append(f"{label} & {data['by_label'].get(code, 0)} \\\\")
    lines += [f"\\midrule Total & {data['total']} \\\\", "\\bottomrule\\end{tabular}"]
    write(out / "campana-borradores.tex", lines)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    rows = load(CAMPAIGN)
    by_cell = {r["cell_id"]: r for r in rows}
    result = {"carried_filter": carried_filter(by_cell), "open_end": open_end(by_cell),
              "clarification_rule": clarification_rule(rows), "language": language(rows), "drafts": drafts(rows)}
    out = ROOT / "memoria" / "generated"
    table_drafts(result["drafts"], out)
    target = FOLDER / "derived"
    target.mkdir(exist_ok=True)
    (target / "reproduccion-correcciones.json").write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
    summary = {k: v for k, v in result.items() if k != "drafts"}
    summary["drafts"] = {k: v for k, v in result["drafts"].items() if k != "items"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
