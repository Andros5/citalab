"""Servicio del portal CitaLab: cuentas, conversaciones, jobs, agenda y perfiles."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from citalab.assistant.engine import Assistant
from citalab.assistant.state import ConversationState
from citalab.config import DATA, OUTPUT, load_settings
from citalab.domain.agenda import (
    LOCATION, MADRID, SCHEDULES, SERVICES, Agenda, DomainError, build_demo_agenda, make_slot, patient_of,
)
from citalab.domain.policy import Auth
from citalab.domain.profiles import Profile, load_profiles, resolve, set_declared
from citalab.domain.text import public_appointment, public_offer
from citalab.llm.client import ChatClient, LLMError
from citalab.portal.storage import Storage

WELCOME = {
    "es": ("Soy un asistente de IA para gestionar citas administrativas con datos sintéticos. Puedo ayudarte a "
           "reservar, consultar, reprogramar o cancelar citas y a configurar recordatorios simulados. No realizo "
           "valoración clínica ni atiendo emergencias: si hay una emergencia, llama al 112. Ninguna operación se "
           "aplica sin tu confirmación. Puedo usar tus preferencias sintéticas para ordenar opciones; puedes pedir "
           "que no las use. No introduzcas datos personales reales."),
    "en": ("I am an AI assistant for administrative appointment tasks with synthetic data. I can help you book, "
           "check, reschedule or cancel appointments and set simulated reminders. I do not give clinical assessments "
           "or handle emergencies: in an emergency, call 112. No operation is applied without your confirmation. I "
           "may use your synthetic preferences to rank options; you can ask me not to. Do not enter real personal data."),
}
DEFAULT_CONFIG = {"default_architecture": "M5", "default_provider": "groq", "remote_enabled": True,
                  "max_calls": 12, "timeout_seconds": 60, "temperature": 0.0, "max_output_tokens": 1200,
                  "daily_call_limit": 2000, "recovery_policy_version": "bounded-transient-v2", "data_mode": "synthetic", "retention_days": 30, "diagnostic_days": 7, "session_minutes": 480}
ROLE_ACCOUNTS = [("investigador", "Investigación", "admin", None), ("revisor", "Revisión", "researcher", None),
                 ("ana", "Ana Sintética", "patient", "patient-ana"), ("bruno", "Bruno Sintético", "patient", "patient-bruno"),
                 ("lucia", "Lucía Sintética (representante de Ana)", "patient", "patient-ana")]
REPRESENTATIONS = {"lucia": ("representative-lucia", ["patient-ana"])}
UI_PREFERENCE_FIELDS = {"language": "language", "detail": "detail_level", "treatment": "treatment",
                        "time_of_day": "time_of_day", "reminder_channel": "reminder_channel"}
PROFILE_KEYS = {"language": "preferred-language", "detail_level": "preferred-detail-level",
                "treatment": "preferred-treatment", "time_of_day": "preferred-time-of-day",
                "reminder_channel": "preferred-reminder-channel"}


DIAGNOSTIC_FIELDS = ("system_prompt", "input", "output", "schema")


def _redact(call: dict) -> dict:
    """Conserva métricas de la llamada y retira su contenido (diagnóstico no activado)."""
    return {k: v for k, v in call.items() if k not in DIAGNOSTIC_FIELDS} | {"diagnostic_redacted": True,
                                                                             "system_prompt": ""}


class PortalError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Portal:
    def __init__(self, storage: Storage | None = None) -> None:
        self.storage = storage or Storage(OUTPUT / "portal" / "citalab.sqlite3")
        self.settings = load_settings()
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.clients: dict[str, ChatClient] = {}
        self._bootstrap_accounts()
        self.config = {**DEFAULT_CONFIG, **(self.storage.get("config") or {})}
        self.config_version = self.storage.get("config_version", 1)
        self.agenda = self._load_agenda()
        self.profiles = self._load_profiles()
        self.purge_expired()

    # ------------------------------------------------------------ arranque
    def _bootstrap_accounts(self) -> None:
        if self.storage.load("users", "investigador"):
            return
        lines = ["Accesos iniciales de CitaLab (datos sintéticos, uso local).", ""]
        for username, name, role, subject in ROLE_ACCOUNTS:
            code = secrets.token_urlsafe(9)
            salt = secrets.token_hex(8)
            actor, represented = REPRESENTATIONS.get(username, (subject, []))
            self.storage.save("users", username, {"username": username, "display_name": name, "role": role,
                                                  "subject_id": subject, "actor_id": actor,
                                                  "represents": represented, "salt": salt, "hash": _hash(code, salt)})
            lines.append(f"{username}: {code}")
        path = self.storage.path.parent / "accesos-iniciales.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _load_agenda(self) -> Agenda:
        resources = self.storage.get("agenda")
        if resources:
            return Agenda(resources)
        agenda = build_demo_agenda(datetime.now(UTC))
        self._seed_demo_appointments(agenda)
        self.storage.put("agenda", agenda.resources)
        return agenda

    @staticmethod
    def _seed_demo_appointments(agenda: Agenda) -> None:
        for patient, service, index in (("patient-ana", "nursing", 3), ("patient-bruno", "general-practice", 5)):
            free = agenda.free_slots(service)
            if len(free) > index:
                agenda.book(patient, free[index]["id"], None, f"seed-{patient}")
        agenda.write_log.clear()

    def _load_profiles(self) -> dict[str, Profile]:
        stored = self.storage.get("profiles")
        if stored:
            return {k: Profile.model_validate(v) for k, v in stored.items()}
        profiles = load_profiles(DATA / "synthetic" / "profiles" / "sprint3_profiles.json")
        self.storage.put("profiles", {k: v.model_dump(mode="json") for k, v in profiles.items()})
        return profiles

    def save_agenda(self) -> None:
        self.storage.put("agenda", self.agenda.snapshot())

    def save_profiles(self) -> None:
        self.storage.put("profiles", {k: v.model_dump(mode="json") for k, v in self.profiles.items()})

    def client(self, provider: str) -> ChatClient:
        if provider not in self.clients:
            config = self.settings.providers.get(provider)
            if not config or not config.available:
                raise PortalError(400, f"El proveedor {provider} no está configurado.")
            self.clients[provider] = ChatClient(config, self.settings)
        return self.clients[provider]

    # ---------------------------------------------------------- sesiones
    def login(self, username: str, password: str) -> tuple[str, dict, str]:
        user = self.storage.load("users", username.strip().lower())
        if not user or _hash(password, user["salt"]) != user["hash"]:
            time.sleep(0.4)
            raise PortalError(401, "Usuario o código de acceso incorrectos.")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(16)
        self.storage.create_session(token, user["username"], csrf, time.time() + self.config["session_minutes"] * 60)
        self.storage.audit(user["username"], "login")
        return token, self.public_user(user), csrf

    def session(self, token: str | None) -> tuple[dict, str]:
        found = self.storage.session(token) if token else None
        if not found or found[2] < time.time():
            raise PortalError(401, "Sesión no válida o caducada.")
        user = self.storage.load("users", found[0])
        if not user:
            raise PortalError(401, "Sesión no válida.")
        return user, found[1]

    @staticmethod
    def public_user(user: dict) -> dict:
        return {k: user[k] for k in ("username", "display_name", "role", "subject_id")}

    def change_password(self, user: dict, current: str, new: str) -> None:
        if _hash(current, user["salt"]) != user["hash"]:
            raise PortalError(400, "El código actual no es correcto.")
        if len(new) < 8:
            raise PortalError(400, "El nuevo código debe tener al menos 8 caracteres.")
        user = {**user, "salt": secrets.token_hex(8)}
        user["hash"] = _hash(new, user["salt"])
        self.storage.save("users", user["username"], user)

    def reset_password(self, actor: dict, username: str) -> str:
        user = self.storage.load("users", username)
        if not user:
            raise PortalError(404, "Cuenta no encontrada.")
        code = secrets.token_urlsafe(9)
        user["salt"] = secrets.token_hex(8)
        user["hash"] = _hash(code, user["salt"])
        self.storage.save("users", username, user)
        self.storage.audit(actor["username"], "reset-password", {"username": username})
        return code

    def accounts(self) -> list[dict]:
        return [self.public_user(u) for u in self.storage.all("users")]

    # ----------------------------------------------------------- catálogo
    def catalog(self) -> dict:
        free = [s for s in self.agenda.resources["Slot"].values() if s["status"] == "free"]
        future = self.agenda.free_slots()
        return {
            "scenario": {"id": "citalab-v3", "version": "3.0", "sha256": "", "require_explicit_service": True},
            "services": [{"code": code, "label": names["es"]} for code, names in SERVICES.items()],
            "schedules": [{"id": schedule, "label": SERVICES[service]["es"], "service_code": service,
                           "modality_code": "in-person", "modality_label": "Presencial", "active": True}
                          for service, schedule in SCHEDULES.items()],
            "availability": {"free_slots": len(free), "future_free_slots": len(future)},
        }

    def bootstrap(self, user: dict) -> dict:
        patients = [{"id": p["id"], "name": p["name"][0]["text"], "version": 1}
                    for p in self.agenda.resources["Patient"].values()]
        if user["role"] == "patient":
            patients = [p for p in patients if p["id"] == user["subject_id"]]
        return {"catalog": self.catalog(), "user": self.public_user(user), "patients": patients,
                "config": {"version": self.config_version, "config": self.config},
                "providers": {name: p.available for name, p in self.settings.providers.items()},
                "models": {name: p.model for name, p in self.settings.providers.items()},
                "fixed_controls": {"confirmation_required": True, "synthetic_only": True,
                                   "external_messages_sent": False}}

    # ------------------------------------------------------ conversaciones
    def _authorized(self, user: dict, conversation: dict) -> None:
        if user["role"] == "patient" and conversation["owner"] != user["username"]:
            raise PortalError(404, "Conversación no encontrada.")

    def create_conversation(self, user: dict, body: dict) -> dict:
        staff = user["role"] != "patient"
        subject = body.get("subject_id") if staff else user["subject_id"]
        if subject not in self.agenda.resources["Patient"]:
            raise PortalError(400, "Paciente sintético no válido.")
        architecture = (body.get("architecture") if staff else None) or self.config["default_architecture"]
        provider = (body.get("provider") if staff else None) or self.config["default_provider"]
        if architecture not in ("M5", "S1", "H"):
            raise PortalError(400, "Arquitectura no válida.")
        self.client(provider)
        language = "en" if body.get("ui_language") == "en" else "es"
        actor = (user.get("actor_id") or subject) if not staff else subject
        state = ConversationState(subject_id=subject, actor_id=actor, language=language)
        conversation = {
            "id": f"conv-{uuid.uuid4().hex[:10]}", "owner": user["username"], "subject_id": subject,
            "subject_name": self.agenda.patient_name(subject), "title": "Nueva conversación",
            "architecture": architecture, "provider": provider, "diagnostic": bool(body.get("diagnostic")),
            "created_at": _now(), "updated_at": _now(), "archived": False, "ui_language": language,
            "turns": [], "state": state.model_dump(mode="json"), "active_job": None,
            "preference_proposal": None, "preference_revision": 0,
            "represented": user.get("represents", []) if not staff else [],
        }
        self._save_conversation(conversation)
        self.storage.audit(user["username"], "conversation-create", {"id": conversation["id"],
                                                                     "architecture": architecture})
        return self.view(conversation)

    def _save_conversation(self, conversation: dict) -> None:
        conversation["updated_at"] = _now()
        self.storage.save("conversations", conversation["id"], conversation, owner=conversation["owner"],
                          updated_at=conversation["updated_at"])

    def conversation(self, user: dict, identifier: str) -> dict:
        conversation = self.storage.load("conversations", identifier)
        if not conversation:
            raise PortalError(404, "Conversación no encontrada.")
        self._authorized(user, conversation)
        return conversation

    def list_conversations(self, user: dict, q: str = "", architecture: str = "", status: str = "",
                           page: int = 1, page_size: int = 20) -> dict:
        where, params = ("WHERE owner=?", (user["username"],)) if user["role"] == "patient" else ("", ())
        items = self.storage.all("conversations", where, params)
        if q:
            needle = q.casefold()
            items = [c for c in items if needle in json.dumps([c["title"], c["subject_name"],
                                                                [t["request"] for t in c["turns"]]],
                                                               ensure_ascii=False).casefold()]
        if architecture:
            items = [c for c in items if c["architecture"] == architecture]
        if status:
            items = [c for c in items if c["state"].get("status") == status]
        start = (max(page, 1) - 1) * page_size
        return {"items": [self.view(c, summary=True) for c in items[start:start + page_size]], "total": len(items)}

    def archive(self, user: dict, identifier: str) -> dict:
        conversation = self.conversation(user, identifier)
        conversation["archived"] = True
        self._save_conversation(conversation)
        return self.view(conversation)

    # -------------------------------------------------------------- turnos
    def post_turn(self, user: dict, identifier: str, body: dict) -> dict:
        with self.lock:
            conversation = self.conversation(user, identifier)
            if conversation["archived"]:
                raise PortalError(409, "La conversación está archivada.")
            if conversation.get("active_job"):
                job = self.storage.load("jobs", conversation["active_job"])
                if job and job["status"] in ("queued", "running"):
                    raise PortalError(409, "Ya hay un mensaje en curso.")
            if body.get("expected_turn") is not None and body["expected_turn"] != len(conversation["turns"]):
                existing = [t for t in conversation["turns"]
                            if body.get("request_id") and t.get("request_id") == body["request_id"]]
                if existing:
                    return self.storage.load("jobs", existing[0]["job_id"]) or {}
                raise PortalError(409, "La conversación ha cambiado; recárgala antes de continuar.")
            action = body.get("action", "message")
            message = (body.get("message") or "").strip()
            if action == "message" and not message:
                raise PortalError(400, "Escribe un mensaje.")
            if len(message) > 2000:
                raise PortalError(400, "El mensaje es demasiado largo.")
            if not self.config["remote_enabled"]:
                raise PortalError(409, "Las llamadas externas están pausadas en Administración.")
            job = {"id": f"job-{uuid.uuid4().hex[:10]}", "conversation_id": identifier, "status": "queued",
                   "at": _now(), "events": [], "calls": []}
            self.storage.save("jobs", job["id"], job, conversation_id=identifier)
            conversation["active_job"] = job["id"]
            self._save_conversation(conversation)
        self.pool.submit(self._run_turn, user, identifier, job["id"], action, message, body.get("request_id"))
        return job

    def _run_turn(self, user: dict, identifier: str, job_id: str, action: str, message: str,
                  request_id: str | None) -> None:
        job = self.storage.load("jobs", job_id)
        job["status"] = "running"
        self.storage.save("jobs", job_id, job, conversation_id=identifier)
        try:
            with self.lock:
                conversation = self.storage.load("conversations", identifier)
                state = ConversationState.model_validate(conversation["state"])
                auth = Auth(state.actor_id, state.subject_id, represented=frozenset(conversation.get("represented", [])),
                            data_mode=self.config.get("data_mode", "synthetic"))
                assistant = Assistant(conversation["architecture"], self.client(conversation["provider"]),
                                      self.agenda, self.profiles, auth, state)
                started = time.perf_counter()
                result = assistant.turn(action, message)
                latency = time.perf_counter() - started
                calls = result.calls if conversation["diagnostic"] else [_redact(c) for c in result.calls]
                turn = {
                    "id": f"turn-{uuid.uuid4().hex[:8]}", "number": len(conversation["turns"]) + 1,
                    "request": message if action == "message" else ("[Confirmar]" if action == "confirm" else "[Descartar]"),
                    "action": action, "response": result.response, "status": result.status, "at": _now(),
                    "job_id": job_id, "request_id": request_id, "calls": calls, "events": result.events,
                    "plans": result.plans, "fallbacks": result.fallbacks, "language": result.language,
                    "latency_s": round(latency, 2), "state": assistant.state.model_dump(mode="json"),
                }
                conversation["turns"].append(turn)
                conversation["state"] = assistant.state.model_dump(mode="json")
                if conversation["title"] == "Nueva conversación" and action == "message":
                    conversation["title"] = message[:60]
                conversation["active_job"] = None
                self._save_conversation(conversation)
                self.save_agenda()
            job.update(status="completed", calls=calls, result_status=result.status,
                       events=[self._ui_event(e) for e in result.events])
        except Exception as exc:  # el job queda fallido sin efectos parciales en la conversación
            with self.lock:
                conversation = self.storage.load("conversations", identifier)
                conversation["active_job"] = None
                self._save_conversation(conversation)
            job.update(status="failed", error=f"No se ha podido procesar el mensaje ({type(exc).__name__}).")
            self.storage.audit(user["username"], "turn-failed", {"conversation": identifier, "error": str(exc)[:300]})
        job["finished_at"] = _now()
        self.storage.save("jobs", job_id, job, conversation_id=identifier)

    def job(self, user: dict, identifier: str) -> dict:
        job = self.storage.load("jobs", identifier)
        if not job:
            raise PortalError(404, "Ejecución no encontrada.")
        self.conversation(user, job["conversation_id"])
        return job

    # ---------------------------------------------------------- preferencias
    def update_preferences(self, user: dict, identifier: str, body: dict) -> dict:
        with self.lock:
            conversation = self.conversation(user, identifier)
            state = ConversationState.model_validate(conversation["state"])
            scope = body.get("scope", "conversation")
            values = {short: body[field] for field, short in UI_PREFERENCE_FIELDS.items()
                      if body.get(field) not in (None, "")}
            if "enabled" in body:
                state.profile_opt_out = not bool(body["enabled"])
            if scope == "turn":
                state.turn_preferences = {**state.turn_preferences, **values}
            elif scope == "conversation":
                state.conversation_preferences = {**state.conversation_preferences, **values}
            elif scope == "profile":
                profile = self.profiles.get(state.subject_id)
                state.conversation_preferences = {**state.conversation_preferences, **values}
                conversation["preference_proposal"] = {
                    "proposal_id": f"pref-{uuid.uuid4().hex[:8]}", "subject_id": state.subject_id,
                    "profile_version": profile.version if profile else 1, "expected_turn": len(conversation["turns"]),
                    "values": {PROFILE_KEYS[k]: v for k, v in values.items()},
                    "profile_usage_enabled": body.get("profile_usage_enabled"), "status": "pending", "stale": False}
            else:
                raise PortalError(400, "Ámbito no válido.")
            conversation["preference_revision"] = conversation.get("preference_revision", 0) + 1
            conversation["state"] = state.model_dump(mode="json")
            self._save_conversation(conversation)
            return self.view(conversation)

    def decide_preference_proposal(self, user: dict, identifier: str, body: dict, accept: bool) -> dict:
        with self.lock:
            conversation = self.conversation(user, identifier)
            proposal = conversation.get("preference_proposal")
            if not proposal or proposal["proposal_id"] != body.get("proposal_id") or proposal["status"] != "pending":
                raise PortalError(409, "La propuesta de preferencias ya no está vigente.")
            if accept:
                profile = self.profiles.get(proposal["subject_id"]) or Profile(subject_id=proposal["subject_id"])
                if profile.version != proposal["profile_version"]:
                    proposal["stale"] = True
                    raise PortalError(409, "El perfil ha cambiado; revisa la propuesta.")
                for key, value in proposal["values"].items():
                    profile = set_declared(profile, key, value, datetime.now(UTC), f"citalab:{identifier}")
                self.profiles[proposal["subject_id"]] = profile
                self.save_profiles()
                self.storage.audit(user["username"], "profile-update-confirmed",
                                   {"subject": proposal["subject_id"], "keys": list(proposal["values"])})
            proposal["status"] = "confirmed" if accept else "rejected"
            self._save_conversation(conversation)
            return self.view(conversation)

    # ------------------------------------------------------------------ vista
    @staticmethod
    def _ui_event(event: dict) -> dict:
        kind = event.get("kind", "event")
        if kind == "tool":
            detail = f"{event.get('name')}({json.dumps(event.get('arguments', {}), ensure_ascii=False)})"
        elif kind == "agent":
            detail = f"{event.get('agent')}: {json.dumps(event.get('detail'), ensure_ascii=False, default=str)[:400]}"
        elif kind == "policy":
            decision = event.get("decision") or event
            detail = f"{decision.get('rule_id')}: {decision.get('reason', '')}"
        else:
            detail = json.dumps({k: v for k, v in event.items() if k not in ("at", "kind")}, ensure_ascii=False,
                                default=str)[:400]
        return {"at": event.get("at", ""), "kind": kind, "detail": detail}

    def _proposal_view(self, state: ConversationState) -> tuple[dict | None, dict | None, bool]:
        proposal = state.proposal
        if not proposal:
            return None, None, False
        live = datetime.fromisoformat(proposal.expires_at) > self.agenda.now()
        language = state.language
        if proposal.operation == "book":
            slot = self.agenda.resources["Slot"].get(proposal.slot_id)
            return (public_offer(slot, language) if slot else None), None, live
        appointment = self.agenda.resources["Appointment"].get(proposal.appointment_id)
        if not appointment:
            return None, None, False
        view = {"proposal_id": proposal.proposal_id, "revision": proposal.revision, "operation": proposal.operation,
                "subject_id": state.subject_id, "appointment_id": proposal.appointment_id,
                "target_id": proposal.slot_id, "expires_at": proposal.expires_at,
                "appointment": public_appointment(appointment, language)}
        if proposal.slot_id and proposal.slot_id in self.agenda.resources["Slot"]:
            slot = self.agenda.resources["Slot"][proposal.slot_id]
            view["target_offer"] = {**public_offer(slot, language), "slot_version": slot["meta"]["versionId"]}
        if proposal.channel:
            view["arguments"] = {"channel": proposal.channel, "minutes_before": proposal.minutes_before}
        return None, view, live

    def view(self, conversation: dict, summary: bool = False) -> dict:
        state = ConversationState.model_validate(conversation["state"])
        calls = [c for t in conversation["turns"] for c in t.get("calls", [])]
        tokens = sum((c.get("total_tokens") or 0) for c in calls)
        offer, operation, live = self._proposal_view(state)
        language = conversation.get("ui_language", "es")
        resolution = resolve(self.profiles.get(state.subject_id), "response-adaptation", self.agenda.now())
        effective = {**{k: v.value for k, v in resolution.values.items()},
                     **{PROFILE_KEYS[k]: v for k, v in state.conversation_preferences.items() if k in PROFILE_KEYS}}
        result = {
            "id": conversation["id"], "owner": conversation["owner"], "subject_id": conversation["subject_id"],
            "subject_name": conversation["subject_name"], "title": conversation["title"], "status": state.status,
            "architecture": conversation["architecture"], "provider": conversation["provider"],
            "model": self.settings.providers[conversation["provider"]].model,
            "diagnostic": conversation["diagnostic"], "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"], "turn_count": len(conversation["turns"]),
            "archived": conversation["archived"], "active_job": conversation.get("active_job"),
            "ui_language": language, "read_only": conversation["archived"], "failed_attempts": [],
            "welcome": {"kind": "initial_notice", "version": 1, "text": WELCOME[language]},
            "total_known_tokens": tokens, "tokens_complete": all(c.get("total_tokens") is not None
                                                                  for c in calls if c.get("status") == "success"),
            "can_confirm": live and not conversation["archived"],
            "profile_usage_enabled": not state.profile_opt_out,
            "config_version": self.config_version,
            "preferences": {"schema_version": 1, "values": {PROFILE_KEYS.get(k, k): v for k, v in
                                                            state.conversation_preferences.items()},
                            "pending_turn_values": state.turn_preferences, "effective": effective,
                            "sources": {}, "scope": "conversation",
                            "revision": conversation.get("preference_revision", 0),
                            "profile_opt_out": state.profile_opt_out},
            "preference_proposal": conversation.get("preference_proposal"),
        }
        if offer:
            result["offer"] = offer
        if operation:
            result["operation_proposal"] = operation
        if state.receipt:
            result["operation_receipt"] = {"status": state.receipt.status, "operation": state.receipt.operation,
                                           "idempotency_key": state.receipt.idempotency_key,
                                           "result_id": state.receipt.result_id}
        if state.shown:
            result["appointment_results"] = [
                public_appointment(self.agenda.resources["Appointment"][s.appointment_id], language)
                for s in state.shown if s.appointment_id in self.agenda.resources["Appointment"]]
        if summary:
            result["turns"] = []
            return result
        result["calls"] = calls
        result["turns"] = [self._turn_view(t) for t in conversation["turns"]]
        result["dialogue_state"] = {
            "pending_question": None, "active_task_ids": [],
            "constraints": state.task.model_dump(exclude_none=True),
            "public_exchanges": [{"user": t["request"], "assistant": t["response"]} for t in conversation["turns"]]}
        return result

    def _turn_view(self, turn: dict) -> dict:
        calls = turn.get("calls", [])
        errors = [c for c in calls if c.get("status") != "success"]
        fallbacks = turn.get("fallbacks", [])
        return {
            "id": turn["id"], "number": turn["number"], "request": turn["request"], "response": turn["response"],
            "status": turn["status"], "at": turn["at"], "job_id": turn.get("job_id"), "calls": calls,
            "response_language": turn.get("language"),
            "events": [self._ui_event(e) for e in turn.get("events", [])],
            "response_metadata": {"version": "v3", "components": sorted({c.get("agent", "") for c in calls}),
                                  "validation": "fallback" if fallbacks else "passed",
                                  "repair_count": sum(1 for c in calls if ":repair" in c.get("agent", "")),
                                  "recovery": bool(fallbacks)},
            "execution_summary": {"schema_version": "execution-summary-v1",
                                  "inference_outcome": "fallback" if fallbacks else "success",
                                  "programmed_recovery": bool(fallbacks), "transport_recovered": bool(errors),
                                  "provider_attempts": len(calls), "provider_attempts_complete": True},
            "state": {"plans": turn.get("plans"), "fallbacks": fallbacks, "task": turn.get("state", {}).get("task"),
                      "agent_steps": [e for e in turn.get("events", []) if e.get("kind") == "agent"],
                      "tool_calls": [e for e in turn.get("events", []) if e.get("kind") == "tool"],
                      "audit_events": [e for e in turn.get("events", []) if e.get("kind") in ("policy", "write",
                                                                                              "denied", "conflict")],
                      "operation_proposal": (turn.get("state") or {}).get("proposal"),
                      "operation_receipt": (turn.get("state") or {}).get("receipt")},
        }

    def export_conversation(self, user: dict, identifier: str) -> dict:
        conversation = self.conversation(user, identifier)
        return {"exported_at": _now(), "conversation": self.view(conversation)}

    # ----------------------------------------------------------- agenda y datos
    def resources(self) -> dict:
        resources = self.agenda.snapshot()
        resources["Location"] = {LOCATION["id"]: {"resourceType": "Location", "id": LOCATION["id"],
                                                  "status": "active", "name": LOCATION["es"]}}
        return resources

    def fhir_bundle(self) -> dict:
        entries = [{"resource": r} for kind in self.agenda.resources.values() for r in kind.values()]
        return {"resourceType": "Bundle", "type": "collection", "timestamp": _now(), "entry": entries}

    def save_slot(self, user: dict, body: dict, identifier: str | None = None) -> dict:
        schedule = body.get("schedule_id")
        service = next((s for s, sch in SCHEDULES.items() if sch == schedule), None)
        if not service:
            raise PortalError(400, "Agenda no válida.")
        try:
            start = datetime.fromisoformat(body["start"]).astimezone(MADRID)
            end = datetime.fromisoformat(body["end"]).astimezone(MADRID)
        except (KeyError, ValueError) as exc:
            raise PortalError(400, "Fechas no válidas.") from exc
        if end <= start:
            raise PortalError(400, "El final debe ser posterior al inicio.")
        with self.lock:
            if identifier:
                slot = self.agenda.resources["Slot"].get(identifier)
                if not slot:
                    raise PortalError(404, "Hueco no encontrado.")
                if slot["status"] == "busy" and any(a["slot"][0]["reference"] == f"Slot/{identifier}"
                                                    and a["status"] == "booked"
                                                    for a in self.agenda.resources["Appointment"].values()):
                    raise PortalError(409, "El hueco tiene una cita; gestiona primero la cita.")
            slot_id = identifier or f"slot-manual-{uuid.uuid4().hex[:6]}"
            new = make_slot(slot_id, service, start, int((end - start).total_seconds() // 60),
                            status=body.get("status", "free"))
            if identifier:
                new["meta"]["versionId"] = str(int(self.agenda.resources["Slot"][identifier]["meta"]["versionId"]) + 1)
            self.agenda.resources["Slot"][slot_id] = new
            self.save_agenda()
        self.storage.audit(user["username"], "slot-save", {"slot": slot_id, "reason": body.get("reason")})
        return new

    def appointment_action(self, user: dict, identifier: str, body: dict) -> dict:
        if not body.get("confirmed"):
            raise PortalError(400, "La operación requiere confirmación.")
        with self.lock:
            appointment = self.agenda.resources["Appointment"].get(identifier)
            if not appointment:
                raise PortalError(404, "Cita no encontrada.")
            patient = patient_of(appointment)
            key = f"admin-{body.get('request_id') or uuid.uuid4().hex}"
            try:
                if body.get("action") == "cancel":
                    result = self.agenda.cancel(patient, identifier, body.get("expected_version"), key)
                elif body.get("action") == "reschedule":
                    result = self.agenda.reschedule(patient, identifier, body.get("expected_version"),
                                                    body.get("slot_id"), None, key)
                else:
                    raise PortalError(400, "Acción no válida.")
            except DomainError as exc:
                raise PortalError(409, f"No se pudo completar: {exc.code}.") from exc
            self.save_agenda()
        self.storage.audit(user["username"], f"appointment-{body.get('action')}", {"appointment": identifier})
        return result

    def profile(self, subject: str) -> dict:
        profile = self.profiles.get(subject)
        if not profile:
            raise PortalError(404, "Perfil no encontrado.")
        return profile.model_dump(mode="json")

    def update_profile(self, user: dict, subject: str, body: dict) -> dict:
        with self.lock:
            profile = self.profiles.get(subject)
            if not profile:
                raise PortalError(404, "Perfil no encontrado.")
            if body.get("expected_version") != profile.version:
                raise PortalError(409, "El perfil ha cambiado; recárgalo.")
            for field, key in (("language", "preferred-language"), ("detail", "preferred-detail-level"),
                               ("treatment", "preferred-treatment")):
                if body.get(field):
                    current = resolve(profile, "response-adaptation", datetime.now(UTC)).value(key)
                    if current != body[field]:
                        profile = set_declared(profile, key, body[field], datetime.now(UTC),
                                               f"admin:{user['username']}")
            self.profiles[subject] = profile
            self.save_profiles()
        self.storage.audit(user["username"], "profile-edit", {"subject": subject, "reason": body.get("reason")})
        return profile.model_dump(mode="json")

    # --------------------------------------------------------- instantáneas
    def snapshots(self) -> list[dict]:
        items = [self.storage.get(key) for key in self.storage.keys("snapshot:")]
        return [{k: v for k, v in item.items() if k != "data"} | {"at": item["created_at"]} for item in items][::-1]

    def create_snapshot(self, user: dict, body: dict) -> dict:
        identifier = f"snap-{datetime.now(UTC):%Y%m%d%H%M%S}"
        record = {"id": identifier, "label": body.get("label") or identifier, "created_at": _now(),
                  "created_by": user["username"], "data": {"agenda": self.agenda.snapshot(),
                                                           "profiles": {k: v.model_dump(mode="json")
                                                                        for k, v in self.profiles.items()}}}
        self.storage.put(f"snapshot:{identifier}", record)
        return {k: v for k, v in record.items() if k != "data"}

    def restore_snapshot(self, user: dict, identifier: str) -> dict:
        record = self.storage.get(f"snapshot:{identifier}")
        if not record:
            raise PortalError(404, "Instantánea no encontrada.")
        with self.lock:
            self.agenda.restore(record["data"]["agenda"])
            self.profiles = {k: Profile.model_validate(v) for k, v in record["data"]["profiles"].items()}
            self.save_agenda()
            self.save_profiles()
        self.storage.audit(user["username"], "snapshot-restore", {"id": identifier})
        return {"restored": identifier}

    def reset_demo(self, user: dict) -> dict:
        with self.lock:
            agenda = build_demo_agenda(datetime.now(UTC))
            self._seed_demo_appointments(agenda)
            self.agenda.restore(agenda.resources)
            self.save_agenda()
        self.storage.audit(user["username"], "demo-reset")
        return self.catalog()

    # --------------------------------------------------------------- admin
    def update_config(self, user: dict, body: dict) -> dict:
        values = body.get("config", body)
        clean = {k: values[k] for k in DEFAULT_CONFIG if k in values}
        if clean.get("default_architecture") not in (None, "M5", "S1", "H"):
            raise PortalError(400, "Arquitectura no válida.")
        if clean.get("data_mode", "synthetic") != "synthetic":
            raise PortalError(400, "CMP-MODE-01: el laboratorio solo admite datos sintéticos.")
        retention = int(clean.get("retention_days", self.config["retention_days"]))
        diagnostic = int(clean.get("diagnostic_days", self.config["diagnostic_days"]))
        if not 1 <= retention <= 90:
            raise PortalError(400, "La conservación debe estar entre 1 y 90 días.")
        if not 1 <= diagnostic <= retention:
            raise PortalError(400, "El diagnóstico no puede conservarse más que el historial.")
        self.config.update(clean)
        self.config_version += 1
        self.storage.put("config", self.config)
        self.storage.put("config_version", self.config_version)
        self.storage.audit(user["username"], "config-update", clean)
        return {"version": self.config_version, "config": self.config}

    # ------------------------------------------------------------ retención
    def retention_status(self) -> dict:
        now = datetime.now(UTC)
        conversations = self.storage.all("conversations")
        history_limit = timedelta(days=self.config["retention_days"])
        diagnostic_limit = timedelta(days=self.config["diagnostic_days"])
        expired = [c for c in conversations if now - datetime.fromisoformat(c["updated_at"]) > history_limit]
        diagnostic = [c for c in conversations if c["diagnostic"]
                      and now - datetime.fromisoformat(c["updated_at"]) > diagnostic_limit]
        return {"retention_days": self.config["retention_days"], "diagnostic_days": self.config["diagnostic_days"],
                "conversations": len(conversations), "expired_conversations": len(expired),
                "expired_diagnostic_copies": len(diagnostic),
                "audit_events": len(self.agenda.resources.get("AuditEvent", {}))}

    def purge_expired(self, actor: str | None = None) -> dict:
        """Borra el historial caducado y retira las copias diagnósticas vencidas (borrado lógico en SQLite)."""
        now = datetime.now(UTC)
        removed = redacted = 0
        for conversation in self.storage.all("conversations"):
            age = now - datetime.fromisoformat(conversation["updated_at"])
            if age > timedelta(days=self.config["retention_days"]):
                self.storage.delete("conversations", conversation["id"])
                removed += 1
            elif conversation["diagnostic"] and age > timedelta(days=self.config["diagnostic_days"]):
                for turn in conversation["turns"]:
                    turn["calls"] = [_redact(c) for c in turn.get("calls", [])]
                conversation["diagnostic"] = False
                self.storage.save("conversations", conversation["id"], conversation, owner=conversation["owner"],
                                  updated_at=conversation["updated_at"])
                redacted += 1
        if removed or redacted:
            self.storage.audit(actor, "retention-purge", {"removed": removed, "redacted": redacted})
        return {"removed_conversations": removed, "redacted_diagnostic_copies": redacted, **self.retention_status()}

    def observability(self) -> dict:
        conversations = self.storage.all("conversations")
        calls = [c for conv in conversations for t in conv["turns"] for c in t.get("calls", [])]
        by_agent: dict[str, dict[str, float]] = {}
        for call in calls:
            entry = by_agent.setdefault(call.get("agent", "?"), {"calls": 0, "errors": 0, "tokens": 0, "latency_ms": 0})
            entry["calls"] += 1
            entry["errors"] += call.get("status") != "success"
            entry["tokens"] += call.get("total_tokens") or 0
            entry["latency_ms"] += call.get("latency_ms") or 0
        return {"conversations": len(conversations), "turns": sum(len(c["turns"]) for c in conversations),
                "calls": len(calls), "by_agent": by_agent}

    def provider_check(self, provider: str) -> dict:
        try:
            reply = self.client(provider).chat("health", [{"role": "user", "content": "Responde solo: ok"}])
            return {"provider": provider, "ok": True, "reply": (reply.get("content") or "")[:40]}
        except (LLMError, PortalError) as exc:
            return {"provider": provider, "ok": False, "error": str(exc)[:200]}

