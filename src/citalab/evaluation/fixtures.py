"""Agenda y perfil aislados para cada episodio de evaluación."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from citalab.config import DATA
from citalab.domain.agenda import Agenda, build_demo_agenda, make_slot
from citalab.domain.profiles import Attribute, Profile, load_profiles

SCENARIOS_FILE = DATA / "evaluation" / "scenarios.json"
PROFILES_FILE = DATA / "synthetic" / "profiles" / "sprint3_profiles.json"

# Código, servicio y comienzo (hora local de Madrid). Mismos huecos que el corpus original.
SLOTS = {
    "f1": ("general-practice", "2026-10-06T09:00:00+02:00"),
    "f2": ("general-practice", "2026-10-06T11:00:00+02:00"),
    "f3": ("general-practice", "2026-10-06T16:00:00+02:00"),
    "f4": ("general-practice", "2026-10-07T10:00:00+02:00"),
    "f5": ("general-practice", "2026-10-09T09:00:00+02:00"),
    "f6": ("general-practice", "2026-10-12T09:00:00+02:00"),
    "f7": ("general-practice", "2026-10-13T16:00:00+02:00"),
    "n1": ("nursing", "2026-10-06T10:00:00+02:00"),
    "n2": ("nursing", "2026-10-08T16:00:00+02:00"),
    "p1": ("pediatrics", "2026-10-07T11:00:00+02:00"),
    "p2": ("pediatrics", "2026-10-12T11:00:00+02:00"),
    "p3": ("pediatrics", "2026-10-12T16:00:00+02:00"),
    "a1": ("general-practice", "2026-10-08T09:00:00+02:00"),
    "a2": ("nursing", "2026-10-09T12:00:00+02:00"),
    "b1": ("general-practice", "2026-10-08T10:00:00+02:00"),
}
APPOINTMENTS = {"apt-s7-a1": ("a1", "patient-ana"), "apt-s7-a2": ("a2", "patient-ana"),
                "apt-s7-b1": ("b1", "patient-bruno")}
PURPOSE_OF = {"preferred-time-of-day": "appointment-ranking", "preferred-modality": "appointment-ranking",
              "preferred-location": "appointment-ranking", "preferred-language": "response-adaptation",
              "preferred-detail-level": "response-adaptation", "preferred-treatment": "response-adaptation",
              "preferred-reminder-channel": "reminder-preference"}


def load_scenarios(path: Path | None = None) -> dict:
    return json.loads((path or SCENARIOS_FILE).read_text(encoding="utf-8"))


def reference_time(scenarios: dict) -> datetime:
    return datetime.fromisoformat(scenarios["reference_time"])


def _book(agenda: Agenda, appointment_id: str, slot_id: str, patient: str, at: datetime) -> None:
    slot = agenda.resources["Slot"][slot_id]
    slot["status"] = "busy"
    agenda.resources["Appointment"][appointment_id] = {
        "resourceType": "Appointment", "id": appointment_id,
        "meta": {"versionId": "1", "lastUpdated": at.isoformat()}, "status": "booked",
        "serviceType": slot["serviceType"], "appointmentType": slot["appointmentType"],
        "start": slot["start"], "end": slot["end"], "slot": [{"reference": f"Slot/{slot['id']}"}],
        "created": at.isoformat(),
        "participant": [{"actor": {"reference": f"Patient/{patient}"}, "status": "accepted"},
                        {"actor": {"reference": "Location/location-primary-001"}, "status": "accepted"}],
    }


def build_agenda(family: dict, now: datetime, fixture: dict | None = None) -> Agenda:
    agenda = build_demo_agenda(now, days=0)  # pacientes y agendas, sin huecos
    agenda.resources["Slot"] = {}
    if fixture is not None:
        for slot_id, spec in fixture["slots"].items():
            agenda.resources["Slot"][slot_id] = make_slot(slot_id, spec["service"], datetime.fromisoformat(spec["start"]))
        for appointment_id, spec in fixture["appointments"].items():
            if spec.get("optional") and not family.get(spec["optional"]):
                continue
            _book(agenda, appointment_id, spec["slot"], spec["patient"], now)
        agenda.set_clock(lambda: now)
        return agenda
    for code, (service, start) in SLOTS.items():
        slot = make_slot(f"s7-{code}", service, datetime.fromisoformat(start))
        agenda.resources["Slot"][slot["id"]] = slot
    for appointment_id, (code, patient) in APPOINTMENTS.items():
        _book(agenda, appointment_id, f"s7-{code}", patient, now)
    if family.get("pediatric"):
        _book(agenda, "apt-s7-a3", "s7-p1", "patient-ana", now)
    agenda.set_clock(lambda: now)
    return agenda


def build_profiles(overrides: dict[str, str], now: datetime) -> dict[str, Profile]:
    profiles = load_profiles(PROFILES_FILE)
    ana = profiles["patient-ana"]
    attributes = [a for a in ana.attributes if not (a.key in overrides and a.source == "declared")]
    for key, value in overrides.items():
        attributes.append(Attribute(attribute_id=f"eval-{key}", key=key, value=value, source="declared",
                                    confidence=1.0, observed_at=now, valid_from=now,
                                    purposes=[PURPOSE_OF[key]], provenance_ref="evaluation-scenario"))
    profiles["patient-ana"] = Profile(subject_id="patient-ana", version=ana.version, attributes=attributes)
    return profiles
