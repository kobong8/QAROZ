from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


RECORDER_SCRIPT = r"""
(() => {
  if (window.__qarozRecorder) return;
  const state = window.__qarozRecorder = {events: [], verify: null};
  const esc = value => CSS.escape(String(value));
  const locator = el => {
    const testid = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
    if (testid) return `[data-testid="${String(testid).replaceAll('"', '\\"')}"]`;
    const role = el.getAttribute('role') || ({BUTTON:'button',A:'link',SELECT:'combobox',TEXTAREA:'textbox'}[el.tagName]);
    const name = (el.getAttribute('aria-label') || el.innerText || el.value || '').trim();
    if (role && name) return `role=${role}[name="${name.replaceAll('"', '\\"')}"]`;
    const label = el.labels && el.labels[0] && el.labels[0].innerText.trim();
    if (label) return `label=${label}`;
    if (el.id) return `#${esc(el.id)}`;
    const parts = []; let node = el;
    while (node && node.nodeType === 1 && parts.length < 5) {
      let part = node.tagName.toLowerCase();
      const siblings = node.parentElement && [...node.parentElement.children].filter(x => x.tagName === node.tagName);
      if (siblings && siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      parts.unshift(part); node = node.parentElement;
    }
    return parts.join(' > ');
  };
  const push = (kind, el, extra={}) => state.events.push({kind, selector: locator(el), ...extra});
  document.addEventListener('click', event => {
    const el = event.target.closest('button,a,input,select,textarea,[role]') || event.target;
    if (state.verify) {
      event.preventDefault(); event.stopImmediatePropagation();
      const type = state.verify; state.verify = null;
      const selector = locator(el);
      let count;
      if (selector.startsWith('role=')) {
        const match = selector.match(/^role=([^[]+)\[name="(.*)"\]$/);
        count = match ? [...document.querySelectorAll('[role],button,a,select,textarea')].filter(node =>
          (node.getAttribute('role') || ({BUTTON:'button',A:'link',SELECT:'combobox',TEXTAREA:'textbox'}[node.tagName])) === match[1] &&
          (node.getAttribute('aria-label') || node.innerText || node.value || '').trim() === match[2]).length : 1;
      } else if (selector.startsWith('label=')) {
        count = [...document.querySelectorAll('label')].filter(node => node.innerText.trim() === selector.slice(6)).length;
      } else count = document.querySelectorAll(selector).length;
      const value = type === 'text' ? (el.innerText || el.value || '').trim() : type === 'count' ? count : undefined;
      push('expected', el, {type, value}); return;
    }
    if (!['INPUT','SELECT','TEXTAREA'].includes(el.tagName)) push('click', el);
  }, true);
  document.addEventListener('change', event => {
    const el = event.target;
    if (el.tagName === 'SELECT') push('select', el, {value: el.value});
    else if (el.type === 'file') push('upload', el, {path: '${UPLOAD_FILE}'});
    else {
      const sensitive = el.type === 'password' || /pass(word)?|secret|token|api.?key/i.test(`${el.name} ${el.id} ${el.autocomplete}`);
      push('fill', el, {value: sensitive ? `\${SECRET:${el.name || el.id || 'VALUE'}}` : el.value, sensitive});
    }
  }, true);
})();
"""


@dataclass
class Recording:
    id: str
    project_id: str
    url: str
    status: str = "starting"
    error: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    expected: list[dict[str, Any]] = field(default_factory=list)
    commands: queue.Queue = field(default_factory=queue.Queue, repr=False)
    updated_at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "project_id": self.project_id, "url": self.url,
                "status": self.status, "error": self.error, "steps": self.steps,
                "expected": self.expected, "updated_at": self.updated_at}


class ScenarioRecorderService:
    """Translates headed-browser events into the existing Scenario JSON contract."""

    def __init__(self) -> None:
        self._recordings: dict[str, Recording] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str, url: str) -> dict[str, Any]:
        recording = Recording(str(uuid.uuid4()), project_id, url)
        recording.steps.append({"action": "goto", "url": url})
        with self._lock:
            self._recordings[recording.id] = recording
        threading.Thread(target=self._run, args=(recording,), daemon=True).start()
        return recording.public()

    def get(self, recording_id: str) -> dict[str, Any] | None:
        recording = self._recordings.get(recording_id)
        return recording.public() if recording else None

    def command(self, recording_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        recording = self._recordings.get(recording_id)
        if not recording:
            return None
        if name == "add_wait":
            recording.steps.append(validate_wait(payload))
            recording.updated_at = time.time()
        elif name in {"verify_visible", "verify_text", "verify_count"}:
            recording.commands.put(("verify", name.removeprefix("verify_")))
        elif name == "stop":
            recording.commands.put(("stop", None))
        else:
            raise ValueError("Unsupported recorder command")
        return recording.public()

    def close(self) -> None:
        for recording in self._recordings.values():
            if recording.status in {"starting", "recording"}:
                recording.commands.put(("stop", None))

    def _run(self, recording: Recording) -> None:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                context.add_init_script(RECORDER_SCRIPT)
                page = context.new_page()
                def navigation(frame: Any) -> None:
                    if frame == page.main_frame and frame.url not in {"about:blank", recording.steps[-1].get("url")}:
                        recording.steps.append({"action": "goto", "url": frame.url})
                        recording.updated_at = time.time()
                page.on("framenavigated", navigation)
                page.goto(recording.url, wait_until="domcontentloaded")
                recording.status = "recording"
                while recording.status == "recording":
                    self._drain_events(page, recording)
                    try:
                        command, value = recording.commands.get(timeout=.15)
                        if command == "verify":
                            page.evaluate("kind => window.__qarozRecorder.verify = kind", value)
                        elif command == "stop":
                            recording.status = "stopped"
                    except queue.Empty:
                        pass
                self._drain_events(page, recording)
                context.close(); browser.close()
        except Exception as exc:
            recording.status = "error"
            recording.error = f"{type(exc).__name__}: {exc}"
        finally:
            recording.updated_at = time.time()

    @staticmethod
    def _drain_events(page: Any, recording: Recording) -> None:
        try:
            events = page.evaluate("() => window.__qarozRecorder.events.splice(0)")
        except Exception:
            return
        for event in events:
            kind = event.pop("kind")
            event.pop("sensitive", None)
            if kind == "expected":
                if event.get("value") is None: event.pop("value", None)
                recording.expected.append(event)
            else:
                recording.steps.append({"action": kind, **event})
        if events:
            recording.updated_at = time.time()


def validate_wait(payload: dict[str, Any]) -> dict[str, Any]:
    selector = payload.get("selector")
    state = payload.get("state", "visible")
    if not isinstance(selector, str) or not selector.strip():
        raise ValueError("Wait selector is required")
    if state not in {"visible", "hidden", "attached", "detached"}:
        raise ValueError("Invalid wait state")
    try:
        timeout = int(payload.get("timeout", 10000))
    except (TypeError, ValueError) as exc:
        raise ValueError("Wait timeout must be an integer") from exc
    if timeout < 1 or timeout > 300000:
        raise ValueError("Wait timeout must be between 1 and 300000 ms")
    return {"action": "wait", "selector": selector.strip(), "state": state, "timeout": timeout}
