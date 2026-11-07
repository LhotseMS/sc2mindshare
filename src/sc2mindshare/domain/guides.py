"""Build order guides and the build check (CR-035, S2-2; P0-1 format, P0-3 rules as amended by Leo's CR-035 notes).

A **build order guide** (a reference build order; P0-1 calls it a benchmark, a word the player never sees) is one
opening for a race against an opponent race, as ordered steps up to a horizon. ``analysis.guides`` loads and checks
the files; ``analysis.build_check`` compares a player's steps (``domain.steps``) with a guide and gives a
``BuildCheck``, or a ``NoBuildCheck`` with the reason none was made (AC10).

Times are whole game seconds (a guide's ``m:ss``) or game loops (a player's start, as ``domain.steps`` keeps it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

#: The verdicts (P0-6, Iris; Stefan's Q2-Q4): a guide step graded by supply, by time, or waiting on an event.
ON_SUPPLY, ON_TIME, A_BIT_LATE, LATE, EARLY = "on supply", "on time", "a bit late", "late", "early"
DONE, MISSING, NOT_COMPARED, GAME_ENDED, OPTIONAL = "done", "missing", "not compared", "not compared (game ended)", "optional"
VERDICTS = (ON_SUPPLY, ON_TIME, A_BIT_LATE, LATE, EARLY, DONE, MISSING, NOT_COMPARED, GAME_ENDED, OPTIONAL)


@dataclass(frozen=True)
class GuideStep:
    """One step of a guide (P0-1 §3). ``number`` counts from 1 in the file's order (the check's "Step <n>")."""

    number: int
    item: str
    text: str
    kind: str
    count: int = 1
    supply: int | None = None
    supply_range: tuple[int, int] | None = None
    time: int | None = None  # whole seconds
    time_interval: tuple[int, int] | None = None
    time_source: str | None = None
    trigger: str | None = None
    alternatives: tuple[str, ...] = ()
    key: bool = False
    optional: bool = False
    note: str | None = None

    @property
    def items(self) -> tuple[str, ...]:
        """The item and its alternatives: any of them pairs with this step."""
        return (self.item, *self.alternatives)

    @property
    def timed(self) -> bool:
        return self.time is not None or self.time_interval is not None

    @property
    def supply_bounds(self) -> tuple[int, int] | None:
        if self.supply is not None:
            return (self.supply, self.supply)
        return self.supply_range


@dataclass(frozen=True)
class Guide:
    """One build order guide (P0-1 §2)."""

    id: str
    name: str
    race: str
    vs: str
    era: str
    patch: str | None
    as_of: str
    horizon: int  # seconds; 6:00 when the file gives none (D8a)
    source: dict[str, Any] = field(compare=False, hash=False)
    steps: tuple[GuideStep, ...] = ()
    file: str = ""  # the file it was read from (for messages only)

    @property
    def team_draft(self) -> bool:
        """AC8: a guide the team wrote, not yet confirmed by a player of that race."""
        return self.source.get("kind") == "project"

    @property
    def attribution(self) -> str | None:
        value = self.source.get("attribution")
        return value if isinstance(value, str) else None

    @property
    def window(self) -> int:
        """The reach plus 30 s: a guide step not made by then is missing (P0-3)."""
        return self.horizon + 30

    def matches(self, race: str, opponent: str | None) -> bool:
        """The guide is for this race and matchup; a guide for any opponent (``vs: Any``) matches every one."""
        return self.race == race and (self.vs == "Any" or self.vs == opponent)


@dataclass(frozen=True)
class Occurrence:
    """One unit (or building, or upgrade) of a player's step, as the comparison sees it: a step of ``count`` n is n
    occurrences (Zerglings counted per unit, TD-39)."""

    item: str
    step: int  # the player's step number
    start: Fraction  # loops
    supply: int  # R (CR-035, D2a)
    supply_range: tuple[int, int] | None
    kind: str
    exact: bool  # a building or a warp-in starts at its init, exactly
    chrono_possible: bool
    estimated: bool  # the start was estimated (no build time): not compared

    @property
    def seconds(self) -> Fraction:
        return self.start / Fraction(112, 5)

    @property
    def low(self) -> int:
        return self.supply_range[0] if self.supply_range else self.supply

    @property
    def high(self) -> int:
        return self.supply_range[1] if self.supply_range else self.supply


@dataclass(frozen=True)
class Later:
    """A start after the window (``done later``): its time and what made it, to link to its node when it has one."""

    item: str
    start: Fraction  # loops
    kind: str
    unit_id: int | None
    done_loop: int | None = None  # an upgrade's completion (the key of its Upgrade node)


@dataclass(frozen=True)
class Row:
    """One occurrence of a guide step and what the player did for it."""

    guide_step: int  # GuideStep.number
    occurrence: int  # 1..count
    verdict: str  # one of VERDICTS
    graded_by: str | None = None  # "time", "supply" or None (done, missing, not compared)
    paired: Occurrence | None = None
    off: int | None = None  # Δ seconds (by time) or Δ supply (by supply), from the range end nearest the guide's value
    approx: bool = False  # ≈: the player's supply range straddles two bands (D6a)
    moment: Fraction | None = None  # a trigger's moment, in seconds (None: it never came, or cannot be evaluated)
    done_later: Later | None = None


@dataclass(frozen=True)
class BuildCheck:
    """A player's build compared with a guide (AC2-AC9)."""

    player: int  # pid
    guide: Guide
    picked: bool  # named on the command line (True) or suggested (False, D1a)
    rows: tuple[Row, ...]
    extras: tuple[tuple[int, str], ...]  # (player step number, item), one per extra occurrence
    counted: tuple[tuple[str, int], ...]  # unit types counted, not graded (item, occurrences), in first-start order
    score: Fraction  # Leo's suggestion score: lower is closer
    game_second: int  # the game's last second

    def rows_of(self, step: int) -> tuple[Row, ...]:
        return tuple(r for r in self.rows if r.guide_step == step)

    def step_verdict(self, step: GuideStep) -> str:
        """A guide step's verdict on the card: a step of several units is done (or graded) only if every one was
        made in time; otherwise it counts once under missing (AC2, O-9)."""
        rows = self.rows_of(step.number)
        missing = [r for r in rows if r.verdict == MISSING]
        return MISSING if missing else rows[0].verdict

    @property
    def graded_by(self) -> str:
        """AC4: "time", "supply" or "time and supply", by the rows that were graded."""
        kinds = {r.graded_by for r in self.rows if r.graded_by}
        if kinds == {"time", "supply"}:
            return "time and supply"
        return "time" if kinds == {"time"} else "supply"


@dataclass(frozen=True)
class NoBuildCheck:
    """No comparison for a player (AC10): the ``build check`` value and the one line his Player node gets."""

    player: int
    value: str  # "none, other matchup" ...
    line: str  # "No build check: ..."
