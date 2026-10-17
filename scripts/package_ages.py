#!/usr/bin/env python3
"""Report the age of every pinned package in one or more lock files.

The project rule: no package (direct or transitive) younger than 14 days.
Each lock is a ``pip freeze`` style file of ``name==version`` lines. For each
pin, the upload date is the newest file of that release on PyPI.

    scripts/py-env .venv/bin/python scripts/package_ages.py requirements/dev.lock

Exit code 0 when every package is at least 14 days old, 1 otherwise, 2 on a
malformed lock. Standard library only.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_AGE_DAYS = 14
PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"

Fetch = Callable[[str, str], dt.datetime]


@dataclass(frozen=True)
class Row:
    name: str
    version: str
    uploaded: dt.datetime
    age_days: int
    too_young: bool


def parse_lock(text: str) -> list[tuple[str, str]]:
    pins = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, sep, version = line.partition("==")
        if not sep or not name or not version or line.startswith("-"):
            raise ValueError(f"not pinned with ==: {line}")
        pins.append((name.strip(), version.strip()))
    return pins


def newest_upload(release: dict[str, Any]) -> dt.datetime:
    times = [f["upload_time_iso_8601"] for f in release.get("urls", [])]
    if not times:
        raise ValueError("release has no uploaded files")
    return max(dt.datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times)


def fetch_from_pypi(name: str, version: str) -> dt.datetime:
    url = PYPI_URL.format(name=name, version=version)
    with urllib.request.urlopen(url, timeout=30) as response:
        return newest_upload(json.load(response))


def report(pins: Sequence[tuple[str, str]], fetch: Fetch, now: dt.datetime) -> list[Row]:
    rows = []
    for name, version in pins:
        uploaded = fetch(name, version)
        age = (now - uploaded).days
        rows.append(Row(name, version, uploaded, age, age < MIN_AGE_DAYS))
    return rows


def format_rows(rows: Sequence[Row]) -> str:
    lines = [
        "| Package | Version | Uploaded (UTC) | Age (days) | OK |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        ok = "NO" if r.too_young else "yes"
        lines.append(f"| {r.name} | {r.version} | {r.uploaded:%Y-%m-%d} | {r.age_days} | {ok} |")
    return "\n".join(lines)


def main(argv: Sequence[str], fetch: Fetch = fetch_from_pypi, now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.now(dt.UTC)
    try:
        pins = [pin for path in argv for pin in parse_lock(Path(path).read_text())]
    except ValueError as exc:
        print(f"package_ages: {exc}", file=sys.stderr)
        return 2
    rows = report(pins, fetch, now)
    print(format_rows(rows))
    young = [r for r in rows if r.too_young]
    if young:
        print(f"\n{len(young)} package(s) younger than {MIN_AGE_DAYS} days")
        return 1
    print(f"\nall {len(rows)} package(s) are at least {MIN_AGE_DAYS} days old")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
