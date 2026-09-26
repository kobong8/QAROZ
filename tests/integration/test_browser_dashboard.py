"""Opt-in UI verification against an isolated local QAROZ instance."""
import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from qa_manager.core.config import Settings
from qa_manager.core.models import RunnerResult, Status
from qa_manager.main import create_app
from qa_manager.runners.playwright_runner import PlaywrightRunner
from qa_manager.runners.trivy_runner import TrivyRunner


@pytest.mark.skipif(os.environ.get("QAROZ_BROWSER_TESTS") != "1", reason="Opt-in: requires installed Chromium")
def test_dashboard_regression_security_and_retry(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    calls = []
    def scenario_run(self, scenario, directory, *args):
        calls.append(scenario["name"])
        return RunnerResult("e2e", scenario["name"], Status.FAIL, message="Expected Upload Complete; actual timeout")
    monkeypatch.setattr(PlaywrightRunner, "run", scenario_run)
    monkeypatch.setattr(TrivyRunner, "status", lambda *a: {"installed": True, "version": "test-version"})
    settings = Settings(tmp_path, tmp_path / "d", tmp_path / "a", tmp_path / "d/db")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(create_app(settings), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        with httpx.Client(base_url=url) as client:
            project = client.post("/api/projects", json={"name": "Task Board", "frontend_url": url}).json()
            endpoint = f"/api/projects/{project['id']}"
            client.post(endpoint + "/scenarios", json={"name": "File Upload", "group": "Tasks",
                        "steps": [{"action": "goto", "url": "/"}], "expected": [{"type": "visible", "selector": "body"}]})
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 1000})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(url)
                    expect(page.locator("#prepPanelSystem")).to_be_visible()
                    page.locator('#editProject').click()
                    page.locator('#projectForm [name="expected_ports"]').fill('5173, 8000')
                    page.locator('#projectForm button[type=submit]').click()
                    expect(page.locator('#projectDialog')).not_to_be_visible()
                    expect(page.locator('#systemPreparation')).to_contain_text('5173, 8000')
                    assert client.get(endpoint).json()['expected_ports'] == [5173, 8000]
                    for name in ("api", "e2e", "regression", "security", "system"):
                        page.locator(f'[data-prep-tab="{name}"]').click()
                        expect(page.locator('.prep-panel:visible')).to_have_count(1)
                        expect(page.locator(f'[data-prep-tab="{name}"]')).to_have_attribute('aria-selected', 'true')
                        expect(page.locator('#' + page.locator(f'[data-prep-tab="{name}"]').get_attribute('aria-controls'))).to_be_visible()
                    page.locator('[data-prep-tab="api"]').click()
                    page.locator('#prepPanelApi .editor > summary').click()
                    page.locator('#apiForm [name="name"]').fill('Health via UI')
                    page.locator('#apiForm [name="url"]').fill(url + '/api/health')
                    page.locator('#apiForm button').click()
                    expect(page.locator('#apiTestList')).to_contain_text('Health via UI')
                    assert client.get(endpoint + '/api-tests').json()[0]['name'] == 'Health via UI'
                    page.locator('[data-prep-tab="e2e"]').click()
                    page.locator('#prepPanelE2e .editor > summary').click()
                    page.locator('#scenarioForm [name="name"]').fill('Page via UI')
                    page.locator('#scenarioForm button').click()
                    expect(page.locator('#scenarioTestList')).to_contain_text('Page via UI')
                    added = next(s for s in client.get(endpoint + '/scenarios').json() if s['name'] == 'Page via UI')
                    client.patch(f"/api/scenarios/{added['id']}", json={'regression_enabled': False})
                    page.reload()
                    page.locator('[data-prep-tab="regression"]').click()
                    expect(page.locator("#regressionList")).to_contain_text("Tasks")
                    expect(page.locator("#regressionList")).to_contain_text("File Upload")
                    checkbox = page.locator("#regressionList .regression-row").filter(has_text="File Upload").locator('input[type=checkbox]')
                    checkbox.uncheck()
                    expect(checkbox).not_to_be_checked()
                    # Wait for the PATCH/reload to finish before rechecking.
                    page.wait_for_function("document.querySelector('#regressionList input[type=checkbox]').checked === false")
                    page.reload()
                    page.locator('[data-prep-tab="regression"]').click()
                    expect(checkbox).not_to_be_checked()
                    checkbox.check()
                    page.locator('[data-run="regression"]').click()
                    expect(page.locator("#regressionMetric")).to_contain_text("1 FAIL", timeout=10000)
                    page.get_by_role("button", name="REGRESSION 상세").first.click()
                    expect(page.locator("#runDetail")).to_contain_text("Expected Upload Complete")
                    page.get_by_role("button", name="Retry Scenario", exact=True).click()
                    expect(page.locator("#runs .run")).to_have_count(2, timeout=10000)
                    assert calls == ["File Upload", "File Upload"]
                    page.locator('[data-prep-tab="security"]').click()
                    page.locator("#projectTrivy").check()
                    page.locator("#saveProjectSecurity").click()
                    expect(page.locator("#toast")).to_contain_text("Security 설정")
                    assert client.get(endpoint).json()["trivy_enabled"] is True
                    page.reload()
                    page.locator('[data-prep-tab="security"]').click()
                    expect(page.locator('#projectTrivy')).to_be_checked()
                    page.locator("#checkTrivy").click()
                    expect(page.locator("#trivyStatus")).to_contain_text("test-version")
                    page.screenshot(path=str(tmp_path / "dashboard-desktop.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    for name in ('system', 'api', 'e2e', 'regression', 'security'):
                        page.locator(f'[data-prep-tab="{name}"]').click()
                        expect(page.locator('.prep-panel:visible')).to_have_count(1)
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.screenshot(path=str(tmp_path / "dashboard-mobile.png"), full_page=True)
                    assert errors == []
                finally:
                    browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
