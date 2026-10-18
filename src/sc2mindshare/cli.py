"""The command line (CR-016, T15): ``sc2mindshare build REPLAY --out graph.json``.

One command turns a replay into the Mindshare import document (``graph.json``), plus the battle
intervals for the screenshot tool (``intervals.json`` and ``Intervals.csv``, next to ``graph.json``).
The ported legacy layer prints debug text while it runs; that goes to the log file (default
``<out>.log``), never to the console or into the JSON. The three outputs are written to temporary names
and renamed only once all are written, so a failed build leaves none of them. The screenshot tool reads
the fixed name ``Intervals.csv`` in the game folder, so one folder holds one build: ``intervals.json``
names its graph, and a folder holding another build's intervals is refused.

Exit codes: 0 built; 1 the analysis or layout failed (the traceback is in the log); 2 a usage error.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.export.intervals import intervals_csv, intervals_json, parse_intervals
from sc2mindshare.export.mindshare_json import build_document, to_json
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import layout
from sc2mindshare.reader.loader import load_replay

PROG = "sc2mindshare"
#: The support files read from the config root (Stefan's "MS SC" folder).
SUPPORT_FILES = ("unitsInfo.csv", "upgradesInfo.csv", "TimeImageTracking.csv")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="StarCraft II replays to Mindshare graphs.")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser(
        "build",
        help="build the Mindshare JSON of a replay",
        description="Build the Mindshare import document of REPLAY, and the battle intervals for the "
        "screenshot tool (intervals.json and Intervals.csv, next to --out).",
    )
    build.add_argument("replay", metavar="REPLAY", type=Path, help="the .SC2Replay file")
    build.add_argument("--out", required=True, type=Path, help="the JSON file to write (graph.json)")
    build.add_argument(
        "--timeline",
        choices=("compressed", "linear"),
        default="compressed",
        help="compressed: empty 10 s windows take no space (default); linear: x is game time",
    )
    build.add_argument(
        "--config-root",
        type=Path,
        default=None,
        help="the folder with unitsInfo.csv, upgradesInfo.csv and TimeImageTracking.csv "
        "(default: the MS_SC_ROOT environment variable)",
    )
    build.add_argument("--log", type=Path, default=None, help="where the run log goes (default: <out>.log)")
    build.add_argument(
        "--with-analysis",
        action="store_true",
        help="also write the analysis values stream 2 reads (supply, stats, unit lifecycles...) as a top-level "
        "'analysis' object (not part of the Mindshare import format)",
    )
    return parser


def _usage_error(message: str) -> int:
    print(f"{PROG}: {message}", file=sys.stderr)
    return 2


def _clock_map(config_root: Path) -> dict[str, str]:
    with (config_root / "TimeImageTracking.csv").open(encoding="utf-8") as f:
        return {row["imageName"]: row["imageID"] for row in csv.DictReader(f)}


def build(replay: Path, out: Path, timeline: str, config_root: Path, log: Path, with_analysis: bool = False) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as log_file:
        try:
            with contextlib.redirect_stdout(log_file):  # the layer's debug prints
                result = analyse(load_replay(replay), config_root)  # a freshly loaded replay
                graph = to_graph(result)
                placed = layout(
                    items(graph), Profile(timeline="linear" if timeline == "linear" else "compressed"), _clock_map(config_root)
                )
                document = to_json(build_document(graph, placed, analysis=result.exposed if with_analysis else None))
                if graph.intervals is None:
                    raise ValueError("the analysis produced no battle intervals")
                intervals = parse_intervals(graph.intervals)
                csv_text = intervals_csv(graph.intervals)
            for warning in placed.warnings:
                print(f"layout warning: {warning}", file=log_file)
                print(f"{PROG}: layout warning: {warning}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001  # the CLI top level: any failure is logged with its traceback, exit 1
            traceback.print_exc(file=log_file)
            print(f"{PROG}: the analysis failed: {type(exc).__name__}: {exc} (traceback in {log})", file=sys.stderr)
            return 1
    outputs = {
        out: document,
        out.parent / "intervals.json": intervals_json(intervals, graph=out.name),
        out.parent / "Intervals.csv": csv_text,
    }
    try:
        _publish(outputs)
    except OSError as exc:
        print(f"{PROG}: writing the outputs failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("wrote " + ", ".join(str(p) for p in outputs))
    return 0


def _temp_name(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def _write_temp(path: Path, text: str) -> Path:
    """Write ``text`` next to ``path`` under a temporary name; return that name."""
    temp = _temp_name(path)
    temp.write_text(text, encoding="utf-8", newline="")
    return temp


def _publish(outputs: dict[Path, str]) -> None:
    """Every output is written to a temporary name first; only when all are written are they renamed,
    so a failed write leaves none of them (and no temporary file) behind. The three renames are separate
    ``os.replace`` calls, each atomic: a reader could see the new graph.json with the old intervals for the
    moment between them, and a failure there (unlikely: a rename writes no data) would leave a mix."""
    next(iter(outputs)).parent.mkdir(parents=True, exist_ok=True)
    written: list[tuple[Path, Path]] = []
    try:
        for path, text in outputs.items():
            written.append((_write_temp(path, text), path))
    except OSError:
        for path in outputs:
            _temp_name(path).unlink(missing_ok=True)
        raise
    for temp, path in written:
        os.replace(temp, path)


def _foreign_intervals(out: Path) -> str | None:
    """Why ``out``'s folder holds another build's intervals, or None. The screenshot tool reads the fixed
    name ``Intervals.csv`` in the game folder, so one folder holds one build's intervals."""
    folder = out.parent
    marker = folder / "intervals.json"
    if marker.is_file():
        try:
            owner = json.loads(marker.read_text(encoding="utf-8")).get("graph")
        except (ValueError, AttributeError):
            owner = None
        if owner != out.name:
            return f"{marker} belongs to {owner or 'an unknown build'}"
    elif (folder / "Intervals.csv").is_file():
        return f"{folder / 'Intervals.csv'} belongs to an unknown build (no intervals.json)"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config_root = args.config_root or (Path(os.environ["MS_SC_ROOT"]) if os.environ.get("MS_SC_ROOT") else None)
    if config_root is None:
        return _usage_error("no config root: pass --config-root or set MS_SC_ROOT")
    if not args.replay.is_file():
        return _usage_error(f"no such replay: {args.replay}")
    missing = [name for name in SUPPORT_FILES if not (config_root / name).is_file()]
    if missing:
        return _usage_error(f"the config root {config_root} lacks {', '.join(missing)}")
    foreign = _foreign_intervals(args.out)
    if foreign:
        return _usage_error(f"{foreign}: use another --out folder for this build")
    log = args.log or args.out.with_suffix(".log")
    return build(args.replay, args.out, args.timeline, config_root, log, args.with_analysis)


if __name__ == "__main__":
    sys.exit(main())
