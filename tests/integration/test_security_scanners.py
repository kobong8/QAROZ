import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_manager.core.config import Settings
from qa_manager.core.models import RunnerResult, Status
from qa_manager.main import create_app
from qa_manager.runners.trivy_runner import TrivyRunner
from qa_manager.runners.zap_runner import ZapRunner


@pytest.mark.parametrize("zap,trivy", [(False, False), (True, False), (False, True), (True, True)])
def test_security_scanners_are_independent(tmp_path, monkeypatch, zap, trivy):
    calls = []
    def zap_scan(self, *args, **kwargs):
        calls.append(("zap", kwargs["active"]))
        return RunnerResult("security", "ZAP", Status.PASS), []
    def trivy_scan(self, *args, **kwargs):
        calls.append(("trivy", False))
        return RunnerResult("security", "Trivy", Status.WARNING)
    monkeypatch.setattr(ZapRunner, "run", zap_scan)
    monkeypatch.setattr(TrivyRunner, "run", trivy_scan)
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d/db")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Task Board", "frontend_url": "http://localhost:5173",
                              "project_path": str(tmp_path), "zap_enabled": zap, "trivy_enabled": trivy}).json()
        service = client.app.state.runs
        results = service._run_category("security", "test-run", project, {})
        assert len(results) == 2
        assert results[0].status == (Status.PASS if zap else Status.SKIPPED)
        assert results[1].status == (Status.WARNING if trivy else Status.SKIPPED)
        assert calls == ([('zap', False)] if zap else []) + ([('trivy', False)] if trivy else [])
        calls.clear()
        service._run_category("trivy", "test-run", project, {})
        assert calls == ([('trivy', False)] if trivy else [])
        calls.clear()
        service._run_category("zap", "test-run", project, {"active": True})
        assert calls == ([('zap', True)] if zap else [])
        assert client.post(f"/api/projects/{project['id']}/run/all", json={"active": True}).status_code == 422
        assert client.post(f"/api/projects/{project['id']}/run/trivy", json={"target": "C:/"}).status_code == 422


def test_trivy_report_persistence_and_download_are_sanitized(tmp_path, monkeypatch):
    from types import SimpleNamespace
    report = (Path(__file__).parents[1] / "fixtures/trivy_report.json").read_text(encoding="utf-8")
    monkeypatch.setattr(TrivyRunner, "executable", lambda *a: "trivy.exe")
    monkeypatch.setattr(TrivyRunner, "execute", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=report))
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d/db")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Task Board", "frontend_url": "http://localhost:5173",
                              "project_path": str(tmp_path), "trivy_enabled": True}).json()
        db = client.app.state.db
        run_id = db.insert("test_runs", {"project_id": project["id"], "suite": "trivy", "trigger": "manual",
                                      "started_at": "2026-01-01", "status": "QUEUED"})
        client.app.state.runs._execute(run_id, project, "trivy", {})
        result = client.get(f"/api/runs/{run_id}").json()
        assert result["status"] == "WARNING"
        assert "SYNTHETIC_SECRET_VALUE" not in json.dumps(result)
        artifact = result["results"][0]["artifacts"][0]["id"]
        assert "SYNTHETIC_SECRET_VALUE" not in client.get(f"/api/artifacts/{artifact}").text
        assert b"SYNTHETIC_SECRET_VALUE" not in settings.database_path.read_bytes()


def test_run_all_uses_security_settings_and_continues_after_scanner_error(tmp_path, monkeypatch):
    from qa_manager.runners.system_runner import SystemRunner
    monkeypatch.setattr(SystemRunner, "run", lambda *a: [RunnerResult("system", "System", Status.PASS)])
    monkeypatch.setattr(ZapRunner, "run", lambda *a, **kw: (RunnerResult("security", "ZAP", Status.ERROR), []))
    monkeypatch.setattr(TrivyRunner, "run", lambda *a, **kw: RunnerResult("security", "Trivy", Status.PASS))
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d/db")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Task Board", "frontend_url": "http://localhost:5173",
                              "zap_enabled": True, "trivy_enabled": True}).json()
        db = client.app.state.db
        run_id = db.insert("test_runs", {"project_id": project["id"], "suite": "all", "trigger": "manual",
                                      "started_at": "2026-01-01", "status": "QUEUED"})
        client.app.state.runs._execute(run_id, project, "all", {})
        result = client.get(f"/api/runs/{run_id}").json()
        assert result["status"] == "ERROR"
        assert [item["status"] for item in result["results"]] == ['PASS', 'SKIPPED', 'SKIPPED', 'ERROR', 'PASS']
