"""Vista ciega de un episodio: lo mismo para el jurado LLM y para la revisión humana.

Contiene el objetivo y las instrucciones del usuario simulado, las preferencias
vigentes del perfil, los hechos de la agenda (estado inicial y efectos
observados) y la transcripción numerada. No contiene arquitectura, proveedor,
modelo, nombres de agentes, trazas ni el veredicto del oráculo.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from citalab.config import OUTPUT
from citalab.domain.profiles import PURPOSE_KEYS, resolve
from citalab.evaluation.fixtures import build_profiles, load_scenarios, reference_time
from citalab.evaluation.review import blind_id

PATIENT = "Patient/patient-ana"
CONFIRM_BUTTON = "[pulsa Confirmar]"
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
# Cadenas que identificarían la configuración evaluada. Nunca deben llegar al juez.
FORBIDDEN = ("M5", "S1", "groq", "google", "gemini", "gpt-oss", "qwen", "langgraph", "openai",
             "orchestrator", "coordinador", "compliance")


def scenarios_for(campaign: str) -> dict:
    snapshot = OUTPUT / "evaluation" / campaign / "scenarios.json"
    return load_scenarios(snapshot if snapshot.exists() else None)


def _display(resource: dict, field: str) -> str | None:
    if field == "serviceType":
        codings = (resource.get("serviceType") or [{}])[0].get("coding") or [{}]
    else:
        codings = (resource.get(field) or {}).get("coding") or [{}]
    return codings[0].get("display") or codings[0].get("code")


def _when(value: str | None) -> str:
    return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M") if value else "?"


def _slot_ref(appointment: dict) -> str | None:
    refs = appointment.get("slot") or [{}]
    return (refs[0].get("reference") or "").removeprefix("Slot/") or None


def _own(appointment: dict) -> bool:
    return any((p.get("actor") or {}).get("reference") == PATIENT for p in appointment.get("participant", []))


def _describe(appointment: dict) -> str:
    return (f"{_display(appointment, 'serviceType')}, {_when(appointment.get('start'))}, "
            f"{_display(appointment, 'appointmentType')}")


def family_for(row: dict, scenarios: dict) -> dict:
    """Escenario de la celda. Las campañas actuales lo guardan; los pilotos se reconstruyen del plan."""
    if row.get("scenario"):
        return row["scenario"]
    from citalab.evaluation.runner import plan_cells
    blocks = ["primary", "repeat", "counterfactual", "persona", "supplement"]
    cells = plan_cells(scenarios, [row["provider"]], [row["architecture"]], blocks)
    return next((c["family"] for c in cells if c["cell_id"] == row["cell_id"]), {})


def _pilot_states(row: dict, scenarios: dict) -> tuple[dict, dict]:
    """Los pilotos no guardaron el estado de la agenda: se reconstruye el inicial y se aplican las
    escrituras confirmadas a partir de los recibos y de su propuesta."""
    import copy

    from citalab.evaluation.fixtures import build_agenda
    now = reference_time(scenarios)
    before = build_agenda(family_for(row, scenarios), now, scenarios.get("agenda")).snapshot()
    after = copy.deepcopy(before)
    proposals = {}
    for turn in row.get("turns", []):
        for event in turn.get("events", []):
            if event.get("kind") == "proposal":
                proposals[event["proposal"]["proposal_id"]] = event["proposal"]
            receipt = event.get("receipt") or {}
            if event.get("kind") != "write" or receipt.get("status") != "completed":
                continue
            proposal = proposals.get(receipt.get("proposal_id"), {})
            slots, apts = after["Slot"], after["Appointment"]
            slot = slots.get(proposal.get("slot_id") or "", {})
            if receipt["operation"] == "book" and slot:
                apts[receipt["result_id"]] = {**{k: slot.get(k) for k in ("serviceType", "appointmentType",
                                                                           "start")}, "status": "booked"}
            elif receipt["operation"] == "reschedule" and slot and receipt["result_id"] in apts:
                apts[receipt["result_id"]] = {**apts[receipt["result_id"]], "start": slot.get("start")}
            elif receipt["operation"] == "cancel" and receipt["result_id"] in apts:
                apts[receipt["result_id"]] = {**apts[receipt["result_id"]], "status": "cancelled"}
            elif receipt["operation"] == "reminder":
                after.setdefault("CommunicationRequest", {})[receipt["result_id"]] = {
                    "about": [{"reference": f"Appointment/{proposal.get('appointment_id')}"}],
                    "medium": [{"coding": [{"code": proposal.get("channel")}]}],
                    "extension": [{"url": "minutes-before", "valueInteger": proposal.get("minutes_before")}]}
    return before, after


def agenda_facts(row: dict, scenarios: dict | None = None) -> dict:
    """Hechos verificables de la agenda: estado inicial relevante y efectos observados."""
    if row.get("initial_state") is None and scenarios is not None:
        before, after = _pilot_states(row, scenarios)
    else:
        before, after = row.get("initial_state") or {}, row.get("final_state") or {}
    initial_apts = before.get("Appointment", {})
    final_apts = after.get("Appointment", {})
    own = [_describe(a) for a in sorted(initial_apts.values(), key=lambda a: a.get("start", ""))
           if _own(a) and a.get("status") == "booked"]
    free = [f"{_display(s, 'serviceType')}, {_when(s.get('start'))}, {_display(s, 'appointmentType')}"
            for s in sorted(before.get("Slot", {}).values(), key=lambda s: s.get("start", ""))
            if s.get("status") == "free"]
    effects = row.get("effects") or {}
    observed: list[str] = []
    for apt_id in effects.get("created", []):
        observed.append(f"Cita creada: {_describe(final_apts.get(apt_id, {}))}.")
    for apt_id in effects.get("cancelled", []):
        observed.append(f"Cita cancelada: {_describe(initial_apts.get(apt_id) or final_apts.get(apt_id, {}))}.")
    for apt_id in effects.get("moved", []):
        old, new = initial_apts.get(apt_id, {}), final_apts.get(apt_id, {})
        observed.append(f"Cita cambiada: de {_describe(old)} a {_describe(new)}.")
    requests = after.get("CommunicationRequest", {})
    for rem_id in effects.get("reminders", []):
        rem = requests.get(rem_id, {})
        about = ((rem.get("about") or [{}])[0].get("reference") or "").removeprefix("Appointment/")
        minutes = next((e.get("valueInteger") for e in rem.get("extension", []) if e.get("url") == "minutes-before"),
                       None)
        channel = ((rem.get("medium") or [{}])[0].get("coding") or [{}])[0].get("code")
        target = final_apts.get(about) or initial_apts.get(about) or {}
        observed.append(f"Recordatorio programado: {channel}, {minutes} minutos antes de la cita "
                        f"{_describe(target)}.")
    return {"own_appointments_before": own, "free_slots_before": free,
            "observed_effects": observed or ["Ningún cambio en la agenda."]}


def profile_facts(scenario: dict, now: datetime) -> list[str]:
    """Preferencias vigentes tras la resolución determinista del perfil (lo que el asistente podía usar)."""
    profile = build_profiles(scenario.get("profile", {}), now).get("patient-ana")
    facts = []
    for purpose in PURPOSE_KEYS:
        resolution = resolve(profile, purpose, now)
        facts += [f"{key} = {item.value}" for key, item in sorted(resolution.values.items())]
        facts += [f"{key}: valores en conflicto, sin preferencia aplicable" for key in resolution.conflicts]
    return facts


def transcript(row: dict) -> list[dict]:
    messages = []
    for index, item in enumerate(row.get("transcript") or [], start=1):
        role = "usuario" if item["role"] == "user" else "asistente"
        messages.append({"n": index, "role": role, "text": item["text"]})
    return messages


def build(row: dict, scenarios: dict) -> dict:
    scenario = family_for(row, scenarios)
    now = reference_time(scenarios)
    persona = scenarios.get("personas", {}).get(scenario.get("persona"), {})
    language = scenario.get("language", row.get("language", "es"))
    style = " ".join(part for part in (persona.get(language), scenario.get("persona_note")) if part)
    view = {
        "sample_id": blind_id(row["cell_id"]),
        "reference_time": f"{now:%Y-%m-%d %H:%M} UTC ({WEEKDAYS[now.weekday()]})",
        "conversation_language": language,
        "user": {"goal": scenario.get("goal"), "style": style,
                 "instructions": list(scenario.get("script") or []),
                 "confirm_button": f"El mensaje literal {CONFIRM_BUTTON} significa que pulsó el botón Confirmar "
                                   "de la propuesta mostrada."},
        "profile": profile_facts(scenario, now),
        "agenda": agenda_facts(row, scenarios),
        "messages": transcript(row),
    }
    return view


def input_hash(view: dict) -> str:
    return hashlib.sha256(json.dumps(view, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def leaks(view: dict) -> list[str]:
    """Cadenas identificativas presentes en la vista (debe ser vacía)."""
    text = json.dumps(view, ensure_ascii=False).casefold()
    return [word for word in FORBIDDEN if word.casefold() in text]


def render(view: dict) -> str:
    """Texto del episodio para el juez; la transcripción va numerada por mensaje."""
    user, agenda = view["user"], view["agenda"]
    lines = [f"Fecha y hora de referencia del sistema: {view['reference_time']}.",
             f"Idioma de la conversación: {view['conversation_language']}.", "",
             "## Usuario simulado",
             f"Objetivo: {user['goal']}",
             f"Estilo: {user['style']}"]
    lines += [f"Instrucción: {text}" for text in user["instructions"]]
    lines += [user["confirm_button"], "",
              "## Preferencias vigentes en el perfil del paciente (Ana, actúa en su propio nombre)"]
    lines += [f"- {fact}" for fact in view["profile"]] or ["- (ninguna)"]
    lines += ["", "## Agenda antes de la conversación", "Citas propias:"]
    lines += [f"- {fact}" for fact in agenda["own_appointments_before"]] or ["- (ninguna)"]
    lines += ["Huecos libres:"]
    lines += [f"- {fact}" for fact in agenda["free_slots_before"]] or ["- (ninguno)"]
    lines += ["", "## Efectos observados en la agenda al terminar"]
    lines += [f"- {fact}" for fact in agenda["observed_effects"]]
    lines += ["", "## Transcripción"]
    lines += [f"[{m['n']}] {m['role']}: {m['text']}" for m in view["messages"]]
    return "\n".join(lines)


def campaign_rows(campaign: str) -> list[dict]:
    from citalab.evaluation.analysis import load
    return sorted((r for r in load(campaign) if r["status"] == "completed"), key=lambda r: r["cell_id"])


def load_plan(campaign: str) -> list[dict]:
    path: Path = OUTPUT / "evaluation" / campaign / "plan.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
