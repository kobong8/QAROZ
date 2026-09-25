from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from qa_manager.api.routes import router
from qa_manager.core.config import Settings, get_settings
from qa_manager.core.database import Database
from qa_manager.services.artifact_service import ArtifactService
from qa_manager.services.project_service import ProjectService
from qa_manager.services.run_service import RunService
from qa_manager.services.scenario_recorder import ScenarioRecorderService


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config.data_dir.mkdir(parents=True, exist_ok=True)
        db = Database(config.database_path)
        db.initialize()
        artifacts = ArtifactService(config.artifact_dir)
        app.state.db = db
        app.state.projects = ProjectService(db)
        app.state.artifacts = artifacts
        app.state.runs = RunService(db, artifacts, config.max_concurrent_runs)
        app.state.recorder = ScenarioRecorderService()
        yield
        app.state.recorder.close()
        app.state.runs.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="QAROZ", version="1.0.0", lifespan=lifespan)
    app.include_router(router)
    web = Path(__file__).parent / "web"
    app.mount("/", StaticFiles(directory=web, html=True), name="dashboard")
    return app
