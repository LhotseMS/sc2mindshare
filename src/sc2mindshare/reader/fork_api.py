"""The old fork's object API on upstream sc2reader 1.9.0 objects, for the strangler port (CR-011).

Stefan's layer (now ``sc2mindshare.analysis``) was written against a fork that edited sc2reader's
event, unit and player classes in place: extra properties (``second`` as ``frame / 22.4``,
``time``, ``playerName``, ``player``/``pid`` on tracker events ...), extra methods
(``registerUpdateEvent``, ``isCombat``, ``countableUnitDeath`` ...), rewritten ``__str__`` methods
(CR-011c makes that text explicit: ``compat.object_text``; no ``__str__`` is overridden here), and
two control-group classes of its own.

``flavour_replay(replay)`` gives a loaded upstream replay that API without touching sc2reader: each
event, unit and player gets a **subclass** of its own upstream class that adds the fork's members
(``obj.__class__`` is swapped), so every ``isinstance`` check against upstream classes still holds,
and ``type(obj).__name__`` and ``str(type(obj))`` read as before. The fork's fields, and the values
it computed differently in ``__init__`` (``second``), are properties backed by
``reader.side_fields`` (CR-020, T19): the objects keep upstream's attributes and values. The
replay's datetimes are made naive again, as the fork's ``utcfromtimestamp`` gave them.

Everything the ported layer imported from sc2reader is re-exported here (``from fork_api import *``
gives every public name), so ``analysis`` never imports sc2reader itself (tests/test_architecture.py). This module, ``plugins.mindshare_context``
and ``compat`` are the strangler's only contact with sc2reader objects. The class swap itself and the
naive datetimes are the remaining changes to sc2reader objects (CR-064, after T19).
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

from sc2mindshare.reader import compat, side_fields

LOOPS_PER_SECOND = compat.LOOPS_PER_SECOND

from sc2mindshare.reader.event_types import COMBAT_ABILITIES

# --- the fork's members, by class ---------------------------------------------------------------


class _EventMixin:
    def isUnique(self, prevEvent: Any) -> bool:
        return True

    def isPlayer(self, pids: Any) -> bool:
        return False


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


class _CommandEventMixin(_GameEventMixin):
    def registerUpdateEvent(self, e: Any) -> None:
        side_fields.get(self, "updateEvents").append(e)
        side_fields.set(e, "targetCommandEvent", self)

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


class _CommandManagerStateEventMixin(_GameEventMixin):
    """The fork's ``__str__`` for this class is not needed (CR-011c)."""


class _SelectionEventMixin(_GameEventMixin):
    def isPlayer(self, playerNames: Any) -> bool:
        return self.playerName in playerNames


class _CameraEventMixin(_GameEventMixin):
    def isPlayer(self, names: Any) -> bool:
        return self.playerName in names


class _ControlGroupEventMixin(_GameEventMixin):
    """The fork's ``__str__`` for this class is not needed (CR-011c)."""


class _MessageEventMixin(_EventMixin):
    frame: int
    name: str

    def _str_prefix(self) -> str:
        return f"{Length(seconds=int(self.frame / LOOPS_PER_SECOND))}\t "


class _TrackerEventMixin(_EventMixin):
    frame: int
    name: str

    def _str_prefix(self) -> str:
        return f"{Length(seconds=int(self.frame / LOOPS_PER_SECOND))}\t "

    @property
    def time(self) -> str:
        return self._str_prefix().replace(".", ":").split("\t")[0]


class _PlayerStatsEventMixin(_TrackerEventMixin):
    """The fork's ``__str__`` for this class is not needed (CR-011c)."""


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


class _UnitInitEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return self.unit_upkeeper  # type: ignore[attr-defined]

    @property
    def pid(self) -> Any:
        return self.upkeep_pid  # type: ignore[attr-defined]

    def isCounted(self) -> bool:
        return True


class _UnitDoneEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return self.unit.owner  # type: ignore[attr-defined]

    @property
    def pid(self) -> Any:
        return self.unit.owner.pid  # type: ignore[attr-defined]


class _UnitTypeChangeEventMixin(_TrackerEventMixin):
    @property
    def pid(self) -> Any:
        return self.unit.owner.pid  # type: ignore[attr-defined]

    @property
    def player(self) -> Any:
        return self.unit.owner  # type: ignore[attr-defined]


class _UpgradeCompleteEventMixin(_TrackerEventMixin):
    """The fork's ``__str__`` for this class is not needed (CR-011c)."""


class _UnitPositionsEventMixin(_TrackerEventMixin):
    @property
    def player(self) -> Any:
        return -1

    @property
    def pid(self) -> Any:
        return -1


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


class _PlayerMixin:
    """The fork's ``nameC`` and ``replaceStrings`` members are gone (CR-023, P2): the layer cleans names with
    ``compat.clean_name`` / ``compat.object_text`` and its fix set, so no fix-less cleaning is left on the objects."""


class _ParticipantMixin(_PlayerMixin):
    """The fork's ``__str__`` for this class is not needed (CR-011c)."""


# --- the fork's fields, kept beside the objects (CR-020, T19) ------------------------------------
# Data descriptors on the flavoured classes: reading falls back to upstream's own value, writing goes
# to reader.side_fields, never onto the object (so its __dict__ stays upstream's).

_FIELDS_BY_MIXIN: tuple[tuple[type, tuple[str, ...]], ...] = (
    (_EventMixin, ("second", "name", "timeLocation")),
    (_CommandEventMixin, (*side_fields.COMMAND_FIELDS, *side_fields.COPIED_FROM_TARGET)),
    (_CommandManagerStateEventMixin, ("commandEvent",)),
    (_SelectionEventMixin, ("cameraLocation",)),
    (_UnitMixin, side_fields.UNIT_FIELDS),
)
for _mixin, _names in _FIELDS_BY_MIXIN:
    for _name in _names:
        setattr(_mixin, _name, side_fields.field(_name))


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
    entities = list(replay.players) + list(getattr(replay, "observers", []))
    for obj in [*replay.events, *replay.objects.values(), *entities]:
        side_fields.adopt(obj, replay)  # their fork fields belong to this replay and go with it
    for event in replay.events:
        flavour_event(event)
    for unit in replay.objects.values():
        _swap(unit)
    for entity in entities:
        _swap(entity)
    for name in ("end_time", "start_time", "date"):
        value = getattr(replay, name, None)
        if value is not None and getattr(value, "tzinfo", None) is not None:
            setattr(replay, name, value.replace(tzinfo=None))
    return replay
