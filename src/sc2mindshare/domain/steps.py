"""A player's build order as numbered steps (CR-034, S2-1; P0-2 rules, P0-6 Option A presentation).

``analysis.build_steps`` computes them from the exposed values (CR-021, TD-18) and puts each on the node
that holds its units; ``export`` writes them as the step properties. A step's start is kept in game loops,
exactly (a derived start such as born - 12 s is 478.2 loops), and rounded down to its second only to be
shown (Leo's rule: rounding first would split a batch at a second boundary).

``BuildStep.line`` is the one text form of a step, used both in the Player node's build-order list and in
a node's ``steps`` property, so the two never disagree (Iris, AC-10). Its ``m:ss`` is description prose
in the guide style, not a time field (``domain.time`` names it as the second stated exception).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from sc2mindshare.domain.time import LOOPS_PER_SECOND

#: ``domain.time.LOOPS_PER_SECOND`` (22.4) as an exact fraction (112/5), so a start's second is exact.
_LOOPS_PER_SECOND = Fraction(str(LOOPS_PER_SECOND))

#: The step kinds (P0-2 §3): a worker or another unit (born, or warped in), a building (its init), a building
#: morph (Lair, Warp Gate: a Building node of its own, D53b), a unit morph (Baneling, Ravager, Overseer: a step
#: in the list only) and an upgrade.
KINDS = ("worker", "unit", "building", "building morph", "unit morph", "upgrade")


def second_of(loop: Fraction) -> int:
    """The whole game second a loop falls in, rounded down (``floor(loop / 22.4)``)."""
    return int(loop // _LOOPS_PER_SECOND)


def loops_of(seconds: Fraction) -> Fraction:
    """A duration in seconds as game loops, exactly (12 s is 268.8 loops)."""
    return seconds * _LOOPS_PER_SECOND


@dataclass(frozen=True)
class BuildStep:
    """One numbered line of a player's build order: ``count`` starts of one item within 8 loops (Leo)."""

    player: int  # the player's pid
    number: int  # step #, 1..N per player, counting lines (D52a)
    kind: str  # one of KINDS
    item: str  # the internal id at the start (U3, never the final type): "SpawningPool", "WarpGateResearch"
    name: str  # the display name, as the nodes are named: "Spawning Pool"
    start: Fraction  # the first member's start, in loops
    supply: int  # R: the supply at the start, Leo's exact reading (CR-035, D2a)
    unit_ids: tuple[int, ...]  # the members, in (start, unit id) order; an upgrade has none
    done_loop: int | None = None  # an upgrade's completion loop (the key of its Upgrade node)
    cancelled: bool = False
    chrono_possible: bool = False
    supply_range: tuple[int, int] | None = None  # (low, high) where the reading is only known within a range (≈)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown step kind {self.kind!r}")
        if self.number < 1:
            raise ValueError(f"a step number starts at 1, not {self.number}")

    @property
    def count(self) -> int:
        return max(1, len(self.unit_ids))

    @property
    def second(self) -> int:
        return second_of(self.start)

    def line(self) -> str:
        """``<step>. <supply> <m:ss> <item>[ ×n][ · note]`` (Iris, AC-10): ``36. 46 4:51 Drone ×8``. A start before
        the game (a unit born after loop 0 but sooner than its build time; none in the sample replays) keeps its
        sign, ``-0:05``, as the pre-game note does (``analysis.fixes.signed_hhmmss``), rather than wrapping."""
        sign, second = ("-", -self.second) if self.second < 0 else ("", self.second)
        text = f"{self.number}. {self.supply} {sign}{second // 60}:{second % 60:02d} {self.name}"
        if self.count > 1:
            text += f" ×{self.count}"
        if self.cancelled:
            text += " · cancelled"
        if self.chrono_possible:
            text += " · chrono possible"
        return text


@dataclass(frozen=True)
class BuildingMorph:
    """A building's morph into another type (Lair, Hive, Greater Spire, Warp Gate, Orbital Command...), shown as a
    Building node of its result at its start, for the whole game (D53b); a step only up to the horizon."""

    player: int
    unit_id: int
    before: str
    after: str
    change_loop: int
    start: Fraction  # change - morph time


@dataclass(frozen=True)
class BuildOrder:
    """Every player's steps up to the horizon, the building morphs of the whole game, and the starts that had to be
    estimated (a type missing from the time tables; logged only, D60a)."""

    steps: tuple[BuildStep, ...]
    morphs: tuple[BuildingMorph, ...]
    horizon_second: int  # 360 (6:00, D48a), or the game's end second when it ends earlier
    estimated: tuple[str, ...] = ()

    def of(self, player: int) -> tuple[BuildStep, ...]:
        return tuple(s for s in self.steps if s.player == player)

    def heading(self) -> str:
        h = self.horizon_second
        return f"Build order to {h // 60}:{h % 60:02d} (supply, time, item):"


@dataclass(frozen=True)
class NodeSource:
    """What a node was built from, read once from the legacy layer (``analysis.to_domain.node_model``): the
    player's pid (Player and Upgrade nodes), the unit ids (a Building's one unit, a Units node's units) and,
    for an Upgrade, the upgrade id and its completion loop. It joins steps to nodes; nothing else reads it."""

    pid: int | None = None
    unit_ids: tuple[int, ...] = ()
    upgrade: str | None = None
    loop: int | None = None
