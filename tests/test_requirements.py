"""Requisitos REQ-CITA y NOR de los capítulos 3 y del apéndice A, verificados sobre la v3."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from citalab.assistant.state import ConversationState
from citalab.assistant.tools import Toolbox
from citalab.domain.agenda import DomainError
from citalab.domain.policy import Auth, check_access, check_profile
from citalab.evaluation import oracle


def toolbox(agenda, profiles, auth=None):
    auth = auth or Auth("patient-ana", "patient-ana")
    return Toolbox(agenda, profiles, auth, ConversationState(subject_id=auth.subject_id, actor_id=auth.actor_id))


# REQ-CITA-01 / NOR-03: solicitante, paciente y representante.
def test_authorized_representative_can_manage_represented_patient(agenda, profiles):
    lucia = Auth("representative-lucia", "patient-ana", represented=frozenset({"patient-ana"}))
    tools = toolbox(agenda, profiles, lucia)
    assert tools.list_appointments()["count"] == 3
    tools.state.turn = 1
    assert "proposal" in tools.propose_cancel("apt-s7-a2")


def test_representative_without_grant_is_denied(agenda, profiles):
    stranger = Auth("representative-lucia", "patient-ana")  # sin relación de representación
    tools = toolbox(agenda, profiles, stranger)
    assert tools.list_appointments()["error"] == "forbidden"
    assert not check_access(Auth("representative-lucia", "patient-bruno", represented=frozenset({"patient-ana"})),
                            "query", "patient-bruno").allowed


# REQ-CITA-04: dos conversaciones compiten por el mismo hueco.
def test_two_conversations_cannot_book_the_same_slot(agenda, profiles):
    first, second = toolbox(agenda, profiles), toolbox(agenda, profiles)
    for tools in (first, second):
        tools.state.turn = 1
        tools.propose_booking("s7-f4")
        tools.state.turn = 2
    assert "receipt" in first.confirm(via="button")
    result = second.confirm(via="button")
    assert result["error"] == "conflict" and second.state.proposal is None


def test_parallel_writes_produce_a_single_booking(agenda):
    outcomes = []

    def attempt(i):
        try:
            outcomes.append(agenda.book("patient-ana", "s7-f5", None, f"parallel-{i}"))
        except DomainError as exc:
            outcomes.append(exc.code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(1 for o in outcomes if isinstance(o, dict)) == 1
    assert outcomes.count("slot-unavailable") == 11


# REQ-CITA-05: no sustituir la modalidad pedida.
def test_requested_modality_is_never_silently_replaced(agenda, profiles):
    tools = toolbox(agenda, profiles)
    result = tools.find_slots("general-practice", modality="phone")
    assert result["options"] == [] and result["unavailable_modality"] == "phone"
    assert tools.find_slots("general-practice", modality="in-person")["options"]


# REQ-CITA-11 / NOR-10: traza mínima separada, sin contenido conversacional.
def test_minimal_audit_trace_without_conversation_content(agenda, profiles):
    tools = toolbox(agenda, profiles)
    tools.state.turn = 1
    tools.propose_booking("s7-f4")
    tools.state.turn = 2
    tools.confirm(via="text", user_text="Sí, confírmala")
    tools.propose_cancel("apt-s7-b1")  # denegado
    events = list(agenda.resources["AuditEvent"].values())
    outcomes = {(e["type"]["code"], e["outcome"]) for e in events}
    assert ("book", "0") in outcomes and ("access", "8") in outcomes
    for event in events:
        assert set(event) <= {"resourceType", "id", "recorded", "type", "action", "outcome", "agent", "entity",
                              "extension"}
        assert "confírmala" not in str(event)


# NOR-11: rechazo de modos de datos incompatibles.
def test_non_synthetic_data_mode_is_rejected(agenda, profiles):
    real = Auth("patient-ana", "patient-ana", data_mode="real")
    assert check_access(real, "query", "patient-ana").rule_id == "CMP-MODE-01"
    assert toolbox(agenda, profiles, real).list_appointments()["error"] == "forbidden"


# NOR-02: el perfil solo se consulta para finalidades definidas.
def test_unknown_profile_purpose_is_denied():
    decision = check_profile(Auth("patient-ana", "patient-ana"), "marketing", opted_out=False)
    assert not decision.allowed and decision.rule_id == "CMP-MINIMIZE-01"


# Validación del usuario simulado (capítulo 4).
def test_simulator_checks_flag_invalid_behaviour():
    family = {"language": "es", "expect": {"effect": "book"}}
    ok = oracle.simulator_checks(family, "user-end:achieved", True, 0, ["Quiero una cita de enfermería, por favor"])
    assert ok["valid"] and ok["flags"] == []
    bad = oracle.simulator_checks(family, "max-turns", False, 2, ["I would like an appointment for nursing please"])
    assert not bad["valid"] and any(f.startswith("confirm-without-proposal") for f in bad["flags"])
    belief = oracle.simulator_checks(family, "user-end:achieved", False, 0, [])
    assert belief["valid"] and "believed-achieved-but-failed" in belief["flags"]


# Retención y diagnóstico (apéndice A, finalidades de los registros).
def test_portal_redacts_calls_and_purges_expired_history(tmp_path):
    from citalab.llm.client import ScriptedClient
    from citalab.portal.service import Portal
    from citalab.portal.storage import Storage
    from conftest import draft, interp

    portal = Portal(Storage(tmp_path / "p.sqlite3"))
    portal.clients["groq"] = ScriptedClient({"context": [interp("query")] * 2, "writer": [draft("Tus citas.")] * 2})
    user = portal.storage.load("users", "investigador")
    plain = portal.create_conversation(user, {"subject_id": "patient-ana", "architecture": "H", "provider": "groq"})
    job = portal.post_turn(user, plain["id"], {"action": "message", "message": "¿Qué citas tengo?",
                                               "expected_turn": 0})
    portal.pool.shutdown(wait=True)
    assert portal.storage.load("jobs", job["id"])["status"] == "completed"
    calls = portal.storage.load("conversations", plain["id"])["turns"][0]["calls"]
    assert calls and all(c["diagnostic_redacted"] and "input" not in c and "output" not in c for c in calls)

    stored = portal.storage.load("conversations", plain["id"])
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    stored["updated_at"] = old
    portal.storage.save("conversations", plain["id"], stored, owner=stored["owner"], updated_at=old)
    assert portal.purge_expired()["removed_conversations"] == 1
    assert portal.storage.load("conversations", plain["id"]) is None
    with pytest.raises(Exception):
        portal.update_config(user, {"retention_days": 120})
    with pytest.raises(Exception):
        portal.update_config(user, {"data_mode": "real"})


# Revisión humana (Apéndice B): NA nunca se convierte en 0 ni en 3.
def test_review_scores_accept_na_and_reject_out_of_range():
    from citalab.evaluation.review import DIMENSIONS, SIMULATOR_DIMENSIONS, _mean, _scores
    scores = _scores({"administrative": 3, "continuity": "NA"}, DIMENSIONS)
    assert scores["administrative"] == 3 and scores["continuity"] is None and scores["clarity"] is None
    assert _mean([3, None, 1]) == 2
    with pytest.raises(ValueError):
        _scores({"coherence": 4}, SIMULATOR_DIMENSIONS)
