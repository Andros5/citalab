"""Estado conversacional compartido por M5, S1 y H."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["READY", "NEEDS_CLARIFICATION", "NEEDS_CONFIRMATION", "COMPLETED", "BLOCKED",
                 "ESCALATED", "FAILED", "DISCARDED"]


class Option(BaseModel):
    number: int
    slot_id: str
    start: str
    service: str


class Shown(BaseModel):
    number: int
    appointment_id: str
    start: str
    service: str


class Proposal(BaseModel):
    proposal_id: str
    operation: Literal["book", "cancel", "reschedule", "reminder"]
    revision: int = 1
    created_turn: int
    expires_at: str
    slot_id: str | None = None
    slot_version: str | None = None
    appointment_id: str | None = None
    appointment_version: str | None = None
    channel: str | None = None
    minutes_before: int | None = None


class Receipt(BaseModel):
    operation: str
    status: str
    result_id: str | None = None
    idempotency_key: str
    at: str
    proposal_id: str


class Task(BaseModel):
    """Restricciones acumuladas de la gestión en curso."""

    operation: str | None = None
    service: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    time: str | None = None
    part_of_day: str | None = None
    modality: str | None = None
    appointment_id: str | None = None
    channel: str | None = None
    minutes_before: int | None = None


class ConversationState(BaseModel):
    subject_id: str
    actor_id: str
    turn: int = 0
    language: Literal["es", "en"] = "es"
    history: list[dict[str, str]] = Field(default_factory=list)
    task: Task = Field(default_factory=Task)
    options: list[Option] = Field(default_factory=list)
    shown: list[Shown] = Field(default_factory=list)
    proposal: Proposal | None = None
    receipt: Receipt | None = None
    # Claves: language, detail_level, treatment, time_of_day, reminder_channel.
    conversation_preferences: dict[str, str] = Field(default_factory=dict)
    turn_preferences: dict[str, str] = Field(default_factory=dict)
    profile_opt_out: bool = False
    status: Status = "READY"
    escalated: bool = False
    counters: dict[str, int] = Field(default_factory=dict)

    def bump(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount

    def remember(self, user: str, assistant: str, limit: int = 8) -> None:
        self.history = [*self.history, {"user": user, "assistant": assistant}][-limit:]


class TurnResult(BaseModel):
    response: str
    status: Status
    plans: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    calls: list[dict[str, Any]] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=list)
    language: str = "es"
