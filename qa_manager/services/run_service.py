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
from qa_manager.runners.trivy_runner import TrivyRunner
from .artifact_service import ArtifactService
from .regression_service import RegressionService


class RunService:
    def __init__(self, db: Database, artifacts: ArtifactService, max_workers: int = 3):
        self.db, self.artifacts = db, artifacts
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="qaroz-run"
        )
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def submit(
        self, project: dict[str, Any], suite: str, options: dict[str, Any] | None = None,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        if suite not in {"system", "api", "e2e", "security", "all", "regression", "zap", "trivy"}:
            raise ValueError("Unknown test suite")
        if (options or {}).get("active") and suite != "zap":
            raise ValueError("Active scanning requires an explicit ZAP run")
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
                "trigger": trigger,
                "started_at": utcnow(),
                "status": Status.QUEUED.value,
                "current_stage": "Queued",
            },
        )
        run_options = dict(options or {})
        self.executor.submit(self._execute, run_id, project, suite, run_options)
        return self.get(run_id)  # type: ignore[return-value]

    def _execute(
        self, run_id: str, project: dict[str, Any], suite: str, options: dict[str, Any]
    ) -> None:
        started = time.perf_counter()
        results: list[RunnerResult] = []
        try:
            categories = options.get("retry_categories") or (
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
            if suite == "all":
                with self._lock:
                    self._active.discard(project["id"])

    def _run_category(
        self,
        category: str,
        run_id: str,
        project: dict[str, Any],
        options: dict[str, Any],
    ) -> list[RunnerResult]:
        if category == "regression":
            return RegressionService(self.db, self.artifacts).run(project, run_id, options)
        if category == "system":
            return SystemRunner().run(project)
        if category == "api":
            cases = self.db.fetchall(
                "SELECT * FROM api_test_cases WHERE project_id=? AND enabled=1",
                (project["id"],),
            )
            selected = options.get("api_case_ids")
            if selected is not None:
                cases = [case for case in cases if case["id"] in selected]
            results = [ApiRunner().run(case) for case in cases]
            for result, case in zip(results, cases):
                result.source_id = case["id"]
            return results or [
                RunnerResult(
                    "api", "API suite", Status.SKIPPED, message="No enabled API cases"
                )
            ]
        if category == "e2e":
            scenarios = self.db.fetchall(
                "SELECT * FROM scenarios WHERE project_id=? AND enabled=1",
                (project["id"],),
            )
            selected = options.get("scenario_ids")
            if selected is not None:
                scenarios = [scenario for scenario in scenarios if scenario["id"] in selected]
            directory = self.artifacts.run_dir(project["id"], run_id)
            results = [
                PlaywrightRunner().run(
                    s,
                    directory,
                    project["frontend_url"],
                    project.get("project_path"),
                )
                for s in scenarios
            ]
            for result, scenario in zip(results, scenarios):
                result.source_id = scenario["id"]
            return results or [
                RunnerResult(
                    "e2e", "E2E suite", Status.SKIPPED, message="No enabled scenarios"
                )
            ]
        settings = {
            row["key"]: row["value"]
            for row in self.db.fetchall("SELECT * FROM settings")
        }
        results = []
        zap_enabled = project.get("zap_enabled")
        if zap_enabled is None:
            zap_enabled = settings.get("security_enabled", "false") == "true"
        if category in {"security", "zap"}:
            if zap_enabled:
                result, alerts = ZapRunner().run(
                    project["frontend_url"], settings.get("zap_api_url", "http://127.0.0.1:8090"),
                    active=category == "zap" and options.get("active") is True,
                    allowed_active_hosts=json.loads(settings.get("allowed_active_hosts", "[]")),
                )
                result.details["scanner"] = "zap"
                for alert in alerts:
                    self.db.insert("zap_alerts", {"run_id": run_id, **alert})
            else:
                result = RunnerResult("security", "ZAP", Status.SKIPPED, message="ZAP is disabled for this project", details={"scanner": "zap"})
            results.append(result)
        if category in {"security", "trivy"}:
            if project.get("trivy_enabled", False):
                result = TrivyRunner().run(
                    project.get("project_path"), self.artifacts.run_dir(project["id"], run_id),
                    configured=settings.get("trivy_executable"),
                    scanners=project.get("trivy_scanners", ["vuln", "misconfig", "secret"]),
                )
            else:
                result = RunnerResult("security", "Trivy", Status.SKIPPED, message="Trivy is disabled for this project", details={"scanner": "trivy"})
            results.append(result)
        return results

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
                "source_id": result.source_id,
            },
        )
        for artifact in result.artifacts:
            self.db.insert("artifacts", {"result_id": result_id, **artifact})

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM test_runs WHERE id=?", (run_id,))

    def list(self, project_id: str) -> list[dict[str, Any]]:
        runs = self.db.fetchall(
            "SELECT * FROM test_runs WHERE project_id=? ORDER BY started_at DESC",
            (project_id,),
        )
        counts = self.db.fetchall(
            "SELECT r.run_id, r.status, COUNT(*) AS count FROM test_results r "
            "JOIN test_runs t ON t.id=r.run_id WHERE t.project_id=? GROUP BY r.run_id, r.status",
            (project_id,),
        )
        summaries = {run["id"]: {status: 0 for status in ("PASS", "FAIL", "WARNING", "ERROR", "SKIPPED")} for run in runs}
        for item in counts:
            if item["run_id"] in summaries:
                summaries[item["run_id"]][item["status"]] = item["count"]
        for run in runs:
            run["summary"] = summaries[run["id"]]
        return runs

    def clear_history(self, project_id: str) -> int:
        # One statement also cascades to results, alerts, and artifact records.
        # Workers may still be writing queued/running runs, so preserve them.
        with self.db.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM test_runs WHERE project_id=? "
                "AND status IN ('PASS', 'FAIL', 'WARNING', 'SKIPPED', 'ERROR')",
                (project_id,),
            )
            return cursor.rowcount

    def results(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM test_results WHERE run_id=? ORDER BY rowid", (run_id,)
        )
        for row in rows:
            row["artifacts"] = self.db.fetchall(
                "SELECT * FROM artifacts WHERE result_id=?", (row["id"],)
            )
        return rows
