"""M5, S1 y H con un LLM guionizado: mismos efectos, distintas decisiones."""

from __future__ import annotations

import json

from citalab.llm.client import LLMError
from conftest import draft, interp


def step(action, **values):
    return {"action": action, "appointment_id": values.get("appointment_id"), "slot_id": values.get("slot_id"),
            "missing": values.get("missing", "none"), "reason": "test"}


def compliance(decision="proceed", rule="none", clinical=False):
    return {"decision": decision, "rule_id": rule, "clinical_notice": clinical, "reason": "test"}


PROFILE = {"use_time_preference": True, "use_reminder_channel": True, "use_language_preference": False,
           "use_detail_preference": True, "reason": "test"}


def test_h_books_after_explicit_confirmation(make_assistant, agenda):
    assistant, client = make_assistant("H", {
        "context": [interp("book", service="general-practice", date_from="2026-10-07", time="10:00"),
                    interp("confirm")],
        "writer": [draft("Propuesta: medicina de familia el 7 de octubre a las 10:00. ¿Lo confirmas?"),
                   draft("Hecho: tu cita del 7 de octubre a las 10:00 ha quedado reservada.")],
    })
    first = assistant.turn("message", "Quiero medicina de familia el 7 de octubre a las 10:00")
    assert first.status == "NEEDS_CONFIRMATION" and agenda.slot("s7-f4")["status"] == "free"
    second = assistant.turn("message", "Sí, confírmala")
    assert second.status == "COMPLETED" and agenda.slot("s7-f4")["status"] == "busy"
    assert {c["agent"] for c in first.calls} == {"context", "writer"}


def test_writer_hallucination_falls_back_to_deterministic_text(make_assistant, agenda):
    assistant, _ = make_assistant("H", {
        "context": [interp("book", service="general-practice", date_from="2026-10-07", time="10:00")],
        "writer": [draft("¡Listo! Tu cita ha quedado reservada para el 7 de octubre a las 10:00.")],
    })
    result = assistant.turn("message", "Quiero medicina de familia el 7 de octubre a las 10:00")
    assert "Todavía no se ha aplicado ningún cambio" in result.response
    assert result.fallbacks and result.fallbacks[0].startswith("writer-check:unsupported-success-claim")
    assert agenda.slot("s7-f4")["status"] == "free"


def test_llm_failure_never_ends_the_conversation(make_assistant):
    assistant, _ = make_assistant("H", {"context": [LLMError("provider-unavailable"),
                                                    interp("query")],
                                        "writer": [draft("Tienes 3 citas pendientes: ... 09:00, 12:00 y 11:00.")]})
    failed = assistant.turn("message", "¿Qué citas tengo?")
    assert "problema técnico" in failed.response and failed.status == "READY"
    again = assistant.turn("message", "¿Qué citas tengo?")
    assert "3 cita" in again.response


def test_h_refuses_other_person_and_escalates_emergency(make_assistant):
    assistant, _ = make_assistant("H", {"context": [interp("cancel", other_person=True),
                                                    interp("book", emergency=True)]})
    refusal = assistant.turn("message", "Cancela la cita de Bruno")
    assert refusal.status == "BLOCKED" and "otra persona" in refusal.response
    stop = assistant.turn("message", "Tengo un dolor fuerte en el pecho, ¿me das cita?")
    assert stop.status == "ESCALATED" and "112" in stop.response


def test_clinical_question_keeps_administrative_task(make_assistant):
    assistant, _ = make_assistant("H", {
        "context": [interp("book", service="nursing", date_from="2026-10-06", time="10:00", clinical_question=True)],
        "writer": [draft("Propuesta de enfermería el 6 de octubre a las 10:00. ¿Lo confirmas?")]})
    result = assistant.turn("message", "Enfermería el 6 a las 10:00. ¿Y este dolor de cabeza?")
    assert result.status == "NEEDS_CONFIRMATION"
    assert result.response.startswith("No puedo hacer valoraciones clínicas")


def test_m5_uses_five_roles_and_only_allowed_actions(make_assistant, agenda):
    assistant, _ = make_assistant("M5", {
        "context": [interp("book", service="general-practice", date_from="2026-10-07", time="10:00")],
        "compliance": [compliance()],
        "profile": [PROFILE],
        "orchestration": [step("propose_booking", slot_id="s7-f4"),  # aún no permitido: no hay opciones
                          ],
        "personalization": [draft("Te propongo el 7 de octubre a las 10:00. ¿Lo confirmas?")],
    })
    result = assistant.turn("message", "Medicina de familia el 7 a las 10:00")
    assert "orchestration-rejected:propose_booking" in result.fallbacks
    assert agenda.slot("s7-f4")["status"] == "free" and assistant.state.proposal is None


def test_m5_full_booking_loop(make_assistant, agenda):
    assistant, _ = make_assistant("M5", {
        "context": [interp("book", service="general-practice", date_from="2026-10-07", time="10:00"),
                    interp("confirm")],
        "compliance": [compliance(), compliance()],
        "profile": [PROFILE, PROFILE],
        "orchestration": [step("find_slots"), step("propose_booking", slot_id="s7-f4"), step("confirm")],
        "personalization": [draft("Propuesta para el 7 de octubre a las 10:00. ¿Lo confirmas?"),
                            draft("Hecho: la cita del 7 de octubre a las 10:00 ha quedado reservada.")],
    })
    first = assistant.turn("message", "Medicina de familia el 7 a las 10:00")
    agents = [c["agent"] for c in first.calls]
    assert agents == ["context", "compliance", "profile", "orchestration", "orchestration", "personalization"]
    assert first.status == "NEEDS_CONFIRMATION"
    second = assistant.turn("message", "Sí")
    assert second.status == "COMPLETED" and agenda.slot("s7-f4")["status"] == "busy"


def tool_call(name, **arguments):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"call-{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def test_s1_tool_loop_and_confirmation(make_assistant, agenda):
    assistant, _ = make_assistant("S1", {"single": [
        tool_call("find_slots", service="general-practice", date_from="2026-10-07", time="10:00"),
        tool_call("propose_booking", slot_id="s7-f4"),
        {"role": "assistant", "content": "Te propongo medicina de familia el 7 de octubre a las 10:00. ¿Confirmas?"},
        tool_call("confirm_pending_proposal"),
        {"role": "assistant", "content": "Tu cita del 7 de octubre a las 10:00 ha quedado reservada."},
    ]})
    first = assistant.turn("message", "Medicina de familia el 7 de octubre a las 10:00")
    assert first.status == "NEEDS_CONFIRMATION" and not first.fallbacks
    second = assistant.turn("message", "Sí, confirmo")
    assert second.status == "COMPLETED" and agenda.slot("s7-f4")["status"] == "busy"


def test_s1_false_success_claim_is_replaced(make_assistant, agenda):
    assistant, _ = make_assistant("S1", {"single": [
        tool_call("find_slots", service="nursing", date_from="2026-10-06", time="10:00"),
        {"role": "assistant", "content": "Tu cita de enfermería está confirmada para el 6 a las 10:00."},
    ]})
    result = assistant.turn("message", "Enfermería el 6 a las 10:00")
    assert result.fallbacks and "unsupported-success-claim" in result.fallbacks[0]
    assert "confirmada" not in result.response and agenda.slot("s7-n1")["status"] == "free"


def test_button_confirmation_is_identical_for_all_architectures(make_assistant, agenda):
    for architecture, script in (("H", {"writer": [draft("Hecho: cita del 7 de octubre a las 10:00 reservada.")]}),
                                 ("S1", {"single": [{"role": "assistant", "content": "Reservada a las 10:00."}]})):
        assistant, _ = make_assistant(architecture, script)
        assistant.state.turn = 1
        assistant.tools = None
        from citalab.assistant.tools import Toolbox
        Toolbox(agenda, assistant.profiles, assistant.auth, assistant.state).propose_booking("s7-f4")
        result = assistant.turn("confirm")
        assert result.status == "COMPLETED"
        agenda.cancel("patient-ana", next(a["id"] for a in agenda.appointments_of("patient-ana")
                                          if a["slot"][0]["reference"] == "Slot/s7-f4"), None, f"undo-{architecture}")
