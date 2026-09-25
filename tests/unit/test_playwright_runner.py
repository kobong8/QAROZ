from types import SimpleNamespace

import playwright.sync_api

from qa_manager.core.models import Status
from qa_manager.runners.playwright_runner import PlaywrightRunner


def test_failure_evidence_is_captured_before_transport_shutdown(tmp_path, monkeypatch):
    state = {"alive": False, "closed": False}
    def capture(path, **kwargs):
        assert state["alive"] and not state["closed"]
        from pathlib import Path
        Path(path).write_bytes(b"evidence")
    page = SimpleNamespace(set_default_timeout=lambda _: None, on=lambda *args: None, screenshot=capture)
    context = SimpleNamespace(tracing=SimpleNamespace(start=lambda **kwargs: None, stop=capture), new_page=lambda: page)
    browser = SimpleNamespace(new_context=lambda: context, close=lambda: state.update(closed=True))
    class Runtime:
        def __enter__(self):
            state["alive"] = True
            return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: browser))
        def __exit__(self, *args):
            state["alive"] = False
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", Runtime)
    runner = PlaywrightRunner()
    def fail(*args):
        raise AssertionError("Expected content missing")
    monkeypatch.setattr(runner, "_expect", fail)
    result = runner.run({"id": "failure", "name": "Failing scenario", "expected": [{}]}, tmp_path, "http://localhost")
    assert result.status == Status.FAIL
    assert {item["type"] for item in result.artifacts} == {"screenshot", "trace"}
    assert (tmp_path / "failure.png").exists()
    assert (tmp_path / "failure.zip").exists()
    assert state == {"alive": False, "closed": True}


def test_navigation_http_error_is_not_a_pass():
    page = SimpleNamespace(goto=lambda *args, **kwargs: SimpleNamespace(status=404))
    import pytest
    with pytest.raises(AssertionError, match="HTTP 404"):
        PlaywrightRunner._step(page, {"action": "goto", "url": "/missing"}, "http://localhost", None)


def test_wait_uses_condition_state_and_ten_second_default():
    calls = []
    locator = SimpleNamespace(wait_for=lambda **kwargs: calls.append(kwargs))
    page = SimpleNamespace(locator=lambda selector: locator)
    PlaywrightRunner._step(page, {"action": "wait", "selector": "#ready", "state": "attached"}, "http://localhost", None)
    assert calls == [{"state": "attached", "timeout": 10000}]
