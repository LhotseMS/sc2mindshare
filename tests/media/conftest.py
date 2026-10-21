"""A fake local Mindshare media server for the CR-069 tests (QA check 4011: a real http.server, not a mock).

It listens on 127.0.0.1, port 0, in a thread, and answers like the real one (``docs/agents/mindshare-specialist``
§8, read in P002): ``GET /media/health`` -> ``{"uploads": "open"}``; ``POST /media/`` (multipart ``file`` then
``type=image``) -> 201 ``{"_id": <new uuid>}``, or 403 when an ``Origin`` header is sent; ``GET
/media/resource/<id>`` -> the stored bytes. Every request is logged, so a test can count them.
"""

from __future__ import annotations

import email.parser
import email.policy
import http.server
import json
import socket
import threading
import uuid
from dataclasses import dataclass, field

import pytest


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes

    def parts(self) -> list[tuple[str, str | None, bytes]]:
        """(name, filename, payload) per multipart part, in the order sent."""
        head = f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode()
        message = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(head + self.body)
        out = []
        for part in message.iter_parts():
            payload = part.get_payload(decode=True)
            out.append((str(part.get_param("name", header="content-disposition")), part.get_filename(), payload or b""))
        return out


@dataclass
class FakeMedia:
    url: str = ""
    requests: list[Request] = field(default_factory=list)
    health_status: int = 200
    health_body: bytes = b'{"uploads": "open"}'
    upload_status: int = 201
    upload_headers: dict[str, str] = field(default_factory=dict)
    redirect_to: str | None = None  # every answer becomes a 302 to here
    stored: dict[str, bytes] = field(default_factory=dict)
    served_bytes: bytes | None = None  # what /media/resource/<id> returns instead of the stored bytes
    created_body: bytes | None = None  # the 201's body instead of {"_id": ..., "type": "image"}

    def posts(self) -> list[Request]:
        return [r for r in self.requests if r.method == "POST"]


class _Handler(http.server.BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, format, *args):  # keep the test output clean
        pass

    def _log(self) -> Request:
        length = int(self.headers.get("Content-Length") or 0)
        request = Request(self.command, self.path, dict(self.headers.items()), self.rfile.read(length) if length else b"")
        self.server.fake.requests.append(request)
        return request

    def _answer(self, status: int, body: bytes, content_type: str = "application/json", **headers: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        self.wfile.write(body)

    def _redirected(self) -> bool:
        if self.server.fake.redirect_to is None:
            return False
        self._answer(302, b"", Location=self.server.fake.redirect_to)
        return True

    def do_GET(self):
        self._log()
        fake = self.server.fake
        if self._redirected():
            return
        if self.path == "/media/health":
            self._answer(fake.health_status, fake.health_body)
        elif self.path.startswith("/media/resource/") and self.path.removeprefix("/media/resource/") in fake.stored:
            data = (
                fake.served_bytes if fake.served_bytes is not None else fake.stored[self.path.removeprefix("/media/resource/")]
            )
            self._answer(200, data, "image/png")
        else:
            self._answer(404, b'{"error": "not found"}')

    def do_POST(self):
        request = self._log()
        fake = self.server.fake
        if self._redirected():
            return
        if self.path != "/media/":
            self._answer(404, b'{"error": "not found"}')
        elif "Origin" in request.headers:
            self._answer(403, b'{"error": "origin not allowed"}')
        elif fake.upload_status != 201:
            self._answer(fake.upload_status, b'{"error": "refused"}', **fake.upload_headers)
        else:
            picture_id = str(uuid.uuid4())
            fake.stored[picture_id] = next(payload for name, _, payload in request.parts() if name == "file")
            created = json.dumps({"_id": picture_id, "type": "image"}).encode()
            self._answer(201, fake.created_body if fake.created_body is not None else created)


class _Server(http.server.ThreadingHTTPServer):
    fake: FakeMedia


@pytest.fixture
def fake_media():
    server = _Server(("127.0.0.1", 0), _Handler)
    server.fake = FakeMedia(url=f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.fake
    server.shutdown()
    server.server_close()


@pytest.fixture
def silent_server():
    """A server that accepts connections and never answers (QA check 4012, AC-7 c)."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    accepted: list[socket.socket] = []
    stop = threading.Event()

    def accept():
        listener.settimeout(0.1)
        while not stop.is_set():
            try:
                accepted.append(listener.accept()[0])
            except TimeoutError:
                continue
            except OSError:
                return

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{listener.getsockname()[1]}"
    stop.set()
    thread.join(2)
    for conn in accepted:
        conn.close()
    listener.close()
