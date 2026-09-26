import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from qa_manager.core.models import Status
from qa_manager.runners.trivy_runner import TrivyRunner

REPORT = (Path(__file__).parents[1] / "fixtures/trivy_report.json").read_text(encoding="utf-8")


def test_report_categories_and_no_secret_in_artifact_or_result(tmp_path, monkeypatch):
    runner = TrivyRunner()
    monkeypatch.setattr(runner, "executable", lambda _: "trivy.exe")
    calls = []
    def execute(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=REPORT, stderr="SYNTHETIC_SECRET_VALUE")
    monkeypatch.setattr(runner, "execute", execute)
    result = runner.run(str(tmp_path), tmp_path / "artifacts", scanners=["vuln", "misconfig", "secret", "license"])
    assert result.status == Status.WARNING
    assert result.details["summary"] == {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0, "UNKNOWN": 1}
    findings = result.details["findings"]
    assert {item["category"] for item in findings} == {"Vulnerabilities", "Misconfigurations", "Secrets", "Licenses"}
    assert findings[0]["FixedVersion"] == "1.1"
    assert findings[1]["Cause"]["Resource"] == "USER"
    assert findings[2]["StartLine"] == 18 and findings[2]["Value"] == "********"
    assert findings[3]["Name"] == "UNKNOWN"
    assert "SYNTHETIC_SECRET_VALUE" not in json.dumps(result.to_dict())
    assert "SYNTHETIC_SECRET_VALUE" not in Path(result.artifacts[0]["local_path"]).read_text()
    args, options = calls[0]
    assert args[-1] == str(tmp_path.resolve())
    assert "--disable-telemetry" in args and "vuln,misconfig,secret,license" in args
    assert options["timeout"] == 300


@pytest.mark.parametrize("stdout,returncode", [("broken SECRET", 0), ('{"SchemaVersion":2,"Results":"bad"}', 0), ('{"SchemaVersion":2,"Results":{}}', 0), ('{}', 0), (REPORT, 1)])
def test_invalid_output_and_process_failure(tmp_path, monkeypatch, stdout, returncode):
    runner = TrivyRunner()
    monkeypatch.setattr(runner, "executable", lambda _: "trivy.exe")
    monkeypatch.setattr(runner, "execute", lambda *args, **kwargs: SimpleNamespace(returncode=returncode, stdout=stdout, stderr="SECRET"))
    result = runner.run(str(tmp_path), tmp_path / "artifacts")
    assert result.status == Status.ERROR
    assert "SECRET" not in json.dumps(result.to_dict())
    assert not result.artifacts


def test_timeout_and_empty_report(tmp_path, monkeypatch):
    runner = TrivyRunner()
    monkeypatch.setattr(runner, "executable", lambda _: "trivy.exe")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("secret command", 1, output="SECRET")
    monkeypatch.setattr(runner, "execute", timeout)
    result = runner.run(str(tmp_path), tmp_path / "artifacts", timeout=1)
    assert result.status == Status.ERROR and "timed out" in result.message
    assert "SECRET" not in json.dumps(result.to_dict())
    monkeypatch.setattr(runner, "execute", lambda *a, **kw: SimpleNamespace(returncode=0, stdout='{"SchemaVersion":2}'))
    assert runner.run(str(tmp_path), tmp_path / "artifacts").status == Status.PASS


def test_installation_and_invalid_executables(tmp_path, monkeypatch):
    monkeypatch.setattr("qa_manager.runners.trivy_runner.shutil.which", lambda _: None)
    runner = TrivyRunner()
    assert not runner.status()["installed"]
    for file in (tmp_path / "missing.exe", tmp_path / "script.cmd", tmp_path / "python.exe"):
        file.write_text("not an executable")
        with pytest.raises(ValueError):
            runner.executable(str(file))
    executable = tmp_path / ("trivy.exe" if os.name == "nt" else "trivy")
    executable.write_text("test")
    executable.chmod(0o755)
    assert runner.executable(str(executable)) == str(executable.resolve())
    monkeypatch.setattr(runner, "execute", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="Version: 0.99.0\n"))
    assert runner.status(str(executable)) == {"installed": True, "version": "0.99.0"}


def test_path_boundary_and_missing_project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(ValueError):
        TrivyRunner.target(None)
    with pytest.raises(ValueError):
        TrivyRunner.target(str(root), "..")
    with pytest.raises(ValueError):
        TrivyRunner.target(str(root), str(tmp_path))
    assert TrivyRunner.target(str(root)) == root.resolve()


def test_subprocess_isolated_and_no_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIVY_SERVER", "https://unwanted.example")
    monkeypatch.setenv("TRIVY_OUTPUT", "leak.json")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    TrivyRunner.execute(["trivy.exe", "fs", str(tmp_path)], cwd=str(tmp_path), timeout=5)
    args, kwargs = calls[0]
    assert isinstance(args[0], list) and kwargs["shell"] is False
    assert kwargs["capture_output"] and kwargs["timeout"] == 5
    assert not any(key.startswith("TRIVY_") for key in kwargs["env"])


def test_escaping_link_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    link = root / "linked-file"
    link.write_text("placeholder")
    original = Path.resolve
    def resolve(path, *args, **kwargs):
        if path == link:
            return tmp_path / "outside"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(ValueError, match="link outside"):
        TrivyRunner.target(str(root))


@pytest.mark.parametrize("scanners", [[], ["vuln;bad"], [None], "vuln"])
def test_invalid_scanners_never_start_process(tmp_path, monkeypatch, scanners):
    monkeypatch.setattr(TrivyRunner, "execute", lambda *a, **kw: pytest.fail("Process must not start"))
    assert TrivyRunner().run(str(tmp_path), tmp_path / "a", scanners=scanners).status == Status.ERROR
