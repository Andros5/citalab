"""Formato de fechas, horas y recursos en español e inglés (zona Europe/Madrid)."""

from __future__ import annotations

import re
from datetime import date, datetime

from citalab.domain.agenda import LOCATION, MADRID, MODALITIES, SERVICES, parse_time, service_of

DAYS = {"es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
MONTHS = {"es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                 "septiembre", "octubre", "noviembre", "diciembre"],
          "en": ["January", "February", "March", "April", "May", "June", "July", "August",
                 "September", "October", "November", "December"]}
CHANNELS = {"sms": {"es": "SMS", "en": "SMS"}, "email": {"es": "correo electrónico", "en": "email"},
            "push": {"es": "notificación push", "en": "push notification"}}


_ES = {"de", "la", "el", "mi", "mis", "tu", "tus", "cita", "citas", "que", "y", "las", "los", "es", "para", "con",
       "quiero", "por", "favor", "una", "un", "del", "al", "me", "se", "no", "si", "sí", "hola", "gracias", "cuál"}
_EN = {"the", "my", "your", "you", "appointment", "appointments", "and", "is", "for", "with", "on", "at", "i",
       "please", "want", "to", "a", "an", "of", "it", "do", "have", "can", "which", "what", "thanks", "hello"}


def detect_language(text: str) -> str | None:
    """Idioma del texto por palabras funcionales; None si no hay evidencia suficiente."""
    words = re.findall(r"[a-záéíóúñü]+", text.casefold())
    es = sum(w in _ES for w in words)
    en = sum(w in _EN for w in words)
    if es == en:
        return None
    return "es" if es > en else "en"


def lang_of(value: str | None) -> str:
    return "en" if value == "en" else "es"


def local(value: str | datetime) -> datetime:
    moment = parse_time(value) if isinstance(value, str) else value
    return moment.astimezone(MADRID)


def format_day(value: str | datetime | date, language: str) -> str:
    day = value if isinstance(value, date) and not isinstance(value, datetime) else local(value).date()
    lang = lang_of(language)
    weekday = DAYS[lang][day.weekday()]
    month = MONTHS[lang][day.month - 1]
    if lang == "en":
        return f"{weekday} {day.day} {month} {day.year}"
    return f"{weekday} {day.day} de {month} de {day.year}"


def format_clock(value: str | datetime) -> str:
    return local(value).strftime("%H:%M")


def format_when(value: str | datetime, language: str) -> str:
    connector = "at" if lang_of(language) == "en" else "a las"
    return f"{format_day(value, language)} {connector} {format_clock(value)}"


def service_label(code: str | None, language: str) -> str:
    return SERVICES.get(code or "", {}).get(lang_of(language), code or "")


def channel_label(code: str, language: str) -> str:
    return CHANNELS.get(code, {}).get(lang_of(language), code)


def describe(resource: dict, language: str) -> str:
    """Servicio, día, hora, modalidad y centro de un Slot o Appointment."""
    lang = lang_of(language)
    modality = MODALITIES["in-person"][lang]
    return (f"{service_label(service_of(resource), lang)}, {format_when(resource['start'], lang)} "
            f"({modality.lower()}, {LOCATION[lang]})")


def anchors(resource: dict) -> list[str]:
    """Fragmentos que una respuesta redactada debe contener para ser fiel."""
    moment = local(resource["start"])
    return [moment.strftime("%H:%M"), str(moment.day)]


def public_offer(slot: dict, language: str = "es") -> dict:
    lang = lang_of(language)
    return {"id": slot["id"], "start": slot["start"], "end": slot["end"],
            "service_display": service_label(service_of(slot), lang),
            "modality_display": MODALITIES["in-person"][lang],
            "location_display": LOCATION[lang]}


def public_appointment(appointment: dict, language: str = "es") -> dict:
    return {"id": appointment["id"], "status": appointment["status"],
            "service_code": service_of(appointment),
            "service_display": service_label(service_of(appointment), language),
            "start": appointment["start"], "end": appointment["end"],
            "version": appointment["meta"]["versionId"],
            "slot_id": appointment["slot"][0]["reference"].split("/", 1)[1]}
