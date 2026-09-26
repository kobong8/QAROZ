import time

import pytest
from fastapi.testclient import TestClient

from qa_manager.core.config import Settings
from qa_manager.core.models import RunnerResult, Status
from qa_manager.main import create_app
from qa_manager.runners.playwright_runner import PlaywrightRunner


def wait_run(client, run_id):
    for _ in range(200):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] not in {"RUNNING", "QUEUED"}:
            return run
        time.sleep(0.01)
    raise AssertionError("Run did not finish")


@pytest.mark.parametrize("statuses,expected", [
    ([Status.PASS, Status.PASS], "PASS"),
    ([Status.PASS, Status.FAIL], "FAIL"),
    ([Status.WARNING, Status.PASS], "WARNING"),
    ([Status.FAIL, Status.ERROR], "ERROR"),
])
def test_regression_selection_history_retry_and_evidence(tmp_path, monkeypatch, statuses, expected):
    calls = []
    def run(self, scenario, artifact_dir, *args):
        calls.append(scenario["name"])
        artifact = artifact_dir / f"{scenario['id']}.png"
        artifact.write_bytes(b"evidence")
        return RunnerResult("e2e", scenario["name"], statuses[scenario["order"]],
                            message="same runner", artifacts=[{"type": "screenshot", "local_path": str(artifact), "metadata": {}}])
    monkeypatch.setattr(PlaywrightRunner, "run", run)
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d/db")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Task Board", "frontend_url": "http://localhost:5173"}).json()
        root = f"/api/projects/{project['id']}"
        base = {"steps": [{"action": "goto", "url": "/"}], "expected": [{"type": "visible", "selector": "body"}]}
        second = client.post(root + "/scenarios", json={**base, "name": "Second", "order": 1, "group": "Tasks"}).json()
        first = client.post(root + "/scenarios", json={**base, "name": "First", "group": "Auth"}).json()
        assert first["regression_enabled"] is True
        client.post(root + "/scenarios", json={**base, "name": "Excluded", "regression_enabled": False})
        client.post(root + "/scenarios", json={**base, "name": "Disabled", "enabled": False})
        result = client.post(root + "/run/regression", json={})
        assert result.status_code == 202
        run_id = result.json()["id"]
        completed = wait_run(client, run_id)
        assert completed["status"] == expected
        assert calls == ["First", "Second"]
        assert completed["results"][1]["source_id"] == second["id"]
        assert completed["results"][0]["details"]["group"] == "Auth"
        artifact_id = completed["results"][0]["artifacts"][0]["id"]
        assert client.get(f"/api/artifacts/{artifact_id}").content == b"evidence"
        assert client.get(root + "/runs").json()[0]["summary"][statuses[0].value] >= 1
        calls.clear()
        retry = client.post(f"/api/runs/{run_id}/retry-failed")
        failed = [name for name, status in zip(["First", "Second"], statuses) if status in {Status.FAIL, Status.ERROR}]
        if failed:
            retried = wait_run(client, retry.json()["id"])
            assert retried["suite"] == "regression"
            assert calls == failed
            calls.clear()
            single = client.post(f"/api/runs/{run_id}/retry-failed", json={"scenario_id": second["id"]})
            wait_run(client, single.json()["id"])
            assert calls == ["Second"]
        else:
            assert retry.status_code == 409
        calls.clear()
        group = client.post(root + "/run/regression", json={"group": "Auth"})
        wait_run(client, group.json()["id"])
        assert calls == ["First"]
        assert client.patch(f"/api/scenarios/{first['id']}", json={"regression_enabled": False}).status_code == 200
        assert client.patch(f"/api/scenarios/{first['id']}", json={"order": "bad"}).status_code == 422
        recipe = client.get(root + "/recipe").json()
        assert recipe["scenarios"][0]["group"] == "Tasks"
        assert client.post(root + "/recipe", json=recipe).status_code == 200


def test_empty_regression_and_retry_exclusions(tmp_path, monkeypatch):
    monkeypatch.setattr(PlaywrightRunner, "run", lambda *a: pytest.fail("Excluded scenarios must not run"))
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d/db")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Task Board", "frontend_url": "http://localhost:5173"}).json()
        root = f"/api/projects/{project['id']}"
        recipe = {"format": "qaroz-recipe", "version": 1, "name": "Legacy", "api_tests": [], "scenarios": [
            {"name": "Page", "steps": [{"action": "goto", "url": "/"}], "expected": [{"type": "visible", "selector": "body"}]}
        ]}
        assert client.post(root + "/recipe", json=recipe).status_code == 200
        scenario = client.get(root + "/scenarios").json()[0]
        assert scenario["regression_enabled"] is True and scenario["order"] == 0
        db = client.app.state.db
        run_id = db.insert("test_runs", {"project_id": project["id"], "suite": "regression", "trigger": "manual", "started_at": "now", "status": "FAIL"})
        db.insert("test_results", {"run_id": run_id, "category": "e2e", "test_name": "Page", "status": "FAIL", "duration_ms": 0, "source_id": scenario["id"]})
        client.patch(f"/api/scenarios/{scenario['id']}", json={"regression_enabled": False})
        assert client.post(f"/api/runs/{run_id}/retry-failed").status_code == 409
        empty = client.post(root + "/run/regression", json={})
        assert wait_run(client, empty.json()["id"])["status"] == "SKIPPED"
        assert client.post(root + "/run/regression", json={"retry_categories": ["security"]}).status_code == 422
