"""Planes de respuesta: hechos deterministas + redacción adaptada por un LLM.

El código decide QUÉ se comunica (hechos, avisos, pregunta). El LLM decide CÓMO
(idioma, detalle, tratamiento). Dos comprobaciones mínimas protegen la
fidelidad: los anclajes (horas y días) deben aparecer, y solo un recibo real
puede anunciar una operación hecha. Si fallan, se usa el texto determinista;
la conversación nunca se interrumpe por ello.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from citalab.domain.agenda import LOCATION
from citalab.domain.text import channel_label, lang_of, service_label

T = {
    "es": {
        "options": "Estos son los huecos disponibles de {service}:",
        "options_pref": "Los he ordenado según tu preferencia guardada ({pref}).",
        "options_q": "¿Cuál te viene bien? Puedes indicarme el número.",
        "no_options": "No he encontrado huecos libres de {service} con esas condiciones ({criteria}).",
        "no_options_q": "¿Quieres que busque en otra fecha o franja?",
        "no_modality": "Esta agenda solo tiene citas presenciales: no hay huecos {modality} disponibles.",
        "no_modality_q": "¿Quieres que busque una cita presencial?",
        "proposal_book": "Propuesta de reserva: {service}, {when} (presencial, {location}).",
        "proposal_cancel": "Propuesta de cancelación: tu cita de {service} del {when}.",
        "proposal_reschedule": "Propuesta de cambio: tu cita de {service} del {old} pasaría al {new}.",
        "proposal_reminder": ("Propuesta de recordatorio simulado por {channel}, {minutes} minutos antes de tu "
                              "cita de {service} del {when}. Es una simulación: no se enviará ningún mensaje real."),
        "default_lead": "He usado la antelación por defecto de {minutes} minutos; puedes cambiarla.",
        "not_applied": "Todavía no se ha aplicado ningún cambio.",
        "confirm_q": "¿Lo confirmas? Puedes responder «sí» o pulsar Confirmar.",
        "receipt_book": "Hecho: tu cita de {service} del {when} ha quedado reservada.",
        "receipt_cancel": "Hecho: tu cita de {service} del {when} ha quedado cancelada.",
        "receipt_reschedule": "Hecho: tu cita de {service} se ha cambiado al {when}.",
        "receipt_reminder": ("Hecho: el recordatorio simulado por {channel} queda activado {minutes} minutos "
                             "antes de tu cita del {when}. No se enviará ningún mensaje real."),
        "conflict": "No he podido completar la operación: el hueco ya no está disponible.",
        "conflict_keep": "Tu cita original se mantiene sin cambios.",
        "conflict_none": "No se ha reservado nada.",
        "conflict_q": "¿Quieres que busque otra opción?",
        "appointments": "Tienes {n} cita(s) pendiente(s):",
        "appointments_none": "No tienes citas pendientes que cumplan esa condición.",
        "reminder_note": "recordatorio por {channel}",
        "discarded": "De acuerdo, he descartado la propuesta. No se ha cambiado nada.",
        "refuse_other": ("No puedo consultar ni gestionar datos o citas de otra persona sin una autorización "
                         "de representación registrada."),
        "refuse_scope": "Esa petición está fuera de lo que puede hacer este asistente administrativo.",
        "clinical": ("No puedo hacer valoraciones clínicas ni dar consejo médico. Si los síntomas son "
                     "intensos o empeoran, contacta con tu centro de salud o llama al 112."),
        "emergency": ("Lo que describes puede ser una urgencia. Llama ahora al 112 o acude a urgencias. "
                      "He detenido la gestión automática."),
        "ask_service": "¿Para qué servicio quieres la cita: medicina de familia, pediatría o enfermería?",
        "ask_appointment": "¿A cuál de tus citas te refieres?",
        "ask_channel": "¿Por qué canal quieres el recordatorio: SMS, correo electrónico o notificación push?",
        "ask_slot": "¿Cuál de las opciones prefieres?",
        "ask_date": "¿Para qué día o franja lo buscas?",
        "ask_generic": "¿Puedes concretar un poco más lo que necesitas?",
        "rephrase": "Perdona, no he entendido bien tu mensaje. ¿Puedes decírmelo de otra forma?",
        "greeting": ("Puedo ayudarte a reservar, consultar, cambiar o cancelar citas y a configurar "
                     "recordatorios simulados. ¿Qué necesitas?"),
        "unavailable": ("Ahora mismo no puedo procesar la petición por un problema técnico del servicio de IA. "
                        "No se ha cambiado nada; inténtalo de nuevo en unos segundos."),
        "confirm_needed": "Para aplicar el cambio necesito que confirmes expresamente la propuesta.",
        "nothing_pending": "No hay ninguna propuesta pendiente de confirmar.",
    },
    "en": {
        "options": "These are the available {service} slots:",
        "options_pref": "I have ordered them by your saved preference ({pref}).",
        "options_q": "Which one suits you? You can tell me the number.",
        "no_options": "I could not find free {service} slots matching those conditions ({criteria}).",
        "no_options_q": "Shall I look on another date or time of day?",
        "no_modality": "This schedule only has in-person appointments: there are no {modality} slots available.",
        "no_modality_q": "Shall I look for an in-person appointment?",
        "proposal_book": "Booking proposal: {service}, {when} (in person, {location}).",
        "proposal_cancel": "Cancellation proposal: your {service} appointment on {when}.",
        "proposal_reschedule": "Change proposal: your {service} appointment on {old} would move to {new}.",
        "proposal_reminder": ("Simulated reminder proposal by {channel}, {minutes} minutes before your "
                              "{service} appointment on {when}. It is a simulation: no real message will be sent."),
        "default_lead": "I used the default lead time of {minutes} minutes; you can change it.",
        "not_applied": "Nothing has been changed yet.",
        "confirm_q": "Do you confirm? You can reply \"yes\" or press Confirm.",
        "receipt_book": "Done: your {service} appointment on {when} is booked.",
        "receipt_cancel": "Done: your {service} appointment on {when} has been cancelled.",
        "receipt_reschedule": "Done: your {service} appointment has been moved to {when}.",
        "receipt_reminder": ("Done: the simulated {channel} reminder is set {minutes} minutes before your "
                             "appointment on {when}. No real message will be sent."),
        "conflict": "I could not complete the operation: the slot is no longer available.",
        "conflict_keep": "Your original appointment is unchanged.",
        "conflict_none": "Nothing has been booked.",
        "conflict_q": "Shall I look for another option?",
        "appointments": "You have {n} upcoming appointment(s):",
        "appointments_none": "You have no upcoming appointments matching that condition.",
        "reminder_note": "{channel} reminder",
        "discarded": "OK, I have discarded the proposal. Nothing has been changed.",
        "refuse_other": ("I cannot access or manage another person's data or appointments without a registered "
                         "representation authorisation."),
        "refuse_scope": "That request is outside what this administrative assistant can do.",
        "clinical": ("I cannot give clinical assessments or medical advice. If symptoms are severe or getting "
                     "worse, contact your health centre or call 112."),
        "emergency": ("What you describe may be an emergency. Call 112 now or go to the emergency department. "
                      "I have stopped the automated process."),
        "ask_service": "Which service do you need: family medicine, paediatrics or nursing?",
        "ask_appointment": "Which of your appointments do you mean?",
        "ask_channel": "Which channel would you like for the reminder: SMS, email or push notification?",
        "ask_slot": "Which option do you prefer?",
        "ask_date": "For which day or time of day should I look?",
        "ask_generic": "Could you tell me a bit more precisely what you need?",
        "rephrase": "Sorry, I did not quite understand your message. Could you say it another way?",
        "greeting": ("I can help you book, check, change or cancel appointments and set simulated reminders. "
                     "What do you need?"),
        "unavailable": ("I cannot process the request right now because of a technical problem with the AI "
                        "service. Nothing has been changed; please try again in a few seconds."),
        "confirm_needed": "To apply the change I need you to explicitly confirm the proposal.",
        "nothing_pending": "There is no pending proposal to confirm.",
    },
}

KNOWLEDGE = {
    "es": [
        "CitaLab es un asistente de IA para gestiones administrativas de citas con datos sintéticos.",
        "Servicios: medicina de familia, pediatría y enfermería; solo hay citas presenciales en el Centro de Salud Demo.",
        "Ninguna reserva, cancelación, cambio o recordatorio se aplica sin que la persona confirme una propuesta concreta.",
        "Para cancelar: se indica qué cita (por servicio y fecha o eligiéndola de la lista), el asistente muestra una "
        "propuesta de cancelación y solo se cancela al confirmarla. El hueco queda libre para otras personas.",
        "Para referirse a una cita basta con indicar su servicio y fecha/hora, o su número en la lista mostrada.",
        "Los recordatorios son simulados: se guardan en la agenda pero nunca se envía un mensaje real. "
        "Canales: SMS, correo electrónico o notificación push.",
        "El asistente no hace valoraciones clínicas ni decide urgencias o prioridades; ante una emergencia, 112.",
        "Las preferencias del perfil (franja, idioma, nivel de detalle, canal) solo ordenan o adaptan; la persona puede "
        "pedir no usarlas en la conversación.",
        "No hay un canal humano integrado en este prototipo.",
    ],
    "en": [
        "CitaLab is an AI assistant for administrative appointment tasks with synthetic data.",
        "Services: family medicine, paediatrics and nursing; only in-person appointments at the Demo Health Centre.",
        "No booking, cancellation, change or reminder is applied unless the person confirms a specific proposal.",
        "To cancel: say which appointment (service and date, or its number in the list), the assistant shows a "
        "cancellation proposal and it is only cancelled once confirmed. The slot becomes free for others.",
        "To refer to an appointment, its service and date/time, or its number in the shown list, is enough.",
        "Reminders are simulated: they are stored in the agenda but no real message is ever sent. "
        "Channels: SMS, email or push notification.",
        "The assistant does not give clinical assessments or decide urgency or priority; in an emergency, call 112.",
        "Profile preferences (time of day, language, detail level, channel) only rank or adapt; the person may ask "
        "not to use them in the conversation.",
        "There is no integrated human channel in this prototype.",
    ],
}


@dataclass
class Plan:
    kind: str
    facts: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    question: str | None = None
    anchors: list[str] = field(default_factory=list)
    answer: str | None = None  # pregunta informativa que el redactor debe responder
    status: str = "READY"

    def as_dict(self) -> dict:
        return {"kind": self.kind, "facts": self.facts, "notices": self.notices,
                "question": self.question, "anchors": self.anchors, "answer": self.answer,
                "status": self.status}


def _t(lang: str, key: str, **values: Any) -> str:
    return T[lang_of(lang)][key].format(**values)


def _anchor(start: str) -> list[str]:
    from citalab.domain.text import local
    moment = local(start)
    return [moment.strftime("%H:%M")]


# ------------------------------------------------------------- constructores
MODALITY_TEXT = {"phone": {"es": "telefónicos", "en": "phone"}, "video": {"es": "por videollamada", "en": "video"}}


def plan_options(result: dict, lang: str) -> Plan:
    if result.get("unavailable_modality"):
        label = MODALITY_TEXT.get(result["unavailable_modality"], {}).get(lang_of(lang), result["unavailable_modality"])
        return Plan("no_options", [_t(lang, "no_modality", modality=label)], question=_t(lang, "no_modality_q"),
                    status="NEEDS_CLARIFICATION")
    service = service_label(result["searched"]["service"], lang)
    if not result["options"]:
        searched = result["searched"]
        criteria = ", ".join(str(v) for k, v in searched.items() if v and k != "service")
        return Plan("no_options", [_t(lang, "no_options", service=service.lower() if lang == "es" else service,
                                      criteria=criteria)], question=_t(lang, "no_options_q"),
                    status="NEEDS_CLARIFICATION")
    facts = [_t(lang, "options", service=service.lower() if lang == "es" else service)]
    facts += [f"{o['number']}. {o['when']}" for o in result["options"]]
    if result.get("applied_preferences"):
        pref = result["applied_preferences"].get("preferred-time-of-day")
        label = {"morning": {"es": "mañanas", "en": "mornings"},
                 "afternoon": {"es": "tardes", "en": "afternoons"}}.get(pref, {}).get(lang_of(lang), pref)
        facts.append(_t(lang, "options_pref", pref=label))
    anchors = [a for o in result["options"] for a in _anchor(o["start"])]
    return Plan("options", facts, question=_t(lang, "options_q"), anchors=anchors, status="READY")


def plan_proposal(result: dict, lang: str) -> Plan:
    proposal = result["proposal"]
    op = proposal["operation"]
    appointment = proposal.get("appointment") or {}
    slot = proposal.get("slot") or {}
    service = service_label(appointment.get("service") or "", lang) or slot.get("service", "")
    if op == "book":
        fact = _t(lang, "proposal_book", service=slot.get("service"), when=slot["when"], location=LOCATION[lang_of(lang)])
        anchors = _anchor(slot["start"])
    elif op == "cancel":
        fact = _t(lang, "proposal_cancel", service=service.lower() if lang == "es" else service, when=appointment["when"])
        anchors = _anchor(appointment["start"])
    elif op == "reschedule":
        fact = _t(lang, "proposal_reschedule", service=service.lower() if lang == "es" else service,
                  old=appointment["when"], new=slot["when"])
        anchors = _anchor(appointment["start"]) + _anchor(slot["start"])
    else:
        fact = _t(lang, "proposal_reminder", channel=channel_label(proposal["channel"], lang),
                  minutes=proposal["minutes_before"], service=service.lower() if lang == "es" else service,
                  when=appointment["when"])
        anchors = [str(proposal["minutes_before"])]
    facts = [fact]
    if result.get("default_lead_time_used"):
        facts.append(_t(lang, "default_lead", minutes=proposal["minutes_before"]))
    facts.append(_t(lang, "not_applied"))
    return Plan("proposal", facts, question=_t(lang, "confirm_q"), anchors=anchors, status="NEEDS_CONFIRMATION")


def plan_receipt(result: dict, lang: str) -> Plan:
    proposal = result["proposal"]
    op = proposal["operation"]
    appointment = proposal.get("appointment") or {}
    slot = proposal.get("slot") or {}
    service = service_label(appointment.get("service") or "", lang) or slot.get("service", "")
    service = service.lower() if lang == "es" else service
    if op == "book":
        fact = _t(lang, "receipt_book", service=service, when=slot["when"])
        anchors = _anchor(slot["start"])
    elif op == "cancel":
        fact = _t(lang, "receipt_cancel", service=service, when=appointment["when"])
        anchors = _anchor(appointment["start"])
    elif op == "reschedule":
        fact = _t(lang, "receipt_reschedule", service=service, when=slot["when"])
        anchors = _anchor(slot["start"])
    else:
        fact = _t(lang, "receipt_reminder", channel=channel_label(proposal["channel"], lang),
                  minutes=proposal["minutes_before"], when=appointment["when"])
        anchors = [str(proposal["minutes_before"])]
    return Plan("receipt", [fact], anchors=anchors, status="COMPLETED")


def plan_conflict(result: dict, lang: str) -> Plan:
    op = (result.get("proposal") or {}).get("operation")
    facts = [_t(lang, "conflict"), _t(lang, "conflict_keep" if op in ("reschedule", "cancel", "reminder") else "conflict_none")]
    return Plan("conflict", facts, question=_t(lang, "conflict_q"), status="NEEDS_CLARIFICATION")


def plan_appointments(result: dict, lang: str) -> Plan:
    items = result.get("appointments", [])
    if not items:
        return Plan("appointments", [_t(lang, "appointments_none")], status="READY")
    facts = [_t(lang, "appointments", n=len(items))]
    for item in items:
        line = f"{item['number']}. {service_label(item['service'], lang)}: {item['when']}"
        if item.get("reminder"):
            line += f" ({_t(lang, 'reminder_note', channel=channel_label(item['reminder']['channel'], lang))})"
        facts.append(line)
    anchors = [a for item in items for a in _anchor(item["start"])]
    return Plan("appointments", facts, anchors=anchors, status="READY")


def plan_simple(kind: str, lang: str, key: str, status: str = "READY", question: str | None = None) -> Plan:
    return Plan(kind, [_t(lang, key)], question=question, status=status)


def plan_ask(missing: str, lang: str) -> Plan:
    key = {"service": "ask_service", "appointment": "ask_appointment", "channel": "ask_channel",
           "slot_choice": "ask_slot", "date": "ask_date"}.get(missing, "ask_generic")
    return Plan("clarify", [], question=_t(lang, key), status="NEEDS_CLARIFICATION")


def plan_info(question: str | None, lang: str, context_facts: list[str]) -> Plan:
    return Plan("info", context_facts, answer=question or "", status="READY")


def notice(lang: str, key: str) -> str:
    return _t(lang, key)


# ------------------------------------------------------------------ render
def deterministic(plans: list[Plan], lang: str) -> str:
    parts: list[str] = []
    for plan in plans:
        parts.extend(plan.notices)
        if plan.kind == "info" and not plan.facts:
            parts.extend(KNOWLEDGE[lang_of(lang)][:3])
        parts.extend(plan.facts)
    question = next((p.question for p in reversed(plans) if p.question), None)
    text = "\n".join(dict.fromkeys(p for p in parts if p))
    return f"{text}\n\n{question}".strip() if question else text


_SUCCESS = re.compile(
    r"\b(he (?:reservado|cancelado|cambiado|activado|configurado|programado|actualizado)|confirmo (?:la|tu|su) "
    r"(?:cita|reserva|cambio|cancelaci[oó]n)|"
    r"(?:est[aá]|queda(?:do)?|ha quedado|ha sido|qued[oó]) (?:ya )?(?:confirmad|reservad|cancelad|activad|"
    r"programad|cambiad|configurad|actualizad)|se ha (?:cambiado|reservado|cancelado|activado|configurado|programado|actualizado)|"
    r"se enviar[aá] (?:un|una|el|la|por)|"
    r"cita confirmada|reserva confirmada|"
    r"(?:is|has been|was) (?:now )?(?:booked|confirmed|cancel+ed|moved|rescheduled|set up|scheduled|activated)|"
    r"i have (?:booked|cancel+ed|moved|set|scheduled)|i (?:booked|cancel+ed|moved)|appointment confirmed|"
    r"booking confirmed|reminder is (?:set|active)|has been updated|i have updated|will be sent (?:by|via|to)|"
    r"i confirm (?:your|the))",
    re.IGNORECASE)
_CLOCK = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")


_NEGATION = re.compile(r"(\bno\b|\bnot\b|n't\b|\bnothing\b|\bnada\b|\bnunca\b|\bnever\b|\btodav[ií]a no\b|"
                       r"\ba[uú]n no\b|\bningun|\bsin\b|\bwithout\b|\bonce\b|\bcuando\b|\bsi (?:la |lo )?confirm|"
                       r"\bif you\b|\bwhen you\b|\bal confirmar\b|\buna vez\b)[^.!?\n]{0,40}$", re.IGNORECASE)


def unsupported_claim(text: str) -> str | None:
    """Primera afirmación de efecto no negada ni condicional, si existe."""
    for match in _SUCCESS.finditer(text):
        before = text[max(0, match.start() - 60):match.start()]
        if not _NEGATION.search(before):
            return match.group(0)
    return None


TRIVIAL = {"discarded", "nothing", "confirm_needed", "refusal", "escalation", "fallback"}


def check_draft(text: str, plans: list[Plan], allowed_clocks: set[str]) -> list[str]:
    """Problemas de fidelidad de una redacción; vacío si es aceptable."""
    problems = []
    if not text.strip():
        return ["empty"]
    for plan in plans:
        for anchor in plan.anchors:
            if anchor not in text:
                problems.append(f"missing-anchor:{anchor}")
    if not any(p.kind == "receipt" for p in plans) and unsupported_claim(text):
        problems.append("unsupported-success-claim")
    if any(p.question for p in plans) and "?" not in text:
        problems.append("missing-question")
    for match in _CLOCK.finditer(text):
        clock = f"{int(match.group(1)):02d}:{match.group(2)}"
        if clock not in allowed_clocks:
            problems.append(f"unknown-time:{clock}")
    return problems


def clocks_in(values: list[str] | str) -> set[str]:
    text = " ".join(values) if isinstance(values, list) else values
    return {f"{int(m.group(1)):02d}:{m.group(2)}" for m in _CLOCK.finditer(text)}
