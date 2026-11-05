"""The old fork's core behaviour, as plain functions over upstream sc2reader 1.9.0 objects (CR-010).

The Mindshare layer was written against a fork that changed sc2reader's events and objects in
place. Each function here gives the fork's value from an unmodified upstream object, so the
strangler port (CR-011) replaces ``e.second`` with ``game_second(e)`` and so on, call site by call
site, bug-faithfully. The time helpers serve the moved legacy layer only: since CR-022 (T21) the
domain models carry ``domain.time.GameTime`` (loops), and only ``export/`` writes time as text.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from sc2reader.utils import Length  # type: ignore[import-untyped]

#: Game loops per real second (LotV "faster"); the fork's base for every time value.
LOOPS_PER_SECOND = 22.4


# --- time ------------------------------------------------------------------------------


def game_second(event: Any) -> float:
    """The fork's ``GameEvent.second`` and ``MessageEvent.second``: ``frame / 22.4`` (a float)."""
    return float(event.frame / LOOPS_PER_SECOND)


def tracker_second(event: Any) -> int:
    """The fork's ``TrackerEvent.second``: ``int(frame / 22.4)``."""
    return int(event.frame / LOOPS_PER_SECOND)


def length_str(seconds: int) -> str:
    """sc2reader's ``Length`` text: ``MM.SS``, or ``HH.MM.SS`` from one hour on."""
    return str(Length(seconds=seconds))


def game_time(event: Any) -> str:
    """The fork's ``GameEvent.time``: ``Length(seconds=int(frame / 22.4))``, e.g. ``"02.02"``."""
    return length_str(int(event.frame / LOOPS_PER_SECOND))


def tracker_time(event: Any) -> str:
    """The fork's ``TrackerEvent.time``: the same length with ``.`` replaced by ``:``, e.g. ``"02:02"``."""
    return game_time(event).replace(".", ":")


def type_at(unit: Any, frame: int) -> str:
    """The unit's type at ``frame`` (upstream's ``Unit.type_history``: frame -> type, in order), by its id
    such as ``Hatchery``; the unit's current type when the history has nothing at or before ``frame``."""
    name = None
    for changed_at, unit_type in unit.type_history.items():
        if changed_at > frame:
            break
        name = unit_type.name
    return str(name if name is not None else unit.name)


#: CR-023 S8: the types missing from sc2reader's datapack that are a mode or a cocoon of a type the unit already
#: was (the value), whose supply the unit keeps, as in the game (Vera confirmed the mode switch). The names are
#: sc2reader's type titles, which the type history holds (OverlordCocoon's title is OverseerCocoon, in the
#: datapack, so it is not listed; nor are Viking, BattleHellion, DroneBurrowed or SwarmHostBurrowed).
MODES_MISSING_FROM_THE_DATAPACK = {
    "ObserverSiegeMode": "Observer",
    "OverseerSiegeMode": "Overseer",
    "OverlordTransport": "Overlord",
    "TransportOverlordCocoon": "Overlord",
    "LiberatorAG": "Liberator",
    "ThorAP": "Thor",
    "RavagerBurrowed": "Ravager",
    "LurkerBurrowed": "Lurker",
}


#: CR-023 P10b (D18a): structures sc2reader's datapack marks neither buildings nor army (OMIT_UNITS meant them as
#: "Shield battery" / "Extractor Rich", which never match), and the unitsInfo.csv row each builds as. Here, not in
#: ``analysis``, since CR-068 (P10c): ``fork_api``'s death rules read it too.
P10B_STRUCTURES = {"ShieldBattery": "Shield Battery", "ExtractorRich": "Extractor"}


def _datapack_names() -> set[str]:
    from sc2reader.data import unit_lookup  # type: ignore[import-untyped]

    return {name for race in ("Protoss", "Terran", "Zerg") for name in unit_lookup[race]}


def unnamed_missing_type(unit: Any, frame: int) -> str | None:
    """CR-023 S8: the unit's type at ``frame`` when it is missing from the datapack and not a named mode
    (``MODES_MISSING_FROM_THE_DATAPACK``); None otherwise."""
    name = type_at(unit, frame)
    if name.lower() in _datapack_names() or name in MODES_MISSING_FROM_THE_DATAPACK:
        return None
    return name


def supply_at(unit: Any, frame: int) -> float:
    """The unit's supply at ``frame`` (CR-023 S6, D15a): the supply of its type then, by upstream's type history
    and datapack (a cocoon counts its target's, RavagerCocoon 3); a type missing from the datapack keeps the
    supply the unit had (ObserverSiegeMode has none there). The unit's current type when the history is empty."""
    known = _datapack_names()
    supply: float | None = None
    for changed_at, unit_type in unit.type_history.items():
        if changed_at > frame:
            break
        if supply is None or str(unit_type.name).lower() in known:
            supply = float(unit_type.supply)
    return supply if supply is not None else float(unit.supply)


def unit_text_at(unit: Any, frame: int, fixes: frozenset[str]) -> str:
    """``object_text(unit, fixes)`` for the unit's type at ``frame`` instead of its final type (CR-023 N1):
    the text the layer names and groups a unit by when ``N1`` is in its fixes."""
    return clean_name(f"{type_at(unit, frame)} ", True, fixes)


# --- names -------------------------------------------------------------------------------

#: The two removals CR-023 P2 skips: a race word anywhere in a name.
_BARE_RACE_WORDS = (("Terran", ""), ("Zerg", ""))

#: The fork's ``MsUtils.replaceStrings`` table, in its order (python bug 2 included: "Zerg" and
#: "Terran" are removed anywhere, so "Zergling" becomes "ling").
_REPLACEMENTS = (
    ("Player 1 - ", ""),
    ("Player 2 - ", ""),
    (" (Terran)", ""),
    (" (Zerg)", ""),
    (" (Protoss)", ""),
    (" upgrade completed", ""),
    ("Attack", "A move"),
    ("zerglingmovementspeed", "ZerglingMovementSpeed"),
    ("zerglingattackspeed", "ZerglingAttackSpeed"),
    ("Chrono Boost Energy Cost", "Chrono Boost"),
    ("Spawn larva", "Inject"),
    ("SiegeTankSieged", "Sieged Tank"),
    ("Terran", ""),
    ("Zerg", ""),
)


def object_text(value: Any, fixes: frozenset[str] = frozenset()) -> str:
    """The text the fork's ``__str__`` gave a unit or a player, made explicit (CR-011c).

    The legacy layer built names and descriptions with ``str(unit)`` and ``"{}".format(player)``,
    which only worked because the fork rewrote ``Unit.__str__`` and ``Participant.__str__``. With
    upstream objects, those calls would print ``Zealot [2C80001]`` and ``Player 1 - name (Zerg)``.
    Every such call site now goes through this function; anything else is ``str()``.
    """
    from sc2reader.data import Unit
    from sc2reader.objects import Player  # type: ignore[import-untyped]

    if isinstance(value, Unit):
        return clean_name(f"{value.name} ", True, fixes)
    if isinstance(value, Player):
        return str(value.name)
    return str(value)


def clean_name(value: Any, split: bool = False, fixes: frozenset[str] = frozenset()) -> str:
    """The fork's ``MsUtils.replaceStrings`` / ``Renamer.replaceStrings``: bug-faithful with no ``fixes``.

    CR-023 P2 (in ``fixes``): the two bare race-word removals (``"Terran"``, ``"Zerg"`` anywhere, python
    bug 2: "Zergling" -> "ling") are skipped. The layer passes its ``ctx.fixes`` at every site whose text
    reaches the output; the default keeps the bug-faithful text (QA's oracle)."""
    text = value if isinstance(value, str) else object_text(value, fixes)
    for old, new in _REPLACEMENTS:
        if "P2" in fixes and (old, new) in _BARE_RACE_WORDS:
            continue
        text = text.replace(old, new)
    text = re.sub(r"\[\w+\]", "", text)
    if split:
        text = re.sub(
            r"(?<=[a-z])([A-Z0-9])|^[A-Z]",
            lambda m: (" " if m.start() != 0 else "") + m.group(0),
            text,
        )
    return text.rstrip()


def player_name(event: Any) -> str:
    """The fork's ``GameEvent.playerName``."""
    if getattr(event, "pid", 16) == 16:
        return "Global"
    player = getattr(event, "player", None)
    if player and not player.name:
        return f"{player.play_race}"
    if player:
        return str(player.name)
    return "no name"


# --- control groups ---------------------------------------------------------------------


class ControlGroupKind(Enum):
    """The fork's control-group event classes, by the raw update type (TD-5 keeps them until a fix).

    Upstream 1.9.0 names them differently (4 = steal and set, 5 = steal and add, 3 = delete);
    stream 3's finding T3-7 will decide the meaning, and the fix is a stream 1 ledger task.
    """

    SET = "SetControlGroupEvent"  # 0
    ADD = "AddToControlGroupEvent"  # 1
    GET = "GetControlGroupEvent"  # 2
    UNKNOWN_3 = "ControlGroupEvent"  # 3: the fork's plain ControlGroupEvent
    STEAL = "StealControlGroupEvent"  # 4
    WEIRD = "WeirdControlGroupEvent"  # 5
    OTHER = "ControlGroupEvent?"  # any other value: the fork's plain ControlGroupEvent


_KIND_BY_UPDATE = {
    0: ControlGroupKind.SET,
    1: ControlGroupKind.ADD,
    2: ControlGroupKind.GET,
    3: ControlGroupKind.UNKNOWN_3,
    4: ControlGroupKind.STEAL,
    5: ControlGroupKind.WEIRD,
}


def control_group_kind(event: Any) -> ControlGroupKind:
    """The class the fork would have created for this control-group event."""
    return _KIND_BY_UPDATE.get(event.update_type, ControlGroupKind.OTHER)


def fork_class_name(event: Any) -> str:
    """The fork's class name for an event (only control-group events were renamed)."""
    from sc2reader.events.game import ControlGroupEvent  # type: ignore[import-untyped]

    if isinstance(event, ControlGroupEvent):
        kind = control_group_kind(event)
        return "ControlGroupEvent" if kind is ControlGroupKind.OTHER else kind.value
    return str(type(event).__name__)
