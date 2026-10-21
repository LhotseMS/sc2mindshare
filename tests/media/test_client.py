"""CR-069 AC-1 groundwork: the local Mindshare media client (``sc2mindshare.media.client``).

Against the fake server in conftest.py (a real HTTP server on 127.0.0.1), never the network.
"""

from __future__ import annotations

import hashlib
import threading

import pytest

from sc2mindshare.media.client import (
    DEFAULT_SERVER,
    MediaError,
    NotLocal,
    Server,
    fetch_picture,
    health,
    parse_server,
    upload_picture,
)

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 3  # not a real picture: the client sends bytes, it never decodes


@pytest.fixture
def clock(tmp_path):
    path = tmp_path / "0-10.png"
    path.write_bytes(PNG)
    return path


# --- which servers are accepted (AC-6) -----------------------------------------------------------------------------


def test_the_default_server_is_the_local_mindshare_backend():
    assert DEFAULT_SERVER == "http://localhost:3042"
    assert parse_server(DEFAULT_SERVER) == Server("localhost", 3042)


@pytest.mark.parametrize(
    ("url", "host"),
    [("http://localhost:3042", "localhost"), ("http://127.0.0.1:3042", "127.0.0.1"), ("http://[::1]:3042", "::1")],
)
def test_the_three_loopback_names_are_one_server(url, host):
    server = parse_server(url)
    assert (server.host, server.port) == (host, 3042)
    assert server.key == "localhost:3042"  # team default (a)


def test_another_port_is_another_server():
    assert parse_server("http://localhost:3043").key == "localhost:3043"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:3042",
        "http://192.168.1.10:3042",  # this Mac's network address is refused too: loopback only (team default b)
        "http://localhost.example.com:3042",
        "http://127.0.0.1.nip.io:3042",
        "http://localhost@example.com:3042",
        "http://user@localhost:3042",
        "http://example.com/localhost",
        "https://localhost:3042",
        "localhost:3042",
        "http://localhost:3042/media",
    ],
)
def test_anything_but_a_plain_loopback_address_is_refused(url):
    with pytest.raises(NotLocal, match="local Mindshare only"):
        parse_server(url)


# --- health -----------------------------------------------------------------------------------------------------------


def test_health_reads_the_upload_status(fake_media):
    server = parse_server(fake_media.url)
    assert health(server) == "open"
    fake_media.health_body = b'{"uploads": "paused"}'
    assert health(server) == "paused"
    assert [(r.method, r.path) for r in fake_media.requests] == [("GET", "/media/health")] * 2


@pytest.mark.parametrize(("status", "body"), [(200, b"<html>"), (200, b'{"other": 1}'), (500, b'{"uploads": "open"}')])
def test_an_unreadable_health_answer_is_an_error(fake_media, status, body):
    fake_media.health_status, fake_media.health_body = status, body
    with pytest.raises(MediaError):
        health(parse_server(fake_media.url))


def test_a_redirect_is_not_followed(fake_media):
    fake_media.redirect_to = "http://example.com/media/health"
    with pytest.raises(MediaError, match="302"):
        health(parse_server(fake_media.url))
    assert len(fake_media.requests) == 1


def test_a_refused_connection_is_an_error():
    with pytest.raises(MediaError):
        health(Server("127.0.0.1", 9), timeout=2)  # the discard port: nothing listens there


def test_a_server_that_never_answers_times_out(silent_server):
    """The client sets a timeout (urllib's default waits forever); a join limit turns a hang into a failure."""
    outcome: list[BaseException] = []

    def call():
        try:
            health(parse_server(silent_server), timeout=0.5)
        except BaseException as exc:  # noqa: BLE001  # the test records whatever ends the call
            outcome.append(exc)

    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    thread.join(5)
    assert not thread.is_alive(), "the client waited past its timeout"
    assert len(outcome) == 1
    assert isinstance(outcome[0], MediaError)


# --- upload and read back ------------------------------------------------------------------------------------------


def test_an_upload_sends_the_file_then_the_type_and_returns_the_id(fake_media, clock):
    picture_id = upload_picture(parse_server(fake_media.url), clock)
    [post] = fake_media.posts()
    assert post.path == "/media/"
    assert "Origin" not in post.headers
    assert post.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert post.parts() == [("file", "0-10.png", PNG), ("type", None, b"image")]
    assert fake_media.stored == {picture_id: PNG}


def test_the_picture_reads_back_byte_for_byte(fake_media, clock):
    server = parse_server(fake_media.url)
    picture_id = upload_picture(server, clock)
    assert hashlib.sha256(fetch_picture(server, picture_id)).hexdigest() == hashlib.sha256(PNG).hexdigest()
    assert [(r.method, r.path) for r in fake_media.requests][-1] == ("GET", f"/media/resource/{picture_id}")


@pytest.mark.parametrize(("status", "headers"), [(429, {"Retry-After": "60"}), (503, {}), (415, {}), (413, {}), (400, {})])
def test_a_refused_upload_is_an_error_with_its_status(fake_media, clock, status, headers):
    fake_media.upload_status, fake_media.upload_headers = status, headers
    with pytest.raises(MediaError) as caught:
        upload_picture(parse_server(fake_media.url), clock)
    assert caught.value.status == status
    assert caught.value.retry_after == headers.get("Retry-After")


@pytest.mark.parametrize("body", [b'{"type": "image"}', b'{"_id": ""}', b'{"_id": 7}', b"<html>"])
def test_a_201_without_an_id_is_an_error(fake_media, clock, body):
    fake_media.created_body = body
    with pytest.raises(MediaError, match="_id"):
        upload_picture(parse_server(fake_media.url), clock)


def test_an_upload_redirect_is_not_followed(fake_media, clock):
    fake_media.redirect_to = "http://example.com/media/"
    with pytest.raises(MediaError, match="302"):
        upload_picture(parse_server(fake_media.url), clock)
    assert len(fake_media.requests) == 1
