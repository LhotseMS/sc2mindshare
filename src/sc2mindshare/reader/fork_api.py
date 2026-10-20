"""The old fork's object API on upstream sc2reader 1.9.0 objects, for the strangler port (CR-011).

Stefan's layer (now ``sc2mindshare.analysis``) was written against a fork that edited sc2reader's
event, unit and player classes in place: extra properties (``second`` as ``frame / 22.4``,
``time``, ``playerName``, ``player``/``pid`` on tracker events, ``nameC`` ...), extra methods
(``registerUpdateEvent``, ``isCombat``, ``countableUnitDeath`` ...), rewritten ``__str__`` methods
(names and descriptions in the CSV come from them), and two control-group classes of its own.

``flavour_replay(replay)`` gives a loaded upstream replay that API without touching sc2reader: each
event, unit and player gets a **subclass** of its own upstream class that adds the fork's members
(``obj.__class__`` is swapped), so every ``isinstance`` check against upstream classes still holds,
and ``type(obj).__name__`` and ``str(type(obj))`` read as before. Instance values the fork computed
differently in ``__init__`` (``second``) are recomputed. The replay's datetimes are made naive
again, as the fork's ``utcfromtimestamp`` gave them.

Everything the ported layer imported from sc2reader is re-exported here (``from fork_api import *``
gives every public name), so ``analysis`` never imports sc2reader itself (tests/test_architecture.py). This module, ``plugins.mindshare_context``
and ``compat`` are the strangler's only contact with sc2reader objects; CR-020 (T19) retires the
class swap.
"""

from __future__ import annotations

from typing import Any

from sc2reader.data import *  # type: ignore[import-untyped]
from sc2reader.data import Unit
from sc2reader.events import *  # type: ignore[import-untyped]
from sc2reader.events.base import Event  # type: ignore[import-untyped]
from sc2reader.events.game import (  # type: ignore[import-untyped]
    AddToControlGroupEvent,
    CameraEvent,
    CommandEvent,
    CommandManagerStateEvent,
    ControlGroupEvent,
    DeleteControlGroupEvent,
    GameEvent,
    GetControlGroupEvent,
    SelectionEvent,
    SetControlGroupEvent,
    TargetUnitCommandEvent,
    UpdateTargetPointCommandEvent,
)
from sc2reader.events.message import ChatEvent, MessageEvent  # type: ignore[import-untyped]
from sc2reader.events.tracker import *  # type: ignore[import-untyped]
from sc2reader.events.tracker import (
    PlayerStatsEvent,
    TrackerEvent,
    UnitBornEvent,
    UnitDiedEvent,
    UnitDoneEvent,
    UnitInitEvent,
    UnitPositionsEvent,
    UnitTypeChangeEvent,
    UpgradeCompleteEvent,
)
from sc2reader.objects import Participant, Player  # type: ignore[import-untyped]
from sc2reader.resources import Map, MapInfo, Replay  # type: ignore[import-untyped]
from sc2reader.utils import Length  # type: ignore[import-untyped]

from sc2mindshare.reader import compat

LOOPS_PER_SECOND = compat.LOOPS_PER_SECOND

from sc2mindshare.reader.event_types import COMBAT_ABILITIES

# --- the fork's members, by class ---------------------------------------------------------------


class _EventMixin:
    def isUnique(self, prevEvent: Any) -> bool:
        return True

    def isPlayer(self, pids: Any) -> bool:
        return False

    def replaceStrings(self, input: Any, split: bool = False) -> str:
        return compat.clean_name(input, split)


class _GameEventMixin(_EventMixin):
    frame: int
    name: str

    @property
    def playerName(self) -> str:
        return compat.player_name(self)

    @property
    def time(self) -> str:
        return compat.game_time(self)

    def _str_prefix(self) -> str:
        return compat.game_time(self)

    def __str__(self) -> str:
        return self._str_prefix() + self.name


class _CommandEventMixin(_GameEventMixin):
    def registerUpdateEvent(self, e: Any) -> None:
        self.updateEvents.append(e)  # type: ignore[attr-defined]
        e.targetCommandEvent = self

    def isCombat(self) -> bool:
        return self.ability_name in COMBAT_ABILITIES  # type: ignore[attr-defined]

    def getJson(self) -> str:
        s: Any = self
        if s.ability_type == "TargetUnit":
            text = f"Targeted {s.target.name}" if s.ability.name == "Attack" else f"{s.ability.name} on {s.target.name}"
        else:
            text = "A move" if s.ability.name == "Attack" else f"{s.ability.name}"
        if bool(s.flag["queued"]):
            text += " Q"
        if bool(s.flag["minimap"]):
            text += " M"
        return text

    def __str__(self) -> str:
        s: Any = self
        string = self._str_prefix() + f" {s.player} "
        if s.has_ability:
            string += f"Ability ({s.ability_id:X})"
            string += f" - {s.ability.name}({s.ability.id})" if s.ability else "No self.ability "
        else:
            string += "Right Click" + f" - {s.ability_type}"
        if s.ability_type == "TargetUnit":
            string += f"; Target: {s.target.name} [{s.target_unit_id:0>8X}]"
        if bool(s.flag["queued"]):
            string += " Q"
        if bool(s.flag["minimap"]):
            string += " M"
        if s.ability_type in ("TargetPoint", "TargetUnit"):
            string += f"; Location: {s.location!s}"
        return string + str(self.__class__)


class _CommandManagerStateEventMixin(_GameEventMixin):
    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + self.name + f" {s.sequence} - {s.commandEvent}"


class _SelectionEventMixin(_GameEventMixin):
    def isPlayer(self, playerNames: Any) -> bool:
        return self.playerName in playerNames

    def __str__(self) -> str:
        s: Any = self
        if s.new_units:
            return (
                f"{self.time} {s.player} Selection             "
                + str(s.new_units)
                + " --- "
                + str(s.new_unit_info)
                + "---"
                + str(s.new_unit_types)
                + " CG: "
                + str(s.control_group)
            )
        return f"{self.time} {s.player} Selection             " + _GameEventMixin.__str__(self) + " CG: " + str(s.control_group)


class _CameraEventMixin(_GameEventMixin):
    def isPlayer(self, names: Any) -> bool:
        return self.playerName in names

    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{self.name} at ({s.x}, {s.y})"


class _ControlGroupEventMixin(_GameEventMixin):
    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + " " + self.name + f" : {s.control_group} : {s.update_type}"


def _cg_str(label: str) -> Any:
    def __str__(self: Any) -> str:
        return str(self._str_prefix()) + f" {self.playerName} CG {self.control_group} {label}"

    return __str__


class _MessageEventMixin(_EventMixin):
    frame: int
    name: str

    def _str_prefix(self) -> str:
        return f"{Length(seconds=int(self.frame / LOOPS_PER_SECOND))}\t "

    def __str__(self) -> str:
        return self._str_prefix() + self.name


class _TrackerEventMixin(_EventMixin):
    frame: int
    name: str

    def _str_prefix(self) -> str:
        return f"{Length(seconds=int(self.frame / LOOPS_PER_SECOND))}\t "

    def __str__(self) -> str:
        return self._str_prefix() + self.name

    @property
    def time(self) -> str:
        return self._str_prefix().replace(".", ":").split("\t")[0]


class _PlayerStatsEventMixin(_TrackerEventMixin):
    def __str__(self) -> str:
        return f"\n Time: {self._str_prefix()}"


class _UnitBornEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return self.unit_controller  # type: ignore[attr-defined]

    @property
    def pid(self) -> Any:
        return self.control_pid  # type: ignore[attr-defined]

    def isPlayer(self, pids: Any) -> bool:
        return bool(pids.contain(self.upkeep_pid))  # type: ignore[attr-defined]  # the fork's bug, kept

    def isCounted(self) -> bool:
        return self.unit.type not in [845]  # type: ignore[attr-defined]

    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{s.unit_upkeeper!s: >15} - Unit born {s.unit} at {s.location} id {s.unit_id}"


class _UnitDiedEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return self.unit.owner  # type: ignore[attr-defined]

    @property
    def pid(self) -> Any:
        return self.unit.owner.pid  # type: ignore[attr-defined]

    def isCounted(self) -> bool:
        return self.countableUnitDeath()

    def isWorker(self) -> bool:
        return bool(self.unit.is_worker)  # type: ignore[attr-defined]

    def countableUnitDeath(self) -> bool:
        u: Any = self.unit  # type: ignore[attr-defined]
        return bool(
            (u.is_army or u.is_building or u.name in ["LurkerBurrowed", "Drone", "Probe", "SCV"])
            and not u.name.startswith(("Broodling", "RichMineral", "Mineral", "Force Field"))
        )

    def buildingDeath(self) -> bool:
        return bool(self.unit.is_building)  # type: ignore[attr-defined]

    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{s.unit.name} - Unit died by {s.killing_unit} {s.unit.owner!s: >15} at {s.location}."


class _UnitInitEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return self.unit_upkeeper  # type: ignore[attr-defined]

    @property
    def pid(self) -> Any:
        return self.upkeep_pid  # type: ignore[attr-defined]

    def isCounted(self) -> bool:
        return True

    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{s.unit_upkeeper!s: >15} - Unit initiated {s.unit} at {s.location}"


class _UnitDoneEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return self.unit.owner  # type: ignore[attr-defined]

    @property
    def pid(self) -> Any:
        return self.unit.owner.pid  # type: ignore[attr-defined]

    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{s.unit.owner!s: >15} - Unit {s.unit}({s.unit.id}) {s.unit.location} done"


class _UnitTypeChangeEventMixin(_TrackerEventMixin):
    @property
    def pid(self) -> Any:
        return self.unit.owner.pid  # type: ignore[attr-defined]

    @property
    def player(self) -> Any:
        return self.unit.owner  # type: ignore[attr-defined]

    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{s.unit.owner!s: >15} - Unit {s.unit} type changed to {s.unit_type_name}"


class _UpgradeCompleteEventMixin(_TrackerEventMixin):
    def __str__(self) -> str:
        s: Any = self
        return self._str_prefix() + f"{s.player!s: >15} - {s.upgrade_type_name} upgrade completed"


class _UnitPositionsEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return -1

    @property
    def pid(self) -> Any:
        return -1

    def __str__(self) -> str:
        return self._str_prefix() + "Unit positions update"


class _UnitMixin:
    @property
    def isScout(self) -> bool:
        return self.unit.name in ("Drone", "Probe", "SCV", "Zergling", "Reaper", "Marine", "Oracle", "Phoenix")  # type: ignore[attr-defined]  # the fork's bug (no self.unit), kept

    @property
    def player(self) -> Any:
        return self.owner  # type: ignore[attr-defined]

    @property
    def diedAtSec(self) -> float | None:
        died_at = self.died_at  # type: ignore[attr-defined]
        return None if died_at is None else died_at / LOOPS_PER_SECOND

    @property
    def nameC(self) -> str:
        return compat.clean_name(self.name, True)  # type: ignore[attr-defined]

    def replaceStrings(self, input: Any, split: bool = False) -> str:
        return compat.clean_name(input, split)

    def __str__(self) -> str:
        return compat.clean_name(f"{self.name} ", True)  # type: ignore[attr-defined]


class _PlayerMixin:
    def replaceStrings(self, input: Any, split: bool = False) -> str:
        return compat.clean_name(input, split)


class _ParticipantMixin(_PlayerMixin):
    def __str__(self) -> str:
        return str(self.name)  # type: ignore[attr-defined]

    def __repr__(self) -> str:
        return str(self)


# --- the fork's own control-group classes -----------------------------------------------------


class StealControlGroupEvent(ControlGroupEvent):  # type: ignore[misc]
    """The fork's class for update type 4 (upstream: a SetControlGroupEvent, "steal and set")."""


class WeirdControlGroupEvent(ControlGroupEvent):  # type: ignore[misc]
    """The fork's class for update type 5 (upstream: an AddToControlGroupEvent, "steal and add")."""


StealControlGroupEvent.__module__ = WeirdControlGroupEvent.__module__ = "sc2reader.events.game"

# --- class swapping ------------------------------------------------------------------------------

_MIXINS: tuple[tuple[type, type], ...] = (
    # most specific first
    (UnitBornEvent, _UnitBornEventMixin),
    (UnitDiedEvent, _UnitDiedEventMixin),
    (UnitInitEvent, _UnitInitEventMixin),
    (UnitDoneEvent, _UnitDoneEventMixin),
    (UnitTypeChangeEvent, _UnitTypeChangeEventMixin),
    (UpgradeCompleteEvent, _UpgradeCompleteEventMixin),
    (UnitPositionsEvent, _UnitPositionsEventMixin),
    (PlayerStatsEvent, _PlayerStatsEventMixin),
    (TrackerEvent, _TrackerEventMixin),
    (CommandEvent, _CommandEventMixin),
    (CommandManagerStateEvent, _CommandManagerStateEventMixin),
    (SelectionEvent, _SelectionEventMixin),
    (CameraEvent, _CameraEventMixin),
    (ControlGroupEvent, _ControlGroupEventMixin),
    (GameEvent, _GameEventMixin),
    (MessageEvent, _MessageEventMixin),
    (Event, _EventMixin),
    (Participant, _ParticipantMixin),
    (Player, _PlayerMixin),
    (Unit, _UnitMixin),
)

_FLAVOURED: dict[type, type] = {}

# The fork's __str__ labels of its control-group classes.
_CG_LABELS: dict[type, str] = {
    StealControlGroupEvent: "Steal",
    WeirdControlGroupEvent: "Weird Add?",
    SetControlGroupEvent: "Set",
    AddToControlGroupEvent: "Add",
    GetControlGroupEvent: "Get",
}

# Upstream control-group classes -> the fork's class for the same update type.
_FORK_CONTROL_GROUP = {
    compat.ControlGroupKind.SET: SetControlGroupEvent,
    compat.ControlGroupKind.ADD: AddToControlGroupEvent,
    compat.ControlGroupKind.GET: GetControlGroupEvent,
    compat.ControlGroupKind.UNKNOWN_3: ControlGroupEvent,
    compat.ControlGroupKind.STEAL: StealControlGroupEvent,
    compat.ControlGroupKind.WEIRD: WeirdControlGroupEvent,
    compat.ControlGroupKind.OTHER: ControlGroupEvent,
}


def flavoured_class(cls: type) -> type:
    """``cls`` with the fork's members: a subclass named, and printed, like ``cls``."""
    if cls in _FLAVOURED or getattr(cls, "_fork_flavoured", False):
        return _FLAVOURED.get(cls, cls)
    mixin = next(m for base, m in _MIXINS if issubclass(cls, base))
    members: dict[str, Any] = {"_fork_flavoured": True, "__module__": cls.__module__}
    if cls in _CG_LABELS:
        members["__str__"] = _cg_str(_CG_LABELS[cls])
    flavoured = type(cls.__name__, (mixin, cls), members)
    flavoured.__qualname__ = cls.__qualname__
    _FLAVOURED[cls] = flavoured
    return flavoured


def _swap(obj: Any, base: type | None = None) -> None:
    if obj is None or getattr(type(obj), "_fork_flavoured", False):
        return
    obj.__class__ = flavoured_class(base or type(obj))


def flavour_event(event: Any) -> None:
    if isinstance(event, ControlGroupEvent) and not isinstance(event, (StealControlGroupEvent, WeirdControlGroupEvent)):
        _swap(event, _FORK_CONTROL_GROUP[compat.control_group_kind(event)])
    else:
        _swap(event)
    if isinstance(event, (GameEvent, MessageEvent)):
        event.second = event.frame / LOOPS_PER_SECOND
    elif isinstance(event, TrackerEvent):
        event.second = int(event.frame / LOOPS_PER_SECOND)
    event.name = type(event).__name__


def flavour_replay(replay: Any) -> Any:
    """Give a loaded replay's events, units and players the fork's API (see the module docstring)."""
    for event in replay.events:
        flavour_event(event)
    for unit in replay.objects.values():
        _swap(unit)
    for entity in list(replay.players) + list(getattr(replay, "observers", [])):
        _swap(entity)
    for name in ("end_time", "start_time", "date"):
        value = getattr(replay, name, None)
        if value is not None and getattr(value, "tzinfo", None) is not None:
            setattr(replay, name, value.replace(tzinfo=None))
    return replay
