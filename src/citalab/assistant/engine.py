"""Motor conversacional con tres arquitecturas sobre el mismo núcleo.

- M5: cinco agentes LLM especializados (contexto, cumplimiento, perfiles,
  orquestación y personalización) coordinados con un grafo LangGraph.
- S1: un único agente LLM con llamadas nativas a herramientas.
- H: flujo programado; el LLM solo interpreta y redacta.

Las tres comparten herramientas, políticas, confirmación y escritura. Ningún
fallo de un LLM termina la conversación: se responde de forma segura y se
registra como `fallback`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from citalab.assistant import prompts
from citalab.assistant.respond import (
    KNOWLEDGE, TRIVIAL, Plan, check_draft, clocks_in, deterministic, notice, plan_appointments, plan_ask,
    plan_conflict, plan_info, plan_options, plan_proposal, plan_receipt, plan_simple,
)
from citalab.assistant.schemas import (
    ComplianceAdvice, Draft, Interpretation, OrchestratorStep, ProfileAdvice,
)
from citalab.assistant.state import ConversationState, Task, TurnResult
from citalab.assistant.tools import Toolbox
from citalab.domain.agenda import Agenda, service_of
from citalab.domain.policy import RULES, Auth, emergency_signal
from citalab.domain.profiles import Profile, resolve
from citalab.domain.text import detect_language, local
from citalab.llm.client import LLMError, TraceSink

Architecture = Literal["M5", "S1", "H"]
OPERATIONS = ("book", "query", "reschedule", "cancel", "reminder")
MAX_ORCHESTRATION_STEPS = 4
MAX_TOOL_ROUNDS = 6
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


class Assistant:
    """Un turno = `turn(action, message)`. El estado vive en `self.state`."""

    def __init__(self, architecture: Architecture, client: Any, agenda: Agenda,
                 profiles: dict[str, Profile], auth: Auth, state: ConversationState | None = None) -> None:
        self.architecture = architecture
        self.base_client = client
        self.agenda = agenda
        self.profiles = profiles
        self.auth = auth
        self.state = state or ConversationState(subject_id=auth.subject_id, actor_id=auth.actor_id)
        self._m5_graph = _build_m5_graph(self) if architecture == "M5" else None

    # ------------------------------------------------------------ entrada
    def turn(self, action: str, message: str = "", proposal_id: str | None = None) -> TurnResult:
        sink = TraceSink()
        self.client = self.base_client.with_sink(sink)
        self.tools = Toolbox(self.agenda, self.profiles, self.auth, self.state)
        self.fallbacks: list[str] = []
        self.turn_language: str | None = None
        self._turn_detail = None
        self.state.turn += 1
        message = (message or "").strip()
        if action == "confirm":
            result = self.tools.confirm(via="button", proposal_id=proposal_id)
            plans = self._confirmation_plans(result)
            text = self._write_after_action(plans, "[Confirmar]")
        elif action == "discard":
            self.tools.discard()
            self.state.task = Task()
            plans = [plan_simple("discarded", self.state.language, "discarded", "DISCARDED")]
            text = deterministic(plans, self.state.language)
        else:
            plans, text = {"M5": self._run_m5, "S1": self._run_s1, "H": self._run_h}[self.architecture](message)
        status = plans[-1].status if plans else "READY"
        if self.state.escalated:
            status = "ESCALATED"
        self.state.status = status  # type: ignore[assignment]
        self.state.remember(message or "[Confirmar]" if action == "confirm" else message or f"[{action}]", text)
        for reason in self.fallbacks:
            self.state.bump(f"fallback:{reason.split(':')[0]}")
        self.state.turn_preferences = {}  # las preferencias de un solo turno caducan aquí
        return TurnResult(response=text, status=status, plans=[p.as_dict() for p in plans],
                          events=self.tools.events, calls=sink.calls, fallbacks=self.fallbacks,
                          language=self._language())

    # ---------------------------------------------------------- utilidades
    def _event(self, agent: str, detail: Any) -> None:
        self.tools.events.append({"at": self.agenda.now().isoformat(), "kind": "agent", "agent": agent,
                                  "detail": detail})

    def _language(self) -> str:
        return (self.turn_language or self.state.turn_preferences.get("language")
                or self.state.conversation_preferences.get("language") or self.state.language)

    def _style(self, use_profile_detail: bool = True) -> dict:
        prefs = {} if self.state.profile_opt_out else {
            k: v.value for k, v in resolve(self.profiles.get(self.auth.subject_id), "response-adaptation",
                                           self.agenda.now()).values.items()}
        turn, conv = self.state.turn_preferences, self.state.conversation_preferences
        detail = (self._turn_detail or turn.get("detail_level") or conv.get("detail_level")
                  or (prefs.get("preferred-detail-level") if use_profile_detail else None) or "standard")
        treatment = turn.get("treatment") or conv.get("treatment") or prefs.get("preferred-treatment", "neutral")
        return {"language": self._language(), "detail_level": detail, "treatment": treatment}

    _turn_detail: str | None = None

    def _apply_directives(self, interp: Interpretation, message: str = "") -> None:
        detected = detect_language(message) if len(message.split()) >= 3 else None
        self.state.language = detected or interp.message_language
        interp.message_language = self.state.language
        # Normalización común a M5 y H: elegir una opción o cambiar condiciones no es confirmar.
        task_op, proposal = self.state.task.operation, self.state.proposal
        if interp.intent in ("confirm", "info") and interp.slot_id and not proposal and task_op and any(
                o.slot_id == interp.slot_id for o in self.state.options):
            interp.intent = task_op
        if interp.intent in ("confirm", "reject") and proposal and self._changes_proposal(interp):
            interp.intent = proposal.operation
        self._turn_detail = None
        if interp.profile_opt_out:
            self.state.profile_opt_out = True
        if interp.response_language:
            if interp.directive_scope == "conversation":
                self.state.conversation_preferences["language"] = interp.response_language
            else:
                self.turn_language = interp.response_language
        if interp.detail_level:
            if interp.directive_scope == "conversation":
                self.state.conversation_preferences["detail_level"] = interp.detail_level
            else:
                self._turn_detail = interp.detail_level

    def _merge_task(self, interp: Interpretation) -> Task:
        task = self.state.task
        values = {"service": interp.service, "date_from": interp.date_from,
                  "date_to": interp.date_to or interp.date_from, "time": interp.time,
                  "part_of_day": interp.part_of_day, "modality": interp.modality,
                  "appointment_id": interp.appointment_id, "channel": interp.reminder_channel,
                  "minutes_before": interp.reminder_minutes_before}
        if interp.intent in OPERATIONS and interp.intent != task.operation:
            task = Task(operation=interp.intent, **{k: v for k, v in values.items() if v is not None})
            self.state.options = [] if interp.intent not in ("book", "reschedule") else self.state.options
        else:
            update = {k: v for k, v in values.items() if v is not None}
            # Una nueva fecha sin hora invalida la hora anterior (y al revés no).
            if interp.date_from and not interp.time:
                update.setdefault("time", None)
            task = task.model_copy(update=update)
        self.state.task = task
        return task

    def _clean_destination(self, task: Task, appointment: dict) -> None:
        """En una reprogramación, la fecha/hora de la propia cita no puede ser el destino."""
        start = local(appointment["start"])
        if task.date_from == start.date().isoformat() and (task.time in (None, start.strftime("%H:%M"))):
            task.date_from = task.date_to = task.time = None

    def _resolve_target(self, task: Task) -> tuple[str | None, list[dict]]:
        own = self.tools.own_appointments()
        if task.appointment_id and any(a["id"] == task.appointment_id for a in own):
            return task.appointment_id, own
        candidates = own
        if task.service:
            candidates = [a for a in candidates if service_of(a) == task.service]
        # En una reprogramación la fecha pedida es el destino: no filtra el origen.
        if task.operation != "reschedule" and task.date_from:
            day = task.date_from
            dated = [a for a in candidates if local(a["start"]).date().isoformat() == day]
            candidates = dated or candidates
        return (candidates[0]["id"] if len(candidates) == 1 else None), own

    def _allowed_clocks(self, message: str, plans: list[Plan]) -> set[str]:
        values = [message, *[f for p in plans for f in p.facts]]
        values += [a["start"] for a in self.agenda.appointments_of(self.auth.subject_id, include_past=True)]
        values += [o.start for o in self.state.options]
        clocks = clocks_in(values)
        clocks |= {local(v).strftime("%H:%M") for v in values if _ISO.match(v)}
        return clocks

    def _info_facts(self) -> list[str]:
        summary = self.tools.context_summary()
        facts = [f"{i + 1}. {a['service']}: {a['when']} (id {a['appointment_id']})"
                 for i, a in enumerate(summary["own_appointments"])]
        return facts

    # ----------------------------------------------------------- redacción
    def _write(self, plans: list[Plan], message: str, agent: str = "personalization") -> str:
        """Agente de personalización (M5) o tarea de redacción (H)."""
        style = self._style()
        lang = style["language"]
        notices = list(dict.fromkeys(n for p in plans for n in p.notices))
        body_plans = [Plan(**{**p.__dict__, "notices": []}) for p in plans]
        if all(p.kind in TRIVIAL for p in body_plans):
            return "\n\n".join([*notices, deterministic(body_plans, lang)]).strip()
        payload: dict[str, Any] = {"plans": [p.as_dict() for p in body_plans], "style": style,
                                   "user_message": message}
        if any(p.kind == "info" for p in plans):
            payload["knowledge"] = KNOWLEDGE[lang]
        try:
            draft = self.client.structured(agent, prompts.prompt("personalization"), payload, Draft,
                                           prompts.VERSION)
            text = draft.text.strip()
            problems = check_draft(text, body_plans, self._allowed_clocks(message, plans))
            if problems:
                self.fallbacks.append(f"writer-check:{problems[0]}")
                self._event(agent, {"rejected_draft": text, "problems": problems})
                text = deterministic(body_plans, lang)
        except LLMError as exc:
            self.fallbacks.append(f"writer-llm:{exc.code}")
            text = deterministic(body_plans, lang)
        return "\n\n".join([*notices, text]).strip()

    def _write_after_action(self, plans: list[Plan], message: str) -> str:
        if self.architecture == "S1":
            return self._s1_write(plans, message)
        return self._write(plans, message)

    def _confirmation_plans(self, result: dict) -> list[Plan]:
        lang = self._language()
        if "receipt" in result:
            return [plan_receipt(result, lang)]
        if result.get("error") == "conflict":
            return [plan_conflict(result, lang)]
        if result.get("error") == "no-pending-proposal":
            return [plan_simple("nothing", lang, "nothing_pending")]
        return [plan_simple("confirm_needed", lang, "confirm_needed", "NEEDS_CONFIRMATION")]

    # ------------------------------------------------------- agente común
    def _interpret(self, message: str) -> Interpretation | None:
        payload = {"message": message, "conversation": self.state.history[-4:],
                   "state": self.tools.context_summary()}
        try:
            interp = self.client.structured("context", prompts.prompt("context"), payload,
                                            Interpretation, prompts.VERSION)
        except LLMError as exc:
            self.fallbacks.append(f"context-llm:{exc.code}")
            return None
        self._event("context", interp.model_dump())
        return interp

    def _interpret_failed(self) -> tuple[list[Plan], str]:
        lang = self.state.language
        key = "unavailable" if any("provider-unavailable" in f for f in self.fallbacks) else "rephrase"
        plans = [plan_simple("fallback", lang, key)]
        return plans, deterministic(plans, lang)

    def _safety(self, message: str, interp: Interpretation) -> list[Plan] | None:
        """Parada por emergencia (red determinista + señal del LLM)."""
        if emergency_signal(message) or interp.emergency:
            self.state.escalated = True
            self.tools.discard() if self.state.proposal else None
            self._event("policy", {"rule_id": "CMP-EMERGENCY-01"})
            return [Plan("escalation", [notice(self._language(), "emergency")], status="ESCALATED")]
        return None

    # ================================================================ H
    def _run_h(self, message: str) -> tuple[list[Plan], str]:
        interp = self._interpret(message)
        if interp is None:
            return self._interpret_failed()
        self._apply_directives(interp, message)
        if (stop := self._safety(message, interp)) is not None:
            return stop, deterministic(stop, self._language())
        plans = self._programmed_flow(message, interp)
        return plans, self._write(plans, message, agent="writer")

    def _programmed_flow(self, message: str, interp: Interpretation) -> list[Plan]:
        lang = self._language()
        notices = [notice(lang, "clinical")] if interp.clinical_question else []
        if interp.other_person:
            self._event("policy", {"rule_id": "CMP-REPRESENT-01"})
            if interp.intent not in ("query",):
                return [Plan("refusal", [notice(lang, "refuse_other")], notices=notices, status="BLOCKED")]
            notices.append(notice(lang, "refuse_other"))
        tb = self.tools
        intent = interp.intent
        if intent == "confirm":
            if self.state.proposal:
                result = tb.confirm(via="text", user_text=message)
                plans = self._confirmation_plans(result)
            else:
                plans = [plan_simple("nothing", lang, "nothing_pending")]
            return self._with_notices(plans, notices)
        if intent == "reject":
            tb.discard()
            self.state.task = Task()
            return self._with_notices([plan_simple("discarded", lang, "discarded", "DISCARDED")], notices)
        if intent not in OPERATIONS:
            return self._with_notices([plan_info(interp.question or message, lang, self._info_facts())], notices)
        task = self._merge_task(interp)
        plans = self._operation_plans(message, interp, task, lang)
        if interp.question and plans and plans[-1].kind != "info":
            plans.append(plan_info(interp.question, lang, []))
        return self._with_notices(plans, notices)

    def _changes_proposal(self, interp: Interpretation) -> bool:
        proposal = self.state.proposal
        if proposal is None:
            return False
        if interp.reminder_channel and interp.reminder_channel != proposal.channel:
            return True
        if interp.reminder_minutes_before and interp.reminder_minutes_before != proposal.minutes_before:
            return True
        if interp.slot_id and interp.slot_id != proposal.slot_id:
            return True
        return bool(interp.date_from or interp.time or interp.part_of_day) and proposal.operation in ("book", "reschedule")

    def _operation_plans(self, message: str, interp: Interpretation, task: Task, lang: str) -> list[Plan]:
        tb = self.tools
        notices: list[str] = []
        if task.operation == "query":
            result = tb.list_appointments(task.service, task.date_from, task.date_to)
            return [plan_appointments(result, lang)]
        if task.operation == "book":
            if not task.service:
                return self._with_notices([plan_ask("service", lang)], notices)
            if interp.slot_id and any(o.slot_id == interp.slot_id for o in self.state.options):
                return self._with_notices(self._propose(tb.propose_booking(interp.slot_id), lang), notices)
            result = tb.find_slots(task.service, task.date_from, task.date_to, task.time, task.part_of_day,
                                   use_time_preference=not self.state.profile_opt_out, modality=task.modality)
            if result.get("exact_match"):
                return self._with_notices(self._propose(tb.propose_booking(result["options"][0]["slot_id"]), lang),
                                          notices)
            return self._with_notices([plan_options(result, lang)], notices)
        target, own = self._resolve_target(task)
        if target is None:
            listing = tb.list_appointments(task.service if task.operation != "reschedule" else None)
            if not listing["appointments"]:
                listing = tb.list_appointments()
            return self._with_notices([plan_appointments(listing, lang), plan_ask("appointment", lang)], notices)
        task.appointment_id = target
        if task.operation == "cancel":
            return self._with_notices(self._propose(tb.propose_cancel(target), lang), notices)
        if task.operation == "reminder":
            result = tb.propose_reminder(target, task.channel, task.minutes_before)
            if result.get("error") == "channel-required":
                return self._with_notices([plan_ask("channel", lang)], notices)
            return self._with_notices(self._propose(result, lang), notices)
        # reprogramación
        appointment = self.agenda.appointment(target)
        self._clean_destination(task, appointment)
        if interp.slot_id and any(o.slot_id == interp.slot_id for o in self.state.options):
            return self._with_notices(self._propose(tb.propose_reschedule(target, interp.slot_id), lang), notices)
        if not (task.date_from or task.time or task.part_of_day):
            if not self.state.options:
                result = tb.find_slots(service_of(appointment), use_time_preference=not self.state.profile_opt_out,
                                       exclude_slot=appointment["slot"][0]["reference"].split("/")[1],
                                       modality=task.modality)
                return self._with_notices([plan_options(result, lang)], notices)
            return self._with_notices([plan_ask("slot_choice", lang)], notices)
        result = tb.find_slots(service_of(appointment), task.date_from, task.date_to, task.time, task.part_of_day,
                               use_time_preference=not self.state.profile_opt_out,
                               exclude_slot=appointment["slot"][0]["reference"].split("/")[1],
                               modality=task.modality)
        if result.get("exact_match"):
            return self._with_notices(self._propose(tb.propose_reschedule(target, result["options"][0]["slot_id"]),
                                                    lang), notices)
        return self._with_notices([plan_options(result, lang)], notices)

    @staticmethod
    def _with_notices(plans: list[Plan], notices: list[str]) -> list[Plan]:
        if notices and plans:
            plans[0].notices = [*notices, *plans[0].notices]
        return plans

    @staticmethod
    def _propose(result: dict, lang: str) -> list[Plan]:
        if "proposal" in result:
            return [plan_proposal(result, lang)]
        error = result.get("error", "")
        if error == "forbidden":
            return [Plan("refusal", [notice(lang, "refuse_other")], status="BLOCKED")]
        if error == "slot-unavailable":
            return [plan_conflict({"proposal": {"operation": "book"}}, lang)]
        return [plan_ask("appointment" if "appointment" in error else "generic", lang)]

    # ================================================================ M5
    def _run_m5(self, message: str) -> tuple[list[Plan], str]:
        final = self._m5_graph.invoke({"message": message, "observations": [], "steps": 0})
        return final["plans"], final["text"]

    def _m5_compliance(self, message: str, interp: Interpretation) -> ComplianceAdvice:
        payload = {"message": message, "interpretation": interp.model_dump(),
                   "rules": {k: v["title"] for k, v in RULES.items()}}
        try:
            advice = self.client.structured("compliance", prompts.prompt("compliance"), payload,
                                            ComplianceAdvice, prompts.VERSION)
        except LLMError as exc:
            self.fallbacks.append(f"compliance-llm:{exc.code}")
            advice = ComplianceAdvice(
                decision="refuse" if interp.other_person and interp.intent != "query" else "proceed",
                rule_id="CMP-REPRESENT-01" if interp.other_person else "none",
                clinical_notice=interp.clinical_question, reason="fallback")
        self._event("compliance", advice.model_dump())
        return advice

    def _m5_profile(self, message: str, interp: Interpretation) -> ProfileAdvice | None:
        task = self.state.task
        needed = task.operation in ("book", "reschedule", "reminder")
        if not needed or self.state.profile_opt_out:
            return None
        purposes = ["appointment-ranking"] if task.operation in ("book", "reschedule") else ["reminder-preference"]
        views = {p: self.tools.preferences(p) for p in purposes}
        if not any(v.get("values") for v in views.values()):
            return ProfileAdvice(use_time_preference=False, use_reminder_channel=False,
                                 use_language_preference=False, use_detail_preference=True, reason="no-saved-values")
        payload = {"message": message, "current_task": task.model_dump(exclude_none=True),
                   "authorized_preferences": views}
        try:
            advice = self.client.structured("profile", prompts.prompt("profile"), payload, ProfileAdvice,
                                            prompts.VERSION)
        except LLMError as exc:
            self.fallbacks.append(f"profile-llm:{exc.code}")
            advice = ProfileAdvice(use_time_preference=not (task.part_of_day or task.time),
                                   use_reminder_channel=not task.channel, use_language_preference=False,
                                   use_detail_preference=True, reason="fallback")
        self._event("profile", advice.model_dump())
        return advice

    def _m5_allowed(self, interp: Interpretation) -> list[str]:
        op = self.state.task.operation
        allowed = ["respond", "ask", "refuse", "list_appointments"]
        if op in ("book", "reschedule"):
            allowed.append("find_slots")
        if op == "book" and self.state.options:
            allowed.append("propose_booking")
        if op == "reschedule" and self.state.options:
            allowed.append("propose_reschedule")
        if op == "cancel":
            allowed.append("propose_cancel")
        if op == "reminder":
            allowed.append("propose_reminder")
        if self.state.proposal and interp.intent == "confirm":
            allowed.append("confirm")
        if self.state.proposal:
            allowed.append("discard")
        return allowed

    def _m5_execute(self, step: OrchestratorStep, message: str, advice: ProfileAdvice | None) -> dict:
        tb, task = self.tools, self.state.task
        use_pref = bool(advice and advice.use_time_preference)
        if step.action == "list_appointments":
            if task.operation == "query":
                return tb.list_appointments(task.service, task.date_from, task.date_to)
            return tb.list_appointments()
        if step.action == "find_slots":
            service = task.service
            exclude = None
            appointment_id = step.appointment_id or task.appointment_id
            if task.operation == "reschedule" and appointment_id in self.agenda.resources["Appointment"]:
                appointment = self.agenda.appointment(appointment_id)
                self._clean_destination(task, appointment)
                service = service_of(appointment)
                exclude = appointment["slot"][0]["reference"].split("/")[1]
            return tb.find_slots(service, task.date_from, task.date_to, task.time, task.part_of_day,
                                 use_time_preference=use_pref, exclude_slot=exclude, modality=task.modality)
        if step.action == "propose_booking":
            return tb.propose_booking(step.slot_id)
        if step.action == "propose_reschedule":
            return tb.propose_reschedule(step.appointment_id or task.appointment_id, step.slot_id)
        if step.action == "propose_cancel":
            return tb.propose_cancel(step.appointment_id or task.appointment_id)
        if step.action == "propose_reminder":
            channel = task.channel
            if not channel and advice is not None and not advice.use_reminder_channel:
                return {"error": "channel-required"}
            return tb.propose_reminder(step.appointment_id or task.appointment_id, channel, task.minutes_before)
        if step.action == "confirm":
            return tb.confirm(via="text", user_text=message)
        if step.action == "discard":
            self.state.task = Task()
            return tb.discard()
        return {}

    def _plans_from_observations(self, observations: list[dict], lang: str) -> list[Plan]:
        """Plan de respuesta a partir de lo que realmente devolvieron las herramientas."""
        for obs in reversed(observations):
            result, action = obs["result"], obs["action"]
            if "receipt" in result:
                return [plan_receipt(result, lang)]
            if result.get("error") == "conflict":
                return [plan_conflict(result, lang)]
            if "proposal" in result and action.startswith("propose"):
                return [plan_proposal(result, lang)]
            if action == "discard":
                return [plan_simple("discarded", lang, "discarded", "DISCARDED")]
            if "options" in result:
                return [plan_options(result, lang)]
            if "appointments" in result:
                return [plan_appointments(result, lang)]
            if result.get("error") == "forbidden":
                return [Plan("refusal", [notice(lang, "refuse_other")], status="BLOCKED")]
            if result.get("error") == "channel-required":
                return [plan_ask("channel", lang)]
            if result.get("error") == "confirmation-rejected":
                return [plan_simple("confirm_needed", lang, "confirm_needed", "NEEDS_CONFIRMATION")]
        return []

    # ================================================================ S1
    def _s1_tools(self) -> list[dict]:
        def fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
            return {"type": "function", "function": {"name": name, "description": description, "parameters": {
                "type": "object", "properties": properties, "required": required or [],
                "additionalProperties": False}}}
        service = {"type": "string", "enum": ["general-practice", "pediatrics", "nursing"]}
        day = {"type": "string", "description": "YYYY-MM-DD"}
        return [
            fn("list_appointments", "Lista las citas propias pendientes, con filtros opcionales.",
               {"service": service, "date_from": day, "date_to": day}),
            fn("find_slots", "Busca huecos libres de un servicio (no reserva nada).",
               {"service": service, "date_from": day, "date_to": day,
                "time": {"type": "string", "description": "HH:MM exacta si la pide"},
                "part_of_day": {"type": "string", "enum": ["morning", "afternoon"]},
                "use_time_preference": {"type": "boolean"},
                "modality": {"type": "string", "enum": ["in-person", "phone", "video"]},
                "exclude_appointment_id": {"type": "string", "description": "cita que se quiere mover"}},
               ["service"]),
            fn("get_preferences", "Preferencias autorizadas del perfil para una finalidad.",
               {"purpose": {"type": "string", "enum": ["appointment-ranking", "response-adaptation",
                                                       "reminder-preference"]}}, ["purpose"]),
            fn("propose_booking", "Crea una propuesta de reserva para un hueco ofrecido.",
               {"slot_id": {"type": "string"}}, ["slot_id"]),
            fn("propose_reschedule", "Propuesta de mover una cita propia a un hueco libre.",
               {"appointment_id": {"type": "string"}, "slot_id": {"type": "string"}},
               ["appointment_id", "slot_id"]),
            fn("propose_cancel", "Propuesta de cancelar una cita propia.",
               {"appointment_id": {"type": "string"}}, ["appointment_id"]),
            fn("propose_reminder", "Propuesta de recordatorio simulado para una cita propia.",
               {"appointment_id": {"type": "string"}, "channel": {"type": "string", "enum": ["sms", "email", "push"]},
                "minutes_before": {"type": "integer"}}, ["appointment_id"]),
            fn("confirm_pending_proposal", "Aplica la propuesta pendiente; solo si la persona la acepta.", {}),
            fn("discard_pending_proposal", "Descarta la propuesta pendiente.", {}),
        ]

    def _s1_call_tool(self, name: str, args: dict, message: str) -> dict:
        tb = self.tools
        if name == "list_appointments":
            return tb.list_appointments(args.get("service"), args.get("date_from"), args.get("date_to"))
        if name == "find_slots":
            exclude = None
            if args.get("exclude_appointment_id") in self.agenda.resources["Appointment"]:
                appointment = self.agenda.resources["Appointment"][args["exclude_appointment_id"]]
                if appointment.get("status") == "booked":
                    exclude = appointment["slot"][0]["reference"].split("/")[1]
            return tb.find_slots(args.get("service"), args.get("date_from"), args.get("date_to"), args.get("time"),
                                 args.get("part_of_day"), bool(args.get("use_time_preference", False)), exclude,
                                 args.get("modality"))
        if name == "get_preferences":
            return tb.preferences(args.get("purpose", "response-adaptation"))
        if name == "propose_booking":
            return tb.propose_booking(args.get("slot_id"))
        if name == "propose_reschedule":
            return tb.propose_reschedule(args.get("appointment_id"), args.get("slot_id"))
        if name == "propose_cancel":
            return tb.propose_cancel(args.get("appointment_id"))
        if name == "propose_reminder":
            return tb.propose_reminder(args.get("appointment_id"), args.get("channel"), args.get("minutes_before"))
        if name == "confirm_pending_proposal":
            return tb.confirm(via="text", user_text=message)
        if name == "discard_pending_proposal":
            return tb.discard()
        return {"error": f"unknown-tool:{name}"}

    def _s1_messages(self, message: str) -> list[dict]:
        style = self._style()
        system = (prompts.prompt("single") + "\n\nESTADO (datos propios autorizados):\n"
                  + json.dumps(self.tools.context_summary(), ensure_ascii=False, default=str)
                  + "\nESTILO PREFERIDO: " + json.dumps(style, ensure_ascii=False))
        messages = [{"role": "system", "content": system}]
        for exchange in self.state.history[-4:]:
            messages += [{"role": "user", "content": exchange["user"]},
                         {"role": "assistant", "content": exchange["assistant"]}]
        messages.append({"role": "user", "content": message})
        return messages

    def _run_s1(self, message: str) -> tuple[list[Plan], str]:
        lang_guess = self.state.language
        if emergency_signal(message):
            self.state.escalated = True
            plans = [Plan("escalation", [notice(lang_guess, "emergency")], status="ESCALATED")]
            return plans, deterministic(plans, lang_guess)
        messages = self._s1_messages(message)
        tools = self._s1_tools()
        observations: list[dict] = []
        text = None
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                reply = self.client.chat("single", messages, tools, prompts.VERSION)
                calls = reply.get("tool_calls") or []
                if not calls:
                    text = (reply.get("content") or "").strip()
                    break
                messages.append({"role": "assistant", "content": reply.get("content") or "", "tool_calls": calls})
                for call in calls:
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    result = self._s1_call_tool(call["function"]["name"], args, message)
                    observations.append({"action": _s1_action(call["function"]["name"]), "result": result})
                    self._event("single", {"tool": call["function"]["name"], "arguments": args})
                    messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                     "content": json.dumps(result, ensure_ascii=False, default=str)})
        except LLMError as exc:
            self.fallbacks.append(f"single-llm:{exc.code}")
        lang = self._language()
        plans = self._plans_from_observations(observations, lang) or [
            plan_info(message, lang, [])]
        if self.state.proposal is not None and plans[-1].kind != "proposal":
            plans[-1].status = "NEEDS_CONFIRMATION"
        if text is None:
            if not observations:
                return self._interpret_failed()
            self.fallbacks.append("single-no-final-text")
            return plans, deterministic(plans, lang)
        checked = [p for p in plans if p.kind != "info"]
        problems = check_draft(text, checked, self._allowed_clocks(message, plans)) if checked else (
            check_draft(text, [], self._allowed_clocks(message, plans)))
        if problems:
            self.fallbacks.append(f"single-check:{problems[0]}")
            self._event("single", {"rejected_draft": text, "problems": problems})
            text = deterministic(checked or plans, lang)
        return plans, text

    def _s1_write(self, plans: list[Plan], message: str) -> str:
        lang = self._language()
        messages = self._s1_messages(message) + [{"role": "user", "content": (
            "La persona ha pulsado el botón Confirmar. Resultado del programa: "
            + json.dumps([p.as_dict() for p in plans], ensure_ascii=False)
            + ". Redacta la respuesta final sin llamar a herramientas.")}]
        try:
            reply = self.client.chat("single", messages, None, prompts.VERSION)
            text = (reply.get("content") or "").strip()
            problems = check_draft(text, plans, self._allowed_clocks(message, plans))
            if problems:
                self.fallbacks.append(f"single-check:{problems[0]}")
                return deterministic(plans, lang)
            return text
        except LLMError as exc:
            self.fallbacks.append(f"single-llm:{exc.code}")
            return deterministic(plans, lang)


def _s1_action(name: str) -> str:
    return {"confirm_pending_proposal": "confirm", "discard_pending_proposal": "discard"}.get(name, name)


# ===================================================================== M5
class M5State(TypedDict, total=False):
    message: str
    interp: Interpretation | None
    compliance: ComplianceAdvice | None
    profile: ProfileAdvice | None
    observations: list[dict]
    steps: int
    step: OrchestratorStep | None
    plans: list[Plan]
    text: str
    done: bool


def _build_m5_graph(assistant: Assistant):
    """Contexto → cumplimiento → perfiles → (orquestar ⇄ actuar) → personalizar."""

    def context(state: M5State) -> M5State:
        interp = assistant._interpret(state["message"])
        if interp is None:
            plans, text = assistant._interpret_failed()
            return {"interp": None, "plans": plans, "text": text, "done": True}
        assistant._apply_directives(interp, state["message"])
        if (stop := assistant._safety(state["message"], interp)) is not None:
            return {"interp": interp, "plans": stop, "text": deterministic(stop, assistant._language()),
                    "done": True}
        if interp.intent in OPERATIONS:
            assistant._merge_task(interp)
        return {"interp": interp, "done": False}

    def compliance(state: M5State) -> M5State:
        interp = state["interp"]
        advice = assistant._m5_compliance(state["message"], interp)
        lang = assistant._language()
        if advice.decision == "escalate":
            assistant.state.escalated = True
            plans = [Plan("escalation", [notice(lang, "emergency")], status="ESCALATED")]
            return {"compliance": advice, "plans": plans, "text": deterministic(plans, lang), "done": True}
        if advice.decision == "refuse":
            key = "refuse_other" if advice.rule_id == "CMP-REPRESENT-01" else "refuse_scope"
            plans = [Plan("refusal", [notice(lang, key)], status="BLOCKED")]
            return {"compliance": advice, "plans": plans, "done": False, "step": None, "steps": 99}
        return {"compliance": advice}

    def profile(state: M5State) -> M5State:
        if state.get("steps", 0) >= 99:
            return {}
        return {"profile": assistant._m5_profile(state["message"], state["interp"])}

    def decide(state: M5State) -> M5State:
        interp = state["interp"]
        allowed = assistant._m5_allowed(interp)
        payload = {"message": state["message"], "interpretation": interp.model_dump(),
                   "compliance": state["compliance"].model_dump() if state.get("compliance") else None,
                   "profile_advice": state["profile"].model_dump() if state.get("profile") else None,
                   "state": assistant.tools.context_summary(),
                   "observations_this_turn": state.get("observations", [])[-3:],
                   "allowed_actions": allowed}
        try:
            step = assistant.client.structured("orchestration", prompts.prompt("orchestration"), payload,
                                               OrchestratorStep, prompts.VERSION)
        except LLMError as exc:
            assistant.fallbacks.append(f"orchestration-llm:{exc.code}")
            step = None
        if step is not None and step.action not in allowed:
            assistant.fallbacks.append(f"orchestration-rejected:{step.action}")
            assistant._event("orchestration", {"rejected": step.model_dump(), "allowed": allowed})
            step = OrchestratorStep(action="respond", appointment_id=None, slot_id=None, missing="none",
                                    reason="not-allowed")
        if step is not None:
            assistant._event("orchestration", step.model_dump())
        return {"step": step, "steps": state.get("steps", 0) + 1}

    def act(state: M5State) -> M5State:
        step = state["step"]
        result = assistant._m5_execute(step, state["message"], state.get("profile"))
        observations = [*state.get("observations", []), {"action": step.action, "result": result}]
        return {"observations": observations}

    def route_after_decide(state: M5State) -> str:
        step = state.get("step")
        if step is None or step.action in ("respond", "ask", "refuse"):
            return "personalize"
        return "act"

    def route_after_act(state: M5State) -> str:
        last = state["observations"][-1]
        terminal = (last["action"].startswith("propose") and "proposal" in last["result"]) or last["action"] in (
            "confirm", "discard") or ("options" in last["result"] and not last["result"]["options"])
        if terminal or state.get("steps", 0) >= MAX_ORCHESTRATION_STEPS:
            return "personalize"
        return "decide"

    def personalize(state: M5State) -> M5State:
        lang = assistant._language()
        interp = state["interp"]
        plans = state.get("plans")
        if not plans:
            step = state.get("step")
            plans = assistant._plans_from_observations(state.get("observations", []), lang)
            if step is not None and step.action == "ask" and step.missing != "none":
                plans = [*plans, plan_ask(step.missing, lang)]
            elif step is not None and step.action == "refuse":
                plans = [Plan("refusal", [notice(lang, "refuse_scope" if not interp.other_person else "refuse_other")],
                              status="BLOCKED")]
            if not plans:
                plans = [plan_info(interp.question or state["message"], lang, assistant._info_facts())]
            elif interp.question and plans[-1].kind != "info":
                plans.append(plan_info(interp.question, lang, []))
        advice = state.get("compliance")
        notices = []
        if (advice and advice.clinical_notice) or interp.clinical_question:
            notices.append(notice(lang, "clinical"))
        if interp.other_person and not any(p.kind == "refusal" for p in plans):
            notices.append(notice(lang, "refuse_other"))
        plans = Assistant._with_notices(plans, notices)
        return {"plans": plans, "text": assistant._write(plans, state["message"])}

    graph = StateGraph(M5State)
    for name, node in (("context", context), ("compliance", compliance), ("profile", profile),
                       ("decide", decide), ("act", act), ("personalize", personalize)):
        graph.add_node(name, node)
    graph.add_edge(START, "context")
    graph.add_conditional_edges("context", lambda s: END if s.get("done") else "compliance")
    graph.add_conditional_edges("compliance", lambda s: END if s.get("done") else (
        "personalize" if s.get("steps", 0) >= 99 else "profile"))
    graph.add_edge("profile", "decide")
    graph.add_conditional_edges("decide", route_after_decide)
    graph.add_conditional_edges("act", route_after_act)
    graph.add_edge("personalize", END)
    return graph.compile()
