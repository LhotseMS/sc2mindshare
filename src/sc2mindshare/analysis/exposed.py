"""Compute the values ``AnalysisResult.exposed`` gives stream 2 (CR-021, T20; P0-2 §2).

Read from the replay's tracker and game events (upstream sc2reader 1.9.0's own attributes, never the
fork's names: ``unit_type_name`` is the type at that event, so a unit born as an Overlord stays an
Overlord here even if it ends the game as an Overseer, TD-13) and from what the layer computed (its
supply history and the build-time tables it read). Measured answers to P0-2's V1-V7 on the sample
replays are in tests/analysis/test_exposed.py.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from sc2mindshare.domain.exposed import (
    Chrono,
    Exposed,
    GameContext,
    PlayerContext,
    StatsSample,
    SupplyPoint,
    TimeTables,
    TypeChange,
    UnitLife,
    UpgradeDone,
)
from sc2mindshare.reader.event_classes import (
    PlayerStatsEvent,
    TargetUnitCommandEvent,
    UnitBornEvent,
    UnitDiedEvent,
    UnitDoneEvent,
    UnitInitEvent,
    UnitTypeChangeEvent,
    UpdateTargetUnitCommandEvent,
    UpgradeCompleteEvent,
)

CHRONO_BOOST = "ChronoBoostEnergyCost"

#: unitsInfo.csv display names that are not their unit type's id once spaces are removed (checked
#: against the 89720 datapack, CR-021 C5).
UNIT_ALIASES = {
    "Hellbat": "BattleHellion",
    "Flying Locust": "LocustMPFlying",
    "Landed Locust": "Locust",
    "Ventral Sacs Overlord": "OverlordTransport",
    "Stasis Ward": "OracleStasisTrap",
}
#: The sheet's rows for the layer's base names, which are not unit types.
_BASE_ROW = re.compile(r"(Main base|Natural|\d+(st|nd|rd|th) base)")


def _build_times(table: Any, known: set[str]) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """unitsInfo.csv's build times keyed by unit type id (see ``TimeTables``), and the rows that name none."""
    keyed: list[tuple[str, str]] = []
    unmapped: list[str] = []
    for name, row in table.items():
        if _BASE_ROW.fullmatch(name):
            continue
        squashed = re.sub(r"[^A-Za-z0-9]", "", name)
        unit_id = next((c for c in (name, squashed, UNIT_ALIASES.get(name)) if c in known), None)
        if unit_id is None:
            unmapped.append(name)
        elif any(key == unit_id for key, _ in keyed):
            raise ValueError(f"unitsInfo.csv has two rows for unit type {unit_id!r} (the second is {name!r})")
        else:
            keyed.append((unit_id, str(row["Build Time"])))
    return tuple(keyed), tuple(unmapped)


def _game(replay: Any) -> GameContext:
    players = list(replay.players)
    contexts = []
    for order, player in enumerate(players):
        others = [p for p in players if p is not player]
        opponent = str(others[0].play_race) if len(players) == 2 else None
        contexts.append(PlayerContext(int(player.pid), order, str(player.play_race), opponent))
    teams = list(getattr(replay, "teams", []))
    return GameContext(
        base_build=int(replay.base_build),
        version=str(replay.release_string),
        loops=int(replay.frames),
        game_type=str(replay.game_type),
        team_size=max((len(t.players) for t in teams), default=0),
        is_ladder=bool(replay.is_ladder),
        players=tuple(contexts),
    )


def _units(replay: Any, pids: set[int]) -> tuple[tuple[UnitLife, ...], tuple[TypeChange, ...]]:
    fields: dict[int, dict[str, Any]] = {}
    changes: list[TypeChange] = []
    current: dict[int, str] = {}
    for e in replay.tracker_events:
        if isinstance(e, (UnitBornEvent, UnitInitEvent)):
            if e.unit_id in fields or e.control_pid not in pids:
                continue
            unit = replay.objects.get(e.unit_id)
            fields[e.unit_id] = {
                "unit_id": int(e.unit_id),
                "owner": int(e.control_pid),
                "first_type": str(e.unit_type_name),
                "born_loop": int(e.frame) if isinstance(e, UnitBornEvent) else None,
                "init_loop": int(e.frame) if isinstance(e, UnitInitEvent) else None,
                "done_loop": None,
                "died_loop": None,
                "killer": None,
                "killing_unit_id": None,
                "x": int(e.x),
                "y": int(e.y),
                "hallucinated": bool(getattr(unit, "hallucinated", False)),
            }
            current[e.unit_id] = str(e.unit_type_name)
        elif not isinstance(e, (UnitDoneEvent, UnitDiedEvent, UnitTypeChangeEvent)) or e.unit_id not in fields:
            continue
        elif isinstance(e, UnitDoneEvent):
            fields[e.unit_id]["done_loop"] = int(e.frame)
        elif isinstance(e, UnitDiedEvent):
            fields[e.unit_id].update(died_loop=int(e.frame), killer=e.killer_pid, killing_unit_id=e.killing_unit_id)
        elif isinstance(e, UnitTypeChangeEvent):
            after = str(e.unit_type_name)
            changes.append(TypeChange(int(e.unit_id), int(e.frame), current[e.unit_id], after))
            current[e.unit_id] = after
    return tuple(UnitLife(**f) for f in fields.values()), tuple(changes)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expose(replay: Any, ctx: Any, support_root: Path) -> Exposed:
    """The exposed values of an analysed replay (``ctx`` is the layer's AnalysisContext)."""
    game = _game(replay)
    pids = {p.pid for p in game.players}
    units, changes = _units(replay, pids)
    upgrades = tuple(
        UpgradeDone(int(e.pid), str(e.upgrade_type_name), int(e.frame), int(e.count))
        for e in replay.tracker_events
        if isinstance(e, UpgradeCompleteEvent) and e.pid in pids
    )
    stats = tuple(
        StatsSample(
            player=int(e.pid),
            loop=int(e.frame),
            food_used=float(e.food_used),
            food_made=float(e.food_made),
            workers_active=int(e.workers_active_count),
            minerals=int(e.minerals_current),
            vespene=int(e.vespene_current),
            minerals_rate=int(e.minerals_collection_rate),
            vespene_rate=int(e.vespene_collection_rate),
            army_minerals=int(e.minerals_used_active_forces),
            army_vespene=int(e.vespene_used_active_forces),
        )
        for e in replay.tracker_events
        if isinstance(e, PlayerStatsEvent) and e.pid in pids
    )
    history = ctx.simple.st.supplyHistory
    supply = tuple(
        SupplyPoint(int(player.pid), str(s.time), float(s.supply), float(s.limit)) for player in history for s in history[player]
    )
    chronos = tuple(
        Chrono(int(e.player.pid), int(e.frame), int(e.target_unit_id))
        for e in replay.game_events
        if isinstance(e, TargetUnitCommandEvent)
        and not isinstance(e, UpdateTargetUnitCommandEvent)
        and e.player is not None
        and vars(e).get("ability_name") == CHRONO_BOOST  # upstream's own value, not a fork property
    )
    build_times, unmapped = _build_times(ctx.simple.unitsInfoDict, {str(u.name) for u in replay.datapack.units.values()})
    tables = TimeTables(
        build_times=build_times,
        research_times=tuple((name, str(row["Upgrade Time"])) for name, row in ctx.simple.upgradesInfoDict.items()),
        units_source_sha256=_sha256(support_root / "unitsInfo.csv"),
        upgrades_source_sha256=_sha256(support_root / "upgradesInfo.csv"),
        unmapped_units=unmapped,
    )
    return Exposed(game, units, changes, upgrades, stats, supply, chronos, tables)
