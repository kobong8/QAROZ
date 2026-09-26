from unittest.mock import Mock

from qa_manager.core.models import RunnerResult, Status
from qa_manager.services.run_service import RunService


def test_individual_suite_does_not_release_run_all_lock():
    service = RunService(Mock(), Mock())
    service._active.add("project")
    service._run_category = Mock(return_value=[RunnerResult("api", "case", Status.PASS)])
    try:
        service._execute("individual", {"id": "project"}, "api", {})
        assert "project" in service._active
        service._execute("all", {"id": "project"}, "all", {})
        assert "project" not in service._active
    finally:
        service.executor.shutdown(wait=True)
