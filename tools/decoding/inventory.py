"""Inventory of what a replay holds, with Blizzard's s2protocol as the reference (CR-041, T3-1).

For each replay: the archive members, every event type in the game and tracker streams
(counted by s2protocol and by sc2reader 1.9.0), and every field of every event type
(types seen, counts, distinct values, the sc2reader attribute that exposes it, and
whether the Mindshare layer reads that attribute).

    scripts/py-env .venv/bin/python tools/decoding/inventory.py [--out docs/decoding/inventory.md]

Read only: replays are opened, never written. Stream 3 tooling, never imported by the product.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mpyq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2p

STREAMS = {
    "game": ("replay.game.events", "decode_replay_game_events"),
    "tracker": ("replay.tracker.events", "decode_replay_tracker_events"),
}

# ---------------------------------------------------------------------------
# Archive


def _archive(path: str) -> mpyq.MPQArchive:
    return mpyq.MPQArchive(path)


def header(path: str) -> dict[str, Any]:
    content = _archive(path).header["user_data_header"]["content"]
    return s2p.latest_protocol().decode_replay_header(content)


def base_build(path: str) -> int:
    return int(header(path)["m_version"]["m_baseBuild"])


def protocol_for(path: str) -> Any:
    return s2p.load_protocol(s2p.protocol_build_for(base_build(path)))


@dataclass(frozen=True)
class Member:
    name: str
    size: int


def members(path: str) -> list[Member]:
    archive = _archive(path)
    listfile = (archive.read_file("(listfile)") or b"").decode("utf-8", "replace")
    return [Member(n, len(archive.read_file(n) or b"")) for n in sorted(listfile.split())]


def player_names(path: str) -> list[str]:
    """Player names from replay.details (used only to check the report leaks none)."""
    details = protocol_for(path).decode_replay_details(_archive(path).read_file("replay.details"))
    return [p["m_name"].decode("utf-8", "replace") for p in details["m_playerList"]]


def gamemetadata(path: str) -> dict[str, Any] | None:
    raw = _archive(path).read_file("replay.gamemetadata.json")
    return json.loads(raw) if raw else None


# ---------------------------------------------------------------------------
# Events


def s2p_events(path: str, stream: str) -> list[dict[str, Any]]:
    member, decoder = STREAMS[stream]
    contents = _archive(path).read_file(member)
    return list(getattr(protocol_for(path), decoder)(contents))


def s2p_counts(path: str, stream: str) -> Counter[str]:
    return Counter(e["_event"] for e in s2p_events(path, stream))


def game_event_ids(path: str) -> dict[str, int]:
    return {name: eid for eid, (_typeid, name) in protocol_for(path).game_event_types.items()}


def tracker_event_ids(path: str) -> dict[str, int]:
    return {name: eid for eid, (_typeid, name) in protocol_for(path).tracker_event_types.items()}


def tracker_classes() -> dict[int, str]:
    """sc2reader 1.9.0's tracker dispatch: event id -> the class it builds."""
    from sc2reader.readers import TrackerEventsReader

    return {eid: cls.__name__ for eid, cls in TrackerEventsReader().EVENT_DISPATCH.items()}


def sc2reader_tracker_counts(path: str) -> Counter[str]:
    """Tracker events sc2reader 1.9.0 keeps on the replay, counted under their s2protocol names."""
    import sc2reader

    by_class = {cls: name for name, eid in tracker_event_ids(path).items() if (cls := tracker_classes().get(eid))}
    replay = sc2reader.load_replay(path, load_level=4, load_map=False)
    return Counter(by_class.get(type(e).__name__, type(e).__name__) for e in replay.tracker_events)


@dataclass
class ReaderCounts:
    parsed: Counter[str] = field(default_factory=Counter)  # every event sc2reader decodes, kept or not
    dropped: set[str] = field(default_factory=set)  # present types that sc2reader decodes and discards
    kept: dict[str, str] = field(default_factory=dict)  # s2protocol name -> sc2reader class


def sc2reader_counts(path: str) -> ReaderCounts:
    """Count what sc2reader 1.9.0 decodes, per game-event type, through its public seam.

    A Replay subclass registers a counting reader with Replay.register_reader (TD-2). The
    reader delegates to the default reader sc2reader would have chosen, so nothing in
    sc2reader is patched. The choice is made when the file is read, because the replay's
    version is not known when readers are registered.
    """
    import sc2reader
    from sc2reader import resources

    names = {eid: name for name, eid in game_event_ids(path).items()}
    result = ReaderCounts()
    dispatch_classes: dict[str, Any] = {}

    class CountingReader:
        def __call__(self, data: bytes, replay: Any) -> Any:
            default = next(
                reader
                for accepts, reader in replay.registered_readers["replay.game.events"]
                if reader is not self and accepts(replay)
            )
            for eid, (cls, parser) in list(default.EVENT_DISPATCH.items()):
                name = names.get(eid, f"id{eid}")
                dispatch_classes[name] = cls

                def counted(d: Any, _parse: Any = parser, _name: str = name) -> Any:
                    result.parsed[_name] += 1
                    return _parse(d)

                default.EVENT_DISPATCH[eid] = (cls, counted)
            return default(data, replay)

    class CountingReplay(resources.Replay):
        def register_default_readers(self) -> None:
            super().register_default_readers()
            self.register_reader("replay.game.events", CountingReader(), lambda r: True)

    factory = sc2reader.factories.SC2Factory()
    factory.load(CountingReplay, path, load_level=4, load_map=False)
    for name in result.parsed:
        cls = dispatch_classes.get(name)
        if cls is None:
            result.dropped.add(name)
        else:
            result.kept[name] = getattr(cls, "__name__", str(cls))
    return result


# ---------------------------------------------------------------------------
# Fields


@dataclass
class FieldStat:
    count: int = 0
    values: Counter[Any] = field(default_factory=Counter)
    types: set[str] = field(default_factory=set)

    @property
    def distinct(self) -> int:
        return len(self.values)

    @property
    def top(self) -> list[tuple[Any, int]]:
        return sorted(self.values.items(), key=lambda kv: (-kv[1], repr(kv[0])))[:5]


def _flatten(prefix: str, value: Any, out: list[tuple[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            if not key.startswith("_"):
                _flatten(f"{prefix}.{key}" if prefix else key, inner, out)
    elif isinstance(value, list):
        for item in value:
            _flatten(prefix + "[]", item, out)
    else:
        out.append((prefix, value))


def field_stats(events: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], FieldStat]:
    stats: dict[tuple[str, str], FieldStat] = {}
    for event in events:
        pairs: list[tuple[str, Any]] = []
        _flatten("", event, pairs)
        for path_, value in pairs:
            stat = stats.setdefault((event["_event"], path_), FieldStat())
            stat.count += 1
            stat.types.add(type(value).__name__)
            stat.values[value] += 1
    return stats


# s2protocol field -> sc2reader 1.9.0 attribute (None: decoded by sc2reader's reader but not exposed).
# Curated from sc2reader/events/{game,tracker}.py at 1.9.0; fields absent from this map are reported as "unmapped".
_CMD_TARGET_UNIT = {
    "m_targetUnitFlags": "target_flags",
    "m_timer": "target_timer",
    "m_tag": "target_unit_id",
    "m_snapshotUnitLink": "target_unit_type",
    "m_snapshotControlPlayerId": "control_player_id",
    "m_snapshotUpkeepPlayerId": "upkeep_player_id",
    "m_snapshotPoint.x": "x",
    "m_snapshotPoint.y": "y",
    "m_snapshotPoint.z": "z",
}
ATTRS: dict[str, dict[str, str | None]] = {
    "NNet.Game.SCmdEvent": {
        "m_cmdFlags": "flags",
        "m_abil": "has_ability",
        "m_abil.m_abilLink": "ability_link",
        "m_abil.m_abilCmdIndex": "command_index",
        "m_abil.m_abilCmdData": "ability_data",
        "m_data.None": None,
        "m_data.Data": "target_data",
        "m_data.TargetPoint.x": "x",
        "m_data.TargetPoint.y": "y",
        "m_data.TargetPoint.z": "z",
        "m_sequence": None,
        "m_otherUnit": "other_unit_id",
        "m_unitGroup": None,
        **{f"m_data.TargetUnit.{k}": v for k, v in _CMD_TARGET_UNIT.items()},
    },
    "NNet.Game.SCmdUpdateTargetPointEvent": {"m_target.x": "x", "m_target.y": "y", "m_target.z": "z"},
    "NNet.Game.SCmdUpdateTargetUnitEvent": {f"m_target.{k}": v for k, v in _CMD_TARGET_UNIT.items()},
    "NNet.Game.SCommandManagerStateEvent": {"m_state": "state", "m_sequence": "sequence"},
    "NNet.Game.SSelectionDeltaEvent": {
        "m_controlGroupId": "control_group",
        "m_delta.m_subgroupIndex": "subgroup_index",
        "m_delta.m_removeMask.Mask": "mask_data",
        "m_delta.m_removeMask.None": "mask_type",
        "m_delta.m_removeMask.OneIndices[]": "mask_data",
        "m_delta.m_removeMask.ZeroIndices[]": "mask_data",
        "m_delta.m_addSubgroups[].m_unitLink": "new_unit_types",
        "m_delta.m_addSubgroups[].m_count": "new_unit_types",
        "m_delta.m_addSubgroups[].m_subgroupPriority": "new_unit_types",
        "m_delta.m_addSubgroups[].m_intraSubgroupPriority": "new_unit_types",
        "m_delta.m_addUnitTags[]": "new_unit_ids",
    },
    "NNet.Game.SControlGroupUpdateEvent": {
        "m_controlGroupIndex": "control_group",
        "m_controlGroupUpdate": "update_type",
        "m_mask.Mask": "mask_data",
        "m_mask.None": "mask_type",
        "m_mask.OneIndices[]": "mask_data",
        "m_mask.ZeroIndices[]": "mask_data",
    },
    "NNet.Game.SCameraUpdateEvent": {
        "m_target": "location",
        "m_target.x": "x",
        "m_target.y": "y",
        "m_distance": "distance",
        "m_pitch": "pitch",
        "m_yaw": "yaw",
        "m_reason": None,
        "m_follow": None,
    },
    "NNet.Game.SCameraSaveEvent": {"m_which": None, "m_target.x": None, "m_target.y": None},
    "NNet.Game.SGameUserLeaveEvent": {"m_leaveReason": None},
    # Event types sc2reader decodes and drops (no class): none of their fields is exposed.
    "NNet.Game.SDecrementGameTimeRemainingEvent": {"m_decrementSeconds": None},
    "NNet.Game.SSetSyncLoadingTimeEvent": {"m_syncTime": None},
    "NNet.Game.SSetSyncPlayingTimeEvent": {"m_syncTime": None},
    "NNet.Game.STriggerSoundLengthSyncEvent": {"m_syncInfo.m_length[]": None, "m_syncInfo.m_soundHash[]": None},
    "NNet.Game.SUserOptionsEvent": {
        "m_gameFullyDownloaded": "game_fully_downloaded",
        "m_developmentCheatsEnabled": "development_cheats_enabled",
        "m_multiplayerCheatsEnabled": "multiplayer_cheats_enabled",
        "m_syncChecksummingEnabled": "sync_checksumming_enabled",
        "m_isMapToMapTransition": "is_map_to_map_transition",
        "m_debugPauseEnabled": "debug_pause_enabled",
        "m_baseBuildNum": "base_build_num",
        "m_buildNum": None,
        "m_versionFlags": None,
        "m_hotkeyProfile": None,
        "m_useGalaxyAsserts": None,
        "m_platformMac": None,
        "m_cameraFollow": None,
        "m_testCheatsEnabled": None,
    },
    "NNet.Replay.Tracker.SUnitBornEvent": {
        "m_unitTagIndex": "unit_id_index",
        "m_unitTagRecycle": "unit_id_recycle",
        "m_unitTypeName": "unit_type_name",
        "m_controlPlayerId": "control_pid",
        "m_upkeepPlayerId": "upkeep_pid",
        "m_x": "x",
        "m_y": "y",
        "m_creatorAbilityName": None,
        "m_creatorUnitTagIndex": None,
        "m_creatorUnitTagRecycle": None,
    },
    "NNet.Replay.Tracker.SUnitInitEvent": {
        "m_unitTagIndex": "unit_id_index",
        "m_unitTagRecycle": "unit_id_recycle",
        "m_unitTypeName": "unit_type_name",
        "m_controlPlayerId": "control_pid",
        "m_upkeepPlayerId": "upkeep_pid",
        "m_x": "x",
        "m_y": "y",
    },
    "NNet.Replay.Tracker.SUnitDiedEvent": {
        "m_unitTagIndex": "unit_id_index",
        "m_unitTagRecycle": "unit_id_recycle",
        "m_killerPlayerId": "killer_pid",
        "m_killerUnitTagIndex": "killing_unit_index",
        "m_killerUnitTagRecycle": "killing_unit_recycle",
        "m_x": "x",
        "m_y": "y",
    },
    "NNet.Replay.Tracker.SUnitDoneEvent": {"m_unitTagIndex": "unit_id_index", "m_unitTagRecycle": "unit_id_recycle"},
    "NNet.Replay.Tracker.SUnitTypeChangeEvent": {
        "m_unitTagIndex": "unit_id_index",
        "m_unitTagRecycle": "unit_id_recycle",
        "m_unitTypeName": "unit_type_name",
    },
    "NNet.Replay.Tracker.SUnitOwnerChangeEvent": {
        "m_unitTagIndex": "unit_id_index",
        "m_unitTagRecycle": "unit_id_recycle",
        "m_controlPlayerId": "control_pid",
        "m_upkeepPlayerId": "upkeep_pid",
    },
    "NNet.Replay.Tracker.SUpgradeEvent": {
        "m_playerId": "pid",
        "m_upgradeTypeName": "upgrade_type_name",
        "m_count": "count",
    },
    "NNet.Replay.Tracker.SUnitPositionsEvent": {"m_firstUnitIndex": "first_unit_index", "m_items[]": "items"},
    "NNet.Replay.Tracker.SPlayerSetupEvent": {
        "m_playerId": "pid",
        "m_type": "type",
        "m_userId": "uid",
        "m_slotId": "sid",
    },
    "NNet.Replay.Tracker.SPlayerStatsEvent": {"m_playerId": "pid"},
}

_UNMAPPED = "unmapped"


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def sc2reader_attr(event: str, field_path: str) -> str | None:
    """The sc2reader 1.9.0 attribute exposing an s2protocol field; None if not exposed."""
    if event == "NNet.Replay.Tracker.SPlayerStatsEvent" and field_path.startswith("m_stats.m_scoreValue"):
        return _snake(field_path.removeprefix("m_stats.m_scoreValue"))
    table = ATTRS.get(event, {})
    if field_path in table:
        return table[field_path]
    return _UNMAPPED


def mindshare_sources(checkout: Path) -> list[Path]:
    """The Mindshare layer's Python files: the fork tree before T09, legacy/ after."""
    roots = []
    for base in (checkout / "legacy", checkout):
        roots += [base / "sc2reader" / "mindshare", base / "execs", base / "sc2reader" / "engine" / "plugins" / "context.py"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files += sorted(root.rglob("*.py"))
    return files


def mindshare_uses(attr: str, sources: Iterable[Path]) -> bool:
    """Static search for `.attr` in the Mindshare sources: an upper bound on real use."""
    pattern = re.compile(r"\." + re.escape(attr) + r"\b")
    return any(pattern.search(p.read_text(encoding="utf-8", errors="replace")) for p in sources)


# ---------------------------------------------------------------------------
# Report

REPLAY_ORDER = ("alcyone", "spores", "spine")


def _fmt_value(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = repr(value) if not isinstance(value, str) else value
    return text.replace("|", "\\|")[:24]


def render_report(replays: Mapping[str, str], checkout: Path) -> str:
    order = [k for k in REPLAY_ORDER if k in replays]
    sources = mindshare_sources(checkout)
    builds = {k: base_build(replays[k]) for k in order}
    out: list[str] = []
    w = out.append
    w("# Replay inventory (generated)")
    w("")
    w("Generated by `tools/decoding/inventory.py` (CR-041, T3-1). Do not edit by hand; regenerate.")
    w("Reference decoder: Blizzard s2protocol 5.0.16.97563.0; compared with sc2reader 1.9.0 (the pin).")
    w(
        "Replays (D5a: data points, not committed): "
        + ", ".join(f"`{k}` base build {builds[k]} (protocol {s2p.protocol_build_for(builds[k])})" for k in order)
        + "."
    )
    w("")
    w(
        "**Mindshare use** is a static search for the sc2reader attribute (`.name`) in the Mindshare layer's "
        "sources (`sc2reader/mindshare/`, `execs/`, the fork's `ContextLoader`). It is an upper bound: generic "
        "names such as `x`, `y`, `location` match more than this event. Values are shown only for the game and "
        "tracker streams; strings that could identify a player are never shown."
    )
    w("")

    w("## 1. Archive members (bytes)")
    w("")
    w("| Member | " + " | ".join(order) + " |")
    w("|---|" + "---|" * len(order))
    sizes = {k: {m.name: m.size for m in members(replays[k])} for k in order}
    for name in sorted({n for k in order for n in sizes[k]}):
        w(f"| `{name}` | " + " | ".join(str(sizes[k].get(name, "-")) for k in order) + " |")
    w("")

    w("## 2. Event types")
    w("")
    reader = {k: sc2reader_counts(replays[k]) for k in order}
    for stream in STREAMS:
        counts = {k: s2p_counts(replays[k], stream) for k in order}
        # The id column comes from the first replay's protocol module. The ids are identical in the
        # three replays' protocols (81009, 83830, 92440): test_event_ids_are_the_same_in_the_three_replays_protocols.
        ids = game_event_ids(replays[order[0]]) if stream == "game" else tracker_event_ids(replays[order[0]])
        kept_tracker = {k: sc2reader_tracker_counts(replays[k]) for k in order} if stream == "tracker" else {}
        classes = {name: tracker_classes().get(eid, "?") for name, eid in ids.items()} if stream == "tracker" else {}
        w(f"### {stream} events")
        w("")
        w("| Event (s2protocol) | id | " + " | ".join(order) + " | sc2reader 1.9.0 |")
        w("|---|---|" + "---|" * len(order) + "---|")
        for name in sorted({n for k in order for n in counts[k]}):
            if stream == "game":
                status = (
                    "dropped"
                    if any(name in reader[k].dropped for k in order)
                    else ("kept as `" + next(reader[k].kept[name] for k in order if name in reader[k].kept) + "`")
                )
                equal = all(reader[k].parsed.get(name, 0) == counts[k].get(name, 0) for k in order)
                status += "" if equal else " **COUNT MISMATCH**"
            else:
                status = f"kept as `{classes.get(name, '?')}`"
                equal = all(kept_tracker[k].get(name, 0) == counts[k].get(name, 0) for k in order)
                status += "" if equal else " **COUNT MISMATCH**"
            w(f"| {name} | {ids.get(name, '')} | " + " | ".join(str(counts[k].get(name, 0)) for k in order) + f" | {status} |")
        w("")

    w("## 3. Fields")
    w("")
    w("Counts, distinct values and top values are for `alcyone`; *distinct (3)* is across all three replays.")
    w("")
    for stream in STREAMS:
        per_replay = {k: field_stats(s2p_events(replays[k], stream)) for k in order}
        main = per_replay[order[0]]
        events = sorted({e for k in order for (e, _f) in per_replay[k]})
        for event in events:
            w(f"### {event}")
            w("")
            w("| Field | Types | Count | Distinct | Distinct (3) | Top values | sc2reader attribute | Mindshare use |")
            w("|---|---|---|---|---|---|---|---|")
            fields = sorted({f for k in order for (e, f) in per_replay[k] if e == event})
            for fpath in fields:
                stat = main.get((event, fpath), FieldStat())
                all_values: set[Any] = set()
                for k in order:
                    all_values |= set(per_replay[k].get((event, fpath), FieldStat()).values)
                attr = sc2reader_attr(event, fpath)
                if attr is None:
                    attr_text, use = "not exposed", "no"
                elif attr == _UNMAPPED:
                    attr_text, use = "unmapped", "?"
                else:
                    attr_text, use = f"`{attr}`", "yes" if mindshare_uses(attr, sources) else "no"
                top = ", ".join(f"{_fmt_value(v)} ×{n}" for v, n in stat.top[:3])
                w(
                    f"| {fpath} | {', '.join(sorted(stat.types))} | {stat.count} | {stat.distinct} | {len(all_values)} "
                    f"| {top} | {attr_text} | {use} |"
                )
            w("")

    w("## 4. replay.gamemetadata.json keys")
    w("")
    for k in order:
        meta = gamemetadata(replays[k]) or {}
        player_keys = sorted({key for p in meta.get("Players", []) for key in p})
        w(f"- `{k}`: {', '.join(sorted(meta))}; per player: {', '.join(player_keys)}")
    w("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve()
    checkout = here.parents[2]
    sys.path.insert(0, str(checkout / "tests" / "decoding"))
    from decoding_support import replay_paths

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=checkout / "docs" / "decoding" / "inventory.md")
    args = ap.parse_args(argv)
    replays = {k: str(v) for k, v in replay_paths().items()}
    args.out.write_text(render_report(replays, checkout) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
