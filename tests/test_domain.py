"""Núcleo determinista: agenda FHIR, perfiles y políticas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from citalab.domain.agenda import DomainError
from citalab.domain.policy import Auth, check_access, check_profile, check_write, emergency_signal
from citalab.domain.profiles import Attribute, Profile, resolve, set_declared
from conftest import NOW


def test_book_is_idempotent_and_blocks_double_booking(agenda):
    first = agenda.book("patient-ana", "s7-f4", None, "k1")
    assert agenda.book("patient-ana", "s7-f4", None, "k1") == first  # repetición sin duplicar
    with pytest.raises(DomainError, match="slot-unavailable"):
        agenda.book("patient-bruno", "s7-f4", None, "k2")
    with pytest.raises(DomainError, match="idempotency-key-reused"):
        agenda.book("patient-ana", "s7-f5", None, "k1")


def test_stale_slot_version_is_rejected(agenda):
    agenda.occupy_slot("s7-n2")
    with pytest.raises(DomainError):
        agenda.book("patient-ana", "s7-n2", "1", "k")


def test_reschedule_keeps_original_when_destination_unavailable(agenda):
    agenda.occupy_slot("s7-n2")
    with pytest.raises(DomainError):
        agenda.reschedule("patient-ana", "apt-s7-a2", None, "s7-n2", None, "k")
    assert agenda.appointment("apt-s7-a2")["start"].startswith("2026-10-09T12:00")


def test_reschedule_moves_and_frees_slots(agenda):
    agenda.reschedule("patient-ana", "apt-s7-a1", None, "s7-f4", None, "k")
    assert agenda.appointment("apt-s7-a1")["slot"][0]["reference"] == "Slot/s7-f4"
    assert agenda.slot("s7-a1")["status"] == "free"


def test_cannot_touch_another_patient(agenda):
    with pytest.raises(DomainError, match="forbidden-subject"):
        agenda.cancel("patient-ana", "apt-s7-b1", None, "k")


def test_reminder_is_simulated_and_replaces_previous(agenda):
    agenda.set_reminder("patient-ana", "apt-s7-a2", "sms", 30, "k1")
    agenda.set_reminder("patient-ana", "apt-s7-a2", "email", 45, "k2")
    active = agenda.reminders_of("apt-s7-a2")
    assert len(active) == 1 and active[0]["medium"][0]["coding"][0]["code"] == "email"
    assert {"url": "simulated", "valueBoolean": True} in active[0]["extension"]


def _attr(key, value, source, confidence, purpose, **extra):
    return Attribute(attribute_id=f"{key}-{source}-{value}", key=key, value=value, source=source,
                     confidence=confidence, observed_at=NOW - timedelta(days=1), purposes=[purpose], **extra)


def test_profile_resolution_rules():
    profile = Profile(subject_id="p", attributes=[
        _attr("preferred-time-of-day", "afternoon", "declared", 1.0, "appointment-ranking"),
        _attr("preferred-time-of-day", "morning", "imported", 0.9, "appointment-ranking"),
        _attr("preferred-modality", "phone", "inferred", 0.4, "appointment-ranking"),
        _attr("preferred-language", "en", "declared", 1.0, "response-adaptation"),
    ])
    ranking = resolve(profile, "appointment-ranking", NOW)
    assert ranking.value("preferred-time-of-day") == "afternoon"  # declarado > importado
    assert ranking.value("preferred-modality") is None  # confianza < 0,5
    assert "preferred-language" not in ranking.values  # otra finalidad


def test_profile_tie_is_not_resolved():
    profile = Profile(subject_id="p", attributes=[
        _attr("preferred-time-of-day", "afternoon", "declared", 1.0, "appointment-ranking"),
        _attr("preferred-time-of-day", "morning", "declared", 1.0, "appointment-ranking"),
    ])
    assert resolve(profile, "appointment-ranking", NOW).conflicts == ["preferred-time-of-day"]


def test_expired_attribute_is_ignored_and_declared_update_versions():
    profile = Profile(subject_id="p", attributes=[
        _attr("preferred-detail-level", "concise", "declared", 1.0, "response-adaptation",
              valid_until=NOW - timedelta(hours=1))])
    assert resolve(profile, "response-adaptation", NOW).value("preferred-detail-level") is None
    updated = set_declared(profile, "preferred-detail-level", "step-by-step", NOW, "test")
    assert updated.version == 2
    assert resolve(updated, "response-adaptation", NOW).value("preferred-detail-level") == "step-by-step"


def test_policy_decisions_cite_rules():
    ana = Auth("patient-ana", "patient-ana")
    assert check_access(ana, "query", "patient-ana").allowed
    denied = check_access(ana, "cancel", "patient-bruno")
    assert not denied.allowed and denied.rule_id == "CMP-REPRESENT-01" and denied.references
    assert not check_access(Auth("x", "x", authenticated=False), "query", "x").allowed
    assert not check_access(ana, "diagnose", "patient-ana").allowed
    assert not check_profile(ana, "appointment-ranking", opted_out=True).allowed
    assert not check_write(ana, "patient-ana", confirmed=False, proposal_live=True).allowed
    assert not check_write(ana, "patient-ana", confirmed=True, proposal_live=False).allowed
    assert check_write(ana, "patient-ana", confirmed=True, proposal_live=True).allowed


@pytest.mark.parametrize("text", ["Tengo un dolor fuerte en el pecho", "I can't breathe", "creo que es un ictus"])
def test_emergency_safety_net(text):
    assert emergency_signal(text)


def test_no_false_emergency():
    assert not emergency_signal("Quiero una cita de enfermería para una cura")


def test_clock_is_used_for_past_slots(agenda):
    agenda.set_clock(lambda: datetime(2026, 10, 7, 12, tzinfo=UTC))
    with pytest.raises(DomainError, match="slot-in-past"):
        agenda.book("patient-ana", "s7-f4", None, "k")
