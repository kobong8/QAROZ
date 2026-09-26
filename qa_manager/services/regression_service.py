from __future__ import annotations

from typing import Any

from qa_manager.core.models import RunnerResult, Status
from qa_manager.runners.playwright_runner import PlaywrightRunner


def regression_fields(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = payload.get("regression_enabled", True)
    group = payload.get("group")
    order = payload.get("order", 0)
    if type(enabled) is not bool:
        raise ValueError("regression_enabled must be a boolean")
    if group is not None and (not isinstance(group, str) or len(group) > 200):
        raise ValueError("group must be a string of at most 200 characters or null")
    if type(order) is not int or not -(2**31) <= order < 2**31:
        raise ValueError("order must be a 32-bit integer")
    return {"regression_enabled": enabled, "group": (group.strip() or None) if group else None, "order": order}


class RegressionService:
    """Select regression assets; RunService owns jobs, aggregation and persistence."""

    def __init__(self, db, artifacts):
        self.db, self.artifacts = db, artifacts

    def scenarios(self, project_id: str, options: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            'SELECT * FROM scenarios WHERE project_id=? AND enabled=1 '
            'AND regression_enabled=1 ORDER BY "order", rowid', (project_id,),
        )
        if "group" in options:
            rows = [row for row in rows if row["group"] == options["group"]]
        if "scenario_ids" in options:
            rows = [row for row in rows if row["id"] in options["scenario_ids"]]
        return rows

    def run(self, project: dict[str, Any], run_id: str, options: dict[str, Any]) -> list[RunnerResult]:
        results = []
        for scenario in self.scenarios(project["id"], options):
            result = PlaywrightRunner().run(
                scenario, self.artifacts.run_dir(project["id"], run_id),
                project["frontend_url"], project.get("project_path"),
            )
            result.source_id = scenario["id"]
            result.details.update(group=scenario["group"], order=scenario["order"])
            results.append(result)
        return results or [RunnerResult("e2e", "Regression suite", Status.SKIPPED,
                                       message="No enabled regression scenarios")]
