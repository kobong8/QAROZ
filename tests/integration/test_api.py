from pathlib import Path

from fastapi.testclient import TestClient

from qa_manager.core.config import Settings
from qa_manager.main import create_app


def test_project_crud_run_and_dashboard(tmp_path: Path):
    settings = Settings(
        tmp_path,
        tmp_path / "data",
        tmp_path / "artifacts",
        tmp_path / "data" / "test.db",
        max_concurrent_runs=2,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 200
        payload = {
            "name": "Demo",
            "frontend_url": "http://127.0.0.1:1",
            "expected_ports": [1],
        }
        created = client.post("/api/projects", json=payload)
        assert created.status_code == 201
        project = created.json()
        assert client.get("/api/projects").json()[0]["name"] == "Demo"
        assert (
            client.put(
                f"/api/projects/{project['id']}", json={"name": "Updated"}
            ).json()["name"]
            == "Updated"
        )
        run = client.post(f"/api/projects/{project['id']}/run/system", json={})
        assert run.status_code == 202
        assert run.json()["project_id"] == project["id"]
        assert client.get(f"/api/projects/{project['id']}/runs").json()
        assert client.delete(f"/api/projects/{project['id']}").status_code == 204


def test_three_projects_remain_independent(tmp_path: Path):
    settings = Settings(
        tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db.sqlite"
    )
    with TestClient(create_app(settings)) as client:
        ids = [
            client.post(
                "/api/projects",
                json={"name": f"P{i}", "frontend_url": f"http://localhost:{8000+i}"},
            ).json()["id"]
            for i in range(3)
        ]
        assert len(set(ids)) == 3
        assert len(client.get("/api/projects").json()) == 3


def test_project_accepts_multiple_backend_and_health_urls(tmp_path: Path):
    settings = Settings(
        tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db.sqlite"
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/projects",
            json={
                "name": "Services",
                "frontend_url": "http://localhost:5173",
                "backend_urls": [
                    "http://localhost:8000/",
                    "http://localhost:8001",
                ],
                "health_urls": [
                    "http://localhost:8000/health",
                    "http://localhost:8001/ready/",
                ],
            },
        )

        assert response.status_code == 201
        project = response.json()
        assert project["backend_urls"] == [
            "http://localhost:8000",
            "http://localhost:8001",
        ]
        assert project["health_urls"] == [
            "http://localhost:8000/health",
            "http://localhost:8001/ready",
        ]
        assert project["backend_url"] == "http://localhost:8000"


def test_backend_urls_must_be_an_array(tmp_path: Path):
    settings = Settings(
        tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db.sqlite"
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/projects",
            json={
                "name": "Invalid",
                "frontend_url": "http://localhost:5173",
                "backend_urls": "http://localhost:8000",
            },
        )
        assert response.status_code == 422
        assert "backend_urls must be an array" in response.json()["detail"]


def test_recipe_round_trip_and_rejects_unknown_version(tmp_path: Path):
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db.sqlite")
    with TestClient(create_app(settings)) as client:
        first = client.post("/api/projects", json={"name": "Source", "frontend_url": "http://localhost:5173"}).json()
        second = client.post("/api/projects", json={"name": "Target", "frontend_url": "http://localhost:5174"}).json()
        client.post(f"/api/projects/{first['id']}/api-tests", json={"name": "Health", "url": "http://localhost:8000/health"})
        client.post(f"/api/projects/{first['id']}/scenarios", json={"name": "Home", "steps": [{"action": "goto", "url": "/"}], "expected": [{"type": "visible", "selector": "body"}]})

        exported = client.get(f"/api/projects/{first['id']}/recipe")
        assert exported.status_code == 200
        assert "attachment" in exported.headers["content-disposition"]
        assert exported.json()["format"] == "qaroz-recipe"
        imported = client.post(f"/api/projects/{second['id']}/recipe", json=exported.json())
        assert imported.json() == {"api_tests": 1, "scenarios": 1}
        assert len(client.get(f"/api/projects/{second['id']}/api-tests").json()) == 1
        bad = {**exported.json(), "version": 999}
        assert client.post(f"/api/projects/{second['id']}/recipe", json=bad).status_code == 422


def test_retry_failed_selects_only_failed_api_and_e2e_items(tmp_path: Path):
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d" / "db.sqlite")
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/projects", json={"name": "Retry", "frontend_url": "http://localhost:5173"}).json()
        case = client.post(f"/api/projects/{project['id']}/api-tests", json={"name": "Broken", "url": "http://127.0.0.1:1"}).json()
        db = client.app.state.db
        run_id = db.insert("test_runs", {"project_id": project["id"], "suite": "api", "trigger": "manual", "started_at": "2026-01-01T00:00:00+00:00", "status": "FAIL"})
        db.insert("test_results", {"run_id": run_id, "category": "api", "test_name": "Broken", "status": "ERROR", "duration_ms": 1, "details": {}, "source_id": case["id"]})

        retried = client.post(f"/api/runs/{run_id}/retry-failed")
        assert retried.status_code == 202
        assert retried.json()["trigger"] == f"retry:{run_id}"
        assert client.post(f"/api/runs/{retried.json()['id']}/retry-failed").status_code in {409, 202}
