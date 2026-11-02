"""Simulador HIS: subconjunto FHIR R4 (Slot, Appointment, CommunicationRequest).

Es la única fuente de verdad de la agenda. Todas las escrituras comprueban
versión, disponibilidad e idempotencia bajo un mismo bloqueo, de modo que una
repetición no duplica efectos y un hueco no puede ocuparse dos veces.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

SERVICES = {
    "general-practice": {"es": "Medicina de familia", "en": "Family medicine"},
    "pediatrics": {"es": "Pediatría", "en": "Paediatrics"},
    "nursing": {"es": "Enfermería", "en": "Nursing"},
}
SCHEDULES = {
    "general-practice": "schedule-primary-001",
    "pediatrics": "schedule-pediatrics-001",
    "nursing": "schedule-nursing-001",
}
MODALITIES = {"in-person": {"es": "Presencial", "en": "In person"}}
LOCATION = {"id": "location-primary-001", "es": "Centro de Salud Demo", "en": "Demo Health Centre"}
REMINDER_CHANNELS = ("sms", "email", "push")


class DomainError(Exception):
    """Error de negocio con código estable y mensaje para el usuario."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _coding(system: str, code: str, display: str) -> dict:
    return {"coding": [{"system": system, "code": code, "display": display}]}


def make_slot(slot_id: str, service: str, start: datetime, minutes: int = 20,
              status: str = "free") -> dict:
    start = start.astimezone(MADRID)
    return {
        "resourceType": "Slot",
        "id": slot_id,
        "meta": {"versionId": "1"},
        "schedule": {"reference": f"Schedule/{SCHEDULES[service]}"},
        "status": status,
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=minutes)).isoformat(),
        "serviceType": [_coding("https://example.invalid/tfm/service", service,
                                SERVICES[service]["es"])],
        "appointmentType": _coding("https://example.invalid/tfm/modality", "in-person",
                                   MODALITIES["in-person"]["es"]),
    }


def service_of(resource: dict) -> str:
    return resource["serviceType"][0]["coding"][0]["code"]


def patient_of(appointment: dict) -> str | None:
    for participant in appointment.get("participant", []):
        reference = participant.get("actor", {}).get("reference", "")
        if reference.startswith("Patient/"):
            return reference.split("/", 1)[1]
    return None


def _fingerprint(**parameters: Any) -> str:
    return hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()


class Agenda:
    """Estado FHIR en memoria con operaciones tipadas y seguras."""

    def __init__(self, resources: dict[str, dict[str, dict]] | None = None,
                 now: Callable[[], datetime] | None = None) -> None:
        self.resources: dict[str, dict[str, dict]] = resources or {}
        for kind in ("Patient", "RelatedPerson", "Schedule", "Slot", "Appointment", "CommunicationRequest",
                     "AuditEvent"):
            self.resources.setdefault(kind, {})
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._idempotency: dict[str, tuple[str, dict]] = {}
        self.write_log: list[dict] = []

    # ---------------------------------------------------------------- lectura
    def now(self) -> datetime:
        return self._now()

    def set_clock(self, now: Callable[[], datetime]) -> None:
        self._now = now

    def patient_name(self, patient_id: str) -> str:
        patient = self.resources["Patient"].get(patient_id)
        return patient["name"][0]["text"] if patient else patient_id

    def slot(self, slot_id: str) -> dict:
        slot = self.resources["Slot"].get(slot_id)
        if not slot:
            raise DomainError("slot-not-found")
        return slot

    def appointment(self, appointment_id: str) -> dict:
        appointment = self.resources["Appointment"].get(appointment_id)
        if not appointment:
            raise DomainError("appointment-not-found")
        return appointment

    def free_slots(self, service: str | None = None, start_from: datetime | None = None,
                   start_to: datetime | None = None) -> list[dict]:
        now = self.now()
        result = []
        for slot in self.resources["Slot"].values():
            start = parse_time(slot["start"])
            if slot["status"] != "free" or start <= now:
                continue
            if service and service_of(slot) != service:
                continue
            if start_from and start < start_from:
                continue
            if start_to and start >= start_to:
                continue
            result.append(slot)
        return sorted(result, key=lambda item: item["start"])

    def appointments_of(self, patient_id: str, *, include_past: bool = False) -> list[dict]:
        now = self.now()
        items = [
            item for item in self.resources["Appointment"].values()
            if item.get("status") == "booked" and patient_of(item) == patient_id
            and (include_past or parse_time(item["end"]) > now)
        ]
        return sorted(items, key=lambda item: item["start"])

    def reminders_of(self, appointment_id: str) -> list[dict]:
        return [item for item in self.resources["CommunicationRequest"].values()
                if item.get("about", [{}])[0].get("reference") == f"Appointment/{appointment_id}"
                and item.get("status") == "active"]

    # -------------------------------------------------------------- escritura
    def _replay(self, key: str, fingerprint: str) -> dict | None:
        if not key:
            raise DomainError("idempotency-key-required")
        previous = self._idempotency.get(key)
        if previous is None:
            return None
        if previous[0] != fingerprint:
            raise DomainError("idempotency-key-reused")
        return copy.deepcopy(previous[1])

    def _remember(self, key: str, fingerprint: str, result: dict, operation: str) -> dict:
        self._idempotency[key] = (fingerprint, copy.deepcopy(result))
        self.write_log.append({"at": self.now().isoformat(), "operation": operation,
                               "idempotency_key": key, "result": copy.deepcopy(result)})
        return result

    @staticmethod
    def _bump(resource: dict) -> None:
        resource["meta"]["versionId"] = str(int(resource["meta"]["versionId"]) + 1)

    def _check_slot(self, slot_id: str, expected_version: str | None) -> dict:
        slot = self.slot(slot_id)
        if expected_version and slot["meta"]["versionId"] != expected_version:
            raise DomainError("slot-changed")
        if slot["status"] != "free":
            raise DomainError("slot-unavailable")
        if parse_time(slot["start"]) <= self.now():
            raise DomainError("slot-in-past")
        return slot

    def _owned(self, patient_id: str, appointment_id: str, expected_version: str | None) -> dict:
        appointment = self.appointment(appointment_id)
        if patient_of(appointment) != patient_id:
            raise DomainError("forbidden-subject")
        if appointment["status"] != "booked":
            raise DomainError("appointment-not-active")
        if expected_version and appointment["meta"]["versionId"] != expected_version:
            raise DomainError("appointment-changed")
        return appointment

    def book(self, patient_id: str, slot_id: str, slot_version: str | None, key: str) -> dict:
        fingerprint = _fingerprint(op="book", patient=patient_id, slot=slot_id)
        with self._lock:
            if (replay := self._replay(key, fingerprint)) is not None:
                return replay
            slot = self._check_slot(slot_id, slot_version)
            number = len(self.resources["Appointment"]) + 1
            appointment_id = f"apt-{number:04d}"
            while appointment_id in self.resources["Appointment"]:
                number += 1
                appointment_id = f"apt-{number:04d}"
            slot["status"] = "busy"
            self._bump(slot)
            self.resources["Appointment"][appointment_id] = {
                "resourceType": "Appointment",
                "id": appointment_id,
                "meta": {"versionId": "1", "lastUpdated": self.now().isoformat()},
                "status": "booked",
                "serviceType": copy.deepcopy(slot["serviceType"]),
                "appointmentType": copy.deepcopy(slot["appointmentType"]),
                "start": slot["start"],
                "end": slot["end"],
                "slot": [{"reference": f"Slot/{slot_id}"}],
                "created": self.now().isoformat(),
                "participant": [
                    {"actor": {"reference": f"Patient/{patient_id}"}, "status": "accepted"},
                    {"actor": {"reference": f"Location/{LOCATION['id']}"}, "status": "accepted"},
                ],
            }
            return self._remember(key, fingerprint, {"status": "completed", "operation": "book",
                                                      "result_id": appointment_id}, "book")

    def cancel(self, patient_id: str, appointment_id: str, version: str | None, key: str) -> dict:
        fingerprint = _fingerprint(op="cancel", patient=patient_id, appointment=appointment_id)
        with self._lock:
            if (replay := self._replay(key, fingerprint)) is not None:
                return replay
            appointment = self._owned(patient_id, appointment_id, version)
            appointment["status"] = "cancelled"
            self._bump(appointment)
            slot = self.resources["Slot"].get(appointment["slot"][0]["reference"].split("/", 1)[1])
            if slot:
                slot["status"] = "free"
                self._bump(slot)
            for reminder in self.reminders_of(appointment_id):
                reminder["status"] = "revoked"
            return self._remember(key, fingerprint, {"status": "completed", "operation": "cancel",
                                                      "result_id": appointment_id}, "cancel")

    def reschedule(self, patient_id: str, appointment_id: str, version: str | None,
                   slot_id: str, slot_version: str | None, key: str) -> dict:
        fingerprint = _fingerprint(op="reschedule", patient=patient_id,
                                   appointment=appointment_id, slot=slot_id)
        with self._lock:
            if (replay := self._replay(key, fingerprint)) is not None:
                return replay
            appointment = self._owned(patient_id, appointment_id, version)
            target = self._check_slot(slot_id, slot_version)
            if service_of(target) != service_of(appointment):
                raise DomainError("service-mismatch")
            old = self.resources["Slot"].get(appointment["slot"][0]["reference"].split("/", 1)[1])
            target["status"] = "busy"
            self._bump(target)
            if old:
                old["status"] = "free"
                self._bump(old)
            appointment.update(start=target["start"], end=target["end"],
                               slot=[{"reference": f"Slot/{slot_id}"}])
            appointment["meta"]["lastUpdated"] = self.now().isoformat()
            self._bump(appointment)
            return self._remember(key, fingerprint, {"status": "completed", "operation": "reschedule",
                                                      "result_id": appointment_id}, "reschedule")

    def set_reminder(self, patient_id: str, appointment_id: str, channel: str,
                     minutes_before: int, key: str) -> dict:
        if channel not in REMINDER_CHANNELS:
            raise DomainError("unsupported-channel")
        if not 5 <= minutes_before <= 7 * 24 * 60:
            raise DomainError("invalid-lead-time")
        fingerprint = _fingerprint(op="reminder", patient=patient_id, appointment=appointment_id,
                                   channel=channel, minutes=minutes_before)
        with self._lock:
            if (replay := self._replay(key, fingerprint)) is not None:
                return replay
            appointment = self._owned(patient_id, appointment_id, None)
            for previous in self.reminders_of(appointment_id):
                previous["status"] = "revoked"
            reminder_id = f"rem-{len(self.resources['CommunicationRequest']) + 1:04d}"
            send_at = parse_time(appointment["start"]) - timedelta(minutes=minutes_before)
            self.resources["CommunicationRequest"][reminder_id] = {
                "resourceType": "CommunicationRequest",
                "id": reminder_id,
                "meta": {"versionId": "1"},
                "status": "active",
                "subject": {"reference": f"Patient/{patient_id}"},
                "about": [{"reference": f"Appointment/{appointment_id}"}],
                "medium": [{"coding": [{"code": channel}]}],
                "occurrenceDateTime": send_at.isoformat(),
                "extension": [{"url": "minutes-before", "valueInteger": minutes_before},
                              {"url": "simulated", "valueBoolean": True}],
            }
            return self._remember(key, fingerprint, {"status": "completed", "operation": "reminder",
                                                      "result_id": reminder_id}, "reminder")

    def audit(self, *, actor: str, subject: str, action: str, outcome: str, operation: str,
              entity: str | None = None, rule_id: str | None = None) -> dict:
        """Traza mínima (FHIR AuditEvent): quién, sobre quién, qué, regla y resultado.

        No incluye mensajes ni contenido de la conversación. action: C/R/U/D;
        outcome: 0 éxito, 4 fallo, 8 denegado.
        """
        with self._lock:
            identifier = f"audit-{len(self.resources['AuditEvent']) + 1:05d}"
            event = {"resourceType": "AuditEvent", "id": identifier, "recorded": self.now().isoformat(),
                     "type": {"code": operation}, "action": action, "outcome": outcome,
                     "agent": [{"who": {"reference": actor}, "requestor": True}],
                     "entity": [{"what": {"reference": f"Patient/{subject}"}}]
                     + ([{"what": {"reference": entity}}] if entity else [])}
            if rule_id:
                event["extension"] = [{"url": "rule-id", "valueString": rule_id}]
            self.resources["AuditEvent"][identifier] = event
            return event

    def occupy_slot(self, slot_id: str) -> None:
        """Evento externo: otra persona ocupa el hueco (escenarios de conflicto)."""
        with self._lock:
            slot = self.slot(slot_id)
            if slot["status"] == "free":
                slot["status"] = "busy"
                self._bump(slot)

    # ------------------------------------------------------------- utilidades
    def snapshot(self) -> dict:
        with self._lock:
            return copy.deepcopy(self.resources)

    def restore(self, resources: dict) -> None:
        with self._lock:
            self.resources = copy.deepcopy(resources)
            self._idempotency.clear()


def build_demo_agenda(reference: datetime, days: int = 21) -> Agenda:
    """Agenda de demostración relativa a una fecha: 3 servicios, días laborables."""
    reference = reference.astimezone(MADRID)
    times = {
        "general-practice": ["09:00", "09:40", "10:20", "11:00", "11:40", "12:20", "16:00", "16:40", "17:20"],
        "pediatrics": ["09:30", "11:00", "12:30", "16:30", "17:30"],
        "nursing": ["08:30", "10:00", "12:00", "16:00", "18:00"],
    }
    resources: dict[str, dict[str, dict]] = {"Slot": {}, "Patient": {}, "Schedule": {}}
    for patient_id, name in (("patient-ana", "Ana Sintética"), ("patient-bruno", "Bruno Sintético")):
        resources["Patient"][patient_id] = {"resourceType": "Patient", "id": patient_id,
                                            "meta": {"versionId": "1"}, "name": [{"text": name}]}
    resources["RelatedPerson"] = {"representative-lucia": {
        "resourceType": "RelatedPerson", "id": "representative-lucia", "meta": {"versionId": "1"},
        "patient": {"reference": "Patient/patient-ana"}, "relationship": [{"text": "Representante sintética"}],
        "name": [{"text": "Lucía Sintética"}]}}
    for service, schedule in SCHEDULES.items():
        resources["Schedule"][schedule] = {"resourceType": "Schedule", "id": schedule, "active": True,
                                           "serviceType": [_coding("https://example.invalid/tfm/service",
                                                                   service, SERVICES[service]["es"])]}
    counter = 0
    for offset in range(1, days + 1):
        day = (reference + timedelta(days=offset)).date()
        if day.weekday() >= 5:
            continue
        for service, values in times.items():
            for value in values:
                counter += 1
                hour, minute = map(int, value.split(":"))
                start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=MADRID)
                # Ocupación determinista para que la agenda no parezca vacía.
                busy = (counter * 7) % 10 < 3
                slot_id = f"slot-{service[:3]}-{day:%m%d}-{value.replace(':', '')}"
                resources["Slot"][slot_id] = make_slot(slot_id, service, start,
                                                       status="busy" if busy else "free")
    return Agenda(resources)
