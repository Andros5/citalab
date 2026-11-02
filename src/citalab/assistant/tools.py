"""Capa de herramientas: la única puerta del asistente a la agenda y al perfil.

Las tres arquitecturas usan exactamente estas funciones. Cada una aplica el
motor de políticas; las propuestas no escriben nada, y `confirm` solo ejecuta
una propuesta vigente, presentada en el turno anterior y aceptada de forma
explícita por la persona (botón o afirmación inequívoca).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from citalab.assistant.state import ConversationState, Option, Proposal, Receipt, Shown
from citalab.domain.agenda import MADRID, SERVICES, Agenda, DomainError, parse_time, service_of
from citalab.domain.policy import Auth, check_access, check_profile, check_write
from citalab.domain.profiles import PURPOSE_KEYS, Profile, resolve
from citalab.domain.text import format_clock, format_when, local, service_label

PROPOSAL_TTL = timedelta(minutes=30)
DEFAULT_REMINDER_MINUTES = 60
MAX_OPTIONS = 5


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


_AFFIRM = re.compile(r"\b(si|sí|vale|ok|okay|de acuerdo|confirmo|confirmar|confirmala|confirmalo|adelante|"
                     r"perfecto|hazlo|reservala|reservalo|cancelala|cambiala|activalo|yes|yep|sure|"
                     r"confirm|confirmed|go ahead|please do|do it|book it|sounds good|correct)\b")
_NEGATE = re.compile(r"^\s*(no\b|espera|todavia no|aun no|mejor no|wait|not yet|don'?t|do not|hold on)")


def explicit_affirmation(text: str) -> bool:
    """Comprobación determinista y deliberadamente estrecha para confirmar por texto."""
    plain = _plain(text)
    if "?" in plain or "¿" in plain or re.search(r"\b(si|if|cuando|when)\s+(lo\s+|la\s+|i\s+)?confirm", plain):
        return False  # una pregunta o un condicional nunca confirman
    return bool(_AFFIRM.search(plain)) and not _NEGATE.search(plain)


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_clock(value: str | None) -> time | None:
    if not value:
        return None
    match = re.match(r"^(\d{1,2})[:.h](\d{2})", value.strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return time(hour, minute) if hour < 24 and minute < 60 else None


@dataclass
class Toolbox:
    agenda: Agenda
    profiles: dict[str, Profile]
    auth: Auth
    state: ConversationState
    events: list[dict] = field(default_factory=list)

    # --------------------------------------------------------------- soporte
    def now(self) -> datetime:
        return self.agenda.now()

    def _event(self, kind: str, **detail: Any) -> None:
        self.events.append({"at": self.now().isoformat(), "kind": kind, **detail})
        actor = f"Person/{self.auth.actor_id}"
        subject = self.auth.subject_id
        if kind == "write":
            receipt = detail["receipt"]
            self.agenda.audit(actor=actor, subject=subject, operation=receipt["operation"],
                              action="C" if receipt["operation"] == "book" else "U", outcome="0",
                              entity=receipt.get("result_id"), rule_id="CMP-CONFIRM-01")
        elif kind == "conflict":
            self.agenda.audit(actor=actor, subject=subject, operation=detail["proposal"]["operation"],
                              action="U", outcome="4", rule_id=detail.get("code"))
        elif kind == "denied" or (kind == "policy" and not detail["decision"]["allowed"]):
            rule = detail.get("rule_id") or detail["decision"]["rule_id"]
            self.agenda.audit(actor=actor, subject=subject, operation="access", action="R", outcome="8",
                              rule_id=rule)

    def own_appointments(self) -> list[dict]:
        return self.agenda.appointments_of(self.auth.subject_id)

    def appointment_summary(self, appointment: dict) -> dict:
        reminders = self.agenda.reminders_of(appointment["id"])
        summary = {"appointment_id": appointment["id"], "service": service_of(appointment),
                   "start": appointment["start"],
                   "when": format_when(appointment["start"], self.state.language)}
        if reminders:
            reminder = reminders[0]
            summary["reminder"] = {"channel": reminder["medium"][0]["coding"][0]["code"],
                                   "minutes_before": reminder["extension"][0]["valueInteger"]}
        return summary

    def context_summary(self) -> dict:
        """Vista mínima compartida que reciben los agentes (datos propios únicamente)."""
        proposal = self.state.proposal
        return {
            "today": self.now().astimezone(MADRID).strftime("%Y-%m-%d (%A) %H:%M Europe/Madrid"),
            "calendar_next_14_days": [
                (self.now().astimezone(MADRID).date() + timedelta(days=i)).strftime("%Y-%m-%d %A")
                for i in range(0, 15)],
            "services": {code: names["es"] for code, names in SERVICES.items()},
            "own_appointments": [self.appointment_summary(a) for a in self.own_appointments()],
            "offered_options": [o.model_dump() for o in self.state.options],
            "pending_proposal": self.describe_proposal(proposal) if proposal else None,
            "current_task": self.state.task.model_dump(exclude_none=True),
            "profile_use": "disabled-by-user" if self.state.profile_opt_out else "allowed",
        }

    # -------------------------------------------------------------- lectura
    def list_appointments(self, service: str | None = None, date_from: str | None = None,
                          date_to: str | None = None) -> dict:
        decision = check_access(self.auth, "query", self.auth.subject_id)
        self._event("tool", name="list_appointments", decision=decision.as_dict(),
                    arguments={"service": service, "date_from": date_from, "date_to": date_to})
        if not decision.allowed:
            self._event("denied", rule_id=decision.rule_id, reason=decision.reason)
            return {"error": "forbidden", "rule_id": decision.rule_id}
        self.agenda.audit(actor=f"Person/{self.auth.actor_id}", subject=self.auth.subject_id, operation="query",
                          action="R", outcome="0", rule_id=decision.rule_id)
        start, end = parse_day(date_from), parse_day(date_to) or parse_day(date_from)
        items = []
        for appointment in self.own_appointments():
            day = local(appointment["start"]).date()
            if service and service_of(appointment) != service:
                continue
            if start and day < start or end and day > end:
                continue
            items.append(appointment)
        self.state.shown = [Shown(number=i + 1, appointment_id=a["id"], start=a["start"],
                                  service=service_of(a)) for i, a in enumerate(items)]
        return {"appointments": [{"number": i + 1, **self.appointment_summary(a)}
                                 for i, a in enumerate(items)], "count": len(items),
                "filters": {"service": service, "date_from": date_from, "date_to": date_to}}

    def preferences(self, purpose: str) -> dict:
        decision = check_profile(self.auth, purpose, self.state.profile_opt_out)
        self._event("tool", name="get_preferences", decision=decision.as_dict(),
                    arguments={"purpose": purpose})
        if not decision.allowed:
            return {"available": False, "reason": decision.rule_id}
        resolution = resolve(self.profiles.get(self.auth.subject_id), purpose, self.now())
        values = {k: v.value for k, v in resolution.values.items()}
        sources = {k: v.source for k, v in resolution.values.items()}
        # Precedencia: turno > conversación > perfil (los ajustes de CitaLab no escriben el perfil).
        overlay = {"preferred-time-of-day": "time_of_day", "preferred-reminder-channel": "reminder_channel",
                   "preferred-language": "language", "preferred-detail-level": "detail_level",
                   "preferred-treatment": "treatment"}
        for key, short in overlay.items():
            for scope, store in (("conversation", self.state.conversation_preferences),
                                 ("turn", self.state.turn_preferences)):
                if short in store and key in PURPOSE_KEYS[purpose]:
                    values[key], sources[key] = store[short], scope
        return {"available": True, "purpose": purpose, "values": values, "sources": sources,
                "conflicts": resolution.conflicts}

    def find_slots(self, service: str | None, date_from: str | None = None, date_to: str | None = None,
                   time_: str | None = None, part_of_day: str | None = None,
                   use_time_preference: bool = True, exclude_slot: str | None = None,
                   modality: str | None = None) -> dict:
        decision = check_access(self.auth, "search", self.auth.subject_id)
        arguments = {"service": service, "date_from": date_from, "date_to": date_to, "time": time_,
                     "part_of_day": part_of_day, "use_time_preference": use_time_preference, "modality": modality}
        self._event("tool", name="find_slots", decision=decision.as_dict(), arguments=arguments)
        if not decision.allowed:
            return {"error": "forbidden", "options": []}
        if service not in SERVICES:
            return {"error": "service-required", "options": []}
        if modality and modality != "in-person":
            # Nunca se sustituye en silencio la modalidad pedida por otra disponible.
            return {"options": [], "unavailable_modality": modality, "exact_match": False,
                    "applied_preferences": {},
                    "searched": {"service": service, "from": date_from, "to": date_to, "time": time_,
                                 "part_of_day": part_of_day, "modality": modality}}
        now = self.now().astimezone(MADRID)
        start_day = parse_day(date_from) or now.date()
        end_day = parse_day(date_to) or (parse_day(date_from) if date_from else now.date() + timedelta(days=14))
        if end_day < start_day:
            start_day, end_day = end_day, start_day
        window_start = datetime.combine(start_day, time(0), MADRID)
        window_end = datetime.combine(end_day + timedelta(days=1), time(0), MADRID)
        slots = [s for s in self.agenda.free_slots(service, window_start, window_end) if s["id"] != exclude_slot]
        wanted = parse_clock(time_)
        if part_of_day in ("morning", "afternoon"):
            slots = [s for s in slots if (local(s["start"]).hour < 14) == (part_of_day == "morning")]
        applied: dict[str, str] = {}
        preferred = None
        if use_time_preference and not part_of_day and not wanted:
            prefs = self.preferences("appointment-ranking")
            preferred = prefs.get("values", {}).get("preferred-time-of-day") if prefs.get("available") else None
            if preferred:
                applied["preferred-time-of-day"] = preferred

        def rank(slot: dict) -> tuple:
            moment = local(slot["start"])
            exact = bool(wanted and moment.time() == wanted and (not date_from or moment.date() == start_day))
            matches_pref = preferred is None or (moment.hour < 14) == (preferred == "morning")
            closeness = abs((moment.hour * 60 + moment.minute) - (wanted.hour * 60 + wanted.minute)) if wanted else 0
            return (not exact, not matches_pref, closeness if wanted else 0, slot["start"])

        slots.sort(key=rank)
        chosen = slots[:MAX_OPTIONS]
        exact_match = bool(chosen and wanted and local(chosen[0]["start"]).time() == wanted
                           and (not date_from or local(chosen[0]["start"]).date() == start_day))
        self.state.options = [Option(number=i + 1, slot_id=s["id"], start=s["start"], service=service)
                              for i, s in enumerate(chosen)]
        return {"options": [{"number": i + 1, "slot_id": s["id"], "start": s["start"],
                             "when": format_when(s["start"], self.state.language),
                             "time": format_clock(s["start"])} for i, s in enumerate(chosen)],
                "exact_match": exact_match, "applied_preferences": applied,
                "searched": {"service": service, "from": str(start_day), "to": str(end_day),
                             "time": time_, "part_of_day": part_of_day}}

    # ---------------------------------------------------------- propuestas
    def _new_proposal(self, **values: Any) -> Proposal:
        previous = self.state.proposal
        proposal = Proposal(proposal_id=f"prop-{uuid.uuid4().hex[:10]}",
                            revision=(previous.revision + 1) if previous else 1,
                            created_turn=self.state.turn,
                            expires_at=(self.now() + PROPOSAL_TTL).isoformat(), **values)
        self.state.proposal = proposal
        self.state.receipt = None
        self._event("proposal", proposal=proposal.model_dump())
        return proposal

    def _owned_or_denied(self, appointment_id: str | None) -> dict | str:
        if not appointment_id:
            return "appointment-required"
        appointment = self.agenda.resources["Appointment"].get(appointment_id)
        if appointment is None or appointment.get("status") != "booked":
            return "appointment-not-found"
        from citalab.domain.agenda import patient_of
        decision = check_access(self.auth, "cancel", patient_of(appointment))
        if not decision.allowed:
            # Se deniega sin revelar ningún dato del recurso ajeno.
            self._event("denied", rule_id=decision.rule_id, reason=decision.reason)
            return "forbidden"
        return appointment

    def propose_booking(self, slot_id: str | None) -> dict:
        self._event("tool", name="propose_booking", arguments={"slot_id": slot_id})
        slot = self.agenda.resources["Slot"].get(slot_id or "")
        if not slot or slot["status"] != "free" or parse_time(slot["start"]) <= self.now():
            return {"error": "slot-unavailable"}
        proposal = self._new_proposal(operation="book", slot_id=slot["id"],
                                      slot_version=slot["meta"]["versionId"])
        return {"proposal": self.describe_proposal(proposal)}

    def propose_cancel(self, appointment_id: str | None) -> dict:
        self._event("tool", name="propose_cancel", arguments={"appointment_id": appointment_id})
        appointment = self._owned_or_denied(appointment_id)
        if isinstance(appointment, str):
            return {"error": appointment}
        proposal = self._new_proposal(operation="cancel", appointment_id=appointment["id"],
                                      appointment_version=appointment["meta"]["versionId"])
        return {"proposal": self.describe_proposal(proposal)}

    def propose_reschedule(self, appointment_id: str | None, slot_id: str | None) -> dict:
        self._event("tool", name="propose_reschedule",
                    arguments={"appointment_id": appointment_id, "slot_id": slot_id})
        appointment = self._owned_or_denied(appointment_id)
        if isinstance(appointment, str):
            return {"error": appointment}
        slot = self.agenda.resources["Slot"].get(slot_id or "")
        if not slot or slot["status"] != "free" or parse_time(slot["start"]) <= self.now():
            return {"error": "slot-unavailable"}
        if service_of(slot) != service_of(appointment):
            return {"error": "service-mismatch"}
        proposal = self._new_proposal(operation="reschedule", appointment_id=appointment["id"],
                                      appointment_version=appointment["meta"]["versionId"],
                                      slot_id=slot["id"], slot_version=slot["meta"]["versionId"])
        return {"proposal": self.describe_proposal(proposal)}

    def propose_reminder(self, appointment_id: str | None, channel: str | None = None,
                         minutes_before: int | None = None) -> dict:
        self._event("tool", name="propose_reminder", arguments={
            "appointment_id": appointment_id, "channel": channel, "minutes_before": minutes_before})
        appointment = self._owned_or_denied(appointment_id)
        if isinstance(appointment, str):
            return {"error": appointment}
        source = "request"
        if not channel:
            prefs = self.preferences("reminder-preference")
            channel = prefs.get("values", {}).get("preferred-reminder-channel") if prefs.get("available") else None
            source = "profile"
        if channel not in ("sms", "email", "push"):
            return {"error": "channel-required"}
        minutes = minutes_before or DEFAULT_REMINDER_MINUTES
        if not 5 <= minutes <= 7 * 24 * 60:
            return {"error": "invalid-lead-time"}
        proposal = self._new_proposal(operation="reminder", appointment_id=appointment["id"],
                                      appointment_version=appointment["meta"]["versionId"],
                                      channel=channel, minutes_before=minutes)
        result = {"proposal": self.describe_proposal(proposal), "channel_source": source}
        if not minutes_before:
            result["default_lead_time_used"] = True
        return result

    def discard(self) -> dict:
        self._event("tool", name="discard", arguments={})
        had = self.state.proposal is not None
        self.state.proposal = None
        return {"discarded": had}

    def describe_proposal(self, proposal: Proposal) -> dict:
        lang = self.state.language
        result: dict[str, Any] = {"proposal_id": proposal.proposal_id, "operation": proposal.operation,
                                  "expires_at": proposal.expires_at}
        if proposal.appointment_id:
            appointment = self.agenda.resources["Appointment"].get(proposal.appointment_id)
            if appointment:
                result["appointment"] = self.appointment_summary(appointment)
        if proposal.slot_id:
            slot = self.agenda.resources["Slot"].get(proposal.slot_id)
            if slot:
                result["slot"] = {"slot_id": slot["id"], "start": slot["start"],
                                  "when": format_when(slot["start"], lang),
                                  "service": service_label(service_of(slot), lang)}
        if proposal.channel:
            result["channel"] = proposal.channel
            result["minutes_before"] = proposal.minutes_before
        return result

    # ------------------------------------------------------- confirmación
    def proposal_live(self) -> bool:
        proposal = self.state.proposal
        return bool(proposal and parse_time(proposal.expires_at) > self.now())

    def confirm(self, *, via: str, proposal_id: str | None = None, user_text: str = "") -> dict:
        """Única ruta de escritura. `via` es "button" o "text"."""
        proposal = self.state.proposal
        self._event("tool", name="confirm", arguments={"via": via, "proposal_id": proposal_id})
        if proposal is None:
            return {"error": "no-pending-proposal"}
        if via == "button":
            confirmed = proposal_id in (None, proposal.proposal_id)
        else:
            # Por texto: la propuesta debe haberse mostrado antes de este mensaje
            # y el mensaje debe ser una afirmación explícita.
            confirmed = proposal.created_turn < self.state.turn and explicit_affirmation(user_text)
        decision = check_write(self.auth, self.auth.subject_id, confirmed=confirmed,
                               proposal_live=self.proposal_live())
        self._event("policy", decision=decision.as_dict())
        if not decision.allowed:
            return {"error": "confirmation-rejected", "rule_id": decision.rule_id, "reason": decision.reason}
        key = f"{proposal.proposal_id}:r{proposal.revision}"
        subject = self.auth.subject_id
        try:
            if proposal.operation == "book":
                result = self.agenda.book(subject, proposal.slot_id, proposal.slot_version, key)
            elif proposal.operation == "cancel":
                result = self.agenda.cancel(subject, proposal.appointment_id, proposal.appointment_version, key)
            elif proposal.operation == "reschedule":
                result = self.agenda.reschedule(subject, proposal.appointment_id, proposal.appointment_version,
                                                proposal.slot_id, proposal.slot_version, key)
            else:
                result = self.agenda.set_reminder(subject, proposal.appointment_id, proposal.channel,
                                                  proposal.minutes_before or DEFAULT_REMINDER_MINUTES, key)
        except DomainError as exc:
            self._event("conflict", code=exc.code, proposal=proposal.model_dump())
            described = self.describe_proposal(proposal)
            self.state.proposal = None
            self.state.options = []
            return {"error": "conflict", "code": exc.code, "proposal": described}
        receipt = Receipt(operation=proposal.operation, status=result["status"],
                          result_id=result.get("result_id"), idempotency_key=key,
                          at=self.now().isoformat(), proposal_id=proposal.proposal_id)
        described = self.describe_proposal(proposal)
        self.state.receipt = receipt
        self.state.proposal = None
        self.state.options = []
        self._event("write", receipt=receipt.model_dump())
        return {"receipt": receipt.model_dump(), "proposal": described}
