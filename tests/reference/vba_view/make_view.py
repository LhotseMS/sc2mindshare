#!/usr/bin/env python3
"""Produce a view JSON (G-VIEW-1) from a legacy events CSV with the VBA view port (CR-006).

    scripts/py-env .venv/bin/python tests/reference/vba_view/make_view.py EVENTS.csv OUT.json \
        [--encoding cp1250] [--rejoin-raw-newlines]

The config parts (visuals, detail, dataTypes) come from src/sc2mindshare/config/ (CR-005).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parents[2] / "src" / "sc2mindshare" / "config"

_spec = importlib.util.spec_from_file_location("vba_view", HERE / "vba_view.py")
assert _spec and _spec.loader
vba_view = importlib.util.module_from_spec(_spec)
sys.modules["vba_view"] = vba_view
_spec.loader.exec_module(vba_view)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("events", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--rejoin-raw-newlines", action="store_true")
    args = parser.parse_args(argv)

    def config(name: str) -> object:
        return json.loads((CONFIG / name).read_text(encoding="utf-8"))

    view = vba_view.build_view(
        args.events.read_text(encoding=args.encoding),
        config("visuals.json"),
        config("details.json"),
        config("data_types.json"),
        rejoin_raw_newlines=args.rejoin_raw_newlines,
    )
    args.out.write_text(json.dumps(view, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(view['nodes'])} nodes, {len(view['links'])} links")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
