import socket

from qa_manager.core.models import Status
from qa_manager.core.models import RunnerResult
from qa_manager.runners.system_runner import SystemRunner


def test_open_and_closed_port_statuses():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    try:
        assert SystemRunner()._port("127.0.0.1", port).status == Status.PASS
    finally:
        sock.close()
    assert SystemRunner()._port("127.0.0.1", port).status == Status.FAIL


def test_missing_health_backend_root_404_is_warning(monkeypatch):
    runner = SystemRunner()
    def http(url):
        return RunnerResult("system", url, Status.FAIL if url.endswith("8000") else Status.PASS,
                            message=f"HTTP {404 if url.endswith('8000') else 200} from {url}")
    monkeypatch.setattr(runner, "_http", http)
    results = runner.run({"frontend_url": "http://localhost:5173", "backend_url": "http://localhost:8000"})
    assert [r.status for r in results] == [Status.PASS, Status.WARNING]
    assert "backend root has no route" in results[1].message


def test_explicit_health_failure_remains_fail(monkeypatch):
    runner = SystemRunner()
    calls = []
    def http(url):
        calls.append(url)
        return RunnerResult("system", url, Status.FAIL, message=f"HTTP 404 from {url}")
    monkeypatch.setattr(runner, "_http", http)
    results = runner.run({"frontend_url": "http://localhost:5173", "backend_url": "http://localhost:8000", "health_url": "http://localhost:8000/health"})
    assert calls == ["http://localhost:5173", "http://localhost:8000/health"]
    assert results[1].status == Status.FAIL


def test_port_check_uses_registered_host_including_ipv6(monkeypatch):
    runner = SystemRunner()
    hosts = []
    def port(host, port):
        hosts.append((host, port))
        return RunnerResult("system", "port", Status.PASS)
    monkeypatch.setattr(runner, "_port", port)
    monkeypatch.setattr(runner, "_http", lambda url: RunnerResult("system", "http", Status.PASS))
    runner.run({"frontend_url": "http://localhost:5173", "backend_url": "http://[::1]:8000", "expected_ports": [5173, 8000]})
    assert hosts == [("localhost", 5173), ("::1", 8000)]


def test_multiple_backends_use_matching_health_urls(monkeypatch):
    runner = SystemRunner()
    calls = []

    def http(url):
        calls.append(url)
        return RunnerResult("system", url, Status.PASS)

    monkeypatch.setattr(runner, "_http", http)
    runner.run(
        {
            "frontend_url": "http://localhost:5173",
            "backend_urls": ["http://localhost:8000", "http://localhost:8001"],
            "health_urls": [
                "http://localhost:8000/health",
                "http://localhost:8001/ready",
            ],
        }
    )

    assert calls == [
        "http://localhost:5173",
        "http://localhost:8000/health",
        "http://localhost:8001/ready",
    ]


def test_multiple_backends_without_health_urls_are_all_checked(monkeypatch):
    runner = SystemRunner()
    calls = []

    def http(url):
        calls.append(url)
        return RunnerResult("system", url, Status.PASS)

    monkeypatch.setattr(runner, "_http", http)
    runner.run(
        {
            "frontend_url": "http://localhost:5173",
            "backend_urls": ["http://localhost:8000", "http://localhost:8001"],
        }
    )

    assert calls == [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8001",
    ]
