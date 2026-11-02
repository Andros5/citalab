"""Motor de políticas determinista: la frontera que ningún LLM puede ampliar.

Cada decisión cita su regla y las referencias normativas (RGPD, Reglamento de
IA, Ley 41/2002). Se combina con `deny-overrides`: basta un fallo para denegar.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

RULES: dict[str, dict[str, object]] = {
    "CMP-MODE-01": {"title": "Solo modo de datos sintético en el laboratorio",
                    "refs": ["AI Act art. 2.6 y 2.8", "RGPD art. 5.1.b"]},
    "CMP-AUTH-01": {"title": "Autenticación de la sesión",
                    "refs": ["RGPD art. 5.1.f", "Ley 41/2002 art. 7"]},
    "CMP-REPRESENT-01": {"title": "Acceso solo a datos propios o representados",
                         "refs": ["Ley 41/2002 arts. 5 y 9", "RGPD art. 5.1.f"]},
    "CMP-PURPOSE-01": {"title": "Operación dentro de la finalidad administrativa",
                       "refs": ["RGPD art. 5.1.b"]},
    "CMP-MINIMIZE-01": {"title": "Vista del perfil limitada a la finalidad",
                        "refs": ["RGPD art. 5.1.c", "RGPD art. 25"]},
    "CMP-OPTOUT-01": {"title": "Renuncia al uso del perfil",
                      "refs": ["RGPD art. 21", "RGPD art. 7.3"]},
    "CMP-CONFIRM-01": {"title": "Confirmación explícita antes de cualquier escritura",
                       "refs": ["RGPD art. 22", "AI Act art. 14"]},
    "CMP-CLINICAL-01": {"title": "Sin valoración clínica en el asistente administrativo",
                        "refs": ["RGPD art. 9", "Ley 41/2002 arts. 4 y 10"]},
    "CMP-EMERGENCY-01": {"title": "Posible emergencia: detener y derivar al 112",
                         "refs": ["AI Act art. 14", "Ley 41/2002 art. 2"]},
    "CMP-AUTOMATION-01": {"title": "Sin priorización clínica automatizada",
                          "refs": ["RGPD art. 22", "AI Act art. 14"]},
    "CMP-TRANSPARENCY-01": {"title": "Aviso de interacción con IA y datos sintéticos",
                            "refs": ["AI Act art. 50", "RGPD arts. 13 y 14"]},
}

READ_OPERATIONS = {"query", "search"}
WRITE_OPERATIONS = {"book", "cancel", "reschedule", "reminder"}
OPERATIONS = READ_OPERATIONS | WRITE_OPERATIONS


@dataclass(frozen=True)
class Auth:
    """Quién actúa (actor) y sobre quién (subject)."""

    actor_id: str
    subject_id: str
    authenticated: bool = True
    represented: frozenset[str] = frozenset()
    data_mode: str = "synthetic"

    def may_act_for(self, patient_id: str) -> bool:
        return patient_id == self.subject_id and (
            self.actor_id == self.subject_id or patient_id in self.represented)


@dataclass
class Decision:
    allowed: bool
    rule_id: str
    reason: str
    obligations: list[str] = field(default_factory=list)

    @property
    def references(self) -> list[str]:
        return list(RULES[self.rule_id]["refs"])  # type: ignore[arg-type]

    def as_dict(self) -> dict:
        return {"allowed": self.allowed, "rule_id": self.rule_id, "reason": self.reason,
                "references": self.references, "obligations": self.obligations}


def check_mode(auth: Auth) -> Decision | None:
    if auth.data_mode != "synthetic":
        return Decision(False, "CMP-MODE-01", f"Modo de datos incompatible con el laboratorio: {auth.data_mode}.")
    return None


def check_access(auth: Auth, operation: str, patient_id: str | None) -> Decision:
    if (denied := check_mode(auth)) is not None:
        return denied
    if not auth.authenticated:
        return Decision(False, "CMP-AUTH-01", "La sesión no está autenticada.")
    if operation not in OPERATIONS:
        return Decision(False, "CMP-PURPOSE-01", f"Operación fuera del alcance: {operation}.")
    if patient_id is not None and not auth.may_act_for(patient_id):
        return Decision(False, "CMP-REPRESENT-01",
                        "El recurso pertenece a otra persona y no consta representación.")
    obligations = ["bound-explicit-confirmation"] if operation in WRITE_OPERATIONS else []
    rule = "CMP-CONFIRM-01" if obligations else "CMP-PURPOSE-01"
    return Decision(True, rule, "Acceso permitido a datos propios.", obligations)


def check_profile(auth: Auth, purpose: str, opted_out: bool) -> Decision:
    from citalab.domain.profiles import PURPOSE_KEYS
    if (denied := check_mode(auth)) is not None:
        return denied
    if not auth.authenticated:
        return Decision(False, "CMP-AUTH-01", "La sesión no está autenticada.")
    if purpose not in PURPOSE_KEYS:
        return Decision(False, "CMP-MINIMIZE-01", f"Finalidad no autorizada para el perfil: {purpose}.")
    if opted_out:
        return Decision(False, "CMP-OPTOUT-01", "La persona ha pedido no usar su perfil.")
    return Decision(True, "CMP-MINIMIZE-01", f"Vista del perfil limitada a «{purpose}».")


def check_write(auth: Auth, patient_id: str, *, confirmed: bool, proposal_live: bool) -> Decision:
    access = check_access(auth, "book", patient_id)
    if not access.allowed:
        return access
    if not confirmed:
        return Decision(False, "CMP-CONFIRM-01", "Falta la confirmación explícita de la propuesta.")
    if not proposal_live:
        return Decision(False, "CMP-CONFIRM-01", "La propuesta ya no está vigente.")
    return Decision(True, "CMP-CONFIRM-01", "Propuesta vigente confirmada por la persona.")


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Red de seguridad mínima: el LLM también marca emergencias; esta lista solo
# garantiza que los casos evidentes nunca dependen de una salida del modelo.
_EMERGENCY = re.compile(
    r"\b(dolor (fuerte )?(en el|de) pecho|no puedo respirar|me ahogo|infarto|ictus|"
    r"perdida de (conocimiento|consciencia)|sangrado abundante|quiero suicidarme|suicid|"
    r"chest pain|can'?t breathe|cannot breathe|heart attack|stroke|unconscious|"
    r"severe bleeding|kill myself)\b")


def emergency_signal(text: str) -> bool:
    return bool(_EMERGENCY.search(_plain(text)))
