#!/usr/bin/env python3
"""Regenerate the Alcyone goldens on purpose (CR-007, T07).

    scripts/py-env .venv/bin/python scripts/regen_golden.py [--csv] [--view]   # default: both

--csv   runs the legacy code (this checkout's .venv-legacy) and rewrites
        tests/golden/alcyone/G-CSV-1.csv and Intervals-1.csv;
--view  rebuilds tests/golden/alcyone/G-VIEW-1.json from G-CSV-1 with the VBA
        view port (raw-newline rows rejoined; proposal td-inbox/rex-2.md).

Never run it to make a failing test pass: a golden changes only with an
entry in tests/golden/CHANGES.md written before the change (approach G1).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
GOLDEN = CHECKOUT / "tests" / "golden" / "alcyone"


def root() -> Path:
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


def regen_csv() -> None:
    ms_sc = root() / "MS SC"
    replay = ms_sc / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
    legacy = CHECKOUT / ".venv-legacy" / "bin" / "python"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        cmd = [str(legacy), str(CHECKOUT / "scripts" / "run_legacy.py"), "--support", str(ms_sc), "--out", str(out), str(replay)]
        subprocess.run(cmd, check=True)
        shutil.copy2(out / replay.stem / "events.csv", GOLDEN / "G-CSV-1.csv")
        shutil.copy2(out / replay.stem / "Intervals.csv", GOLDEN / "Intervals-1.csv")
    print(f"rewrote {GOLDEN / 'G-CSV-1.csv'} and Intervals-1.csv")


def regen_view() -> None:
    cmd = [
        sys.executable,
        str(CHECKOUT / "tests" / "reference" / "vba_view" / "make_view.py"),
        str(GOLDEN / "G-CSV-1.csv"),
        str(GOLDEN / "G-VIEW-1.json"),
        "--rejoin-raw-newlines",
    ]
    subprocess.run(cmd, check=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--view", action="store_true")
    args = parser.parse_args(argv)
    both = not args.csv and not args.view
    if args.csv or both:
        regen_csv()
    if args.view or both:
        regen_view()
    print("Now: git diff tests/golden/ must match the entry in tests/golden/CHANGES.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
