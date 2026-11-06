"""The local Mindshare's media API (CR-069): upload status, picture upload and read-back.

Only Stefan's local Mindshare is ever contacted (D42a): an address is accepted only when it is plain
``http://<loopback name>:<port>``, with ``localhost``, ``127.0.0.1`` and ``[::1]`` the three loopback names, and
anything else is refused before any connection (team default b: this Mac's network address is refused too). The
three names on one port are one server, keyed ``localhost:<port>`` (team default a).

``http.client`` is used rather than ``urllib.request``: it never follows a redirect, so a local server that
answers with a redirect elsewhere cannot send a request off this computer. Every request has a timeout.
The upload is ``POST /media/`` with the multipart parts ``file`` then ``type=image``, and no ``Origin`` header
(the server refuses a foreign Origin with 403). Facts from the read-only search of the Mindshare Content
Pipeline in P002 (CR-069 Notes for Developer).
"""

from __future__ import annotations

import http.client
import json
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_SERVER = "http://localhost:3042"
LOOPBACK = ("localhost", "127.0.0.1", "::1")
TIMEOUT_S = 10.0


class NotLocal(ValueError):
    """An address that is not the local Mindshare; refused before any connection."""


class MediaError(Exception):
    """The server refused, failed or gave an answer that cannot be read; nothing more is sent."""

    def __init__(self, message: str, status: int | None = None, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class Server:
    host: str  # one of LOOPBACK
    port: int

    @property
    def key(self) -> str:
        """The server as the clock record writes it: the three loopback names on one port are one server."""
        return f"localhost:{self.port}"


def parse_server(url: str) -> Server:
    """The local Mindshare at ``url``, or ``NotLocal``: only ``http://<loopback name>:<port>``, nothing more."""
    refused = NotLocal(f"{url!r}: uploads go to the local Mindshare only (http://localhost:<port>)")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise refused from exc
    if parts.scheme != "http" or parts.username is not None or parts.password is not None:
        raise refused
    if parts.hostname not in LOOPBACK or port is None or parts.path not in ("", "/") or parts.query or parts.fragment:
        raise refused
    return Server(parts.hostname, port)


def _request(
    server: Server, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None, *, timeout: float
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection(server.host, server.port, timeout=timeout)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    except (OSError, http.client.HTTPException) as exc:  # refused, timed out, dropped, garbled
        raise MediaError(f"{method} {path} on {server.key}: no answer ({type(exc).__name__}: {exc})") from exc
    finally:
        connection.close()


def _refused(method: str, path: str, server: Server, status: int, headers: dict[str, str], body: bytes) -> MediaError:
    retry_after = headers.get("retry-after")
    where = f" to {headers['location']} (not followed)" if 300 <= status < 400 and "location" in headers else ""
    wait = f", retry after {retry_after}" if retry_after is not None else ""
    text = body[:200].decode("utf-8", "replace")
    return MediaError(f"{method} {path} on {server.key}: {status}{where}{wait}: {text}", status, retry_after)


def _json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        return None


def health(server: Server, *, timeout: float = TIMEOUT_S) -> str:
    """The server's upload status, ``"open"`` or ``"paused"`` (``GET /media/health``)."""
    status, headers, body = _request(server, "GET", "/media/health", timeout=timeout)
    if status != 200:
        raise _refused("GET", "/media/health", server, status, headers, body)
    answer = _json(body)
    uploads = answer.get("uploads") if isinstance(answer, dict) else None
    if uploads not in ("open", "paused"):
        raise MediaError(f"GET /media/health on {server.key}: unreadable answer {body[:200]!r}", status)
    return str(uploads)


def upload_picture(server: Server, path: Path, *, timeout: float = TIMEOUT_S) -> str:
    """Upload one picture file as it is on disk; its picture ID on this server (``POST /media/``, 201)."""
    boundary = f"sc2mindshare-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = b"".join(
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            path.read_bytes(),
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\nimage\r\n--{boundary}--\r\n'.encode(),
        )
    )
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))}
    status, answer_headers, answer = _request(server, "POST", "/media/", body, headers, timeout=timeout)
    if status != 201:
        raise _refused("POST", "/media/", server, status, answer_headers, answer)
    created = _json(answer)
    picture_id = created.get("_id") if isinstance(created, dict) else None
    if not isinstance(picture_id, str) or not picture_id:
        raise MediaError(f"POST /media/ on {server.key}: 201 without an _id: {answer[:200]!r}", status)
    return picture_id


def fetch_picture(server: Server, picture_id: str, *, timeout: float = TIMEOUT_S) -> bytes:
    """The picture's bytes as the server serves them (``GET /media/resource/<id>``)."""
    path = f"/media/resource/{picture_id}"
    status, headers, body = _request(server, "GET", path, timeout=timeout)
    if status != 200:
        raise _refused("GET", path, server, status, headers, body)
    return body
