from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    RUNNING = "RUNNING"
    QUEUED = "QUEUED"


@dataclass
class RunnerResult:
    category: str
    test_name: str
    status: Status
    duration_ms: int = 0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    source_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


TERMINAL_STATUSES = {
    Status.PASS,
    Status.FAIL,
    Status.WARNING,
    Status.SKIPPED,
    Status.ERROR,
}


def aggregate_status(results: list[RunnerResult]) -> Status:
    statuses = {r.status for r in results}
    if Status.ERROR in statuses:
        return Status.ERROR
    if Status.FAIL in statuses:
        return Status.FAIL
    if Status.WARNING in statuses:
        return Status.WARNING
    if statuses and statuses <= {Status.PASS, Status.SKIPPED}:
        return Status.PASS if Status.PASS in statuses else Status.SKIPPED
    return Status.ERROR
