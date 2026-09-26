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
        current_step = None
        current_expectation = None
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
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
                try:
                    context = browser.new_context()
                    context.tracing.start(screenshots=True, snapshots=True, sources=True)
                    page = context.new_page()
                    page.set_default_timeout(10000)
                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    page.on("pageerror", lambda exc: console_errors.append(str(exc)))
                    page.on("response", lambda response: network_errors.append(
                        {"status": response.status, "url": response.url}
                    ) if response.status >= 400 else None)
                    try:
                        for index, step in enumerate(scenario.get("steps", []), 1):
                            current_step = {"index": index, "action": step.get("action"), "selector": step.get("selector")}
                            self._step(page, step, base_url, project_path)
                        current_step = None
                        for expectation in scenario.get("expected", []):
                            current_expectation = expectation
                            self._expect(page, expectation)
                        current_expectation = None
                        status = Status.WARNING if console_errors or network_errors else Status.PASS
                        message = "Scenario completed" + ("; browser console/network errors were observed" if status == Status.WARNING else "")
                    except (AssertionError, PlaywrightTimeoutError) as exc:
                        status, message = Status.FAIL, str(exc)
                    except Exception as exc:
                        status, message = Status.ERROR, f"Browser execution failed: {type(exc).__name__}: {exc}"
                    # Capture evidence while the browser and Playwright transport are alive.
                    if status != Status.PASS:
                        artifact_dir.mkdir(parents=True, exist_ok=True)
                        for kind, path, capture in (
                            ("screenshot", screenshot, lambda: page.screenshot(path=str(screenshot), full_page=True, timeout=5000)),
                            ("trace", trace, lambda: context.tracing.stop(path=str(trace))),
                        ):
                            try:
                                capture()
                                artifacts.append({"type": kind, "local_path": str(path), "metadata": {}})
                            except Exception as exc:
                                message += f"; {kind} capture failed: {type(exc).__name__}"
                    else:
                        context.tracing.stop()
                finally:
                    browser.close()
        except Exception as exc:
            status, message = (
                Status.ERROR,
                f"Browser execution failed: {type(exc).__name__}: {exc}",
            )
        return RunnerResult(
            "e2e",
            scenario["name"],
            status,
            int((time.perf_counter() - started) * 1000),
            message,
            {"console_errors": console_errors, "network_errors": network_errors,
             "failed_step": current_step, "failed_expectation": current_expectation},
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
            response = page.goto(destination, wait_until="domcontentloaded")
            if response and response.status >= 400:
                raise AssertionError(f"Navigation returned HTTP {response.status}: {destination}")
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
                timeout=int(step.get("timeout", 10000)),
            )
        else:
            raise ValueError(f"Unsupported scenario action: {action}")

    @staticmethod
    def _expect(page: Any, expectation: dict[str, Any]) -> None:
        from playwright.sync_api import expect

        locator = page.locator(expectation["selector"])
        kind = expectation.get("type", "visible")
        if kind == "visible":
            expect(locator).to_be_visible()
        elif kind == "text":
            expect(locator).to_contain_text(expectation["value"])
        elif kind == "count":
            expect(locator).to_have_count(int(expectation["value"]))
        else:
            raise ValueError(f"Unsupported expectation: {kind}")
