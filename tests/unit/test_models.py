from qa_manager.core.models import RunnerResult, Status, aggregate_status


def test_aggregate_status_precedence():
    assert aggregate_status([RunnerResult("x", "a", Status.PASS)]) == Status.PASS
    assert (
        aggregate_status(
            [
                RunnerResult("x", "a", Status.PASS),
                RunnerResult("x", "b", Status.WARNING),
            ]
        )
        == Status.WARNING
    )
    assert (
        aggregate_status(
            [RunnerResult("x", "a", Status.FAIL), RunnerResult("x", "b", Status.ERROR)]
        )
        == Status.ERROR
    )
