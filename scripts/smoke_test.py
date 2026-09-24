"""Packaging smoke test: construct the app and initialize a disposable database."""

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from qa_manager.core.config import Settings
from qa_manager.main import create_app

with TemporaryDirectory() as directory:
    root = Path(directory)
    settings = Settings(
        root, root / "data", root / "artifacts", root / "data" / "qaroz.db"
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
print("QAROZ smoke test passed")
