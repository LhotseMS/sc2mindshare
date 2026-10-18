"""Command-manager state and retargets (CR-045, T3-5).

A *retarget* is sc2reader's `UpdateTargetPointCommandEvent` / `UpdateTargetUnitCommandEvent`
(s2protocol `SCmdUpdateTarget*`): the previous order given again with a new target, carrying no
ability of its own. Most follow a smart (right-click) command; 25-35 % follow a selection change.

F3-010 (supported, three replays): every retarget is followed, in the same game loop and by the
same player, by a `CommandManagerStateEvent` with state 1. Counting both as actions counts each
retarget twice; `actions_without_paired_states` counts it once. The command-manager events that
are not paired with a retarget ("unpaired", mostly in runs) have no established meaning yet.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sc2reader.events.game import (  # type: ignore[import-untyped]
    CommandEvent,
    CommandManagerStateEvent,
    SelectionEvent,
    UpdateTargetPointCommandEvent,
    UpdateTargetUnitCommandEvent,
)

RETARGETS = (UpdateTargetPointCommandEvent, UpdateTargetUnitCommandEvent)


@dataclass(frozen=True)
class CommandActivity:
    commands: int  # new orders (s2protocol SCmdEvent)
    retargets: int  # the previous order given again with a new target
    paired_states: int  # command-manager states right after a retarget, same loop
    unpaired_states: int  # the other command-manager states (meaning open)
    retargets_after_selection: int  # retargets whose last preceding input was a selection change

    @property
    def actions_without_paired_states(self) -> int:
        return self.commands + self.retargets + self.unpaired_states


def command_manager_states(replay: Any) -> set[int]:
    return {e.state for e in replay.game_events if isinstance(e, CommandManagerStateEvent)}


def command_activity(replay: Any) -> dict[int, CommandActivity]:
    """Per player id: new commands, retargets and command-manager states, in the replay's event order."""
    per_player: dict[int, list[Any]] = defaultdict(list)
    for event in replay.game_events:
        if event.player is not None:
            per_player[event.player.pid].append(event)
    result = {}
    for pid, events in sorted(per_player.items()):
        counts = {"commands": 0, "retargets": 0, "paired": 0, "unpaired": 0, "after_selection": 0}
        selection_since_command = False
        previous = None
        for event in events:
            if isinstance(event, RETARGETS):
                counts["retargets"] += 1
                counts["after_selection"] += selection_since_command
            elif isinstance(event, CommandEvent):
                counts["commands"] += 1
                selection_since_command = False
            elif isinstance(event, SelectionEvent):
                selection_since_command = True
            elif isinstance(event, CommandManagerStateEvent):
                paired = isinstance(previous, RETARGETS) and previous.frame == event.frame
                counts["paired" if paired else "unpaired"] += 1
            previous = event
        result[pid] = CommandActivity(
            commands=counts["commands"],
            retargets=counts["retargets"],
            paired_states=counts["paired"],
            unpaired_states=counts["unpaired"],
            retargets_after_selection=counts["after_selection"],
        )
    return result
