from __future__ import annotations

from datetime import UTC, datetime

import pytest

from citalab.assistant.engine import Assistant
from citalab.domain.policy import Auth
from citalab.evaluation.fixtures import build_agenda, build_profiles
from citalab.llm.client import ScriptedClient

NOW = datetime(2026, 10, 5, 8, tzinfo=UTC)
FIELDS = ("service", "date_from", "date_to", "time", "part_of_day", "appointment_id", "slot_id", "modality",
          "reminder_channel", "reminder_minutes_before", "response_language", "detail_level", "directive_scope",
          "question")


def interp(intent: str, **values) -> dict:
    """Salida de contexto mínima: todo a null salvo lo indicado."""
    data = {field: None for field in FIELDS}
    data.update(intent=intent, message_language="es", profile_opt_out=False, other_person=False,
                clinical_question=False, emergency=False)
    data.update(values)
    return data


def draft(text: str) -> dict:
    return {"text": text}


@pytest.fixture
def agenda():
    return build_agenda({"pediatric": True}, NOW)


@pytest.fixture
def profiles():
    return build_profiles({}, NOW)


@pytest.fixture
def make_assistant(agenda, profiles):
    def factory(architecture: str, script: dict) -> tuple[Assistant, ScriptedClient]:
        client = ScriptedClient(script)
        return Assistant(architecture, client, agenda, profiles, Auth("patient-ana", "patient-ana")), client
    return factory
