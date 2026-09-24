from qa_manager.core.models import Status
from qa_manager.runners.zap_runner import ZapRunner


def test_active_scan_rejects_unapproved_remote_target():
    result, alerts = ZapRunner().run(
        "https://example.com", "http://127.0.0.1:8090", active=True
    )
    assert result.status == Status.ERROR
    assert alerts == []
