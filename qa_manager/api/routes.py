from __future__ import annotations

import json
import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse

from qa_manager.core.security import validate_http_url
from qa_manager.runners.zap_runner import ZapRunner

router = APIRouter(prefix="/api")


def state(request: Request):
    return request.app.state


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "QAROZ"}


@router.get("/projects")
def projects(request: Request):
    return state(request).projects.list()


@router.post("/projects", status_code=201)
def create_project(request: Request, payload: dict[str, Any] = Body(...)):
    try:
        return state(request).projects.create(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/projects/{project_id}")
def project(request: Request, project_id: str):
    result = state(request).projects.get(project_id)
    if not result:
        raise HTTPException(404, "Project not found")
    return result


@router.put("/projects/{project_id}")
def update_project(
    request: Request, project_id: str, payload: dict[str, Any] = Body(...)
):
    try:
        result = state(request).projects.update(project_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not result:
        raise HTTPException(404, "Project not found")
    return result


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(request: Request, project_id: str):
    if not state(request).projects.delete(project_id):
        raise HTTPException(404, "Project not found")


@router.get("/projects/{project_id}/api-tests")
def api_tests(request: Request, project_id: str):
    return state(request).db.fetchall(
        "SELECT * FROM api_test_cases WHERE project_id=? ORDER BY rowid", (project_id,)
    )


@router.post("/projects/{project_id}/api-tests", status_code=201)
def create_api_test(
    request: Request, project_id: str, payload: dict[str, Any] = Body(...)
):
    if not state(request).projects.get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        validate_http_url(payload["url"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if not isinstance(payload.get("assertions", {}), dict):
        raise HTTPException(422, "assertions must be a JSON object")
    try:
        expected_status = int(payload.get("expected_status", 200))
        if not 100 <= expected_status <= 599:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(422, "expected_status must be between 100 and 599")
    data = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "name": payload.get("name", "API test"),
        "method": payload.get("method", "GET").upper(),
        "url": payload["url"],
        "headers": payload.get("headers", {}),
        "query": payload.get("query", {}),
        "body": payload.get("body"),
        "expected_status": expected_status,
        "assertions": payload.get("assertions", {}),
        "max_response_ms": payload.get("max_response_ms"),
        "enabled": bool(payload.get("enabled", True)),
    }
    state(request).db.insert("api_test_cases", data)
    return state(request).db.fetchone(
        "SELECT * FROM api_test_cases WHERE id=?", (data["id"],)
    )


@router.delete("/api-tests/{case_id}", status_code=204)
def delete_api_test(request: Request, case_id: str):
    state(request).db.execute("DELETE FROM api_test_cases WHERE id=?", (case_id,))


@router.get("/projects/{project_id}/scenarios")
def scenarios(request: Request, project_id: str):
    return state(request).db.fetchall(
        "SELECT * FROM scenarios WHERE project_id=? ORDER BY rowid", (project_id,)
    )


@router.post("/projects/{project_id}/scenarios", status_code=201)
def create_scenario(
    request: Request, project_id: str, payload: dict[str, Any] = Body(...)
):
    if not state(request).projects.get(project_id):
        raise HTTPException(404, "Project not found")
    permitted = {"goto", "click", "fill", "select", "upload", "wait"}
    steps, expected = payload.get("steps"), payload.get("expected")
    if not isinstance(steps, list) or not steps or not isinstance(expected, list) or not expected:
        raise HTTPException(422, "A scenario requires non-empty steps and expected arrays")
    if any(not isinstance(step, dict) or step.get("action") not in permitted for step in steps):
        raise HTTPException(422, "Unsupported scenario action")
    for step in steps:
        required = "url" if step["action"] == "goto" else "selector"
        if not isinstance(step.get(required), str) or not step[required].strip():
            raise HTTPException(422, f"Scenario step requires {required}")
        if step["action"] == "select" and "value" not in step:
            raise HTTPException(422, "select requires value")
        if step["action"] == "upload" and not step.get("path"):
            raise HTTPException(422, "upload requires path")
    for item in expected:
        if not isinstance(item, dict) or item.get("type", "visible") not in {"visible", "text", "count"} or not item.get("selector"):
            raise HTTPException(422, "Expected results require a selector and visible/text/count type")
        if item.get("type") in {"text", "count"} and "value" not in item:
            raise HTTPException(422, "text/count expectations require value")
    data = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "name": payload.get("name", "Scenario"),
        "runner_ref": payload.get("runner_ref"),
        "steps": payload.get("steps", []),
        "expected": payload.get("expected", []),
        "enabled": bool(payload.get("enabled", True)),
        "tags": payload.get("tags", []),
    }
    state(request).db.insert("scenarios", data)
    return state(request).db.fetchone(
        "SELECT * FROM scenarios WHERE id=?", (data["id"],)
    )


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(request: Request, scenario_id: str):
    state(request).db.execute("DELETE FROM scenarios WHERE id=?", (scenario_id,))


@router.post("/projects/{project_id}/run/{suite}", status_code=202)
def run(
    request: Request,
    project_id: str,
    suite: str,
    options: dict[str, Any] | None = Body(default=None),
):
    project_value = state(request).projects.get(project_id)
    if not project_value:
        raise HTTPException(404, "Project not found")
    if not project_value["enabled"]:
        raise HTTPException(409, "Project is disabled")
    try:
        return state(request).runs.submit(project_value, suite, options)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/projects/{project_id}/runs")
def runs(request: Request, project_id: str):
    return state(request).runs.list(project_id)


@router.get("/runs/{run_id}")
def run_detail(request: Request, run_id: str):
    value = state(request).runs.get(run_id)
    if not value:
        raise HTTPException(404, "Run not found")
    value["results"] = state(request).runs.results(run_id)
    value["alerts"] = state(request).db.fetchall(
        "SELECT * FROM zap_alerts WHERE run_id=?", (run_id,)
    )
    return value


@router.get("/runs/{run_id}/results")
def results(request: Request, run_id: str):
    return state(request).runs.results(run_id)


@router.get("/artifacts/{artifact_id}")
def artifact(request: Request, artifact_id: str):
    record = state(request).db.fetchone(
        "SELECT * FROM artifacts WHERE id=?", (artifact_id,)
    )
    if not record:
        raise HTTPException(404, "Artifact not found")
    try:
        path = state(request).artifacts.resolve(record["local_path"])
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    return FileResponse(path, filename=path.name)


@router.get("/settings")
def settings(request: Request):
    values = {
        row["key"]: row["value"]
        for row in state(request).db.fetchall("SELECT * FROM settings")
    }
    values.setdefault("zap_api_url", "http://127.0.0.1:8090")
    values.setdefault("allowed_active_hosts", "[]")
    values.setdefault("security_enabled", "false")
    return values


@router.put("/settings")
def update_settings(request: Request, payload: dict[str, Any] = Body(...)):
    allowed = {"zap_api_url", "zap_executable", "allowed_active_hosts", "security_enabled"}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "zap_api_url":
            try:
                validate_http_url(str(value), allow_remote=False)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        if key == "security_enabled":
            if value not in (True, False, "true", "false"):
                raise HTTPException(422, "security_enabled must be true or false")
            value = "true" if value is True or value == "true" else "false"
        if key == "zap_executable" and value and not Path(value).expanduser().is_file():
            raise HTTPException(422, "ZAP executable does not exist")
        serialized = json.dumps(value) if isinstance(value, list) else str(value)
        state(request).db.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, serialized),
        )
    return settings(request)


@router.get("/system/zap/status")
def zap_status(request: Request):
    config = settings(request)
    return ZapRunner().status(config["zap_api_url"])


@router.get("/system/readiness")
def readiness(request: Request):
    packages = {name: importlib.util.find_spec(name) is not None for name in ("psutil", "playwright")}
    chromium = False
    browser_message = "Playwright package is not installed"
    if packages["playwright"]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                chromium = Path(playwright.chromium.executable_path).is_file()
            browser_message = "Chromium installed" if chromium else "Run: python -m playwright install chromium"
        except Exception as exc:
            browser_message = f"Playwright check failed: {type(exc).__name__}"
    return {
        "python": sys.executable, "packages": packages, "chromium": chromium,
        "browser_message": browser_message, "zap": zap_status(request),
        "security_enabled": settings(request)["security_enabled"] == "true",
    }
