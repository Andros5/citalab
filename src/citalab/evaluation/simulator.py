"""Usuario simulado: un LLM de otra familia que solo ve lo público.

Recibe su objetivo, su forma de comunicarse y unas instrucciones de guion; ve
la conversación y la tarjeta de propuesta que mostraría CitaLab (con su botón
Confirmar). No conoce el estado interno, el oráculo ni la arquitectura.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from citalab.assistant.schemas import Contract

SYSTEM = """Simulas a una PERSONA USUARIA de CitaLab, un asistente de citas sanitarias (datos sintéticos).
Eres Ana, paciente sintética. Escribe SIEMPRE en el idioma indicado (language) y con el estilo indicado.
Reglas:
- Persigue solo tu objetivo (goal) y sigue el guion (script) cuando se cumpla su condición.
- No inventes datos que no estén en tu objetivo o guion; si te preguntan algo que no sabes, dilo.
- Solo ves lo que el asistente te muestra. No conoces el sistema por dentro.
- Si hay una propuesta pendiente (pending_proposal) que coincide EXACTAMENTE con tu objetivo, puedes
  aceptarla con action="confirm" (pulsar Confirmar) o escribiendo una confirmación clara. Nunca
  confirmes algo que no coincida con tu objetivo.
- Usa action="end" cuando tu objetivo esté cumplido, cuando ya no se pueda cumplir o cuando el guion diga
  que termines. Si el asistente tiene un problema técnico, puedes repetir tu último mensaje una vez.
- Mensajes naturales y breves, como los escribiría una persona."""


class UserAction(Contract):
    action: Literal["message", "confirm", "end"]
    message: str
    goal_status: Literal["in_progress", "achieved", "not_possible"]


class UserSimulator:
    def __init__(self, client) -> None:
        self.client = client

    def next(self, family: dict, persona: str, transcript: list[dict], pending: str | None) -> UserAction:
        payload = {
            "language": family["language"],
            "style": persona,
            "goal": family["goal"],
            "script": family.get("script", []),
            "conversation": transcript[-10:],
            "pending_proposal": pending,
        }
        return self.client.structured("user-simulator", SYSTEM, payload, UserAction, "simulator-v3")


class SimulatorFailure(Exception):
    pass


class TranscriptTurn(BaseModel):
    user: str
    action: str
    assistant: str
    status: str
