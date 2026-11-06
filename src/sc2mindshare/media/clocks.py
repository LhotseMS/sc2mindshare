"""The clock record and the upload run (CR-069): which clock pictures the local Mindshare has, and uploading the rest.

The record, ``MS SC/ClockImageRecord.csv``, holds one row per accepted upload: the clock's file name, its picture
ID, the server (``localhost:<port>``), the upload time and the file's sha256 (for audit). Rows are appended and
flushed to disk one at a time, so a run that stops keeps every clock it uploaded; the file is never rewritten. A
row counts only for its own server. Absent means no clock has a picture yet; a file that cannot be read stops an
upload run and is left exactly as it is.

``upload_clocks`` is a dry run unless ``live``: it asks for the upload status once, says which of the needed
clocks are missing on this server, and with ``live`` uploads them one at a time, ``pace_s`` apart and at most
``max_uploads`` in a run. A 429 waits the server's Retry-After once and tries again; a second 429, a 503, a
server that stops answering, a Retry-After over 120 s or the cap stop the run cleanly (``EXIT_LIMIT``, 3), and the next run resumes from
the record. A file the server refuses (400, 413, 415) is reported and skipped; such a run, a paused or unreadable
server, a 201 without an ``_id`` or an unreadable record end with ``EXIT_REFUSED`` (4).
"""

from __future__ import annotations

import csv
import datetime
import email.utils
import hashlib
import io
import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sc2mindshare.media.client import TIMEOUT_S, MediaError, Server, health, upload_picture

RECORD_FILE = "ClockImageRecord.csv"
HEADER = ("imageName", "imageID", "server", "uploadedAt", "sha256")
EXIT_DONE = 0
EXIT_LIMIT = 3  # stopped cleanly at a limit (429 twice, 503, no answer, the per-run cap); run again later
EXIT_REFUSED = 4  # refused or failed (paused, unreadable answer or record, a file refused, a 201 without _id)
MAX_UPLOADS = 95  # under the server's 100 a day per address
PACE_S = 3.5  # under its 20 a minute
FILE_REFUSED = (400, 413, 415)
MAX_RETRY_WAIT_S = 120.0  # a longer Retry-After (the per-address cap is a rolling 24 h) stops the run instead


class RecordUnreadable(Exception):
    """The clock record exists but is not a record this code wrote."""


@dataclass(frozen=True)
class RecordRow:
    image_name: str
    image_id: str
    server: str
    uploaded_at: str
    sha256: str


def read_record(path: Path) -> tuple[RecordRow, ...]:
    """The record's rows; none when the file is absent."""
    if not path.exists():
        return ()
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RecordUnreadable(f"{path}: {exc}") from exc
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or tuple(rows[0]) != HEADER:
        raise RecordUnreadable(f"{path}: the header is not {','.join(HEADER)}")
    out = []
    for number, row in enumerate(rows[1:], start=2):
        if len(row) != len(HEADER) or not all(row):
            raise RecordUnreadable(f"{path} line {number}: expected {len(HEADER)} non-empty fields")
        out.append(RecordRow(*row))
    return tuple(out)


def clock_map(rows: Sequence[RecordRow], server_key: str) -> dict[str, str]:
    """File name -> picture ID, from this server's rows only (a later row wins)."""
    return {row.image_name: row.image_id for row in rows if row.server == server_key}


def append_row(path: Path, row: RecordRow) -> None:
    """One row more, flushed to disk before the next upload starts; the header first when the file is new."""
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        if new:
            writer.writerow(HEADER)
        writer.writerow((row.image_name, row.image_id, row.server, row.uploaded_at, row.sha256))
        f.flush()
        os.fsync(f.fileno())


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


def _retry_seconds(retry_after: str | None) -> float | None:
    """The server's Retry-After in seconds (a number or an HTTP date); None when it gave none or none readable."""
    if retry_after is None:
        return None
    if retry_after.strip().isdigit():
        return float(retry_after.strip())
    try:
        when = email.utils.parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:  # "-0000" (RFC 5322: UTC, source unknown) parses as naive
        when = when.replace(tzinfo=datetime.UTC)
    return max(0.0, (when - datetime.datetime.now(datetime.UTC)).total_seconds())


@dataclass
class UploadRun:
    exit_code: int
    message: str = ""  # one line: why the run stopped (empty when it finished)
    missing: list[str] = field(default_factory=list)  # needed and not recorded for this server, at the start
    uploaded: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)  # "<file> (<status>)" the server refused (400, 413, 415)
    left: list[str] = field(default_factory=list)  # still missing when the run stopped


def upload_clocks(
    server: Server,
    needed: Sequence[str],
    images: Path,
    record: Path,
    *,
    live: bool,
    max_uploads: int = MAX_UPLOADS,
    pace_s: float = PACE_S,
    say: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], str] = _now,
    timeout: float = TIMEOUT_S,
) -> UploadRun:
    """Upload the needed clocks this server has no picture for (a dry run unless ``live``)."""
    try:
        recorded: Mapping[str, str] = clock_map(read_record(record), server.key)
    except RecordUnreadable as exc:
        return UploadRun(EXIT_REFUSED, f"cannot read the clock record ({exc}): nothing uploaded; the file is left as it is")
    try:
        uploads = health(server, timeout=timeout)
    except MediaError as exc:
        return UploadRun(EXIT_REFUSED, f"{exc}: nothing uploaded")
    say(f"{server.key}: uploads: {uploads}")
    missing = [name for name in dict.fromkeys(needed) if name not in recorded]
    run = UploadRun(EXIT_DONE, missing=missing, left=list(missing))
    say(f"{len(needed)} clocks needed, {len(needed) - len(missing)} already recorded for {server.key}, {len(missing)} to upload")
    if not missing:
        say("nothing to upload")
        return run
    for name in missing:
        say(f"  {name}")
    if not live:
        say("dry run: nothing uploaded; run again with --live to upload them")
        return run
    if uploads != "open":
        run.exit_code, run.message = EXIT_REFUSED, f"{server.key}: uploads are {uploads}; nothing uploaded"
        return run

    def stop(code: int, why: str) -> UploadRun:
        run.exit_code = code
        left = f"{len(run.left)} left; run again to upload the rest" if run.left else "none left"
        run.message = f"stopped after uploading {len(run.uploaded)}: {why}; {left}"
        return run

    for index, name in enumerate(missing):
        if len(run.uploaded) + len(run.refused) >= max_uploads:
            return stop(EXIT_LIMIT, f"the per-run cap of {max_uploads} uploads is reached")
        if index:
            sleep(pace_s)
        path = images / name
        try:
            try:
                picture_id = upload_picture(server, path, timeout=timeout)
            except MediaError as first:
                wait = _retry_seconds(first.retry_after) if first.status == 429 else None
                if wait is None or wait > MAX_RETRY_WAIT_S:  # no wait the server named, or one too long: stop
                    raise
                say(f"  {name}: 429, waiting the server's Retry-After ({first.retry_after}) once")
                sleep(wait)
                picture_id = upload_picture(server, path, timeout=timeout)
        except MediaError as exc:
            if exc.status in FILE_REFUSED:
                run.refused.append(f"{name} ({exc.status})")
                run.left.remove(name)
                say(f"  {name}: refused by the server ({exc.status}); skipped")
                continue
            if exc.status in (429, 503) or exc.status is None:
                retry = f"; the server says retry after {exc.retry_after}" if exc.retry_after else ""
                return stop(EXIT_LIMIT, f"{exc}{retry}")
            return stop(EXIT_REFUSED, str(exc))
        append_row(record, RecordRow(name, picture_id, server.key, now(), hashlib.sha256(path.read_bytes()).hexdigest()))
        run.uploaded.append(name)
        run.left.remove(name)
        say(f"  {name}: {picture_id}")
    say(f"uploaded {len(run.uploaded)} to {server.key}")
    if run.refused:
        return stop(EXIT_REFUSED, f"the server refused {', '.join(run.refused)}")
    return run
