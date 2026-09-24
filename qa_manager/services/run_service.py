from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from qa_manager.core.database import Database, utcnow
from qa_manager.core.models import RunnerResult, Status, aggregate_status
from qa_manager.runners.api_runner import ApiRunner
from qa_manager.runners.playwright_runner import PlaywrightRunner
from qa_manager.runners.system_runner import SystemRunner
from qa_manager.runners.zap_runner import ZapRunner
from .artifact_service import ArtifactService


class RunService:
    def __init__(self, db: Database, artifacts: ArtifactService, max_workers: int = 3):
        self.db, self.artifacts = db, artifacts
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="qaroz-run"
        )
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def submit(
        self, project: dict[str, Any], suite: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if suite not in {"system", "api", "e2e", "security", "all"}:
            raise ValueError("Unknown test suite")
        with self._lock:
            if suite == "all" and project["id"] in self._active:
                raise RuntimeError("A Run All is already active for this project")
            if suite == "all":
                self._active.add(project["id"])
        run_id = str(uuid.uuid4())
        self.db.insert(
            "test_runs",
            {
                "id": run_id,
                "project_id": project["id"],
                "suite": suite,
                "trigger": "manual",
                "started_at": utcnow(),
                "status": Status.QUEUED.value,
                "current_stage": "Queued",
            },
        )
        run_options = {**(options or {}), "security_requested": suite == "security"}
        self.executor.submit(self._execute, run_id, project, suite, run_options)
        return self.get(run_id)  # type: ignore[return-value]

    def _execute(
        self, run_id: str, project: dict[str, Any], suite: str, options: dict[str, Any]
    ) -> None:
        started = time.perf_counter()
        results: list[RunnerResult] = []
        try:
            categories = (
                [suite] if suite != "all" else ["system", "api", "e2e", "security"]
            )
            for category in categories:
                self.db.execute(
                    "UPDATE test_runs SET status=?, current_stage=? WHERE id=?",
                    (Status.RUNNING.value, category.title(), run_id),
                )
                category_results = self._run_category(
                    category, run_id, project, options
                )
                results.extend(category_results)
                # Persist each phase immediately so polling clients can inspect progress
                # and evidence survives if a later external tool crashes.
                for result in category_results:
                    self._save_result(run_id, result)
            final = aggregate_status(results)
        except Exception as exc:
            result = RunnerResult(
                suite,
                "Runner orchestration",
                Status.ERROR,
                message=f"Unexpected runner error: {type(exc).__name__}: {exc}",
            )
            self._save_result(run_id, result)
            final = Status.ERROR
        finally:
            self.db.execute(
                "UPDATE test_runs SET status=?, current_stage=NULL, ended_at=?, duration_ms=? WHERE id=?",
                (
                    final.value,
                    utcnow(),
                    int((time.perf_counter() - started) * 1000),
                    run_id,
                ),
            )
            with self._lock:
                self._active.discard(project["id"])

    def _run_category(
        self,
        category: str,
        run_id: str,
        project: dict[str, Any],
        options: dict[str, Any],
    ) -> list[RunnerResult]:
        if category == "system":
            return SystemRunner().run(project)
        if category == "api":
            cases = self.db.fetchall(
                "SELECT * FROM api_test_cases WHERE project_id=? AND enabled=1",
                (project["id"],),
            )
            return [ApiRunner().run(case) for case in cases] or [
                RunnerResult(
                    "api", "API suite", Status.SKIPPED, message="No enabled API cases"
                )
            ]
        if category == "e2e":
            scenarios = self.db.fetchall(
                "SELECT * FROM scenarios WHERE project_id=? AND enabled=1",
                (project["id"],),
            )
            directory = self.artifacts.run_dir(project["id"], run_id)
            return [
                PlaywrightRunner().run(
                    s,
                    directory,
                    project["frontend_url"],
                    project.get("project_path"),
                )
                for s in scenarios
            ] or [
                RunnerResult(
                    "e2e", "E2E suite", Status.SKIPPED, message="No enabled scenarios"
                )
            ]
        settings = {
            row["key"]: row["value"]
            for row in self.db.fetchall("SELECT * FROM settings")
        }
        if not options.get("security_requested") and settings.get("security_enabled", "false") != "true":
            return [RunnerResult(
                "security", "ZAP Scan", Status.SKIPPED,
                message="Security is not enabled for Run All. Install/start ZAP, configure its API, then enable security in Settings.",
            )]
        result, alerts = ZapRunner().run(
            project["frontend_url"],
            settings.get("zap_api_url", "http://127.0.0.1:8090"),
            active=bool(options.get("active")),
            allowed_active_hosts=json.loads(settings.get("allowed_active_hosts", "[]")),
        )
        for alert in alerts:
            self.db.insert("zap_alerts", {"run_id": run_id, **alert})
        return [result]

    def _save_result(self, run_id: str, result: RunnerResult) -> None:
        result_id = self.db.insert(
            "test_results",
            {
                "run_id": run_id,
                "category": result.category,
                "test_name": result.test_name,
                "status": result.status.value,
                "duration_ms": result.duration_ms,
                "message": result.message,
                "details": result.details,
            },
        )
        for artifact in result.artifacts:
            self.db.insert("artifacts", {"result_id": result_id, **artifact})

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM test_runs WHERE id=?", (run_id,))

    def list(self, project_id: str) -> list[dict[str, Any]]:
        return self.db.fetchall(
            "SELECT * FROM test_runs WHERE project_id=? ORDER BY started_at DESC",
            (project_id,),
        )

    def results(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM test_results WHERE run_id=? ORDER BY rowid", (run_id,)
        )
        for row in rows:
            row["artifacts"] = self.db.fetchall(
                "SELECT * FROM artifacts WHERE result_id=?", (row["id"],)
            )
        return rows
