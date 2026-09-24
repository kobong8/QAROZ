"""Opt-in real Chromium regression: QAROZ_BROWSER_TESTS=1 pytest."""
import os
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from qa_manager.core.models import Status
from qa_manager.runners.playwright_runner import PlaywrightRunner


@pytest.mark.skipif(os.environ.get("QAROZ_BROWSER_TESTS") != "1", reason="Opt-in: requires installed Chromium")
def test_real_failed_assertion_saves_readable_evidence(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<!doctype html><html><body><h1>Actual content</h1></body></html>")
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = PlaywrightRunner().run(
            {"id": "failure-proof", "name": "Intentional assertion failure",
             "steps": [{"action": "goto", "url": "/"}],
             "expected": [{"type": "text", "selector": "h1", "value": "Expected different content"}]},
            tmp_path, f"http://127.0.0.1:{server.server_port}",
        )
        assert result.status == Status.FAIL, result.message
        assert {item["type"] for item in result.artifacts} == {"screenshot", "trace"}, result.message
        assert (tmp_path / "failure-proof.png").read_bytes().startswith(b"\x89PNG")
        with zipfile.ZipFile(tmp_path / "failure-proof.zip") as trace:
            assert any(name.endswith(".trace") for name in trace.namelist())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
