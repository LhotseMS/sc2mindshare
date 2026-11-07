"""The command line (CR-016, T15): ``sc2mindshare build REPLAY --out graph.json``, and (CR-069)
``sc2mindshare upload-clocks REPLAY [REPLAY ...]``.

One command turns a replay into the Mindshare import document (``graph.json``), plus the battle
intervals for the screenshot tool (``intervals.json`` and ``Intervals.csv``, next to ``graph.json``).
The ported legacy layer prints debug text while it runs; that goes to the log file (default
``<out>.log``), never to the console or into the JSON. The three outputs are written to temporary names
and renamed only once all are written, so a failed build leaves none of them. The screenshot tool reads
the fixed name ``Intervals.csv`` in the game folder, so one folder holds one build: ``intervals.json``
names its graph, and a folder holding another build's intervals is refused.

The clock pictures come from the clock record (``ClockImageRecord.csv`` in the config root, CR-069): the
build reads the rows of ``--clock-server`` (the local Mindshare) and never contacts it; a clock the record lacks
is left out with a warning naming ``upload-clocks``, the command that uploads it.

Exit codes: 0 built (or, for upload-clocks, done or a dry run); 1 the analysis or layout failed (the traceback is
in the log); 2 a usage error; 3 upload-clocks stopped cleanly at a limit (run it again later); 4 upload-clocks was
refused or failed.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from sc2mindshare.analysis.build_check import UnknownPlayer
from sc2mindshare.analysis.build_steps import build_order
from sc2mindshare.analysis.guides import library
from sc2mindshare.analysis.run import AnalysisResult, analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.guides import BuildCheck, NoBuildCheck
from sc2mindshare.domain.models import Graph
from sc2mindshare.export.intervals import intervals_csv, intervals_json, parse_intervals
from sc2mindshare.export.mindshare_json import build_document, to_json
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutResult, layout
from sc2mindshare.media.client import DEFAULT_SERVER, NotLocal, Server, parse_server
from sc2mindshare.media.clocks import (
    MAX_UPLOADS,
    PACE_S,
    RECORD_FILE,
    RecordUnreadable,
    clock_map,
    read_record,
    upload_clocks,
)
from sc2mindshare.reader.loader import load_replay

PROG = "sc2mindshare"
#: The support files read from the config root (Stefan's "MS SC" folder).
SUPPORT_FILES = ("unitsInfo.csv", "upgradesInfo.csv")  # CR-069: TimeImageTracking.csv is no longer read


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
        help="the folder with unitsInfo.csv, upgradesInfo.csv and the clock record ClockImageRecord.csv "
        "(default: the MS_SC_ROOT environment variable)",
    )
    build.add_argument(
        "--clock-server",
        default=DEFAULT_SERVER,
        help=f"whose clock pictures to use, from the clock record (default {DEFAULT_SERVER}, the local Mindshare; "
        "the build never contacts it)",
    )
    build.add_argument("--log", type=Path, default=None, help="where the run log goes (default: <out>.log)")
    build.add_argument(
        "--guide",
        action="append",
        default=[],
        metavar="PLAYER=GUIDE",
        help="compare PLAYER's build (his name, or 1 or 2) with the build order guide GUIDE (a shipped guide's id, or "
        "a guide file); repeatable. A player not named gets the closest guide for his matchup, marked suggested",
    )
    build.add_argument(
        "--with-analysis",
        action="store_true",
        help="also write the analysis values stream 2 reads (supply, stats, unit lifecycles...) as a top-level "
        "'analysis' object (not part of the Mindshare import format)",
    )
    upload = commands.add_parser(
        "upload-clocks",
        help="upload the clock pictures the replays need to the local Mindshare",
        description="Upload to the local Mindshare the clock pictures the timelines of REPLAY need and the clock "
        "record does not yet hold for it, and record each one's picture ID. A dry run unless --live: it shows the "
        "server's upload status and the clocks it would upload. Exit codes: 0 done or a dry run; 1 the analysis of a "
        "replay failed; 2 a usage error; 3 stopped cleanly at a limit (the server's or --max: run it again later); "
        "4 refused or failed.",
    )
    upload.add_argument("replay", metavar="REPLAY", type=Path, nargs="+", help="the .SC2Replay files")
    upload.add_argument(
        "--config-root",
        type=Path,
        default=None,
        help="the folder with the support tables, ClockImages/ and ClockImageRecord.csv (default: MS_SC_ROOT)",
    )
    upload.add_argument("--server", default=DEFAULT_SERVER, help=f"the local Mindshare (default {DEFAULT_SERVER})")
    upload.add_argument("--live", action="store_true", help="really upload (default: a dry run that uploads nothing)")
    upload.add_argument(
        "--max", type=int, default=MAX_UPLOADS, help=f"at most this many uploads in a run (default {MAX_UPLOADS})"
    )
    upload.add_argument("--pace", type=float, default=PACE_S, help=f"seconds between two uploads (default {PACE_S})")
    return parser


def _usage_error(message: str) -> int:
    print(f"{PROG}: {message}", file=sys.stderr)
    return 2


def _clock_map(config_root: Path, server: Server) -> tuple[dict[str, str], str | None]:
    """The clock pictures the record holds for ``server`` (file name -> picture ID), and why there are none, if
    there are none: an absent or unreadable record leaves the timeline without clocks; the build still succeeds."""
    record = config_root / RECORD_FILE
    if not record.exists():
        return {}, f"no clock record {record}: the timeline has no clock pictures; run {PROG} upload-clocks"
    try:
        return clock_map(read_record(record), server.key), None
    except RecordUnreadable as exc:
        return {}, f"cannot read the clock record ({exc}): the timeline has no clock pictures"


def _laid_out(
    replay: Path, config_root: Path, timeline: str, clocks: dict[str, str], guides: Sequence[str] = ()
) -> tuple[AnalysisResult, Graph, LayoutResult]:
    """The analysis result, its graph and the layout: the one pipeline ``build`` and ``upload-clocks`` share (CR-035:
    with the build check, the guides named on the command line for ``build``)."""
    result = analyse(load_replay(replay), config_root)  # a freshly loaded replay; its exposed values feed the steps
    graph = to_graph(result, guides=guides)
    placed = layout(items(graph), Profile(timeline="linear" if timeline == "linear" else "compressed"), clocks)
    return result, graph, placed


def build(
    replay: Path,
    out: Path,
    timeline: str,
    config_root: Path,
    log: Path,
    with_analysis: bool = False,
    clock_server: Server | None = None,
    guides: Sequence[str] = (),
) -> int:
    clocks, no_clocks = _clock_map(config_root, clock_server or parse_server(DEFAULT_SERVER))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as log_file:
        try:
            with contextlib.redirect_stdout(log_file):  # the layer's debug prints
                result, graph, placed = _laid_out(replay, config_root, timeline, clocks, guides)
                build_checks = graph.build_checks
                document = to_json(build_document(graph, placed, analysis=result.exposed if with_analysis else None))
                if graph.intervals is None:
                    raise ValueError("the analysis produced no battle intervals")
                intervals = parse_intervals(graph.intervals)
                csv_text = intervals_csv(graph.intervals)
            if no_clocks:
                print(f"clock record: {no_clocks}", file=log_file)
                print(f"{PROG}: {no_clocks}", file=sys.stderr)
            for check in build_checks:
                if isinstance(check, NoBuildCheck):
                    print(f"build check: player {check.player}: {check.line}", file=log_file)
                    print(f"{PROG}: build check: {check.line}", file=sys.stderr)
                else:
                    how = "picked" if check.picked else "suggested"
                    print(f"build check: player {check.player}: {check.guide.name} ({how}, score {check.score})", file=log_file)
            for warning in placed.warnings:
                print(f"layout warning: {warning}", file=log_file)
                print(f"{PROG}: layout warning: {warning}", file=sys.stderr)
        except UnknownPlayer as exc:
            return _usage_error(str(exc))
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


def upload(replays: Sequence[Path], config_root: Path, server: Server, live: bool, max_uploads: int, pace: float) -> int:
    """``upload-clocks``: the clocks the replays' timelines need, by the real pipeline (one layout each: one clock
    per window, the same in both timelines), then the upload run against the local Mindshare."""
    needed: list[str] = []
    for replay in replays:
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # the layer's debug prints
                _, _, placed = _laid_out(replay, config_root, "compressed", {})
        except Exception as exc:  # noqa: BLE001  # the CLI top level: any analysis failure is one message, exit 1
            print(f"{PROG}: the analysis of {replay} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        needed += [name for name in placed.clock_names if name not in needed]
    images = config_root / "ClockImages"
    absent = [name for name in needed if not (images / name).is_file()]
    if absent:
        return _usage_error(f"{images} lacks the clock pictures {', '.join(absent)}")
    run = upload_clocks(server, needed, images, config_root / RECORD_FILE, live=live, max_uploads=max_uploads, pace_s=pace)
    if run.message:
        print(f"{PROG}: {run.message}", file=sys.stderr)
    return run.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config_root = args.config_root or (Path(os.environ["MS_SC_ROOT"]) if os.environ.get("MS_SC_ROOT") else None)
    if config_root is None:
        return _usage_error("no config root: pass --config-root or set MS_SC_ROOT")
    try:
        server = parse_server(args.server if args.command == "upload-clocks" else args.clock_server)
    except NotLocal as exc:
        return _usage_error(str(exc))
    if args.command == "upload-clocks":
        missing_replays = [str(r) for r in args.replay if not r.is_file()]
        if missing_replays:
            return _usage_error(f"no such replay: {', '.join(missing_replays)}")
        if args.max < 1 or args.pace < 0:
            return _usage_error("--max must be at least 1 and --pace not negative")
        missing = [name for name in SUPPORT_FILES if not (config_root / name).is_file()]
        if missing:
            return _usage_error(f"the config root {config_root} lacks {', '.join(missing)}")
        return upload(args.replay, config_root, server, args.live, args.max, args.pace)
    if not args.replay.is_file():
        return _usage_error(f"no such replay: {args.replay}")
    missing = [name for name in SUPPORT_FILES if not (config_root / name).is_file()]
    if missing:
        return _usage_error(f"the config root {config_root} lacks {', '.join(missing)}")
    foreign = _foreign_intervals(args.out)
    if foreign:
        return _usage_error(f"{foreign}: use another --out folder for this build")
    malformed = [g for g in args.guide if not all(g.partition("=")[0::2]) or "=" not in g]
    if malformed:
        return _usage_error(f"--guide {malformed[0]}: write it as PLAYER=GUIDE")
    log = args.log or args.out.with_suffix(".log")
    return build(args.replay, args.out, args.timeline, config_root, log, args.with_analysis, server, args.guide)


if __name__ == "__main__":
    sys.exit(main())
