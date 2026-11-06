"""CR-069 (QA check 4011): no test reaches the network. An autouse guard in conftest.py fails any connection
to an address that is not this computer's loopback; tests marked ``network`` (map downloads) are exempt."""

import socket
import threading

import pytest


def test_a_non_loopback_connection_fails_before_it_starts():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, pytest.raises(OSError, match="network guard"):
        s.connect(("192.0.2.1", 80))  # TEST-NET-1: never routed
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s, pytest.raises(OSError, match="network guard"):
        s.connect_ex(("2001:db8::1", 80))  # the IPv6 documentation range


def test_create_connection_is_guarded_too():
    with pytest.raises(OSError, match="network guard"):
        socket.create_connection(("192.0.2.1", 80), timeout=1)


def test_loopback_connections_work():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    accepted = []
    thread = threading.Thread(target=lambda: accepted.append(listener.accept()[0]), daemon=True)
    thread.start()
    with socket.create_connection(("127.0.0.1", listener.getsockname()[1]), timeout=2):
        thread.join(2)
    assert accepted
    accepted[0].close()
    listener.close()
