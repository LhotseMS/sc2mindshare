#!/usr/bin/env python3
"""The one-picture check (CR-069 AC-1): one clock on Stefan's local Mindshare, before anything else is built.

    scripts/py-env .venv/bin/python scripts/one_clock_check.py --config-root "MS SC" --out <one-clock.json>
        [--live | --picture-id <id>]

Without ``--live`` (the default) it is a dry run: it asks the local Mindshare for its upload status once, says
what it would upload and uploads nothing, writing nothing. With ``--live`` (only with Stefan's OK) it uploads the
one clock picture (``<config root>/ClockImages/0-10.png`` by default) exactly as it is on disk. With
``--picture-id`` it uploads nothing and uses a picture uploaded before. Either way it then reads the picture back
by its ID and checks that it is the same picture: the same size and the same pixels, decoded (D51a: the server
re-encodes the PNG it stores, so the bytes differ). Then it writes an import file holding that single clock node
in the new form (``nodeImage`` = the picture ID, ``name`` = the file name, ``ID`` = ``clock-0-10-1``). The last
line printed is a JSON report for QA's record: server, picture ID, the upload's status, the file's sha256, the
served sha256 (audit only), the picture comparison, and the file written with its sha256.

Exit codes: 0 done (or a dry run); 2 a usage error (no such clock file, an address that is not the local
Mindshare, ``--live`` with ``--picture-id``); 4 refused or failed (uploads paused, no answer, a refused upload,
a picture read back that differs).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from sc2mindshare.export.mindshare_json import load_config, to_json
from sc2mindshare.layout.profile import Profile
from sc2mindshare.media.client import DEFAULT_SERVER, MediaError, NotLocal, fetch_picture, health, parse_server, upload_picture

PROG = "one_clock_check"
EXIT_USAGE = 2
EXIT_REFUSED = 4


class PictureDiffers(Exception):
    """The picture read back is not the file's picture (another size, other pixels, or no picture)."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def same_picture(expected: bytes, served: bytes) -> str:
    """How the served picture compares with the file's, decoded: ``identical: 80x48 RGBA, same pixels``, or
    ``PictureDiffers``. Both are compared as RGBA, so a lossless re-encoding (another compression, extra chunks)
    is the same picture."""
    try:
        with Image.open(io.BytesIO(expected)) as a, Image.open(io.BytesIO(served)) as b:
            if a.size != b.size:
                raise PictureDiffers(f"size differs: {a.size[0]}x{a.size[1]} on disk, {b.size[0]}x{b.size[1]} served")
            if a.convert("RGBA").tobytes() != b.convert("RGBA").tobytes():
                raise PictureDiffers(f"pixels differ ({a.size[0]}x{a.size[1]}, compared as RGBA)")
            return f"identical: {a.size[0]}x{a.size[1]} {a.mode}, same pixels"
    except (UnidentifiedImageError, OSError) as exc:
        raise PictureDiffers(f"not a picture: {exc}") from exc


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
    parser.add_argument("--out", required=True, type=Path, help="the one-node import file to write")
    parser.add_argument("--live", action="store_true", help="really upload (default: a dry run that uploads nothing)")
    parser.add_argument("--picture-id", default=None, help="use this picture, uploaded before: no upload")
    args = parser.parse_args(argv)

    if args.live and args.picture_id:
        return _fail(EXIT_USAGE, "--live uploads a new picture and --picture-id uses one uploaded before: give one")
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

    status: int | None = None
    try:
        uploads = health(server)
        print(f"{server.key}: uploads: {uploads}")
        if args.picture_id:
            picture_id = str(args.picture_id)
        elif not args.live:
            print(f"dry run: would upload {args.clock} ({len(data)} bytes, sha256 {_sha256(data)}) to {server.key}")
            print("nothing uploaded; run again with --live to upload it")
            return 0
        elif uploads != "open":
            return _fail(EXIT_REFUSED, f"{server.key}: uploads are {uploads}; nothing uploaded")
        else:
            picture_id, status = upload_picture(server, picture), 201
        served = fetch_picture(server, picture_id)
    except MediaError as exc:
        return _fail(EXIT_REFUSED, str(exc))
    try:
        comparison = same_picture(data, served)
    except PictureDiffers as exc:
        return _fail(EXIT_REFUSED, f"picture {picture_id} is not {picture}: {exc}; no import file written")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_json(clock_document(args.clock, picture_id)), encoding="utf-8")
    report = {
        "server": server.key,
        "clock": args.clock,
        "pictureID": picture_id,
        "status": status,
        "uploaded": status == 201,
        "sha256_file": _sha256(data),
        "sha256_served": _sha256(served),
        "picture": comparison,
        "out": str(args.out),
        "sha256_out": _sha256(args.out.read_bytes()),
    }
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
