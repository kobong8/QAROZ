from __future__ import annotations

import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from qa_manager.core.models import RunnerResult, Status


class ZapRunner:
    def status(self, api_url: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(
                f"{api_url.rstrip('/')}/JSON/core/view/version/", timeout=2
            ) as response:
                data = json.load(response)
            return {"running": True, "version": data.get("version")}
        except Exception as exc:
            return {"running": False, "message": str(exc)}

    def start(self, executable: str, port: int = 8090) -> subprocess.Popen[str]:
        path = Path(executable).resolve()
        if not path.is_file():
            raise ValueError("Configured ZAP executable does not exist")
        # Arguments are fixed: there is intentionally no arbitrary command input.
        return subprocess.Popen(
            [
                str(path),
                "-daemon",
                "-port",
                str(port),
                "-config",
                "autoupdate.checkOnStart=false",
                "-config",
                "connection.dnsTtlSuccessfulQueries=-1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def run(
        self,
        target: str,
        api_url: str,
        *,
        active: bool = False,
        allowed_active_hosts: list[str] | None = None,
    ) -> tuple[RunnerResult, list[dict[str, Any]]]:
        started = time.perf_counter()
        host = urllib.parse.urlparse(target).hostname or ""
        if active and host not in {
            "localhost",
            "127.0.0.1",
            "::1",
            *(allowed_active_hosts or []),
        }:
            return (
                RunnerResult(
                    "security",
                    "ZAP Active Scan",
                    Status.ERROR,
                    message=f"Active scan target {host!r} is not explicitly allowed",
                ),
                [],
            )
        try:
            self._get(
                api_url,
                "/JSON/core/action/accessUrl/",
                {"url": target, "followRedirects": "true"},
            )
            spider = self._get(
                api_url, "/JSON/spider/action/scan/", {"url": target, "recurse": "true"}
            )["scan"]
            self._wait(api_url, "/JSON/spider/view/status/", spider)
            if active:
                scan = self._get(api_url, "/JSON/ascan/action/scan/", {"url": target})[
                    "scan"
                ]
                self._wait(api_url, "/JSON/ascan/view/status/", scan, timeout=300)
            raw = self._get(api_url, "/JSON/core/view/alerts/", {"baseurl": target})
            alerts = [
                {
                    "risk": a.get("risk"),
                    "confidence": a.get("confidence"),
                    "url": a.get("url"),
                    "name": a.get("name"),
                    "description": a.get("description"),
                }
                for a in raw.get("alerts", [])
            ]
            severe = sum(a["risk"] in {"High", "Medium"} for a in alerts)
            status = Status.WARNING if alerts else Status.PASS
            message = (
                f"Collected {len(alerts)} alert(s), including {severe} medium/high"
            )
            return (
                RunnerResult(
                    "security",
                    "ZAP Active Scan" if active else "ZAP Spider & Passive Scan",
                    status,
                    int((time.perf_counter() - started) * 1000),
                    message,
                    {"alert_count": len(alerts)},
                ),
                alerts,
            )
        except Exception as exc:
            return (
                RunnerResult(
                    "security",
                    "ZAP Scan",
                    Status.ERROR,
                    int((time.perf_counter() - started) * 1000),
                    f"ZAP execution failed: {type(exc).__name__}: {exc}",
                ),
                [],
            )

    @staticmethod
    def _get(
        api_url: str, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        url = f"{api_url.rstrip('/')}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)

    def _wait(self, api_url: str, path: str, scan_id: str, timeout: int = 120) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if (
                int(self._get(api_url, path, {"scanId": scan_id}).get("status", 0))
                >= 100
            ):
                return
            time.sleep(1)
        raise TimeoutError("ZAP scan timed out")
