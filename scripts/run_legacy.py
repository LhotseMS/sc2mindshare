#!/usr/bin/env python3
"""Run the legacy Mindshare parser (the old sc2reader fork) on replays, offline.

Used to produce the legacy golden output (CR-003, T03). For each replay it
stages a private copy of the old ``C:/MS SC`` layout without ``Intervals.csv``,
so the legacy code takes "pass 1" (no heatmaps, no uploads), and runs it in a
child process of the legacy environment with every network connection blocked.

    scripts/py-env <root>/.tools/venvs/legacy/bin/python scripts/run_legacy.py \
        --support "<root>/MS SC" --out <root>/.tools/tmp/legacy-run \
        "<root>/MS SC/Alcyone LE__lilTiGGer_vs_blacksquall/Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"

Per replay, ``<out>/<replay stem>/`` gets ``events.csv`` (the legacy CSV),
``Intervals.csv``, ``run.log`` (everything the legacy code printed) and
``summary.json``. Standard library only; the legacy code is imported only in
the child process.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

SUPPORT_FILES = (
    "unitsInfo.csv",
    "upgradesInfo.csv",
    "mapsInfo.csv",
    "ImageTracking.csv",
    "TimeImageTracking.csv",
)
CREEP_ERROR = "'CreepTracker' object has no attribute 'creepTracker'"


class NetworkBlockedError(OSError):
    pass


def stage(replay: Path, support: Path, workdir: Path) -> Path:
    """Build ``<workdir>/MS SC`` with the support files and ``Replays/<replay>``.

    Returns the staged data root. A game folder is never staged, so no
    ``Intervals.csv`` exists and the legacy code runs pass 1.
    """
    root = workdir / "MS SC"
    if root.exists():
        shutil.rmtree(root)
    (root / "Replays").mkdir(parents=True)
    for name in SUPPORT_FILES:
        source = support / name
        if not source.is_file():
            raise FileNotFoundError(f"support file missing: {source}")
        shutil.copy2(source, root / name)
    shutil.copy2(replay, root / "Replays" / replay.name)
    return root


BLOCKED_AUDIT_EVENTS = frozenset({"socket.connect", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo"})


def _refuse_network(event: str, _args: tuple[object, ...]) -> None:
    if event in BLOCKED_AUDIT_EVENTS:
        raise NetworkBlockedError(f"network access is blocked in the legacy run ({event})")


def block_network() -> None:
    """Make every outgoing connection, datagram and name lookup in this process fail.

    An audit hook (PEP 578) sees ``socket.connect`` (which also covers
    ``connect_ex`` and ``create_connection``), ``socket.sendto``,
    ``socket.sendmsg`` and ``socket.getaddrinfo`` from any library, and
    cannot be removed once added, so the guard lasts for the whole process.
    """
    sys.addaudithook(_refuse_network)


def find_outputs(root: Path) -> tuple[Path, Path]:
    """Return the events CSV and Intervals.csv the legacy code wrote under ``root``."""
    events = sorted(root.glob("*/events_*.csv"))
    intervals = sorted(root.glob("*/Intervals.csv"))
    if len(events) != 1 or len(intervals) != 1:
        raise RuntimeError(f"expected one events CSV and one Intervals.csv under {root}, found {events} {intervals}")
    return events[0], intervals[0]


def count_creep_errors(log_text: str) -> int:
    return log_text.count(CREEP_ERROR)


def child(replay_name: str, log_path: Path) -> int:
    """Child process: run the legacy parseReplay offline, output to the log.

    A crash is written to the log with its traceback, and the child exits 1.
    """
    block_network()
    with log_path.open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            from execs.mindShareReplay import parseReplay  # type: ignore[import-not-found]  # legacy code, legacy venv only

            parseReplay(replay_name, load_map=False)
        except Exception:  # noqa: BLE001 (any legacy crash goes to the log with its traceback)
            traceback.print_exc(file=log)
            return 1
    return 0


def run_one(replay: Path, support: Path, out: Path, python: str) -> dict[str, object]:
    workdir = out / replay.stem
    workdir.mkdir(parents=True, exist_ok=True)
    root = stage(replay, support, workdir)
    log_path = workdir / "run.log"
    env = dict(os.environ, MS_SC_ROOT=str(root))
    env.pop("MS_UPLOADS_ENABLED", None)
    result = subprocess.run(
        [python, str(Path(__file__).resolve()), "--child", replay.name, "--log", str(log_path)],
        env=env,
        check=False,
    )
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    if result.returncode != 0:
        raise RuntimeError(f"legacy run failed for {replay.name} (exit {result.returncode}); see {log_path}")
    events, intervals = find_outputs(root)
    shutil.copy2(events, workdir / "events.csv")
    shutil.copy2(intervals, workdir / "Intervals.csv")
    with (workdir / "events.csv").open(encoding="utf-8") as f:
        rows = sum(1 for _ in f)
    summary: dict[str, object] = {
        "replay": replay.name,
        "events_csv_rows": rows,
        "events_csv_name": events.name,
        "creep_tracker_errors": count_creep_errors(log_text),
        "log_lines": log_text.count("\n"),
    }
    (workdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("replays", nargs="*", type=Path)
    parser.add_argument("--support", type=Path, help="folder with the C:/MS SC support files")
    parser.add_argument("--out", type=Path, help="output folder")
    parser.add_argument("--child", help=argparse.SUPPRESS)
    parser.add_argument("--log", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child:
        return child(args.child, args.log)
    if not args.replays or not args.support or not args.out:
        parser.error("replays, --support and --out are required")
    for replay in args.replays:
        print(json.dumps(run_one(replay, args.support, args.out, sys.executable)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
