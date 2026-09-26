import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from qa_manager.core.models import Status
from qa_manager.runners.api_runner import ApiRunner
from qa_manager.runners.api_runner import json_equal


def test_json_assertions_compare_nested_types():
    assert not json_equal(True, 1)
    assert not json_equal({"items": [False]}, {"items": [0]})
    assert not json_equal(1, 1.0)
    assert json_equal({"items": [True, 1, None]}, {"items": [True, 1, None]})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": {"ready": True}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def test_api_runner_assertions_and_redaction():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        case = {
            "name": "health",
            "url": f"http://127.0.0.1:{server.server_port}",
            "method": "GET",
            "headers": {"Authorization": "secret"},
            "expected_status": 200,
            "assertions": {"data.ready": True},
        }
        result = ApiRunner().run(case)
        assert result.status == Status.PASS
        assert result.details["request"]["headers"]["Authorization"] == "[REDACTED]"
    finally:
        server.shutdown()
