import socket
import pytest

from utils import find_available_port


def test_find_available_port_returns_free_port():
    port = find_available_port(start_port=5500, max_attempts=5)
    sock = socket.socket()
    try:
        sock.bind(('0.0.0.0', port))
    finally:
        sock.close()
    assert port >= 5500


def test_find_available_port_raises_when_exhausted():
    start_port = 5600
    max_attempts = 3
    sockets = []
    for i in range(max_attempts):
        s = socket.socket()
        s.bind(('0.0.0.0', start_port + i))
        sockets.append(s)
    try:
        with pytest.raises(RuntimeError):
            find_available_port(start_port=start_port, max_attempts=max_attempts)
    finally:
        for s in sockets:
            s.close()
