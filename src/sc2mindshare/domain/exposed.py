"""The values the analysis exposes for stream 2 (CR-021, T20; Cam's P0-2 field list, TD-15, TD-18).

``AnalysisResult.exposed`` is stream 2's read API: what happened in the replay, as plain data, with
times in **game loops** (TD-30; the game clock is loops / 22.4). Nothing here is in the default JSON;
``sc2mindshare build --with-analysis`` adds it as a top-level ``analysis`` object.

The P0-2 numbers map to fields as follows (P0-2 §2):

- U1 ``UnitLife.unit_id`` · U2 ``owner`` · U3 ``first_type`` (the type at birth or init, never the final
  type, TD-13) · U4 ``born_loop`` · U5 ``init_loop`` · U6 ``done_loop`` · U7 ``died_loop``, ``killer``,
  ``killing_unit_id`` · U8 ``x``, ``y`` · U9 ``base`` (None until T22 P1 fixes the base detector) ·
  U10 ``hallucinated``
- M1 ``TypeChange.unit_id`` · M2 ``loop`` · M3 ``before``, ``after`` (every change, in order)
- UP1 ``UpgradeDone.player`` · UP2 ``upgrade`` (the raw id) · UP3 ``loop`` · UP4 ``count``
- PS1 ``StatsSample`` (every PlayerStats sample) · PS2 ``SupplyPoint`` (the layer's own supply and cap
  history) · PS3 ``Chrono`` (Chrono Boost commands with their target)
- C1 ``GameContext.base_build``, ``version`` · C2 ``loops`` · C3 ``PlayerContext`` (race, opponent race,
  order) · C4 ``game_type``, ``team_size``, ``is_ladder`` · C5 ``TimeTables`` (the build and research
  times the analysis read, with their source files' sha256)

No player names: players are identified by their pid (and their order).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitLife:
    """One unit or building of a player, from its birth or init event onwards (U1-U10)."""

    unit_id: int
    owner: int
    first_type: str
    born_loop: int | None
    init_loop: int | None
    done_loop: int | None
    died_loop: int | None
    killer: int | None
    killing_unit_id: int | None
    x: int
    y: int
    hallucinated: bool
    base: str | None = None


@dataclass(frozen=True)
class TypeChange:
    """One UnitTypeChangeEvent, with the type before it (M1-M3)."""

    unit_id: int
    loop: int
    before: str
    after: str


@dataclass(frozen=True)
class UpgradeDone:
    """One UpgradeCompleteEvent (UP1-UP4); cosmetics and loop 0 are kept, filtering is the reader's."""

    player: int
    upgrade: str
    loop: int
    count: int


@dataclass(frozen=True)
class StatsSample:
    """One PlayerStats sample (PS1)."""

    player: int
    loop: int
    food_used: float
    food_made: float
    workers_active: int
    minerals: int
    vespene: int
    minerals_rate: int
    vespene_rate: int
    army_minerals: int
    army_vespene: int


@dataclass(frozen=True)
class SupplyPoint:
    """One entry of the layer's supply history (PS2), as the layer keeps it (time as its own text).

    It adds a unit's supply when the unit is born or done, not when it starts, so it is not the game's food_used:
    fine for supply blocks, never for a step's supply (CR-035 reads ``analysis.build_steps.supply_reading``)."""

    player: int
    time: str
    supply: float
    limit: float


@dataclass(frozen=True)
class Chrono:
    """One Chrono Boost command on a target (PS3)."""

    player: int
    loop: int
    target_unit_id: int


@dataclass(frozen=True)
class PlayerContext:
    pid: int
    order: int
    race: str
    opponent_race: str | None


@dataclass(frozen=True)
class GameContext:
    """C1-C4."""

    base_build: int
    version: str
    loops: int
    game_type: str
    team_size: int
    is_ladder: bool
    players: tuple[PlayerContext, ...]


@dataclass(frozen=True)
class TimeTables:
    """C5: the build and research times the analysis read, as text, keyed by the internal ids the units
    and upgrades carry (U3's ``first_type``, UP2's ``upgrade``), and the sha256 of each source file (so
    stream 2's oracles can be regenerated when they change, TD-29).

    unitsInfo.csv names units by display name ("Void Ray"); each row is keyed by the unit type of the
    replay's own datapack it names: the same text, the text without spaces and punctuation, or one of
    five aliases (``analysis.exposed.UNIT_ALIASES``). The sheet's base rows ("Natural" ... "9th base")
    are the layer's, not unit types, and are left out; any other row that names no unit type is listed
    in ``unmapped_units`` (none on the sample replays). upgradesInfo.csv is keyed by internal id already.

    ``supplies`` (CR-035, D2a): unitsInfo.csv's Supply column as text, keyed like ``build_times`` ("0.5" for a
    Zergling, "0" for an Overlord), for the exact supply reading at each step's start."""

    build_times: tuple[tuple[str, str], ...]
    research_times: tuple[tuple[str, str], ...]
    units_source_sha256: str
    upgrades_source_sha256: str
    unmapped_units: tuple[str, ...] = ()
    supplies: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Exposed:
    game: GameContext
    units: tuple[UnitLife, ...]
    type_changes: tuple[TypeChange, ...]
    upgrades: tuple[UpgradeDone, ...]
    stats: tuple[StatsSample, ...]
    supply: tuple[SupplyPoint, ...]
    chronos: tuple[Chrono, ...]
    tables: TimeTables
