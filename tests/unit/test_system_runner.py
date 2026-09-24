import socket

from qa_manager.core.models import Status
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
