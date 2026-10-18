"""Sweep stream 3's findings over the upstream replay corpus in test_replays/ (CR-056, E1).

For each replay that plain sc2reader 1.9.0 loads, the replay is loaded again through
``sc2mindshare.decoding.load`` and checked against:

- parity: the game-event classes are equal apart from CameraSaveEvent, and the tracker events are
  equal (type and attributes), so stream 3's readers change nothing sc2reader exposes;
- F3-009: every camera update that lands exactly on a saved point matches one slot only;
- F3-016: the resume loop in ``replay.resumable.events`` is one loop before the first PlayerLeaveEvent;
- F3-017: ``replay.sync.events`` has the measured framing and game loops // 64 records;
- F3-018: UserOptionsEvent's ``base_build_num`` is the replay's base build;
- F3-020: every creator is alive at the birth loop; after loop 0, only Broodlings have no creator;
  the creator's owner is the unit's controller.

A finding is "not applicable" for a replay when the replay has nothing to check (no member, the
framing differs, no leave, no births with a creator). The corpus is read only and never a golden (D5a).

    scripts/py-env .venv/bin/python tools/decoding/corpus_findings.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

CHECKOUT = Path(__file__).resolve().parents[2]
CORPUS = CHECKOUT / "test_replays"
FINDINGS = ("parity", "F3-009", "F3-016", "F3-017", "F3-018", "F3-020")

_REFS = {"unit", "player", "unit_upkeeper", "unit_controller", "killer", "killing_player", "killing_unit"}


def _imports() -> tuple[Any, ...]:
    if str(CHECKOUT / "src") not in sys.path:
        sys.path.insert(0, str(CHECKOUT / "src"))
    import sc2reader
    from sc2mindshare.decoding import load
    from sc2mindshare.decoding.camera_hotkeys import camera_saves
    from sc2mindshare.decoding.creators import creations
    from sc2mindshare.decoding.side_members import side_members, user_options
    from sc2reader.events.game import CameraEvent

    return sc2reader, CameraEvent, load, camera_saves, creations, side_members, user_options


def _shape(events: Iterable[Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(type(e).__name__, {k: v for k, v in vars(e).items() if k not in _REFS}) for e in events]


def _type_at(unit: Any, frame: int) -> str:
    name = unit.name
    for f, t in sorted(unit.type_history.items()):
        if f <= frame:
            name = t.name
    return str(name)


def _camera(replay: Any, camera_saves: Any, camera_event: Any) -> tuple[int, int]:
    saved: dict[tuple[int, int], tuple[float, float]] = {}
    pending = list(camera_saves(replay))
    exact = ambiguous = 0
    for index, event in enumerate(replay.game_events):
        while pending and pending[0].stream_position <= index:
            save = pending.pop(0)
            if save.player is not None:
                saved[(save.player.pid, save.slot)] = (save.saved_x, save.saved_y)
        if event.player is None or not isinstance(event, camera_event):
            continue
        slots = [s for (owner, s), at in saved.items() if owner == event.player.pid and at == (event.x, event.y)]
        exact += bool(slots)
        ambiguous += len(slots) > 1
    return exact, ambiguous


def check_replay(path: Path) -> dict[str, Any]:
    """One replay's result: per finding True (holds), False (contradicts) or absent (not applicable)."""
    sc2reader, camera_event, load, camera_saves, creations, side_members, user_options = _imports()
    row: dict[str, Any] = {"path": path.relative_to(CHECKOUT).as_posix() if path.is_relative_to(CHECKOUT) else str(path)}
    try:
        plain = sc2reader.load_replay(str(path), load_level=4, load_map=False)
    except Exception as exc:  # noqa: BLE001  (any load failure: the replay is "could not load")
        row["could_not_load"] = type(exc).__name__
        return row
    row["base_build"] = int(plain.base_build)
    try:
        replay = load(str(path)).replay
    except Exception as exc:  # noqa: BLE001
        row["parity"] = False
        row["detail"] = {"parity": f"decoding.load failed: {exc!r}"[:200]}
        return row
    detail: dict[str, Any] = {}
    plain_classes = Counter(type(e).__name__ for e in plain.game_events)
    ours = Counter(type(e).__name__ for e in replay.game_events)
    row["parity"] = not (plain_classes - ours) and not (set(ours - plain_classes) - {"CameraSaveEvent"})
    row["parity"] = row["parity"] and _shape(plain.tracker_events) == _shape(replay.tracker_events)

    exact, ambiguous = _camera(replay, camera_saves, camera_event)
    if exact:
        row["F3-009"] = ambiguous == 0
        detail["F3-009"] = {"exact": exact, "ambiguous": ambiguous}

    side = side_members(replay)
    leaves = [e.frame for e in replay.game_events if type(e).__name__ == "PlayerLeaveEvent"]
    if side.resume_loop is not None and leaves:
        row["F3-016"] = side.resume_loop == min(leaves) - 1
        detail["F3-016"] = {"resume_minus_first_leave": side.resume_loop - min(leaves)}
    if side.sync_checksums is not None:
        row["F3-017"] = len(side.sync_checksums) == int(replay.frames) // 64
    options = user_options(replay)
    if options and all(o.base_build_num is not None for o in options):
        row["F3-018"] = {o.base_build_num for o in options} == {int(replay.base_build)}
        detail["F3-018"] = sorted({o.base_build_num for o in options})

    rows = list(creations(replay))
    if any(r.creator_id is not None for r in rows):
        not_alive, other_owner, no_creator = 0, Counter[str](), Counter[str]()
        for r in rows:
            if r.creator_id is None:
                if r.frame:
                    no_creator[r.unit_type] += 1
                continue
            creator = replay.objects.get(r.creator_id)
            if (
                creator is None
                or creator.started_at is None
                or creator.started_at > r.frame
                or (creator.died_at is not None and creator.died_at < r.frame)
            ):
                not_alive += 1
                continue
            owner = creator.owner.pid if creator.owner is not None else 0
            if owner != r.player_id:
                other_owner[f"{_type_at(creator, r.frame)}->{r.unit_type}"] += 1
        row["F3-020"] = not_alive == 0 and set(no_creator) <= {"Broodling"}
        detail["F3-020"] = {
            "not_alive": not_alive,
            "no_creator_after_loop_0": dict(no_creator),
            "other_owner": dict(other_owner),
        }
    row["detail"] = detail
    return row


def summarise(results: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Per finding: replays checked, holds, contradicts, not applicable; plus the replays that could not load."""
    results = list(results)
    loaded = [r for r in results if "could_not_load" not in r]
    out = {"corpus": {"replays": len(results), "could_not_load": len(results) - len(loaded)}}
    for finding in FINDINGS:
        values = [r[finding] for r in loaded if finding in r]
        out[finding] = {
            "checked": len(values),
            "holds": sum(values),
            "contradicts": len(values) - sum(values),
            "not_applicable": len(loaded) - len(values),
        }
    return out


def contradictions(results: Iterable[dict[str, Any]]) -> list[tuple[str, int, str, Any]]:
    """(finding, base build, replay, detail) for every contradiction, sorted."""
    return sorted(
        (f, r["base_build"], r["path"], r.get("detail", {}).get(f)) for r in results for f in FINDINGS if r.get(f) is False
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", type=Path, help="write every replay's result here")
    args = parser.parse_args(argv)
    results = [check_replay(p) for p in sorted(CORPUS.rglob("*.SC2Replay"))]
    if args.json:
        args.json.write_text(json.dumps(results, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summarise(results), indent=1))
    for c in contradictions(results):
        print(*c, sep=" | ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
