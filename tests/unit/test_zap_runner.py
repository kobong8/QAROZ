from qa_manager.core.models import Status
from qa_manager.runners.zap_runner import ZapRunner


def test_zap_key_sent_in_header_not_url(monkeypatch):
    import io
    import urllib.request
    monkeypatch.setenv("QAROZ_ZAP_API_KEY", "local-test-key")
    requests = []
    def open_url(request, timeout):
        requests.append(request)
        return io.BytesIO(b'{"version":"test"}')
    monkeypatch.setattr(urllib.request, "urlopen", open_url)
    assert ZapRunner().status("http://127.0.0.1:8090")["running"]
    assert requests[0].get_header("X-zap-api-key") == "local-test-key"
    assert "local-test-key" not in requests[0].full_url


def test_active_scan_rejects_unapproved_remote_target():
    result, alerts = ZapRunner().run(
        "https://example.com", "http://127.0.0.1:8090", active=True
    )
    assert result.status == Status.ERROR
    assert alerts == []
