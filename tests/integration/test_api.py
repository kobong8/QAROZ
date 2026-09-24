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
