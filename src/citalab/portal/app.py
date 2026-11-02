"""API HTTP de CitaLab (FastAPI) y servidor de la interfaz compilada.

Arranque: python -m citalab.portal.app  →  http://127.0.0.1:8765
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from citalab.assistant import prompts
from citalab.config import OUTPUT, ROOT
from citalab.portal.service import Portal, PortalError

COOKIE = "citalab_session"
DIST = ROOT / "web" / "dist"

ARCHITECTURES = {
    "M5": {"id": "M5", "title": "M5 · Cinco agentes especializados",
           "summary": "Contexto, cumplimiento, perfiles, orquestación y personalización como agentes LLM "
                      "coordinados por un grafo LangGraph.",
           "agents": ["context", "compliance", "profile", "orchestration", "personalization"]},
    "S1": {"id": "S1", "title": "S1 · Agente único",
           "summary": "Un único agente LLM con llamadas nativas a las mismas herramientas y controles.",
           "agents": ["single"]},
    "H": {"id": "H", "title": "H · Híbrida",
          "summary": "Flujo programado en código; el LLM solo interpreta el mensaje y redacta la respuesta.",
          "agents": ["context", "writer"]},
}


def create_app(portal: Portal | None = None) -> FastAPI:
    app = FastAPI(title="CitaLab", version="3.0")
    service = portal or Portal()
    app.state.portal = service

    @app.exception_handler(PortalError)
    async def _portal_error(_: Request, exc: PortalError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    def current(request: Request) -> dict:
        user, csrf = service.session(request.cookies.get(COOKIE))
        if request.method not in ("GET", "HEAD") and request.headers.get("X-CSRF-Token") != csrf:
            raise PortalError(403, "Falta el token de seguridad de la sesión.")
        return user

    def staff(user: dict = Depends(current)) -> dict:
        if user["role"] == "patient":
            raise PortalError(403, "Solo para el equipo investigador.")
        return user

    def admin(user: dict = Depends(current)) -> dict:
        if user["role"] not in ("admin", "researcher"):
            raise PortalError(403, "Solo para administración.")
        return user

    async def body(request: Request) -> dict[str, Any]:
        try:
            value = await request.json()
        except (json.JSONDecodeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    # ---------------------------------------------------------------- auth
    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": "3.0"}

    @app.post("/api/auth/login")
    async def login(request: Request, response: Response) -> dict:
        data = await body(request)
        token, user, csrf = service.login(str(data.get("username", "")), str(data.get("password", "")))
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict",
                            max_age=service.config["session_minutes"] * 60)
        return {"user": user, "csrf": csrf}

    @app.get("/api/auth/me")
    def me(request: Request) -> dict:
        user, csrf = service.session(request.cookies.get(COOKIE))
        return {"user": service.public_user(user), "csrf": csrf}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, user: dict = Depends(current)) -> dict:
        service.storage.drop_session(request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.post("/api/auth/password")
    async def password(request: Request, user: dict = Depends(current)) -> dict:
        data = await body(request)
        service.change_password(user, str(data.get("current_password") or data.get("current") or ""),
                                str(data.get("new_password") or data.get("new") or ""))
        return {"ok": True}

    @app.get("/api/bootstrap")
    def bootstrap(user: dict = Depends(current)) -> dict:
        return service.bootstrap(user)

    @app.get("/api/catalog")
    def catalog(user: dict = Depends(current)) -> dict:
        return service.catalog()

    # ------------------------------------------------------- conversaciones
    @app.get("/api/conversations/page")
    def conversations_page(q: str = "", architecture: str = "", status: str = "", page: int = 1,
                           page_size: int = 20, user: dict = Depends(current)) -> dict:
        return service.list_conversations(user, q, architecture, status, page, min(page_size, 100))

    @app.get("/api/conversations")
    def conversations(user: dict = Depends(current)) -> list[dict]:
        return service.list_conversations(user, page_size=100)["items"]

    @app.post("/api/conversations", status_code=201)
    async def create(request: Request, user: dict = Depends(current)) -> dict:
        return service.create_conversation(user, await body(request))

    @app.get("/api/conversations/{identifier}")
    def conversation(identifier: str, user: dict = Depends(current)) -> dict:
        return service.view(service.conversation(user, identifier))

    @app.get("/api/conversations/{identifier}/export")
    def export(identifier: str, user: dict = Depends(current)) -> dict:
        return service.export_conversation(user, identifier)

    @app.post("/api/conversations/{identifier}/turns", status_code=202)
    async def turn(identifier: str, request: Request, user: dict = Depends(current)) -> dict:
        return service.post_turn(user, identifier, await body(request))

    @app.put("/api/conversations/{identifier}/preferences")
    async def preferences(identifier: str, request: Request, user: dict = Depends(current)) -> dict:
        return service.update_preferences(user, identifier, await body(request))

    @app.post("/api/conversations/{identifier}/preference-proposal/{decision}")
    async def preference_decision(identifier: str, decision: str, request: Request,
                                  user: dict = Depends(current)) -> dict:
        if decision not in ("confirm", "reject"):
            raise PortalError(404, "Acción no válida.")
        return service.decide_preference_proposal(user, identifier, await body(request), decision == "confirm")

    @app.post("/api/conversations/{identifier}/archive")
    def archive(identifier: str, user: dict = Depends(current)) -> dict:
        return service.archive(user, identifier)

    @app.get("/api/jobs/{identifier}")
    def job(identifier: str, user: dict = Depends(current)) -> dict:
        return service.job(user, identifier)

    # ---------------------------------------------------------------- datos
    @app.get("/api/resources")
    def resources(user: dict = Depends(staff)) -> dict:
        return service.resources()

    @app.get("/api/fhir/export")
    def fhir_export(user: dict = Depends(staff)) -> dict:
        return service.fhir_bundle()

    @app.get("/api/profiles/{subject}")
    def profile(subject: str, user: dict = Depends(current)) -> dict:
        if user["role"] == "patient" and user["subject_id"] != subject:
            raise PortalError(404, "Perfil no encontrado.")
        return service.profile(subject)

    @app.put("/api/profiles/{subject}")
    async def update_profile(subject: str, request: Request, user: dict = Depends(staff)) -> dict:
        return service.update_profile(user, subject, await body(request))

    @app.post("/api/slots")
    async def create_slot(request: Request, user: dict = Depends(staff)) -> dict:
        return service.save_slot(user, await body(request))

    @app.put("/api/slots/{identifier}")
    async def update_slot(identifier: str, request: Request, user: dict = Depends(staff)) -> dict:
        return service.save_slot(user, await body(request), identifier)

    @app.post("/api/appointments/{identifier}")
    async def appointment(identifier: str, request: Request, user: dict = Depends(staff)) -> dict:
        return service.appointment_action(user, identifier, await body(request))

    @app.get("/api/snapshots")
    def snapshots(user: dict = Depends(staff)) -> list[dict]:
        return service.snapshots()

    @app.post("/api/snapshots")
    async def create_snapshot(request: Request, user: dict = Depends(staff)) -> dict:
        return service.create_snapshot(user, await body(request))

    @app.post("/api/snapshots/{identifier}/restore")
    def restore_snapshot(identifier: str, user: dict = Depends(staff)) -> dict:
        return service.restore_snapshot(user, identifier)

    @app.post("/api/demo/reset")
    def reset_demo(user: dict = Depends(admin)) -> dict:
        return service.reset_demo(user)

    # ------------------------------------------------------------ administración
    def prompt_history() -> list[dict]:
        return service.storage.get("prompt_history", [])

    def active_prompts() -> list[dict]:
        history = prompt_history()
        result = []
        for role, base in prompts.DEFAULTS.items():
            versions = [h for h in history if h["role"] == role]
            latest = versions[-1] if versions else None
            result.append({"role": role, "version": latest["version"] if latest else 1,
                           "instruction": prompts.prompt(role), "base_prompt": base,
                           "base_hash": prompts.VERSION, "at": latest["at"] if latest else None,
                           "reason": latest["reason"] if latest else "Versión inicial v3"})
        return result

    @app.get("/api/admin/prompts")
    def get_prompts(user: dict = Depends(staff)) -> dict:
        return {"active": active_prompts(), "history": prompt_history()[::-1]}

    @app.put("/api/admin/prompts")
    async def put_prompts(request: Request, user: dict = Depends(admin)) -> dict:
        from datetime import UTC, datetime
        data = await body(request)
        role, instruction = data.get("role"), str(data.get("instruction") or "").strip()
        if role not in prompts.DEFAULTS or len(instruction) < 20:
            raise PortalError(400, "Instrucción no válida.")
        current = next(p for p in active_prompts() if p["role"] == role)
        if data.get("expected_version") not in (None, current["version"]):
            raise PortalError(409, "La instrucción ha cambiado; recarga antes de publicar.")
        overrides = {p["role"]: p["instruction"] for p in active_prompts()}
        overrides[role] = instruction
        prompts.save_overrides(overrides)
        history = prompt_history()
        history.append({"role": role, "version": current["version"] + 1, "instruction": instruction,
                        "base_prompt": prompts.DEFAULTS[role], "base_hash": prompts.VERSION,
                        "at": datetime.now(UTC).isoformat(), "reason": str(data.get("reason") or "")[:500]})
        service.storage.put("prompt_history", history)
        service.storage.audit(user["username"], "prompt-publish", {"role": role})
        return get_prompts(user)

    @app.put("/api/admin/config")
    async def put_config(request: Request, user: dict = Depends(admin)) -> dict:
        return service.update_config(user, await body(request))

    @app.get("/api/admin/accounts")
    def accounts(user: dict = Depends(admin)) -> list[dict]:
        return service.accounts()

    @app.post("/api/admin/accounts/{username}/reset-password")
    def reset_password(username: str, user: dict = Depends(admin)) -> dict:
        return {"username": username, "one_time_display_password": service.reset_password(user, username)}

    @app.get("/api/admin/audit")
    def audit(user: dict = Depends(admin)) -> list[dict]:
        return service.storage.audit_rows()

    @app.get("/api/admin/retention")
    def retention(user: dict = Depends(admin)) -> dict:
        return service.retention_status()

    @app.post("/api/admin/retention")
    def purge(user: dict = Depends(admin)) -> dict:
        return service.purge_expired(user["username"])

    @app.get("/api/admin/observability")
    def observability(user: dict = Depends(staff)) -> dict:
        return service.observability()

    @app.post("/api/admin/providers/{provider}/check")
    def provider_check(provider: str, user: dict = Depends(admin)) -> dict:
        return service.provider_check(provider)

    @app.get("/api/architecture")
    def architectures(user: dict = Depends(current)) -> list[dict]:
        return list(ARCHITECTURES.values())

    @app.get("/api/architecture/{identifier}")
    def architecture(identifier: str, user: dict = Depends(current)) -> dict:
        if identifier not in ARCHITECTURES:
            raise PortalError(404, "Arquitectura no encontrada.")
        return ARCHITECTURES[identifier]

    # ------------------------------------------------------------- evaluación
    @app.get("/api/evaluation/campaigns")
    def campaigns(user: dict = Depends(staff)) -> list[dict]:
        root = OUTPUT / "evaluation"
        items = []
        for folder in sorted(root.glob("*/")) if root.exists() else []:
            results = folder / "results.jsonl"
            if results.exists():
                lines = [ln for ln in results.read_text(encoding="utf-8").splitlines() if ln.strip()]
                manifest = folder / "manifest.json"
                items.append({"id": folder.name, "episodes": len(lines),
                              "manifest": json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}})
        return items

    @app.get("/api/evaluation/campaigns/{campaign}")
    def campaign(campaign: str, user: dict = Depends(staff)) -> dict:
        from citalab.evaluation.analysis import _dependency_groups, load, summarize
        folder = OUTPUT / "evaluation" / campaign
        if not (folder / "results.jsonl").exists():
            raise PortalError(404, "Campaña no encontrada.")
        rows = load(campaign)
        summary = summarize(rows, _dependency_groups(campaign))
        episodes = [{k: r.get(k) for k in ("cell_id", "provider", "architecture", "unit_id", "operation", "block",
                                           "status", "success", "goal", "safety", "user_turns", "assistant_calls",
                                           "fallback_count", "end_reason")} for r in rows]
        return {"id": campaign, "summary": summary, "episodes": episodes}

    @app.get("/api/evaluation/campaigns/{campaign}/episodes/{cell_id}")
    def episode(campaign: str, cell_id: str, user: dict = Depends(staff)) -> dict:
        from citalab.evaluation.analysis import load
        for row in load(campaign):
            if row["cell_id"] == cell_id:
                return row
        raise PortalError(404, "Episodio no encontrado.")

    from citalab.evaluation.review import register_review_routes
    register_review_routes(app, staff, body)

    # --------------------------------------------------------- interfaz web
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise PortalError(404, "Ruta no encontrada.")
        target = (DIST / path).resolve()
        if path and target.is_file() and DIST.resolve() in target.parents:
            return FileResponse(target)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Interfaz no compilada: ejecuta `pnpm build` en web/."}, status_code=503)

    return app


def main() -> None:
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8765, log_level="warning")


if __name__ == "__main__":
    main()


__all__ = ["create_app", "main", "Path"]
