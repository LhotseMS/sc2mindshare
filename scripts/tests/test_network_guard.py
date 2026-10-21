"""Rex's N1 on CR-069: the network guard covers scripts/tests too (the same guard as tests/conftest.py)."""

import socket

import pytest


def test_a_non_loopback_connection_fails_here_too():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s, pytest.raises(OSError, match="network guard"):
        s.connect(("192.0.2.1", 80))  # TEST-NET-1: never routed
