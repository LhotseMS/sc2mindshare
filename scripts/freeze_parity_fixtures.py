#!/usr/bin/env python3
"""Freeze the analysis and reader parity as fixtures, so tests no longer need the legacy venv (CR-019, T18).

    scripts/py-env .venv/bin/python scripts/freeze_parity_fixtures.py models <game> <replay>
    scripts/py-env .venv/bin/python scripts/freeze_parity_fixtures.py reader <game> <replay>

``models`` writes ``tests/golden/<game>/models-faithful.json``: the bug-faithful domain graph of the
replay (``to_graph(..., fixes=())``), node by node and link by link, with the intervals text. It is
written only if the graph renders exactly the CSV that a live legacy run writes for the replay.

``reader`` writes ``tests/golden/<game>/reader-state-legacy.summary.json``: the summary and sha256 of
the legacy reader's state dump (``scripts/dump_reader_state.py`` run in ``.venv-legacy``), written
only if the new reader's dump is equal to it.

Both need this checkout's ``.venv-legacy`` and refuse to overwrite an existing fixture: a fixture is
frozen once (a change to one is a golden change, with its CHANGES.md entry).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.models import Graph, Link, Node
from sc2mindshare.reader.loader import load_replay

CHECKOUT = Path(__file__).resolve().parents[1]
GOLDEN = CHECKOUT / "tests" / "golden"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _root() -> Path:
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


def scratch() -> Path:
    """Where temporary folders go: <root>/.tools/tmp, never the caller's TMPDIR (D30a)."""
    path = _root() / ".tools" / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- the model fixture ------------------------------------------------------------------------------


def graph_doc(graph: Graph) -> dict[str, Any]:
    """The graph as plain JSON data, in its order: every field of every node and link."""
    return {
        "nodes": [
            {
                "kind": n.kind,
                "id": n.id,
                "name": n.name,
                "description": n.description,
                "images": list(n.images),
                "values": [[k, v] for k, v in n.values],
                "start_seconds": n.start_seconds,
            }
            for n in graph.nodes
        ],
        "links": [
            {
                "node1": lk.node1,
                "node2": lk.node2,
                "name1": lk.name1,
                "name2": lk.name2,
                "description": lk.description,
                "direction": lk.direction,
                "name": lk.name,
            }
            for lk in graph.links
        ],
        "intervals": graph.intervals,
    }


def graph_from_doc(doc: dict[str, Any]) -> Graph:
    """The inverse of graph_doc (the models validate their fields on construction)."""
    return Graph(
        nodes=tuple(
            Node(
                kind=n["kind"],
                id=n["id"],
                name=n["name"],
                description=n["description"],
                images=tuple(n["images"]),
                values=tuple((k, v) for k, v in n["values"]),
                start_seconds=n["start_seconds"],
            )
            for n in doc["nodes"]
        ),
        links=tuple(Link(**lk) for lk in doc["links"]),
        intervals=doc["intervals"],
    )


def to_text(doc: dict[str, Any]) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def faithful_graph(replay: Path, support_root: Path) -> Graph:
    with contextlib.redirect_stdout(io.StringIO()):  # the moved layer prints debug text
        return to_graph(analyse(load_replay(replay), support_root), fixes=())


# --- the reader summary ----------------------------------------------------------------------------


def canonical(state: dict[str, Any]) -> bytes:
    return (json.dumps(state, indent=None, sort_keys=True) + "\n").encode("utf-8")


def reader_summary(state: dict[str, Any]) -> dict[str, Any]:
    """The pinned form of a reader-state dump (the shape of Alcyone's summary since CR-010)."""
    return {
        "class_counts": state["class_counts"],
        "command_updates": len(state["command_updates"]),
        "game_events": state["game_events"],
        "sha256": hashlib.sha256(canonical(state)).hexdigest(),
        "units": len(state["units"]),
        "updates": len(state["updates"]),
        "updates_with_target": sum(1 for u in state["updates"] if u["target"] is not None),
    }


# --- the commands ------------------------------------------------------------------------------------


def _target(game: str, file_name: str) -> Path:
    path = GOLDEN / game / file_name
    if path.exists():
        raise SystemExit(f"{path} exists: a parity fixture is frozen once (a change needs a CHANGES.md entry)")
    if not LEGACY_PY.exists():
        raise SystemExit(f"{LEGACY_PY} is missing: freezing needs the live legacy run (scripts/legacy-env)")
    return path


def freeze_models(game: str, replay: Path, support_root: Path) -> int:
    path = _target(game, "models-faithful.json")
    legacy_rows = _load("legacy_rows", CHECKOUT / "tests" / "analysis" / "legacy_rows.py")
    graph = faithful_graph(replay, support_root)
    with tempfile.TemporaryDirectory(dir=scratch()) as tmp:
        cmd = [str(LEGACY_PY), str(CHECKOUT / "scripts" / "run_legacy.py"), "--support", str(support_root), "--out", tmp]
        subprocess.run([*cmd, str(replay)], check=True, capture_output=True)
        legacy_csv = (Path(tmp) / replay.stem / "events.csv").read_text(encoding="utf-8")
        legacy_intervals = (Path(tmp) / replay.stem / "Intervals.csv").read_text(encoding="utf-8")
    if legacy_rows.render(graph) != legacy_csv or graph.intervals != legacy_intervals:
        print(f"{game}: the models do not render the live legacy CSV and intervals; nothing written")
        return 1
    doc = graph_doc(graph)
    assert graph_from_doc(doc) == graph  # the fixture reads back as the same models
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_text(doc), encoding="utf-8")
    print(f"{path}: {len(graph.nodes)} nodes, {len(graph.links)} links; renders the live legacy CSV")
    return 0


def freeze_reader(game: str, replay: Path) -> int:
    path = _target(game, "reader-state-legacy.summary.json")
    dumper = CHECKOUT / "scripts" / "dump_reader_state.py"
    with tempfile.TemporaryDirectory(dir=scratch()) as tmp:
        out = Path(tmp) / "legacy.json"
        # cwd: the fork's CreepTracker may write debug images to the working directory
        subprocess.run([str(LEGACY_PY), str(dumper), str(replay), str(out)], check=True, capture_output=True, cwd=tmp)
        legacy = json.loads(out.read_text(encoding="utf-8"))
    new = _load("dump_reader_state", dumper).dump(str(replay))
    if legacy != new:
        print(f"{game}: the new reader's dump differs from the legacy one; nothing written")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reader_summary(legacy), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{path}: {legacy['game_events']} game events; the new dump equals the legacy one")
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=("models", "reader"))
    parser.add_argument("game")
    parser.add_argument("replay", type=Path)
    parser.add_argument("--support", type=Path, default=_root() / "MS SC")
    args = parser.parse_args(argv)
    if args.what == "models":
        return freeze_models(args.game, args.replay, args.support)
    return freeze_reader(args.game, args.replay)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
