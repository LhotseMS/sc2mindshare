"""Regenerate the decoding goldens (tests/decoding/golden/<replay>.decoded.json).

Only on purpose: a change to a golden is part of the task that changes the output, and the
reviewer checks the diff against the task record's expected delta.

    scripts/py-env .venv/bin/python tools/decoding/regen_golden.py
"""

from __future__ import annotations

import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CHECKOUT / "src"))
sys.path.insert(0, str(CHECKOUT / "tests" / "decoding"))

from decoding_support import replay_paths
from sc2mindshare.decoding import load
from sc2mindshare.decoding.export import to_json


def main() -> int:
    golden = CHECKOUT / "tests" / "decoding" / "golden"
    golden.mkdir(exist_ok=True)
    for name, path in replay_paths().items():
        out = golden / f"{name}.decoded.json"
        out.write_text(to_json(load(str(path))), encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
