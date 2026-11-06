#!/usr/bin/env python3
"""Make ``tests/golden/clock-record-fixture.csv`` (CR-069), the clock record the current goldens are built from.

    scripts/py-env .venv/bin/python tests/golden/make_clock_record_fixture.py [--check]

One row per clock picture in ``MS SC/ClockImages`` (480, ``0-00.png`` to ``79-50.png``), in the record's own
format (``media.clocks``): the picture ID is made up, ``uuid5`` of a fixed namespace and the file name, so it is
stable and never a real server's; the server is ``localhost:3042``; the upload time is fixed; the sha256 is the
file's. Run once when the fixture was made; ``--check`` confirms the committed file is what it makes.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "clock-record-fixture.csv"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/LhotseMS/sc2mindshare/CR-069/clock-record-fixture")
SERVER = "localhost:3042"
UPLOADED_AT = "2026-10-21T00:00:00+00:00"
HEADER = "imageName,imageID,server,uploadedAt,sha256"
CLOCK_FILE = re.compile(r"^\d+-\d{2}\.png$")  # the folder also holds player2BattleImageDivider.png


def _root() -> Path:
    d = HERE
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


def _minutes_seconds(name: str) -> tuple[int, int]:
    m, s = name.removesuffix(".png").split("-")
    return int(m), int(s)


def fixture_text(images: Path) -> str:
    names = sorted((p.name for p in images.glob("*.png") if CLOCK_FILE.match(p.name)), key=_minutes_seconds)
    rows = [HEADER]
    for name in names:
        sha = hashlib.sha256((images / name).read_bytes()).hexdigest()
        rows.append(f"{name},{uuid.uuid5(NAMESPACE, name)},{SERVER},{UPLOADED_AT},{sha}")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="compare with the committed fixture; write nothing")
    args = parser.parse_args(argv)
    text = fixture_text(_root() / "MS SC" / "ClockImages")
    if args.check:
        same = FIXTURE.read_text(encoding="utf-8") == text
        print("the fixture is what the script makes" if same else "the fixture differs from what the script makes")
        return 0 if same else 1
    FIXTURE.write_text(text, encoding="utf-8")
    print(f"wrote {FIXTURE} ({text.count(chr(10)) - 1} clocks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
