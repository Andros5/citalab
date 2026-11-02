"""API del portal con un LLM guionizado (sin red)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from citalab.llm.client import ScriptedClient
from citalab.portal.app import create_app
from citalab.portal.service import Portal
from citalab.portal.storage import Storage
from conftest import draft, interp


@pytest.fixture
def portal(tmp_path):
    service = Portal(Storage(tmp_path / "portal.sqlite3"))
    service.clients["groq"] = ScriptedClient({"context": [interp("query")] * 5,
                                              "writer": [draft("Tienes tus citas.")] * 5})
    return service


def login(client, portal, username):
    codes = dict(line.split(": ") for line in (portal.storage.path.parent / "accesos-iniciales.txt")
                 .read_text(encoding="utf-8").splitlines() if ": " in line)
    response = client.post("/api/auth/login", json={"username": username, "password": codes[username]})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf"]}


def wait(client, job_id):
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.05)
    raise AssertionError("job sin terminar")


def test_login_required_and_csrf_enforced(portal):
    client = TestClient(create_app(portal))
    assert client.get("/api/bootstrap").status_code == 401
    assert client.post("/api/auth/login", json={"username": "investigador", "password": "x"}).status_code == 401
    login(client, portal, "investigador")
    assert client.post("/api/conversations", json={"subject_id": "patient-ana"}).status_code == 403


def test_conversation_turn_roundtrip(portal):
    client = TestClient(create_app(portal))
    headers = login(client, portal, "investigador")
    conversation = client.post("/api/conversations", headers=headers,
                               json={"subject_id": "patient-ana", "architecture": "H", "provider": "groq"}).json()
    job = client.post(f"/api/conversations/{conversation['id']}/turns", headers=headers,
                      json={"action": "message", "message": "¿Qué citas tengo?", "expected_turn": 0}).json()
    assert wait(client, job["id"])["status"] == "completed"
    view = client.get(f"/api/conversations/{conversation['id']}").json()
    assert view["turn_count"] == 1 and view["turns"][0]["calls"]
    stale = client.post(f"/api/conversations/{conversation['id']}/turns", headers=headers,
                        json={"action": "message", "message": "otra", "expected_turn": 0})
    assert stale.status_code == 409


def test_patient_cannot_see_other_conversations_or_profiles(portal):
    client = TestClient(create_app(portal))
    headers = login(client, portal, "investigador")
    conversation = client.post("/api/conversations", headers=headers,
                               json={"subject_id": "patient-bruno", "architecture": "H", "provider": "groq"}).json()
    other = TestClient(create_app(portal))
    login(other, portal, "ana")
    assert other.get(f"/api/conversations/{conversation['id']}").status_code == 404
    assert other.get("/api/profiles/patient-bruno").status_code == 404
    assert other.get("/api/resources").status_code == 403
    assert other.get("/api/bootstrap").json()["patients"] == [{"id": "patient-ana", "name": "Ana Sintética",
                                                               "version": 1}]
