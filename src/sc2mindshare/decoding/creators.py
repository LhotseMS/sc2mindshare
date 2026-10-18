"""Unit creator attribution: who produced each unit, with which ability (CR-055, T3-14).

SUnitBornEvent carries the creator unit's tag (index, recycle) and the creator ability's name.
sc2reader 1.9.0's tracker reader decodes both (struct fields 7, 8 and 9) and its UnitBornEvent
drops them. A tracker-events reader keeps them in a separate store, read with ``creations(replay)``:
the births stay plain sc2reader UnitBornEvents, so nothing that stream 1 or sc2reader's plugins
see changes.

Measured on the three replays (s2protocol as the oracle):

- Every creator tag names a unit alive at that loop. Its owner is the born unit's controller,
  except for spawned effects owned by another player: ForceField (neutral, from a Sentry) and one
  ChangelingZealot.
- Larva are created by a Hatchery, Lair or Hive with an empty ability name (``""``). A Zerg unit's
  creator is its egg (the larva's own tag, after the type change), with ``LarvaTrain``; the
  structure behind it is the creator of that larva.
- The births with no creator are the loop-0 units (map units of player 0 and each player's start
  units) and, later, Broodlings and one ParasiticBombRelayDummy.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Any

TRACKER_EVENTS = "replay.tracker.events"
EVENT_ID = 1  # SUnitBornEvent
_CREATOR_INDEX, _CREATOR_RECYCLE, _CREATOR_ABILITY = 7, 8, 9


@dataclass(frozen=True)
class Creation:
    """One birth: the unit, its controller, and the unit and ability that created it (None when absent)."""

    frame: int
    unit_id: int
    unit_type: str
    player_id: int
    creator_id: int | None
    creator_ability: str | None


#: replay -> its creations, in stream order (a weak map: no attribute is set on the Replay).
_CREATIONS: weakref.WeakKeyDictionary[Any, tuple[Creation, ...]] = weakref.WeakKeyDictionary()


def _creation(event: Any, data: dict[int, Any]) -> Creation:
    index, recycle, ability = data.get(_CREATOR_INDEX), data.get(_CREATOR_RECYCLE), data.get(_CREATOR_ABILITY)
    return Creation(
        frame=int(event.frame),
        unit_id=int(event.unit_id),
        unit_type=str(event.unit_type_name),
        player_id=int(event.control_pid),
        # sc2reader's unit ids: index << 18 | recycle (UnitBornEvent.unit_id)
        creator_id=None if index is None or recycle is None else index << 18 | recycle,
        creator_ability=None if ability is None else bytes(ability).decode("utf8"),
    )


class _KeepCreators:
    """A tracker-events reader that delegates to sc2reader's own choice and records the creator fields.

    The births are built by sc2reader's UnitBornEvent itself; a fresh instance of the chosen reader's
    class is used, so the factory's shared reader is never modified (the pattern of CR-044).
    """

    def __call__(self, data: bytes, replay: Any) -> Any:
        default = next(
            reader for accepts, reader in replay.registered_readers[TRACKER_EVENTS] if reader is not self and accepts(replay)
        )
        reader = type(default)()
        born_class = reader.EVENT_DISPATCH[EVENT_ID]
        found: list[Creation] = []

        def born(frames: int, event_data: dict[int, Any], build: int) -> Any:
            event = born_class(frames, event_data, build)
            found.append(_creation(event, event_data))
            return event

        reader.EVENT_DISPATCH[EVENT_ID] = born
        events = reader(data, replay)
        _CREATIONS[replay] = tuple(found)
        return events


def register_readers(replay: Any) -> None:
    """The stream 3 registration for `reader/extensions.register_readers(replay)` (TD-2)."""
    replay.register_reader(TRACKER_EVENTS, _KeepCreators(), lambda r: True)


def creations(replay: Any) -> tuple[Creation, ...]:
    """Every birth in the tracker stream, in order; empty when the reader was not registered."""
    return _CREATIONS.get(replay, ())


#: Zerg town halls: the creators of larvae (F3-020).
TOWN_HALLS = frozenset({"Hatchery", "Lair", "Hive"})
LARVA = "Larva"
LARVA_TRAIN = "LarvaTrain"


@dataclass(frozen=True)
class LarvaProduction:
    """A larva-made unit traced to its town hall: unit -> egg (the larva's own tag) -> the larva's creator (CR-057)."""

    frame: int
    unit_id: int
    unit_type: str
    player_id: int
    larva_id: int
    #: None when the larva's birth (or its creator) is not in the tracker stream.
    town_hall_id: int | None
    #: The town hall's type at the unit's birth loop (Hatchery, Lair or Hive), None with town_hall_id.
    town_hall_type: str | None


def _type_at(unit: Any, frame: int) -> str:
    """A unit's type at a loop; sc2reader's ``name`` is its final type (F3-007)."""
    name = unit.name
    for loop, unit_type in sorted(unit.type_history.items()):
        if loop <= frame:
            name = unit_type.name
    return str(name)


def larva_production(replay: Any) -> tuple[LarvaProduction, ...]:
    """Every ``LarvaTrain`` birth with its larva and town hall, in stream order."""
    larva_creator = {c.unit_id: c.creator_id for c in creations(replay) if c.unit_type == LARVA}
    rows = []
    for c in creations(replay):
        if c.creator_ability != LARVA_TRAIN or c.creator_id is None:
            continue
        hall_id = larva_creator.get(c.creator_id)
        hall = None if hall_id is None else replay.objects.get(hall_id)
        rows.append(
            LarvaProduction(
                frame=c.frame,
                unit_id=c.unit_id,
                unit_type=c.unit_type,
                player_id=c.player_id,
                larva_id=c.creator_id,
                town_hall_id=None if hall is None else hall_id,
                town_hall_type=None if hall is None else _type_at(hall, c.frame),
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class LarvaUse:
    """Per town hall: larvae it spawned, how many of them became an egg, and the units they made."""

    player_id: int
    town_hall_id: int
    larvae: int
    larvae_used: int
    units: int


def larva_use(replay: Any) -> tuple[LarvaUse, ...]:
    """One row per town hall that spawned a larva, ordered by its id."""
    larvae: dict[int, set[int]] = {}
    owner: dict[int, int] = {}
    for c in creations(replay):
        if c.unit_type == LARVA and c.creator_id is not None:
            larvae.setdefault(c.creator_id, set()).add(c.unit_id)
            owner.setdefault(c.creator_id, c.player_id)
    used: dict[int, set[int]] = {}
    units: dict[int, int] = {}
    for p in larva_production(replay):
        if p.town_hall_id is not None:
            used.setdefault(p.town_hall_id, set()).add(p.larva_id)
            units[p.town_hall_id] = units.get(p.town_hall_id, 0) + 1
    return tuple(LarvaUse(owner[h], h, len(larvae[h]), len(used.get(h, set())), units.get(h, 0)) for h in sorted(larvae))
