"""Test-session setup shared by every test under this folder.

No GIT_* variable reaches a test: a GIT_DIR (or GIT_WORK_TREE, GIT_INDEX_FILE, ...) set by whoever runs
the suite would override ``git -C <temporary repository>`` and send the git-based tests' commits into a
real repository (incident 2026-10-18 12:38, decision D1a). The git helpers also pass an environment
without them, so this is the second guard, not the only one.

No test reaches the network (CR-069, QA check 4011): every connection to an address that is not this
computer's loopback fails at once, unless the test is marked ``network`` (map downloads, deselected offline).
"""

import ipaddress
import os
import socket

import pytest


def pytest_configure(config):
    for name in [k for k in os.environ if k.startswith("GIT_")]:
        del os.environ[name]


_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex


def _loopback(address):
    if not isinstance(address, tuple):
        return True  # a Unix socket path: this computer
    host = str(address[0])
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False  # any other name


def _check(sock, address):
    if sock.family in (socket.AF_INET, socket.AF_INET6) and not _loopback(address):
        raise OSError(f"network guard: a test tried to connect to {address!r}; tests reach only this computer")


def _guarded_connect(self, address):
    _check(self, address)
    return _REAL_CONNECT(self, address)


def _guarded_connect_ex(self, address):
    _check(self, address)
    return _REAL_CONNECT_EX(self, address)


@pytest.fixture(autouse=True)
def _network_guard(request, monkeypatch):
    if request.node.get_closest_marker("network") is None:
        monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
        monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
