"""Upstream sc2reader 1.9.0's event classes, for ``isinstance`` checks outside reader/ (CR-021, T20).

Only reader/ imports sc2reader (tests/test_architecture.py). Code that reads upstream's own attributes,
such as ``analysis.exposed``, takes the classes from here rather than from ``fork_api``, so it does not
depend on the fork's API. The fork-flavoured classes ``fork_api.flavour_replay`` swaps in are subclasses
of these, so the checks hold on a flavoured replay too. ``__all__`` is the explicit re-export
``mypy --strict`` needs.
"""

from __future__ import annotations

from sc2reader.events.game import (  # type: ignore[import-untyped]
    TargetUnitCommandEvent,
    UpdateTargetUnitCommandEvent,
)
from sc2reader.events.tracker import (  # type: ignore[import-untyped]
    PlayerStatsEvent,
    UnitBornEvent,
    UnitDiedEvent,
    UnitDoneEvent,
    UnitInitEvent,
    UnitTypeChangeEvent,
    UpgradeCompleteEvent,
)

__all__ = [
    "PlayerStatsEvent",
    "TargetUnitCommandEvent",
    "UnitBornEvent",
    "UnitDiedEvent",
    "UnitDoneEvent",
    "UnitInitEvent",
    "UnitTypeChangeEvent",
    "UpdateTargetUnitCommandEvent",
    "UpgradeCompleteEvent",
]
