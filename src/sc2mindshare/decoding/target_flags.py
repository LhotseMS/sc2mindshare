"""Target-unit flags on unit-targeted commands and retargets (CR-046, T3-6).

sc2reader exposes the field as `target_flags` and marks its meaning unknown. On the three replays it
takes two values:

- 111 (0b0110_1111): the target tag is a unit the tracker stream knows (every one of them);
- 175 (0b1010_1111): the target tag never appears in the tracker stream, and the target is never one
  of the player's own units.

F3-011 (supported on three replays; engine replay would confirm): 175 marks a fog-of-war snapshot
target (the player's memory of a unit seen earlier), whose tag is the snapshot's, not the unit's.
Bits 6 and 7 are the only difference. Any other value is reported, never guessed.
"""

from __future__ import annotations

import enum
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sc2reader.events.game import TargetUnitCommandEvent  # type: ignore[import-untyped]
from sc2reader.events.tracker import UnitBornEvent, UnitInitEvent  # type: ignore[import-untyped]

UNIT_FLAGS = 111
SNAPSHOT_FLAGS = 175


class TargetKind(enum.Enum):
    UNIT = "unit"
    SNAPSHOT = "snapshot"
    UNKNOWN = "unknown"


def classify(flags: int) -> TargetKind:
    if flags == UNIT_FLAGS:
        return TargetKind.UNIT
    if flags == SNAPSHOT_FLAGS:
        return TargetKind.SNAPSHOT
    return TargetKind.UNKNOWN


@dataclass(frozen=True)
class TargetFlagSummary:
    by_kind_and_relation: dict[tuple[TargetKind, str], int] = field(default_factory=dict)
    resolved: dict[TargetKind, int] = field(default_factory=dict)  # targets whose tag the tracker stream knows
    unknown_flags: dict[int, int] = field(default_factory=dict)


def _relation(event: Any) -> str:
    owner = event.control_player_id
    if not owner:
        return "neutral"
    return "own" if event.player is not None and owner == event.player.pid else "enemy"


def target_flag_summary(replay: Any) -> TargetFlagSummary:
    """Unit-targeted commands and retargets by flag kind and target relation, with tag resolution."""
    tracked = {e.unit_id for e in replay.tracker_events if isinstance(e, (UnitBornEvent, UnitInitEvent))}
    by_kind: Counter[tuple[TargetKind, str]] = Counter()
    resolved: Counter[TargetKind] = Counter({TargetKind.UNIT: 0, TargetKind.SNAPSHOT: 0})
    unknown: Counter[int] = Counter()
    for event in replay.game_events:
        if not isinstance(event, TargetUnitCommandEvent):
            continue
        kind = classify(event.target_flags)
        if kind is TargetKind.UNKNOWN:
            unknown[event.target_flags] += 1
        by_kind[(kind, _relation(event))] += 1
        if event.target_unit_id in tracked:
            resolved[kind] += 1
    return TargetFlagSummary(dict(by_kind), dict(resolved), dict(unknown))
