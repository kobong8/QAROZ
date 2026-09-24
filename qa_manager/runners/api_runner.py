from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from qa_manager.core.models import RunnerResult, Status
from qa_manager.core.security import redact


def lookup(data: Any, dotted_path: str) -> Any:
    current = data
    for part in dotted_path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


class ApiRunner:
    def run(self, case: dict[str, Any]) -> RunnerResult:
        started = time.perf_counter()
        url = case["url"]
        query = case.get("query") or {}
        if query:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query)
        body = case.get("body")
        encoded_body = json.dumps(body).encode() if body is not None else None
        headers = {
            key: (
                os.environ.get(value[4:], "")
                if isinstance(value, str) and value.startswith("env:")
                else value
            )
            for key, value in (case.get("headers") or {}).items()
        }
        if encoded_body is not None:
            headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(
            url,
            data=encoded_body,
            headers=headers,
            method=case.get("method", "GET").upper(),
        )
        try:
            try:
                response = urllib.request.urlopen(request, timeout=30)
                raw, status_code, response_headers = (
                    response.read(),
                    response.status,
                    dict(response.headers),
                )
            except urllib.error.HTTPError as exc:
                raw, status_code, response_headers = (
                    exc.read(),
                    exc.code,
                    dict(exc.headers),
                )
            duration = int((time.perf_counter() - started) * 1000)
            failures: list[str] = []
            expected_status = int(case.get("expected_status", 200))
            if status_code != expected_status:
                failures.append(
                    f"expected HTTP {expected_status}, received {status_code}"
                )
            max_ms = case.get("max_response_ms")
            if max_ms is not None and duration > int(max_ms):
                failures.append(f"response took {duration}ms (limit {max_ms}ms)")
            parsed: Any = None
            if case.get("assertions"):
                try:
                    parsed = json.loads(raw)
                    for field, expected in case["assertions"].items():
                        try:
                            actual = lookup(parsed, field)
                            if actual != expected:
                                failures.append(
                                    f"{field}: expected {expected!r}, received {actual!r}"
                                )
                        except (KeyError, IndexError, TypeError, ValueError):
                            failures.append(f"{field}: field not found")
                except json.JSONDecodeError:
                    failures.append("response is not valid JSON")
            details = redact(
                {
                    "request": {
                        "method": request.method,
                        "url": url,
                        "headers": headers,
                        "body": body,
                    },
                    "response": {
                        "status": status_code,
                        "headers": response_headers,
                        "body": (
                            parsed
                            if parsed is not None
                            else raw.decode(errors="replace")[:10000]
                        ),
                    },
                }
            )
            return RunnerResult(
                "api",
                case["name"],
                Status.FAIL if failures else Status.PASS,
                duration,
                "; ".join(failures) or f"HTTP {status_code} matched expectations",
                details,
            )
        except Exception as exc:
            return RunnerResult(
                "api",
                case["name"],
                Status.ERROR,
                int((time.perf_counter() - started) * 1000),
                f"Request execution failed: {type(exc).__name__}: {exc}",
                {
                    "request": redact(
                        {"method": request.method, "url": url, "headers": headers}
                    )
                },
            )
