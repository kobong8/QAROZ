from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from qa_manager.core.models import RunnerResult, Status


class PlaywrightRunner:
    def run(
        self,
        scenario: dict[str, Any],
        artifact_dir: Path,
        base_url: str,
        project_path: str | None = None,
    ) -> RunnerResult:
        started = time.perf_counter()
        screenshot = artifact_dir / f"{scenario['id']}.png"
        trace = artifact_dir / f"{scenario['id']}.zip"
        console_errors: list[str] = []
        network_errors: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return RunnerResult(
                "e2e",
                scenario["name"],
                Status.ERROR,
                message="Playwright is not installed; run 'pip install -e .' and 'playwright install chromium'",
            )
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context()
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                page = context.new_page()
                page.on(
                    "console",
                    lambda msg: (
                        console_errors.append(msg.text) if msg.type == "error" else None
                    ),
                )
                page.on(
                    "response",
                    lambda response: (
                        network_errors.append(
                            {"status": response.status, "url": response.url}
                        )
                        if response.status >= 400
                        else None
                    ),
                )
                for step in scenario.get("steps", []):
                    self._step(page, step, base_url, project_path)
                for expectation in scenario.get("expected", []):
                    self._expect(page, expectation)
                context.tracing.stop()
                browser.close()
            return RunnerResult(
                "e2e",
                scenario["name"],
                Status.PASS,
                int((time.perf_counter() - started) * 1000),
                "Scenario completed",
                {"console_errors": console_errors, "network_errors": network_errors},
            )
        except AssertionError as exc:
            status, message = Status.FAIL, str(exc)
        except Exception as exc:
            status, message = (
                Status.ERROR,
                f"Browser execution failed: {type(exc).__name__}: {exc}",
            )
        try:
            page.screenshot(path=str(screenshot), full_page=True)
            artifacts.append(
                {"type": "screenshot", "local_path": str(screenshot), "metadata": {}}
            )
            context.tracing.stop(path=str(trace))
            artifacts.append(
                {"type": "trace", "local_path": str(trace), "metadata": {}}
            )
            browser.close()
        except Exception:
            pass
        return RunnerResult(
            "e2e",
            scenario["name"],
            status,
            int((time.perf_counter() - started) * 1000),
            message,
            {"console_errors": console_errors, "network_errors": network_errors},
            artifacts,
        )

    @staticmethod
    def _step(
        page: Any, step: dict[str, Any], base_url: str, project_path: str | None
    ) -> None:
        action = step.get("action")
        selector = step.get("selector")
        if action == "goto":
            target = step["url"]
            if target.startswith(("http://", "https://")):
                if urlparse(target).netloc != urlparse(base_url).netloc:
                    raise ValueError(
                        "Scenario navigation must stay on the registered frontend"
                    )
                destination = target
            else:
                destination = base_url.rstrip("/") + "/" + target.lstrip("/")
            page.goto(destination, wait_until="domcontentloaded")
        elif action == "click":
            page.locator(selector).click()
        elif action == "fill":
            page.locator(selector).fill(str(step.get("value", "")))
        elif action == "select":
            page.locator(selector).select_option(str(step["value"]))
        elif action == "upload":
            if not project_path:
                raise ValueError("File upload requires a registered project path")
            root = Path(project_path).resolve()
            upload = Path(step["path"]).resolve()
            if not upload.is_file() or not upload.is_relative_to(root):
                raise ValueError(
                    "Upload file must be inside the registered project path"
                )
            page.locator(selector).set_input_files(str(upload))
        elif action == "wait":
            page.locator(selector).wait_for(
                state=step.get("state", "visible"),
                timeout=int(step.get("timeout", 5000)),
            )
        else:
            raise ValueError(f"Unsupported scenario action: {action}")

    @staticmethod
    def _expect(page: Any, expectation: dict[str, Any]) -> None:
        locator = page.locator(expectation["selector"])
        kind = expectation.get("type", "visible")
        if kind == "visible" and not locator.is_visible():
            raise AssertionError(f"{expectation['selector']} is not visible")
        if kind == "text" and expectation["value"] not in locator.inner_text():
            raise AssertionError(
                f"Expected text {expectation['value']!r} in {expectation['selector']}"
            )
        if kind == "count" and locator.count() != int(expectation["value"]):
            raise AssertionError(f"Expected {expectation['value']} matching elements")
