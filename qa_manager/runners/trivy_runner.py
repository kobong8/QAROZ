from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from qa_manager.core.models import RunnerResult, Status

SCANNERS = {"vuln", "misconfig", "secret", "license"}
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")


class TrivyRunner:
    """Local CLI adapter. Untrusted stdout/stderr are never persisted verbatim."""

    @staticmethod
    def executable(configured: str | None = None) -> str:
        candidate = configured or shutil.which("trivy")
        if not candidate:
            raise ValueError("Trivy is not installed; configure a local trivy executable")
        path = Path(candidate).expanduser().resolve()
        if not path.is_file() or path.name.lower() not in {"trivy", "trivy.exe"}:
            raise ValueError("Select an existing trivy or trivy.exe executable (not a script)")
        if os.name == "nt" and path.suffix.lower() != ".exe":
            raise ValueError("Windows requires trivy.exe")
        if os.name != "nt" and not os.access(path, os.X_OK):
            raise ValueError("Trivy file is not executable")
        return str(path)

    @staticmethod
    def execute(arguments: list[str], *, cwd: str, timeout: int):
        # Ignore inherited Trivy configuration that could redirect results to a server.
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("TRIVY_")}
        return subprocess.run(
            arguments, shell=False, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, cwd=cwd, env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def status(self, configured: str | None = None) -> dict[str, Any]:
        try:
            executable = self.executable(configured)
            with tempfile.TemporaryDirectory(prefix="qaroz-trivy-") as directory:
                process = self.execute([executable, "--version"], cwd=directory, timeout=10)
            match = re.search(r"Version:\s*([\w.+-]+)", process.stdout)
            if process.returncode or not match:
                raise ValueError("Trivy version check failed")
            return {"installed": True, "version": match.group(1)}
        except (ValueError, OSError, subprocess.SubprocessError):
            return {"installed": False, "message": "Trivy unavailable. Install Trivy or check its executable path."}

    @staticmethod
    def target(project_path: str | None, target: str | None = None) -> Path:
        if not project_path:
            raise ValueError("Trivy requires a registered project_path")
        root = Path(project_path).expanduser().resolve(strict=True)
        candidate = Path(target) if target else root
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve(strict=True)
        if not root.is_dir() or not candidate.is_dir() or not candidate.is_relative_to(root):
            raise ValueError("Trivy target must be a directory inside the registered project_path")
        # Reject escaping links/junctions before the scanner traverses the tree.
        def failed(error):
            raise error
        for directory, dirs, files in os.walk(candidate, followlinks=False, onerror=failed):
            for name in dirs + files:
                entry = Path(directory) / name
                if not entry.resolve().is_relative_to(root):
                    raise ValueError("Trivy target contains a link outside the registered project_path")
            dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()
                       and not (Path(directory) / name).is_junction()]
        return candidate

    @staticmethod
    def parse_report(raw: str) -> dict[str, Any]:
        document = json.loads(raw)
        if not isinstance(document, dict) or document.get("SchemaVersion") != 2:
            raise ValueError("Unsupported Trivy JSON report")
        results = document.get("Results")
        if results is None:
            results = []
        if not isinstance(results, list):
            raise ValueError("Invalid Trivy Results")
        fields = {
            "Vulnerabilities": ("VulnerabilityID", "PkgName", "InstalledVersion", "FixedVersion", "Severity", "Title"),
            "Misconfigurations": ("ID", "Type", "Severity", "Title", "Message", "Status"),
            "Secrets": ("RuleID", "Category", "Severity", "Title", "StartLine", "EndLine"),
            "Licenses": ("PkgName", "Name", "Category", "Severity", "FilePath"),
        }
        findings, sensitive = [], set()
        for result in results:
            if not isinstance(result, dict):
                raise ValueError("Invalid Trivy result")
            for category, allowed in fields.items():
                entries = result.get(category)
                if entries is None:
                    entries = []
                if not isinstance(entries, list):
                    raise ValueError("Invalid Trivy findings")
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise ValueError("Invalid Trivy finding")
                    # Only scalar allowlisted fields survive; Code, Match, arbitrary
                    # metadata and source snippets never enter artifacts or the DB.
                    item = {key: entry[key] for key in allowed if key in entry
                            and isinstance(entry[key], (str, int, float, bool))}
                    if category == "Misconfigurations" and item.get("Status", "FAIL") != "FAIL":
                        continue
                    item["category"] = category
                    item["Target"] = result.get("Target") if isinstance(result.get("Target"), str) else ""
                    if category == "Secrets":
                        item["Value"] = "********"
                        if isinstance(entry.get("Match"), str) and entry["Match"]:
                            sensitive.add(entry["Match"])
                    if category == "Misconfigurations":
                        cause = entry.get("CauseMetadata") or {}
                        if isinstance(cause, dict):
                            item["Cause"] = {key: cause[key] for key in ("Resource", "Provider", "Service", "StartLine", "EndLine")
                                             if key in cause and isinstance(cause[key], (str, int))}
                    severity = str(item.get("Severity", "UNKNOWN")).upper()
                    item["Severity"] = severity if severity in SEVERITIES else "UNKNOWN"
                    findings.append(item)
        # Also mask known matches if repeated in an otherwise allowed field.
        def scrub(value):
            if isinstance(value, str):
                for secret in sorted(sensitive, key=len, reverse=True):
                    value = value.replace(secret, "********")
                return value
            if isinstance(value, list):
                return [scrub(item) for item in value]
            if isinstance(value, dict):
                return {key: scrub(item) for key, item in value.items()}
            return value
        findings = scrub(findings)
        return {"scanner": "trivy", "sanitized": True, "findings": findings,
                "summary": {severity: sum(item["Severity"] == severity for item in findings) for severity in SEVERITIES}}

    def run(self, project_path: str | None, artifact_dir: Path, *,
            configured: str | None = None, scanners: list[str] | None = None,
            target: str | None = None, timeout: int = 300, offline: bool = False) -> RunnerResult:
        started = time.perf_counter()
        try:
            selected = ["vuln", "misconfig", "secret"] if scanners is None else scanners
            if not isinstance(selected, list) or not selected or any(not isinstance(s, str) or s not in SCANNERS for s in selected):
                raise ValueError("Select at least one supported Trivy scanner")
            executable = self.executable(configured)
            destination = self.target(project_path, target)
            with tempfile.TemporaryDirectory(prefix="qaroz-trivy-") as directory:
                config = Path(directory) / "trivy.yaml"
                config.write_text("{}", encoding="utf-8")
                arguments = [executable, "fs", "--config", str(config),
                             "--scanners", ",".join(dict.fromkeys(selected)), "--format", "json",
                             "--disable-telemetry", "--skip-version-check", "--cache-backend", "memory",
                             "--exit-code", "0", "--timeout", f"{timeout}s"]
                if offline:
                    arguments += ["--offline-scan", "--skip-db-update", "--skip-java-db-update", "--skip-check-update"]
                arguments.append(str(destination))
                process = self.execute(arguments, cwd=directory, timeout=timeout)
            if process.returncode:
                return RunnerResult("security", "Trivy", Status.ERROR,
                                    int((time.perf_counter() - started) * 1000),
                                    f"Trivy exited with code {process.returncode}; check installation and database availability",
                                    {"scanner": "trivy"})
            report = self.parse_report(process.stdout)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact = artifact_dir / "trivy.sanitized.json"
            artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            count = len(report["findings"])
            return RunnerResult("security", "Trivy", Status.WARNING if count else Status.PASS,
                                int((time.perf_counter() - started) * 1000), f"Trivy collected {count} finding(s)", report,
                                [{"type": "trivy-json", "local_path": str(artifact), "metadata": {"sanitized": True}}])
        except subprocess.TimeoutExpired:
            message = f"Trivy timed out after {timeout} seconds"
        except (ValueError, OSError, subprocess.SubprocessError):
            message = "Trivy could not scan: check executable, project path (including links), scanner options and JSON output"
        return RunnerResult("security", "Trivy", Status.ERROR, int((time.perf_counter() - started) * 1000),
                            message, {"scanner": "trivy"})
