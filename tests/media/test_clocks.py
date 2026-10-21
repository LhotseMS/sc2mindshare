"""CR-069: the clock record and the upload run (``sc2mindshare.media.clocks``), against the fake server.

AC-2 to AC-8 at the level of the run: which clocks are missing, what a dry run does, what a confirmed run uploads
and records, and how it stops. Pacing and Retry-After go through an injected sleep, so no test sleeps for real
(QA check 4011): the sleeps are asserted instead. The command around it is in test_upload_clocks_cli.py.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import pytest

from sc2mindshare.media.client import parse_server
from sc2mindshare.media.clocks import (
    EXIT_LIMIT,
    EXIT_REFUSED,
    HEADER,
    RECORD_FILE,
    RecordRow,
    RecordUnreadable,
    append_row,
    clock_map,
    read_record,
    upload_clocks,
)

NAMES = [f"{m}-{s:02d}.png" for m in range(2) for s in range(0, 60, 10)]  # 0-00.png .. 1-50.png, 12 clocks


@pytest.fixture
def images(tmp_path):
    folder = tmp_path / "ClockImages"
    folder.mkdir()
    for i, name in enumerate(NAMES):
        (folder / name).write_bytes(b"\x89PNG clock " + name.encode() + bytes([i]) * 40)
    return folder


@pytest.fixture
def record(tmp_path):
    return tmp_path / RECORD_FILE


class Recorder:
    def __init__(self):
        self.lines: list[str] = []
        self.sleeps: list[float] = []

    def say(self, line: str) -> None:
        self.lines.append(line)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _run(fake, images, record, needed=NAMES, live=True, **kwargs):
    rec = Recorder()
    result = upload_clocks(
        parse_server(fake.url),
        needed,
        images,
        record,
        live=live,
        say=rec.say,
        sleep=rec.sleep,
        now=lambda: "2026-10-21T10:00:00+00:00",
        **kwargs,
    )
    return result, rec


def _row(name, image_id="id-" + "x", server="localhost:3042"):
    return RecordRow(name, image_id, server, "2026-10-20T00:00:00+00:00", "0" * 64)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- the record ------------------------------------------------------------------------------------------------------


def test_the_record_is_absent_by_default(record):
    assert read_record(record) == ()


def test_rows_are_appended_with_a_header_once(record):
    append_row(record, _row("0-10.png", "a"))
    append_row(record, _row("0-20.png", "b"))
    assert record.read_text(encoding="utf-8").splitlines() == [
        ",".join(HEADER),
        "0-10.png,a,localhost:3042,2026-10-20T00:00:00+00:00," + "0" * 64,
        "0-20.png,b,localhost:3042,2026-10-20T00:00:00+00:00," + "0" * 64,
    ]
    assert read_record(record) == (_row("0-10.png", "a"), _row("0-20.png", "b"))


@pytest.mark.parametrize(
    "text",
    [
        "imageName,imageID\n0-10.png,a\n",  # another header
        ",".join(HEADER) + "\n0-10.png,a,localhost:3042\n",  # a short row
        ",".join(HEADER) + "\n0-10.png,,localhost:3042,t," + "0" * 64 + "\n",  # an empty ID
        b"\xff\xfe\x00".decode("latin-1"),  # not UTF-8 text
    ],
)
def test_an_unreadable_record_raises(record, text):
    record.write_bytes(text.encode("latin-1"))
    with pytest.raises(RecordUnreadable):
        read_record(record)


def test_only_this_servers_rows_count():
    rows = (_row("0-10.png", "a", "localhost:3042"), _row("0-20.png", "b", "localhost:3043"))
    assert clock_map(rows, "localhost:3042") == {"0-10.png": "a"}
    assert clock_map(rows, "localhost:3043") == {"0-20.png": "b"}


# --- AC-2: a dry run ---------------------------------------------------------------------------------------------------


def test_a_dry_run_lists_what_is_missing_and_uploads_nothing(fake_media, images, record):
    result, rec = _run(fake_media, images, record, live=False)
    assert result.exit_code == 0
    assert [(r.method, r.path) for r in fake_media.requests] == [("GET", "/media/health")]
    assert not record.exists()  # no empty file either
    assert "uploads: open" in rec.text
    assert result.missing == NAMES
    assert all(name in rec.text for name in NAMES)
    assert "dry run" in rec.text and "--live" in rec.text


def test_a_dry_run_shows_a_paused_server(fake_media, images, record):
    fake_media.health_body = b'{"uploads": "paused"}'
    result, rec = _run(fake_media, images, record, live=False)
    assert result.exit_code == 0 and "uploads: paused" in rec.text and fake_media.posts() == []


# --- AC-3, AC-4: a confirmed run -----------------------------------------------------------------------------------------


def test_a_confirmed_run_uploads_each_missing_clock_once_and_records_it(fake_media, images, record):
    result, rec = _run(fake_media, images, record)
    assert result.exit_code == 0
    posts = fake_media.posts()
    assert [p.parts()[0][1] for p in posts] == NAMES
    assert [hashlib.sha256(p.parts()[0][2]).hexdigest() for p in posts] == [_sha(images / n) for n in NAMES]
    rows = read_record(record)
    assert [r.image_name for r in rows] == NAMES
    assert {r.image_id for r in rows} == set(fake_media.stored)
    assert {r.server for r in rows} == {"localhost:" + fake_media.url.rsplit(":", 1)[1]}
    assert [r.sha256 for r in rows] == [_sha(images / n) for n in NAMES]
    assert {r.uploaded_at for r in rows} == {"2026-10-21T10:00:00+00:00"}
    assert f"uploaded {len(NAMES)}" in rec.text
    assert rec.sleeps == [3.5] * (len(NAMES) - 1)  # paced between uploads, never before the first


def test_a_full_record_uploads_nothing(fake_media, images, record):
    _run(fake_media, images, record)
    fake_media.requests.clear()
    result, rec = _run(fake_media, images, record)
    assert result.exit_code == 0 and fake_media.posts() == [] and "nothing to upload" in rec.text


def test_a_partial_record_uploads_exactly_the_rest(fake_media, images, record):
    for name in NAMES[:5]:
        append_row(record, _row(name, "kept-" + name, "localhost:" + fake_media.url.rsplit(":", 1)[1]))
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == 0
    assert [p.parts()[0][1] for p in fake_media.posts()] == NAMES[5:]
    assert [r.image_name for r in read_record(record)] == NAMES


# --- AC-5: another server's rows ---------------------------------------------------------------------------------------


def test_rows_of_another_port_count_as_missing(fake_media, images, record):
    port = int(fake_media.url.rsplit(":", 1)[1])
    for name in NAMES:
        append_row(record, _row(name, "elsewhere", f"localhost:{port + 1}"))
    append_row(record, _row(NAMES[0], "here", f"localhost:{port}"))
    result, _ = _run(fake_media, images, record, live=False)
    assert result.missing == NAMES[1:]


def test_localhost_and_127_0_0_1_on_one_port_are_one_server(fake_media, images, record):
    """The fake listens on 127.0.0.1; rows written while it was called localhost are its rows (team default a)."""
    port = int(fake_media.url.rsplit(":", 1)[1])
    for name in NAMES:
        append_row(record, _row(name, "here", f"localhost:{port}"))
    result, _ = _run(fake_media, images, record, live=False)
    assert result.missing == []


# --- AC-7: limits, lost server, the cap ----------------------------------------------------------------------------------


class Script:
    """Upload answers by POST number (1-based); the fake's own answer otherwise."""

    def __init__(self, fake, answers):
        self.fake, self.answers, self.count = fake, answers, 0

    def install(self, monkeypatch):
        from sc2mindshare.media import clocks

        real = clocks.upload_picture

        def scripted(server, path, **kw):
            self.count += 1
            answer = self.answers.get(self.count)
            if answer is not None:
                self.fake.upload_status, self.fake.upload_headers = answer
            else:
                self.fake.upload_status, self.fake.upload_headers = 201, {}
            return real(server, path, **kw)

        monkeypatch.setattr(clocks, "upload_picture", scripted)


def test_a_429_waits_the_servers_retry_after_once_then_goes_on(fake_media, images, record, monkeypatch):
    Script(fake_media, {3: (429, {"Retry-After": "61"})}).install(monkeypatch)
    result, rec = _run(fake_media, images, record)
    assert result.exit_code == 0
    assert 61.0 in rec.sleeps and rec.sleeps.count(61.0) == 1
    assert [r.image_name for r in read_record(record)] == NAMES


def test_a_second_429_stops_cleanly_with_the_servers_retry_time(fake_media, images, record, monkeypatch):
    Script(fake_media, {4: (429, {"Retry-After": "61"}), 5: (429, {"Retry-After": "61"})}).install(monkeypatch)
    result, rec = _run(fake_media, images, record)
    assert result.exit_code == EXIT_LIMIT == 3
    assert [r.image_name for r in read_record(record)] == NAMES[:3]  # every clock already uploaded is recorded
    assert result.left == NAMES[3:]
    assert f"{len(NAMES) - 3} left" in result.message
    assert "61" in result.message and "60 s" not in result.message  # the server's own time, never a fixed one
    assert "Traceback" not in rec.text and "\n" not in result.message
    fake_media.requests.clear()
    again, _ = _run(fake_media, images, record)  # the next run uploads only the clocks left
    assert again.exit_code == 0
    assert [p.parts()[0][1] for p in fake_media.posts()] == NAMES[3:]


def test_a_503_stops_cleanly(fake_media, images, record, monkeypatch):
    Script(fake_media, {2: (503, {})}).install(monkeypatch)
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == EXIT_LIMIT
    assert [r.image_name for r in read_record(record)] == NAMES[:1]
    assert "503" in result.message and f"{len(NAMES) - 1} left" in result.message


@pytest.mark.parametrize("status", [415, 413, 400])
def test_a_refused_file_is_reported_and_the_run_goes_on(fake_media, images, record, monkeypatch, status):
    Script(fake_media, {2: (status, {})}).install(monkeypatch)
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == EXIT_REFUSED == 4
    assert [r.image_name for r in read_record(record)] == [n for n in NAMES if n != NAMES[1]]
    assert NAMES[1] in result.message and str(status) in result.message


def test_a_201_without_an_id_records_nothing_and_stops(fake_media, images, record):
    fake_media.created_body = b'{"type": "image"}'
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == EXIT_REFUSED
    assert not record.exists() and len(fake_media.posts()) == 1


def test_the_per_run_cap_stops_and_says_how_many_are_left(fake_media, images, record):
    result, _ = _run(fake_media, images, record, max_uploads=5)
    assert result.exit_code == EXIT_LIMIT
    assert len(fake_media.posts()) == 5 and len(read_record(record)) == 5
    assert f"{len(NAMES) - 5} left" in result.message


def test_the_default_cap_is_95(fake_media, tmp_path, record):
    folder = tmp_path / "many"
    folder.mkdir()
    names = [f"{m}-{s:02d}.png" for m in range(20) for s in range(0, 60, 10)]  # 120 synthetic clocks
    for name in names:
        (folder / name).write_bytes(name.encode())
    result, _ = _run(fake_media, folder, record, needed=names)
    assert result.exit_code == EXIT_LIMIT
    assert len(fake_media.posts()) == 95 and "25 left" in result.message


def test_a_server_that_stops_answering_ends_the_run(silent_server, images, record):
    """AC-7 c: the client's timeout ends it; a join limit turns a hang into a failure."""
    outcome = []

    def call():
        rec = Recorder()
        outcome.append(
            upload_clocks(
                parse_server(silent_server), NAMES, images, record, live=True, say=rec.say, sleep=rec.sleep, timeout=0.5
            )
        )

    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    thread.join(10)
    assert not thread.is_alive()
    assert outcome[0].exit_code == EXIT_REFUSED  # the health check got no answer: nothing was uploaded


def test_the_record_is_written_per_upload(fake_media, images, record, monkeypatch):
    """AC-7 d: when the connection drops after upload k, the record already has k rows."""
    from sc2mindshare.media import clocks

    real = clocks.upload_picture
    calls = {"n": 0}

    def dropping(server, path, **kw):
        calls["n"] += 1
        if calls["n"] == 4:
            assert len(read_record(record)) == 3  # written before the next upload starts
            raise clocks.MediaError("POST /media/: no answer (connection reset)")
        return real(server, path, **kw)

    monkeypatch.setattr(clocks, "upload_picture", dropping)
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == EXIT_LIMIT
    assert len(read_record(record)) == 3


# --- AC-8: nothing is uploaded when the server is closed or the record unreadable -------------------------------------------


@pytest.mark.parametrize(
    "setup",
    [
        {"health_body": b'{"uploads": "paused"}'},
        {"health_body": b"<html>"},
        {"health_status": 500},
    ],
    ids=["paused", "non-json", "error"],
)
def test_nothing_is_uploaded_when_the_server_is_not_open(fake_media, images, record, setup):
    append_row(record, _row("9-00.png", "a", "localhost:1"))
    before = _sha(record)
    for name, value in setup.items():
        setattr(fake_media, name, value)
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == EXIT_REFUSED
    assert fake_media.posts() == [] and _sha(record) == before
    assert result.message


def test_nothing_is_uploaded_when_the_connection_is_refused(images, record):
    rec = Recorder()
    result = upload_clocks(parse_server("http://127.0.0.1:9"), NAMES, images, record, live=True, say=rec.say, sleep=rec.sleep)
    assert result.exit_code == EXIT_REFUSED and not record.exists()


def test_an_unreadable_record_stops_before_any_request_and_is_left_as_it_is(fake_media, images, record):
    record.write_text("not,a,record\n", encoding="utf-8")
    before = _sha(record)
    result, _ = _run(fake_media, images, record)
    assert result.exit_code == EXIT_REFUSED
    assert fake_media.requests == [] and _sha(record) == before
    assert "record" in result.message
