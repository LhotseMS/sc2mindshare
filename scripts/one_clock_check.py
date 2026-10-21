#!/usr/bin/env python3
"""The one-picture check (CR-069 AC-1): one clock on Stefan's local Mindshare, before anything else is built.

    scripts/py-env .venv/bin/python scripts/one_clock_check.py --config-root "MS SC" --out <one-clock.json> [--live]

Without ``--live`` (the default) it is a dry run: it asks the local Mindshare for its upload status once, says
what it would upload and uploads nothing, writing nothing. With ``--live`` (only with Stefan's OK) it uploads the
one clock picture (``<config root>/ClockImages/0-10.png`` by default), reads the picture back by its ID and
compares the bytes with the file, and writes an import file holding that single clock node in the new form
(``nodeImage`` = the picture ID, ``name`` = the file name, ``ID`` = ``clock-0-10-1``). The last line printed is
a JSON report (server, picture ID, status, both sha256s, the file written and its sha256) for QA's record.

Exit codes: 0 done (or a dry run); 2 a usage error (no such clock file, an address that is not the local
Mindshare); 4 refused or failed (uploads paused, no answer, a refused upload, bytes read back that differ).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sc2mindshare.export.mindshare_json import load_config, to_json
from sc2mindshare.layout.profile import Profile
from sc2mindshare.media.client import DEFAULT_SERVER, MediaError, NotLocal, fetch_picture, health, parse_server, upload_picture

PROG = "one_clock_check"
EXIT_USAGE = 2
EXIT_REFUSED = 4


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clock_document(clock: str, picture_id: str) -> dict[str, Any]:
    """An import document with the one clock node, in the form CR-069 gives clock nodes."""
    config = load_config()
    node = {
        "type": "image",
        "name": clock,
        "ID": f"clock-{clock.removesuffix('.png')}-1",
        "nodeImage": picture_id,
        "size": list(Profile().clock_size),
        "properties": {},
        "position": {"x": 0.0, "y": 0.0, "z": 0.01},
    }
    return {
        "visuals": config["visuals"],
        "detail": config["detail"],
        "dataTypes": config["dataTypes"],
        "nodes": [node],
        "links": [],
    }


def _fail(code: int, message: str) -> int:
    print(f"{PROG}: {message}", file=sys.stderr)
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=PROG, description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--config-root", type=Path, default=None, help="the MS SC folder (default: MS_SC_ROOT)")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"the local Mindshare (default {DEFAULT_SERVER})")
    parser.add_argument("--clock", default="0-10.png", help="the clock picture under ClockImages/ (default 0-10.png)")
    parser.add_argument("--out", required=True, type=Path, help="the one-node import file to write (with --live)")
    parser.add_argument("--live", action="store_true", help="really upload (default: a dry run that uploads nothing)")
    args = parser.parse_args(argv)

    config_root = args.config_root or (Path(os.environ["MS_SC_ROOT"]) if os.environ.get("MS_SC_ROOT") else None)
    if config_root is None:
        return _fail(EXIT_USAGE, "no config root: pass --config-root or set MS_SC_ROOT")
    try:
        server = parse_server(args.server)
    except NotLocal as exc:
        return _fail(EXIT_USAGE, str(exc))
    picture = config_root / "ClockImages" / args.clock
    if not picture.is_file():
        return _fail(EXIT_USAGE, f"no clock picture {picture}")
    data = picture.read_bytes()

    try:
        uploads = health(server)
        print(f"{server.key}: uploads: {uploads}")
        if not args.live:
            print(f"dry run: would upload {args.clock} ({len(data)} bytes, sha256 {_sha256(data)}) to {server.key}")
            print("nothing uploaded; run again with --live to upload it")
            return 0
        if uploads != "open":
            return _fail(EXIT_REFUSED, f"{server.key}: uploads are {uploads}; nothing uploaded")
        picture_id = upload_picture(server, picture)
        served = fetch_picture(server, picture_id)
    except MediaError as exc:
        return _fail(EXIT_REFUSED, str(exc))
    if _sha256(served) != _sha256(data):
        return _fail(
            EXIT_REFUSED,
            f"picture {picture_id}: the bytes read back differ from {picture} "
            f"(sha256 {_sha256(served)} != {_sha256(data)}); no import file written",
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_json(clock_document(args.clock, picture_id)), encoding="utf-8")
    report = {
        "server": server.key,
        "clock": args.clock,
        "pictureID": picture_id,
        "status": 201,
        "sha256_file": _sha256(data),
        "sha256_served": _sha256(served),
        "out": str(args.out),
        "sha256_out": _sha256(args.out.read_bytes()),
    }
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
