"""Research: completed upgrades without the cosmetics, and the commands that queue research (CR-060, part 1).

Measured on the three replays (F3-025):

- ``UpgradeCompleteEvent`` also reports cosmetics: every ``RewardDance*`` and ``Spray*`` entry at loop 0
  (the player's unlocked rewards), and a ``Spray*`` entry each time a spray is used in game. They are
  not research and are left out here.
- A research is queued by a command whose ability is named ``Research*``, ``Evolve*`` or ``Upgrade*``
  (but ``UpgradeTo*`` is a morph, such as ``UpgradeToLair``).

Pairing a command with its completion needs a map from ability to upgrade (``EvolveMetabolicBoost``
completes ``zerglingmovementspeed``; ``ResearchWarpGate`` completes ``WarpGateResearch``) and the
research durations; both wait for CR-053's unit and upgrade data, so no start time is derived here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sc2reader.events.game import (  # type: ignore[import-untyped]
    CommandEvent,
    UpdateTargetPointCommandEvent,
    UpdateTargetUnitCommandEvent,
)
from sc2reader.events.tracker import UpgradeCompleteEvent  # type: ignore[import-untyped]

COSMETIC_PREFIXES = ("RewardDance", "Spray")
RESEARCH_PREFIXES = ("Research", "Evolve", "Upgrade")
MORPH_PREFIX = "UpgradeTo"


@dataclass(frozen=True)
class ResearchEvent:
    frame: int
    player_id: int
    #: The upgrade's name for a completion, the ability's name for a command.
    name: str


def is_research_ability(name: str | None) -> bool:
    return name is not None and name.startswith(RESEARCH_PREFIXES) and not name.startswith(MORPH_PREFIX)


def research_completions(replay: Any) -> tuple[ResearchEvent, ...]:
    """Completed upgrades, without the reward and spray cosmetics, in stream order."""
    return tuple(
        ResearchEvent(int(e.frame), int(e.pid), str(e.upgrade_type_name))
        for e in replay.tracker_events
        if isinstance(e, UpgradeCompleteEvent) and not str(e.upgrade_type_name).startswith(COSMETIC_PREFIXES)
    )


def research_commands(replay: Any) -> tuple[ResearchEvent, ...]:
    """Commands that queue a research (retargets excluded), in stream order."""
    return tuple(
        ResearchEvent(int(e.frame), int(e.player.pid), str(e.ability_name))
        for e in replay.game_events
        if isinstance(e, CommandEvent)
        and not isinstance(e, UpdateTargetPointCommandEvent | UpdateTargetUnitCommandEvent)
        and e.player is not None
        and is_research_ability(getattr(e, "ability_name", None))
    )
