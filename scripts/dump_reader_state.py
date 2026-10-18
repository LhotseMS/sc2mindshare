#!/usr/bin/env python3
"""Dump the reader-level state the Mindshare layer depends on, from either reader (CR-010, T10).

    scripts/py-env .venv-legacy/bin/python scripts/dump_reader_state.py REPLAY OUT.json   # the old fork
    scripts/py-env .venv/bin/python scripts/dump_reader_state.py REPLAY OUT.json          # the new loader

The flavour follows the interpreter: the legacy venv has the fork (sc2reader 1.8.0), the main venv
the pinned 1.9.0 plus ``sc2mindshare.reader``. The JSON holds, per game event index: the fork's
class name; the fields copied onto ``Update*CommandEvent``s and their target command; the
command flags; and, per unit id, the frames of the unit's init, done and death back-links.
Two dumps of the same replay must be equal (``tests/reader/test_reader_parity.py``).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def _flavour() -> str:
    import sc2reader  # type: ignore[import-untyped]

    return "legacy" if sc2reader.__version__ == "1.8.0" else "new"


def _load(path: str) -> Any:
    if _flavour() == "legacy":
        import sc2reader

        return sc2reader.load_replay(path, debug=True, load_map=False)
    from sc2mindshare.reader.loader import load_replay

    return load_replay(path)


def _class_name(event: Any) -> str:
    if _flavour() == "legacy":
        return type(event).__name__
    from sc2mindshare.reader.compat import fork_class_name

    return fork_class_name(event)


def _link(event: Any) -> list[Any] | None:
    return None if event is None else [event.frame, type(event).__name__]


def dump(path: str) -> dict[str, Any]:
    replay = _load(path)
    events = list(replay.game_events)
    index = {id(e): i for i, e in enumerate(events)}
    classes = [_class_name(e) for e in events]
    updates = []
    commands = {}
    for i, e in enumerate(events):
        name = type(e).__name__
        if name in ("UpdateTargetUnitCommandEvent", "UpdateTargetPointCommandEvent"):
            ability = getattr(e, "ability", None)
            target = getattr(e, "targetCommandEvent", None)
            updates.append(
                {
                    "i": i,
                    "frame": e.frame,
                    "pid": e.pid,
                    "ability_name": getattr(e, "ability_name", None),
                    "ability_id": getattr(e, "ability_id", None),
                    "has_ability": getattr(e, "has_ability", None),
                    "ability_type": getattr(e, "ability_type", None),
                    "ability_data": repr(getattr(e, "ability_data", None)),
                    "ability": None if ability is None else [ability.id, ability.name],
                    "queued": getattr(e, "queued", None),
                    "minimap": getattr(e, "minimap", None),
                    "repeated": getattr(e, "repeated", None),
                    "target": None if target is None else index.get(id(target), "<not a game event>"),
                }
            )
        if hasattr(e, "updateEvents") and e.updateEvents:
            commands[str(i)] = [index.get(id(u), "<not a game event>") for u in e.updateEvents]
    units = {}
    for unit_id, unit in sorted(replay.objects.items()):
        links = {
            "init": _link(getattr(unit, "initEvent", None)),
            "done": _link(getattr(unit, "doneEvent", None)),
            "death": _link(getattr(unit, "deathEvent", None)),
        }
        if any(links.values()):
            units[str(unit_id)] = links
    return {
        "flavour_independent": True,
        "game_events": len(events),
        "classes": classes,
        "class_counts": dict(sorted(Counter(classes).items())),
        "updates": updates,
        "command_updates": commands,
        "units": units,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    state = dump(argv[0])
    Path(argv[1]).write_text(json.dumps(state, indent=None, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{_flavour()}: {state['game_events']} game events, {len(state['updates'])} updates, {len(state['units'])} units")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
