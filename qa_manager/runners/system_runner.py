from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from qa_manager.core.models import RunnerResult, Status


class SystemRunner:
    def run(self, project: dict) -> list[RunnerResult]:
        results: list[RunnerResult] = []
        for rule in project.get("process_rules", []):
            results.append(self._process(rule))
        for port in project.get("expected_ports", []):
            host = "localhost"
            urls = [project.get("frontend_url")]
            urls += project.get("backend_urls") or (
                [project["backend_url"]] if project.get("backend_url") else []
            )
            urls += project.get("health_urls") or (
                [project["health_url"]] if project.get("health_url") else []
            )
            for url in urls:
                if url:
                    parsed = urlparse(url)
                    if (parsed.port or (443 if parsed.scheme == "https" else 80)) == int(port):
                        host = parsed.hostname or host
                        break
            results.append(self._port(host, int(port)))
        # A backend may have no route at /. Always check the frontend, and
        # only require a successful backend HTTP response for an explicit health URL.
        frontend = project["frontend_url"]
        results.append(self._http(frontend))
        backends = project.get("backend_urls") or (
            [project["backend_url"]] if project.get("backend_url") else []
        )
        health_urls = project.get("health_urls") or (
            [project["health_url"]] if project.get("health_url") else []
        )
        for index, backend in enumerate(backends):
            health = health_urls[index] if index < len(health_urls) else None
            target = health or backend
            if target == frontend:
                continue
            result = self._http(target)
            if not health and result.message.startswith("HTTP 404 "):
                result.status = Status.WARNING
                result.message += "; backend root has no route. Configure an existing health/API URL or verify API cases."
            results.append(result)
        # Also support additional standalone health endpoints.
        for health in health_urls[len(backends):]:
            if health != frontend:
                results.append(self._http(health))
        return results

    def _process(self, rule: str) -> RunnerResult:
        started = time.perf_counter()
        try:
            import psutil

            found = any(
                rule.lower() in (proc.info.get("name") or "").lower()
                for proc in psutil.process_iter(["name"])
            )
            status, message = (
                (Status.PASS, f"Process matching {rule!r} is running")
                if found
                else (Status.FAIL, f"No process matching {rule!r}")
            )
        except Exception as exc:
            status, message = (
                Status.ERROR,
                f"Process inspection failed: {type(exc).__name__}: {exc}",
            )
        return RunnerResult(
            "system",
            f"Process: {rule}",
            status,
            int((time.perf_counter() - started) * 1000),
            message,
        )

    def _port(self, host: str, port: int) -> RunnerResult:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=2):
                status, message = Status.PASS, f"{host}:{port} is accepting connections"
        except (OSError, TimeoutError) as exc:
            status, message = Status.FAIL, f"{host}:{port} is not reachable: {exc}"
        return RunnerResult(
            "system",
            f"Port: {port}",
            status,
            int((time.perf_counter() - started) * 1000),
            message,
        )

    def _http(self, url: str) -> RunnerResult:
        started = time.perf_counter()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "QAROZ/1.0"})
            with urllib.request.urlopen(request, timeout=5) as response:
                code = response.status
            status = Status.PASS if 200 <= code < 400 else Status.FAIL
            message = f"HTTP {code} from {url}"
        except urllib.error.HTTPError as exc:
            status, message = Status.FAIL, f"HTTP {exc.code} from {url}"
        except urllib.error.URLError as exc:
            status, message = (
                Status.FAIL,
                f"Health endpoint is unreachable: {exc.reason}",
            )
        except Exception as exc:
            status, message = (
                Status.ERROR,
                f"Health request failed: {type(exc).__name__}: {exc}",
            )
        return RunnerResult(
            "system",
            f"HTTP: {url}",
            status,
            int((time.perf_counter() - started) * 1000),
            message,
        )
