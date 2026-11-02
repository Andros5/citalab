"""Perfil de usuario: atributos con procedencia, confianza, vigencia y finalidad.

La resolución es determinista (no la hace un LLM): descarta lo retirado, caducado,
no autorizado para la finalidad o con confianza < 0,5; prioriza declarado >
importado > inferido y, ante un empate con valores distintos, no elige.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["declared", "imported", "inferred"]
Purpose = Literal["appointment-ranking", "response-adaptation", "reminder-preference"]

PURPOSE_KEYS: dict[str, tuple[str, ...]] = {
    "appointment-ranking": ("preferred-time-of-day", "preferred-modality", "preferred-location"),
    "response-adaptation": ("preferred-language", "preferred-detail-level", "preferred-treatment"),
    "reminder-preference": ("preferred-reminder-channel",),
}
ALLOWED_VALUES: dict[str, tuple[str, ...]] = {
    "preferred-time-of-day": ("morning", "afternoon"),
    "preferred-modality": ("in-person", "phone", "video"),
    "preferred-language": ("es", "en"),
    "preferred-detail-level": ("concise", "standard", "step-by-step"),
    "preferred-treatment": ("formal", "neutral"),
    "preferred-reminder-channel": ("sms", "email", "push"),
}
SOURCE_RANK = {"declared": 3, "imported": 2, "inferred": 1}
MIN_CONFIDENCE = 0.5


class Attribute(BaseModel):
    attribute_id: str
    key: str
    value: str
    source: Source
    confidence: float = Field(ge=0, le=1)
    observed_at: datetime
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    purposes: list[str]
    status: str = "active"
    sensitivity: str = "ordinary"
    provenance_ref: str = ""


class Profile(BaseModel):
    subject_id: str
    version: int = 1
    attributes: list[Attribute] = Field(default_factory=list)


class Resolved(BaseModel):
    key: str
    value: str
    source: Source
    confidence: float
    attribute_id: str


class Resolution(BaseModel):
    purpose: str
    values: dict[str, Resolved] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)

    def value(self, key: str) -> str | None:
        item = self.values.get(key)
        return item.value if item else None


def resolve(profile: Profile | None, purpose: str, now: datetime) -> Resolution:
    resolution = Resolution(purpose=purpose)
    if profile is None:
        return resolution
    for key in PURPOSE_KEYS[purpose]:
        candidates = []
        for attribute in profile.attributes:
            if attribute.key != key:
                continue
            reason = None
            if attribute.status != "active":
                reason = "inactive"
            elif purpose not in attribute.purposes:
                reason = "purpose"
            elif attribute.valid_until and attribute.valid_until <= now:
                reason = "expired"
            elif attribute.valid_from and attribute.valid_from > now:
                reason = "not-yet-valid"
            elif attribute.confidence < MIN_CONFIDENCE:
                reason = "low-confidence"
            elif attribute.value not in ALLOWED_VALUES.get(key, (attribute.value,)):
                reason = "invalid-value"
            if reason:
                resolution.excluded.append(f"{attribute.attribute_id}:{reason}")
            else:
                candidates.append(attribute)
        if not candidates:
            continue
        candidates.sort(key=lambda a: (SOURCE_RANK[a.source], a.confidence, a.observed_at), reverse=True)
        best = candidates[0]
        tied = [a for a in candidates[1:]
                if (SOURCE_RANK[a.source], a.confidence, a.observed_at)
                == (SOURCE_RANK[best.source], best.confidence, best.observed_at) and a.value != best.value]
        if tied:
            resolution.conflicts.append(key)
            continue
        resolution.values[key] = Resolved(key=key, value=best.value, source=best.source,
                                          confidence=best.confidence, attribute_id=best.attribute_id)
    return resolution


def load_profiles(path: Path) -> dict[str, Profile]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["subject_id"]: Profile.model_validate(item) for item in data["profiles"]}


def set_declared(profile: Profile, key: str, value: str, now: datetime, provenance: str) -> Profile:
    """Nueva versión con un atributo declarado (tras confirmación expresa del titular)."""
    if value not in ALLOWED_VALUES.get(key, ()):
        raise ValueError(f"invalid-preference:{key}")
    purpose = next(p for p, keys in PURPOSE_KEYS.items() if key in keys)
    attributes = [a for a in profile.attributes if not (a.key == key and a.source == "declared")]
    attributes.append(Attribute(attribute_id=f"{profile.subject_id}-{key}-v{profile.version + 1}",
                                key=key, value=value, source="declared", confidence=1.0,
                                observed_at=now, valid_from=now, purposes=[purpose],
                                provenance_ref=provenance))
    return Profile(subject_id=profile.subject_id, version=profile.version + 1, attributes=attributes)
