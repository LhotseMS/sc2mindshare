"""The network guard (CR-069, QA check 4011; Rex's N1): no test reaches the network.

``tests/conftest.py`` and ``scripts/tests/conftest.py`` both load this module and use ``guard`` as an autouse
fixture: a connection to an address that is not this computer's loopback fails at once with "network guard",
unless the test is marked ``network`` (map downloads, deselected offline with ``-m "not network"``).

What it does not cover: name lookups. ``socket.getaddrinfo`` (DNS) is not guarded, so a test may still resolve
a name; it only cannot connect to what the name resolves to. Connections made outside Python's ``socket``
module (a subprocess, a C extension with its own sockets) are not seen either.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import pytest

_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex


def _loopback(address: Any) -> bool:
    if not isinstance(address, tuple):
        return True  # a Unix socket path: this computer
    host = str(address[0])
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False  # any other name


def _check(sock: socket.socket, address: Any) -> None:
    if sock.family in (socket.AF_INET, socket.AF_INET6) and not _loopback(address):
        raise OSError(f"network guard: a test tried to connect to {address!r}; tests reach only this computer")


def _guarded_connect(self: socket.socket, address: Any) -> None:
    _check(self, address)
    _REAL_CONNECT(self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
    _check(self, address)
    return _REAL_CONNECT_EX(self, address)


@pytest.fixture(autouse=True)
def guard(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("network") is None:
        monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
        monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
