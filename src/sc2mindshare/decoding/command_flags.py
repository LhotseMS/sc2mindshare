"""Command flag bits and camera zoom (CR-048, T3-8).

Bit names are upstream sc2reader's (the Galaxy `c_cmd*` constants, bit 26 `attack_once` from 4.13).
Measured meanings (three replays, against s2protocol's raw events):

- F3-013: bit 3 `smart_click` is set exactly on commands without an ability: a smart (right-click) command;
- F3-014: bit 16 `minimap` commands target a point far (more than 20 map units) from the player's camera,
  other point commands a point near it: the target was clicked on the minimap;
- bits 5 and 10 occur together, only on data commands.

`zoom_events` counts camera updates that carry a distance or a pitch (a zoom or tilt), per player.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, fields
from typing import Any

from sc2reader.events.game import (  # type: ignore[import-untyped]
    CameraEvent,
    CommandEvent,
    DataCommandEvent,
    TargetPointCommandEvent,
    UpdateTargetPointCommandEvent,
    UpdateTargetUnitCommandEvent,
)

BIT_NAMES = {
    0: "alternate",
    1: "queued",
    2: "preempt",
    3: "smart_click",
    4: "smart_rally",
    5: "subgroup",
    6: "set_autocast",
    7: "set_autocast_on",
    8: "user",
    9: "data_a",
    10: "data_b",
    11: "ai",
    12: "ai_ignore_on_finish",
    13: "is_order",
    14: "script",
    15: "homogenous_interruption",
    16: "minimap",
    17: "repeat",
    18: "dispatch_to_other_unit",
    19: "target_self",
    26: "attack_once",
}
MINIMAP_DISTANCE = 20.0  # map units between the camera centre and the target


def flag_names(flags: int) -> tuple[str, ...]:
    return tuple(BIT_NAMES.get(bit, f"bit{bit}") for bit in range(32) if flags >> bit & 1)


@dataclass(frozen=True)
class FlagSummary:
    commands: int = 0
    queued: int = 0
    smart: int = 0
    minimap: int = 0
    repeat: int = 0
    data: int = 0
    smart_without_ability: int = 0
    smart_with_ability: int = 0
    minimap_far: int = 0
    minimap_near: int = 0
    other_far: int = 0
    other_near: int = 0

    def __add__(self, other: FlagSummary) -> FlagSummary:
        return FlagSummary(*(getattr(self, f.name) + getattr(other, f.name) for f in fields(self)))


RETARGETS = (UpdateTargetPointCommandEvent, UpdateTargetUnitCommandEvent)


def command_flag_summary(replay: Any) -> dict[int, FlagSummary]:
    """Per player id: new commands (retargets excluded) by flag, with the smart and minimap checks."""
    counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    camera: dict[int, tuple[float, float]] = {}
    for event in sorted(replay.game_events, key=lambda e: e.frame):
        if event.player is None:
            continue
        pid = event.player.pid
        if isinstance(event, CameraEvent):
            if event.location != (0.0, 0.0):  # a zoom-only update has no target; sc2reader reads it as (0, 0)
                camera[pid] = event.location
            continue
        if not isinstance(event, CommandEvent) or isinstance(event, RETARGETS):
            continue
        c = counts[pid]
        names = flag_names(event.flags)
        c["commands"] += 1
        for key, bit in (("queued", "queued"), ("smart", "smart_click"), ("minimap", "minimap"), ("repeat", "repeat")):
            c[key] += bit in names
        c["data"] += isinstance(event, DataCommandEvent)
        if "smart_click" in names:
            c["smart_with_ability" if event.has_ability else "smart_without_ability"] += 1
        if isinstance(event, TargetPointCommandEvent) and pid in camera:
            far = math.dist((event.x, event.y), camera[pid]) > MINIMAP_DISTANCE
            prefix = "minimap" if "minimap" in names else "other"
            c[f"{prefix}_{'far' if far else 'near'}"] += 1
    return {pid: FlagSummary(**c) for pid, c in sorted(counts.items())}


def zoom_events(replay: Any) -> dict[int, int]:
    result: dict[int, int] = defaultdict(int)
    for event in replay.game_events:
        zoomed = isinstance(event, CameraEvent) and (event.distance is not None or event.pitch is not None)
        if zoomed and event.player is not None:
            result[event.player.pid] += 1
    return dict(result)
