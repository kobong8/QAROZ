from __future__ import annotations

import json
import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from qa_manager.core.security import validate_http_url
from qa_manager.runners.zap_runner import ZapRunner
from qa_manager.runners.trivy_runner import TrivyRunner
from qa_manager.services.scenario_recorder import validate_wait
from qa_manager.services.regression_service import regression_fields

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
        if step["action"] == "wait":
            try:
                normalized = validate_wait(step)
                step.update(normalized)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
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
        **validate_regression(payload),
    }
    state(request).db.insert("scenarios", data)
    return state(request).db.fetchone(
        "SELECT * FROM scenarios WHERE id=?", (data["id"],)
    )


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(request: Request, scenario_id: str):
    state(request).db.execute("DELETE FROM scenarios WHERE id=?", (scenario_id,))


RECIPE_VERSION = 1
API_RECIPE_FIELDS = (
    "name", "method", "url", "headers", "query", "body", "expected_status",
    "assertions", "max_response_ms", "enabled",
)
SCENARIO_RECIPE_FIELDS = (
    "name", "runner_ref", "steps", "expected", "enabled", "tags",
    "regression_enabled", "group", "order",
)


def validate_regression(payload):
    try:
        return regression_fields(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/scenarios/{scenario_id}")
def update_scenario_metadata(request: Request, scenario_id: str, payload: dict[str, Any] = Body(...)):
    db = state(request).db
    current = db.fetchone("SELECT * FROM scenarios WHERE id=?", (scenario_id,))
    if not current:
        raise HTTPException(404, "Scenario not found")
    if set(payload) - {"regression_enabled", "group", "order", "enabled"}:
        raise HTTPException(422, "Only scenario selection metadata can be updated")
    values = validate_regression({**current, **payload})
    enabled = payload.get("enabled", current["enabled"])
    if type(enabled) is not bool:
        raise HTTPException(422, "enabled must be a boolean")
    db.execute('UPDATE scenarios SET regression_enabled=?, "group"=?, "order"=?, enabled=? WHERE id=?',
               (values["regression_enabled"], values["group"], values["order"], enabled, scenario_id))
    return db.fetchone("SELECT * FROM scenarios WHERE id=?", (scenario_id,))


@router.get("/projects/{project_id}/recipe")
def export_recipe(request: Request, project_id: str):
    project_value = state(request).projects.get(project_id)
    if not project_value:
        raise HTTPException(404, "Project not found")
    cases = api_tests(request, project_id)
    scenario_values = scenarios(request, project_id)
    recipe = {
        "format": "qaroz-recipe",
        "version": RECIPE_VERSION,
        "name": project_value["name"],
        "api_tests": [
            {key: item.get(key) for key in API_RECIPE_FIELDS} for item in cases
        ],
        "scenarios": [
            {key: item.get(key) for key in SCENARIO_RECIPE_FIELDS}
            for item in scenario_values
        ],
    }
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_value["name"])
    return JSONResponse(
        recipe,
        headers={"Content-Disposition": (
            'attachment; filename="project.qaroz.json"; '
            f"filename*=UTF-8''{quote((safe_name or 'project') + '.qaroz.json')}"
        )},
    )


@router.post("/projects/{project_id}/recipe")
def import_recipe(
    request: Request, project_id: str, payload: dict[str, Any] = Body(...)
):
    if not state(request).projects.get(project_id):
        raise HTTPException(404, "Project not found")
    if payload.get("format") != "qaroz-recipe" or payload.get("version") != RECIPE_VERSION:
        raise HTTPException(422, "Unsupported QAROZ recipe format or version")
    cases, scenario_values = payload.get("api_tests"), payload.get("scenarios")
    if not isinstance(cases, list) or not isinstance(scenario_values, list):
        raise HTTPException(422, "api_tests and scenarios must be arrays")
    if len(cases) + len(scenario_values) > 1000:
        raise HTTPException(422, "A recipe may contain at most 1000 items")

    # Reuse the public validators before changing the database, so malformed recipes
    # cannot result in a partially imported instruction set.
    normalized_cases: list[dict[str, Any]] = []
    normalized_scenarios: list[dict[str, Any]] = []
    for item in cases:
        if not isinstance(item, dict):
            raise HTTPException(422, "Each API recipe item must be an object")
        try:
            validate_http_url(item["url"])
            expected_status = int(item.get("expected_status", 200))
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(422, f"Invalid API recipe item: {exc}") from exc
        if not 100 <= expected_status <= 599 or not isinstance(item.get("assertions", {}), dict):
            raise HTTPException(422, "Invalid API expected_status or assertions")
        if not isinstance(item.get("headers", {}), dict) or not isinstance(item.get("query", {}), dict):
            raise HTTPException(422, "API headers and query must be objects")
        normalized_cases.append({
            "id": str(uuid.uuid4()), "project_id": project_id,
            **{key: item.get(key) for key in API_RECIPE_FIELDS},
            "name": item.get("name", "API test"), "method": item.get("method", "GET").upper(),
            "headers": item.get("headers", {}), "query": item.get("query", {}),
            "expected_status": expected_status, "assertions": item.get("assertions", {}),
            "enabled": bool(item.get("enabled", True)),
        })
    permitted = {"goto", "click", "fill", "select", "upload", "wait"}
    for item in scenario_values:
        if not isinstance(item, dict):
            raise HTTPException(422, "Each scenario recipe item must be an object")
        steps, expected = item.get("steps"), item.get("expected")
        if not isinstance(steps, list) or not steps or not isinstance(expected, list) or not expected:
            raise HTTPException(422, "Recipe scenarios require non-empty steps and expected arrays")
        if any(not isinstance(step, dict) or step.get("action") not in permitted for step in steps):
            raise HTTPException(422, "Unsupported scenario action in recipe")
        for step in steps:
            required = "url" if step["action"] == "goto" else "selector"
            if not isinstance(step.get(required), str) or not step[required].strip():
                raise HTTPException(422, f"Recipe scenario step requires {required}")
            if step["action"] == "select" and "value" not in step:
                raise HTTPException(422, "Recipe select action requires value")
            if step["action"] == "upload" and not step.get("path"):
                raise HTTPException(422, "Recipe upload action requires path")
            if step["action"] == "wait":
                try:
                    step.update(validate_wait(step))
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
        for expected_item in expected:
            if not isinstance(expected_item, dict) or expected_item.get("type", "visible") not in {"visible", "text", "count"} or not expected_item.get("selector"):
                raise HTTPException(422, "Recipe expectations require a selector and visible/text/count type")
            if expected_item.get("type") in {"text", "count"} and "value" not in expected_item:
                raise HTTPException(422, "Recipe text/count expectations require value")
        normalized_scenarios.append({
            "id": str(uuid.uuid4()), "project_id": project_id,
            **{key: item.get(key) for key in SCENARIO_RECIPE_FIELDS},
            "name": item.get("name", "Scenario"), "enabled": bool(item.get("enabled", True)),
            "tags": item.get("tags", []),
            **validate_regression(item),
        })
    for item in normalized_cases:
        state(request).db.insert("api_test_cases", item)
    for item in normalized_scenarios:
        state(request).db.insert("scenarios", item)
    return {"api_tests": len(normalized_cases), "scenarios": len(normalized_scenarios)}


@router.post("/projects/{project_id}/recordings", status_code=201)
def start_recording(request: Request, project_id: str):
    project_value = state(request).projects.get(project_id)
    if not project_value:
        raise HTTPException(404, "Project not found")
    return state(request).recorder.start(project_id, project_value["frontend_url"])


@router.get("/recordings/{recording_id}")
def recording(request: Request, recording_id: str):
    result = state(request).recorder.get(recording_id)
    if not result:
        raise HTTPException(404, "Recording not found")
    return result


@router.post("/recordings/{recording_id}/commands")
def recording_command(request: Request, recording_id: str, payload: dict[str, Any] = Body(...)):
    try:
        result = state(request).recorder.command(recording_id, payload.get("command", ""), payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not result:
        raise HTTPException(404, "Recording not found")
    return result


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
    options = options or {}
    if set(options) - {"active", "group", "scenario_ids", "api_case_ids"}:
        raise HTTPException(422, "Unsupported run option")
    if "active" in options and (type(options["active"]) is not bool or suite != "zap"):
        raise HTTPException(422, "active is a boolean supported only for explicit ZAP runs")
    if "group" in options and options["group"] is not None and not isinstance(options["group"], str):
        raise HTTPException(422, "group must be a string or null")
    for key in ("scenario_ids", "api_case_ids"):
        if key in options and (not isinstance(options[key], list) or any(not isinstance(item, str) for item in options[key])):
            raise HTTPException(422, f"{key} must be an array of IDs")
    try:
        return state(request).runs.submit(project_value, suite, options)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/projects/{project_id}/runs")
def runs(request: Request, project_id: str):
    return state(request).runs.list(project_id)


@router.delete("/projects/{project_id}/runs")
def clear_run_history(request: Request, project_id: str):
    if not state(request).projects.get(project_id):
        raise HTTPException(404, "Project not found")
    return {"deleted": state(request).runs.clear_history(project_id)}


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


@router.post("/runs/{run_id}/retry-failed", status_code=202)
def retry_failed(request: Request, run_id: str, payload: dict[str, Any] | None = Body(default=None)):
    previous = state(request).runs.get(run_id)
    if not previous:
        raise HTTPException(404, "Run not found")
    if previous["status"] in {"RUNNING", "QUEUED"}:
        raise HTTPException(409, "Wait for the run to finish before retrying")
    project_value = state(request).projects.get(previous["project_id"])
    if not project_value or not project_value["enabled"]:
        raise HTTPException(409, "Project is unavailable or disabled")
    enabled_ids = {
        "api": {item["id"] for item in state(request).db.fetchall(
            "SELECT id FROM api_test_cases WHERE project_id=? AND enabled=1",
            (project_value["id"],),
        )},
        "e2e": {item["id"] for item in state(request).db.fetchall(
            "SELECT id FROM scenarios WHERE project_id=? AND enabled=1",
            (project_value["id"],),
        )},
    }
    failed = [
        item for item in state(request).runs.results(run_id)
        if item["status"] in {"FAIL", "ERROR"} and item["category"] in {"api", "e2e"}
        and item.get("source_id") in enabled_ids[item["category"]]
    ]
    if previous["suite"] == "regression":
        regression_ids = {row["id"] for row in state(request).db.fetchall(
            "SELECT id FROM scenarios WHERE project_id=? AND regression_enabled=1",
            (project_value["id"],),
        )}
        failed = [item for item in failed if item["source_id"] in regression_ids]
    if payload and "scenario_id" in payload:
        failed = [item for item in failed if item["category"] == "e2e" and item["source_id"] == payload["scenario_id"]]
    if not failed:
        raise HTTPException(409, "No retryable failed API or E2E items")
    categories = {item["category"] for item in failed}
    suite = "regression" if previous["suite"] == "regression" else next(iter(categories)) if len(categories) == 1 else "all"
    options = {
        "api_case_ids": [item["source_id"] for item in failed if item["category"] == "api"],
        "scenario_ids": [item["source_id"] for item in failed if item["category"] == "e2e"],
        "retry_of": run_id,
        "retry_categories": ["regression"] if suite == "regression" else sorted(categories),
    }
    try:
        return state(request).runs.submit(project_value, suite, options, trigger=f"retry:{run_id}")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    allowed = {"zap_api_url", "zap_executable", "allowed_active_hosts", "security_enabled", "trivy_executable"}
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
        if key == "trivy_executable" and not isinstance(value, str):
            raise HTTPException(422, "trivy_executable must be a path string or empty string")
        if key == "trivy_executable" and value:
            try:
                TrivyRunner.executable(value)
            except (ValueError, TypeError, OSError) as exc:
                raise HTTPException(422, "Select an existing local Trivy executable") from exc
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


@router.get("/system/trivy/status")
def trivy_status(request: Request):
    return TrivyRunner().status(settings(request).get("trivy_executable"))


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
