"""Casos adversariales sobre la capa de herramientas compartida (todas las arquitecturas).

Ninguna salida de un LLM puede ampliar estos límites: aquí se llama a las
herramientas directamente con argumentos maliciosos o fuera de orden.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from citalab.assistant.state import ConversationState
from citalab.assistant.tools import Toolbox, explicit_affirmation
from citalab.domain.policy import Auth


@pytest.fixture
def tools(agenda, profiles):
    state = ConversationState(subject_id="patient-ana", actor_id="patient-ana")
    return Toolbox(agenda, profiles, Auth("patient-ana", "patient-ana"), state)


def snapshot_ok(agenda, before):
    return agenda.snapshot()["Appointment"] == before["Appointment"]


@pytest.mark.parametrize("operation", ["cancel", "reminder", "reschedule"])
def test_other_patient_appointment_is_denied_without_disclosure(tools, agenda, operation):
    before = agenda.snapshot()
    call = {"cancel": lambda: tools.propose_cancel("apt-s7-b1"),
            "reminder": lambda: tools.propose_reminder("apt-s7-b1", "sms", 30),
            "reschedule": lambda: tools.propose_reschedule("apt-s7-b1", "s7-f4")}[operation]
    result = call()
    assert result == {"error": "forbidden"}  # sin fechas, servicio ni identidad del ajeno
    assert tools.state.proposal is None and snapshot_ok(agenda, before)


def test_listing_never_includes_other_patients(tools):
    listed = tools.list_appointments()
    assert {a["appointment_id"] for a in listed["appointments"]} == {"apt-s7-a1", "apt-s7-a2", "apt-s7-a3"}


def test_confirm_without_proposal_writes_nothing(tools, agenda):
    before = agenda.snapshot()
    assert tools.confirm(via="text", user_text="sí")["error"] == "no-pending-proposal"
    assert snapshot_ok(agenda, before)


def test_text_confirmation_in_same_turn_as_proposal_is_rejected(tools, agenda):
    tools.state.turn = 1
    tools.propose_booking("s7-f4")
    result = tools.confirm(via="text", user_text="sí, confirmo")
    assert result["error"] == "confirmation-rejected"
    assert agenda.slot("s7-f4")["status"] == "free"


@pytest.mark.parametrize("text", ["no", "espera, todavía no", "¿qué pasaría si confirmo?", "explícamelo", "wait"])
def test_non_affirmative_text_never_confirms(tools, agenda, text):
    tools.state.turn = 1
    tools.propose_booking("s7-f4")
    tools.state.turn = 2
    assert tools.confirm(via="text", user_text=text)["error"] == "confirmation-rejected"
    assert agenda.slot("s7-f4")["status"] == "free"


def test_button_confirmation_must_match_proposal(tools, agenda):
    tools.state.turn = 1
    tools.propose_booking("s7-f4")
    assert tools.confirm(via="button", proposal_id="prop-otra")["error"] == "confirmation-rejected"
    assert agenda.slot("s7-f4")["status"] == "free"


def test_expired_proposal_cannot_be_confirmed(tools, agenda):
    tools.state.turn = 1
    tools.propose_booking("s7-f4")
    later = agenda.now() + timedelta(hours=2)
    agenda.set_clock(lambda: later)
    tools.state.turn = 2
    assert tools.confirm(via="text", user_text="sí")["error"] == "confirmation-rejected"


def test_stale_proposal_after_external_booking_is_a_conflict(tools, agenda):
    tools.state.turn = 1
    tools.propose_booking("s7-n2")
    agenda.occupy_slot("s7-n2")
    tools.state.turn = 2
    result = tools.confirm(via="button")
    assert result["error"] == "conflict" and tools.state.proposal is None


def test_valid_confirmation_writes_once(tools, agenda):
    tools.state.turn = 1
    tools.propose_booking("s7-f4")
    tools.state.turn = 2
    assert "receipt" in tools.confirm(via="text", user_text="Sí, confírmala")
    assert agenda.slot("s7-f4")["status"] == "busy"
    assert tools.confirm(via="button")["error"] == "no-pending-proposal"  # no hay segunda escritura


def test_profile_opt_out_blocks_preference_reads(tools):
    tools.state.profile_opt_out = True
    assert tools.preferences("appointment-ranking") == {"available": False, "reason": "CMP-OPTOUT-01"}


def test_minimised_profile_view_only_returns_purpose_fields(tools):
    view = tools.preferences("reminder-preference")
    assert set(view["values"]) <= {"preferred-reminder-channel"}


def test_unknown_slot_or_invented_ids_are_rejected(tools):
    assert tools.propose_booking("slot-inventado") == {"error": "slot-unavailable"}
    assert tools.propose_cancel("apt-inventada") == {"error": "appointment-not-found"}


@pytest.mark.parametrize("text,expected", [("Sí, confírmala", True), ("vale", True), ("Yes, please do", True), ("Sí, confírmala, ¿vale?", False),
                                           ("No, gracias", False), ("todavía no", False)])
def test_affirmation_detector(text, expected):
    assert explicit_affirmation(text) is expected
