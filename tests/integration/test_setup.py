from pathlib import Path

from fastapi.testclient import TestClient

from qa_manager.core.config import Settings
from qa_manager.core.models import RunnerResult, Status
from qa_manager.main import create_app
from qa_manager.runners.zap_runner import ZapRunner


def test_optional_security_and_explicit_scan(tmp_path: Path, monkeypatch):
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db")
    calls = []
    def scan(self, *args, **kwargs):
        calls.append(args)
        return RunnerResult("security", "ZAP", Status.ERROR, message="ZAP unavailable"), []
    monkeypatch.setattr(ZapRunner, "run", scan)
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Example", "frontend_url": "http://localhost:5173"}).json()
        service = client.app.state.runs
        assert client.get("/api/settings").json()["security_enabled"] == "false"
        assert service._run_category("security", "unused", project, {})[0].status == Status.SKIPPED
        assert not calls
        assert service._run_category("security", "unused", project, {"security_requested": True})[0].status == Status.ERROR
        assert len(calls) == 1
        assert client.put("/api/settings", json={"security_enabled": True}).json()["security_enabled"] == "true"
        assert service._run_category("security", "unused", project, {})[0].status == Status.ERROR
        assert len(calls) == 2
        assert client.put("/api/settings", json={"zap_api_url": "https://remote.example"}).status_code == 422


def test_scenario_registration_requires_executable_checks(tmp_path: Path):
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Example", "frontend_url": "http://localhost:5173"}).json()
        endpoint = f"/api/projects/{project['id']}/scenarios"
        assert client.post(endpoint, json={"name": "Empty"}).status_code == 422
        assert client.post(endpoint, json={"steps": ["bad"], "expected": [{}]}).status_code == 422
        good = {"name": "Page smoke", "steps": [{"action": "goto", "url": "/"}], "expected": [{"type": "visible", "selector": "body"}]}
        assert client.post(endpoint, json=good).status_code == 201
        assert client.get(endpoint).json()[0]["name"] == "Page smoke"
        good["expected"][0]["type"] = "unknown"
        assert client.post(endpoint, json=good).status_code == 422
