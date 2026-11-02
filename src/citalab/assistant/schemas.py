"""Contratos de salida de los agentes LLM: planos, pequeños y con enumeraciones.

Lección de la versión anterior: un esquema de 29 campos con citas literales y
validadores regex posteriores hacía fallar a modelos de 20B. Aquí cada contrato
cabe en una pantalla y ningún campo obliga a copiar texto del usuario.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Contract(BaseModel):
    """Base común: los modelos pequeños a veces escriben "null" como texto."""

    @model_validator(mode="before")
    @classmethod
    def _nulls(cls, data):
        if isinstance(data, dict):
            if "properties" in data and isinstance(data["properties"], dict) and "type" in data:
                data = data["properties"]  # el modelo copió el envoltorio del esquema
            return {k: (None if isinstance(v, str) and v.strip().lower() in ("null", "") else v)
                    for k, v in data.items()}
        return data

Intent = Literal["book", "query", "reschedule", "cancel", "reminder", "confirm", "reject",
                 "info", "greeting", "other"]
Service = Literal["general-practice", "pediatrics", "nursing"]
PartOfDay = Literal["morning", "afternoon"]
Channel = Literal["sms", "email", "push"]
Language = Literal["es", "en"]
Detail = Literal["concise", "standard", "step-by-step"]


class Interpretation(Contract):
    """Agente de contexto: qué pide la persona en este mensaje."""

    intent: Intent
    message_language: Language
    service: Service | None
    date_from: str | None = Field(description="YYYY-MM-DD")
    date_to: str | None = Field(description="YYYY-MM-DD, igual a date_from si es un día")
    time: str | None = Field(description="HH:MM si pide una hora concreta")
    part_of_day: PartOfDay | None
    appointment_id: str | None = Field(description="id de una cita propia mencionada")
    slot_id: str | None = Field(description="id de una opción ofrecida que elige")
    modality: Literal["in-person", "phone", "video"] | None
    reminder_channel: Channel | None
    reminder_minutes_before: int | None
    response_language: Language | None = Field(description="solo si lo pide expresamente")
    detail_level: Detail | None = Field(description="solo si lo pide expresamente")
    directive_scope: Literal["turn", "conversation"] | None
    profile_opt_out: bool
    other_person: bool = Field(description="pide datos o gestiones de otra persona")
    clinical_question: bool
    emergency: bool
    question: str | None = Field(description="pregunta informativa a responder, resumida")


class ComplianceAdvice(Contract):
    """Agente de cumplimiento: riesgo del mensaje (no concede permisos)."""

    decision: Literal["proceed", "refuse", "escalate"]
    rule_id: Literal["none", "CMP-REPRESENT-01", "CMP-PURPOSE-01", "CMP-CLINICAL-01",
                     "CMP-EMERGENCY-01", "CMP-AUTOMATION-01"]
    clinical_notice: bool
    reason: str


class ProfileAdvice(Contract):
    """Agente de perfiles: qué preferencias aplican a esta petición."""

    use_time_preference: bool
    use_reminder_channel: bool
    use_language_preference: bool
    use_detail_preference: bool
    reason: str


OrchestratorAction = Literal[
    "list_appointments", "find_slots", "propose_booking", "propose_reschedule",
    "propose_cancel", "propose_reminder", "confirm", "discard", "respond", "ask", "refuse",
]


class OrchestratorStep(Contract):
    """Agente orquestador: siguiente acción entre las habilitadas.

    Servicio, fechas, canal y antelación ya están en la tarea interpretada; el
    coordinador solo elige la acción y, si procede, la cita o el hueco.
    """

    action: OrchestratorAction
    appointment_id: str | None
    slot_id: str | None
    missing: Literal["service", "date", "appointment", "channel", "slot_choice", "none"]
    reason: str


class Draft(Contract):
    """Agente de personalización: texto final dirigido a la persona."""

    text: str
