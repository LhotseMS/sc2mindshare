"""Each player's build order as numbered steps, on the nodes that show them (CR-034, S2-1).

``build_order(exposed, fixes)`` turns the analysis's exposed values (CR-021; stream 2 reads nothing else,
TD-18) into the steps by P0-2's rules (``sources/specs/stream2-build-step-extraction.md``, revised
2026-10-21) and Stefan's decisions:

- **What is a step:** every building (its init, under its type then), unit and worker (born - build time;
  a warp-in at its init), upgrade (done - research time), building morph (change - morph time) and unit
  morph (the change into its cocoon) a player started, workers included (D49b). Not: the units existing
  at loop 0, hallucinations, the things nobody builds (``EXCLUDED``), cosmetic upgrades, a cancelled unit
  morph, and the Drone a cancelled building hands back (same owner and unit index, recycle + 1, born
  within ``RETURN_LOOPS``; Rex).
- **Up to 6:00** (D48a): a start whose second is 6:00 is in, 6:01 is out, decided per unit before
  grouping (F4b); a shorter game is listed to its end.
- **One line per batch** (Leo; D52a): per player and item, starts in (loop, unit id) order join the line
  opened by the item's first start when within 8 loops of it (anchored, not chained); the step number
  counts lines, in (start loop, unit id) order.
- **Supply** (CR-035, D2a; Leo's reading R(L)): the last PlayerStats sample at or before the start (12 before
  the first sample) plus every visible supply change strictly between that sample and the start, rounded
  down (``supply_reading``). Where the changes between two samples do not add up to the next sample, the
  step also carries the range its supply lies in (marked ≈, D6a).
- **Notes:** "cancelled" (a building its owner killed before it was done, P0-2 §3.5) and "chrono possible"
  (Rex's rule, D59a: a Chrono Boost of the player on a building whose type at the chrono can make the item,
  active at ``[L, L + 448)``, overlapping a member's ``[start, done)``; the start never moves).
- **Building morphs** (D53b): every one in the game becomes a Building node of its result at its start;
  only those up to the horizon are numbered steps.

``with_build_order(graph, order, fixes)`` puts each step on the node holding its first unit (D58a: one
step, one node), adds the morph Building nodes and appends each player's list to his Player node's
description. A unit morph and a cancelled building have no node of their own: they are in the list only.
"""

from __future__ import annotations

import bisect
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from fractions import Fraction

from sc2mindshare.analysis.exports.node import X_LD  # the layer's line break in descriptions
from sc2mindshare.analysis.exposed import research_row
from sc2mindshare.domain.exposed import Exposed, TypeChange, UnitLife
from sc2mindshare.domain.guides import Later
from sc2mindshare.domain.models import Graph, Node
from sc2mindshare.domain.steps import (
    BuildingMorph,
    BuildOrder,
    BuildStep,
    NodeSource,
    loops_of,
    second_of,
)
from sc2mindshare.domain.time import GameTime
from sc2mindshare.reader.compat import clean_name

#: The horizon (D48a): 6:00.
HORIZON_SECOND = 360
#: Leo's grouping window: a start joins the line its item's first start opened within this many loops.
GROUP_LOOPS = 8
#: Chrono Boost lasts 20 s at 22.4 loops per second (Rex, D59a).
CHRONO_LOOPS = 448
#: The supply before the first PlayerStats sample (LotV start).
START_SUPPLY = 12
#: A cancelled building's Drone is born again this many loops after the cancel, at most (spine: 17; 2 s).
RETURN_LOOPS = 45

WORKERS = frozenset({"Drone", "Probe", "SCV"})
#: P0-2 §5, plus the map's beacons: never a step.
EXCLUDED = re.compile(
    r"Larva|Egg|\w*Cocoon|LurkerMPEgg|CreepTumor\w*|Broodling\w*|Locust\w*|Changeling\w*|InfestedTerran\w*|MULE"
    r"|AutoTurret|PointDefenseDrone|KD8Charge|RavenRepairDrone|Interceptor\w*|AdeptPhaseShift|OracleStasisTrap"
    r"|DisruptorPhased|ParasiticBomb\w*Dummy|ReaperPlaceholder|InvisibleTargetDummy|SpecialNexus|Beacon\w*"
)
#: Cosmetic and game-setup upgrades: never a step.
EXCLUDED_UPGRADES = re.compile(r"(Spray|Reward|Game)\w*")
#: Units that start at their init (a warp-in), not at birth; any other unit with an init is a building.
WARP_IN_UNITS = frozenset({"Zealot", "Stalker", "Sentry", "Adept", "HighTemplar", "DarkTemplar"})
#: The building morphs (one type change, at completion: start = change - morph time). Any other building
#: type change (lift, land, a lowered depot, an add-on's new host) is not a step (P0-2 §3.2).
BUILDING_MORPHS = frozenset(
    {
        ("Hatchery", "Lair"),
        ("Lair", "Hive"),
        ("Spire", "GreaterSpire"),
        ("Gateway", "WarpGate"),
        ("CommandCenter", "OrbitalCommand"),
        ("CommandCenter", "PlanetaryFortress"),
    }
)
#: The unit morphs, by their cocoon and what it becomes: the start is the change into the cocoon (exact);
#: a cocoon that turns back (a cancel) or never finishes is no step.
UNIT_MORPH_COCOONS = {
    "BanelingCocoon": "Baneling",
    "RavagerCocoon": "Ravager",
    "OverlordCocoon": "Overseer",
    "LurkerMPEgg": "LurkerMP",
    "BroodLordCocoon": "BroodLord",
}
#: Rex's producer table (D59a): what a chrono on a building of each type can speed up. Gateway and Warp Gate
#: count as one type.
PRODUCERS: dict[str, frozenset[str]] = {
    "Nexus": frozenset({"Probe", "Mothership"}),
    "Gateway": frozenset(WARP_IN_UNITS),
    "RoboticsFacility": frozenset({"Observer", "WarpPrism", "Immortal", "Colossus", "Disruptor"}),
    "Stargate": frozenset({"Phoenix", "Oracle", "VoidRay", "Tempest", "Carrier"}),
    "CyberneticsCore": frozenset(
        {"WarpGateResearch"} | {f"ProtossAir{k}Level{n}" for k in ("Weapons", "Armors") for n in (1, 2, 3)}
    ),
    "Forge": frozenset({f"ProtossGround{k}Level{n}" for k in ("Weapons", "Armors") for n in (1, 2, 3)})
    | {f"ProtossShieldsLevel{n}" for n in (1, 2, 3)},
    "TwilightCouncil": frozenset({"Charge", "BlinkTech", "AdeptPiercingAttack"}),
    "TemplarArchive": frozenset({"PsiStormTech"}),
    "DarkShrine": frozenset({"DarkTemplarBlinkUpgrade"}),
    "RoboticsBay": frozenset({"ExtendedThermalLance", "ObserverGraviticBooster", "GraviticDrive"}),
    "FleetBeacon": frozenset({"PhoenixRangeUpgrade", "VoidRaySpeedUpgrade", "TempestGroundAttackUpgrade"}),
}
_SAME_PRODUCER = {"WarpGate": "Gateway"}

#: CR-035 (Leo's reading): Zerg structures that are not made from a Drone (a Queen's tumor, the Nydus worm).
NO_DRONE = re.compile(r"CreepTumor\w*|NydusCanal\w*")

#: The kind of node that holds a step of each kind (a building morph's node is made here; a unit morph has none).
_HELD_BY = {"building": "Building", "worker": "Units", "unit": "Units", "upgrade": "Upgrade"}


def _seconds(text: str) -> Fraction | None:
    """A time table's text as seconds: ``"12"``, ``"8.57"``, ``"30 (20)"`` (the first number), ``"100 s"``;
    None for ``"-"`` or anything without a number."""
    match = re.match(r"\s*(\d+(?:\.\d+)?)", text)
    return Fraction(match.group(1)) if match else None


@dataclass(frozen=True)
class _Start:
    """One started thing, before grouping."""

    player: int
    kind: str
    item: str
    start: Fraction
    unit_id: int | None
    done: int | None  # the end of its production, for the chrono overlap (None: never chrono'd)
    cancelled: bool = False
    morph: BuildingMorph | None = None
    name: str | None = None  # the display name, when not the item's own (an upgrade's display-name row)
    estimated: bool = False  # no build or research time: the start is estimated at its end (D60a; CR-035 AC3)


def _cancelled(u: UnitLife) -> bool:
    """P0-2 §3.5: killed by its own player, by itself, before it was done."""
    before_done = u.done_loop is None or (u.died_loop is not None and u.died_loop < u.done_loop)
    return u.died_loop is not None and before_done and u.killer == u.owner and u.killing_unit_id == u.unit_id


def _returning_drones(units: Iterable[UnitLife]) -> set[int]:
    """The Drones a cancelled building handed back (Rex): same owner, same unit index, recycle + 1, born
    within ``RETURN_LOOPS`` after the cancel. They are the same Drone coming back, not a new worker."""
    units = list(units)
    out: set[int] = set()
    for c in (u for u in units if _cancelled(u) and u.init_loop is not None):
        died = c.died_loop if c.died_loop is not None else 0
        for u in units:
            if (
                u.first_type == "Drone"
                and u.owner == c.owner
                and u.born_loop is not None
                and 0 <= u.born_loop - died <= RETURN_LOOPS
                and u.unit_id >> 18 == c.unit_id >> 18
                and u.unit_id & 0x3FFFF == (c.unit_id & 0x3FFFF) + 1
            ):
                out.add(u.unit_id)
    return out


def _starts(exposed: Exposed, estimated: list[str]) -> list[_Start]:
    """Every started thing of the game (P0-2 §3), before the horizon and the grouping."""
    times = {k: _seconds(v) for k, v in exposed.tables.build_times}
    returning = _returning_drones(exposed.units)

    def derived(player: int, item: str, end: int, seconds: Fraction | None) -> Fraction:
        """The start (end - the time); with no time, the end itself, noted in ``estimated``."""
        if seconds is None:
            estimated.append(
                f"CR-034: no build or research time for {item} (player {player}): its start is estimated at loop {end}"
            )
            return Fraction(end)
        return end - loops_of(seconds)

    out: list[_Start] = []
    owner: dict[int, UnitLife] = {}
    for u in exposed.units:
        owner[u.unit_id] = u
        if u.hallucinated or EXCLUDED.fullmatch(u.first_type) or u.unit_id in returning or 0 in (u.born_loop, u.init_loop):
            continue
        if u.init_loop is not None:  # a building, or a warped-in unit: it starts at its init
            kind = "unit" if u.first_type in WARP_IN_UNITS else "building"
            cancelled = kind == "building" and _cancelled(u)
            out.append(_Start(u.owner, kind, u.first_type, Fraction(u.init_loop), u.unit_id, None, cancelled))
        elif u.born_loop is not None:
            kind = "worker" if u.first_type in WORKERS else "unit"
            start = derived(u.owner, u.first_type, u.born_loop, times.get(u.first_type))
            guessed = times.get(u.first_type) is None
            out.append(_Start(u.owner, kind, u.first_type, start, u.unit_id, u.born_loop, estimated=guessed))
    changes = defaultdict(list)
    for c in exposed.type_changes:
        changes[c.unit_id].append(c)
    for unit_id, unit_changes in changes.items():
        u = owner[unit_id]
        if u.hallucinated:
            continue
        for i, c in enumerate(unit_changes):
            if (c.before, c.after) in BUILDING_MORPHS:
                start = derived(u.owner, c.after, c.loop, times.get(c.after))
                morph = BuildingMorph(u.owner, unit_id, c.before, c.after, c.loop, start)
                guessed = times.get(c.after) is None
                out.append(_Start(u.owner, "building morph", c.after, start, unit_id, None, morph=morph, estimated=guessed))
            elif c.after in UNIT_MORPH_COCOONS and i + 1 < len(unit_changes):
                if unit_changes[i + 1].after == UNIT_MORPH_COCOONS[c.after]:
                    out.append(_Start(u.owner, "unit morph", unit_changes[i + 1].after, Fraction(c.loop), unit_id, None))
    for up in exposed.upgrades:
        if up.loop == 0 or up.count == 0 or EXCLUDED_UPGRADES.fullmatch(up.upgrade):
            continue
        row = research_row(up.upgrade, exposed.tables.research_times)  # D63a: by upgrade id
        start = derived(up.player, up.upgrade, up.loop, _seconds(row[1]) if row else None)
        name = row[0] if row and " " in row[0] else None  # a row named for display names the step
        guessed = not row or _seconds(row[1]) is None
        out.append(_Start(up.player, "upgrade", up.upgrade, start, None, up.loop, name=name, estimated=guessed))
    return out


def every_start(exposed: Exposed, player: int) -> tuple[Later, ...]:
    """CR-035 (call 8): every start of the player in the whole game, not only to 6:00, less the cancelled ones (they
    never count as made, call 6), in start order: where a guide step not made in time was made later."""
    made = [s for s in _starts(exposed, []) if s.player == player and not s.cancelled]
    made.sort(key=lambda s: (s.start, s.unit_id if s.unit_id is not None else 0, s.item))
    return tuple(Later(s.item, s.start, s.kind, s.unit_id, s.done if s.kind == "upgrade" else None) for s in made)


@dataclass(frozen=True)
class SupplyReading:
    """One player's supply as the game counts it (``food_used``: units in production included), at any loop
    (CR-035, D2a; Leo's algorithm notes §1): the PlayerStats samples, and the visible changes between them."""

    loops: tuple[int, ...]  # the samples' loops, in order
    food: tuple[Fraction, ...]  # food_used at each sample
    changes: tuple[tuple[Fraction, Fraction], ...]  # (loop, supply change), in loop order
    _keys: tuple[Fraction, ...] = field(default=(), repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_keys", tuple(loop for loop, _ in self.changes))

    def _sum(self, after: Fraction, upto: Fraction, inclusive: bool) -> Fraction:
        """The changes in ``(after, upto)``, or ``(after, upto]`` when ``inclusive``."""
        lo = bisect.bisect_right(self._keys, after)
        hi = (bisect.bisect_right if inclusive else bisect.bisect_left)(self._keys, upto)
        return sum((d for _, d in self.changes[lo:hi]), Fraction(0))

    def exact(self, loop: Fraction) -> tuple[Fraction, Fraction]:
        """R before rounding, and the other end of its window: ``left`` = the last sample at or before ``loop``
        (12 before the first) + the changes strictly between it and ``loop``; ``right`` = the next sample less the
        changes from ``loop`` to it. They differ when the changes between the two samples do not add up."""
        i = bisect.bisect_right(self.loops, loop)
        s0_loop, s0 = (Fraction(self.loops[i - 1]), self.food[i - 1]) if i else (Fraction(0), Fraction(START_SUPPLY))
        left = s0 + self._sum(s0_loop, loop, inclusive=False)
        if i >= len(self.loops):
            return left, left
        s1_loop = Fraction(self.loops[i])
        lo, hi = bisect.bisect_left(self._keys, loop), bisect.bisect_right(self._keys, s1_loop)
        right = self.food[i] - sum((d for _, d in self.changes[lo:hi]), Fraction(0))  # the changes in [loop, s1]
        return left, right

    def reached(self, supply: int) -> Fraction | None:
        """The first loop from which the reading R is at least ``supply`` (a guide step's supply moment, Leo §4), or
        None if it never is. R changes only at a sample or a change, so those are the moments looked at."""
        if START_SUPPLY >= supply:
            return Fraction(0)
        moments = sorted({Fraction(loop) for loop in self.loops} | set(self._keys))
        return next((m for m in moments if self.at(m + Fraction(1, 1000))[0] >= supply), None)

    def at(self, loop: Fraction) -> tuple[int, tuple[int, int] | None]:
        """R, ``floor`` of the reading at ``loop`` (nothing at exactly ``loop`` counts), and its range (low, high)
        when the window cannot pin it to one value (D6a), else None."""
        left, right = self.exact(loop)
        r, other = int(left // 1), int(right // 1)
        return r, (None if r == other else (min(r, other), max(r, other)))


def _food(value: float) -> Fraction:
    """A sample's food_used (whole or half) as an exact fraction."""
    return Fraction(value).limit_denominator(2)


def supply_reading(exposed: Exposed) -> dict[int, SupplyReading]:
    """Per player, the samples and the visible supply changes (Leo's algorithm notes §1): a unit adds its supply
    at its start (a building or warp-in at its init, a trained unit at born - build time, a returning Drone at
    its birth, a unit of the game's start at 0); a Zerg structure takes its Drone (-1 at its init); a morph adds
    the difference (a cocoon counts as what it becomes); a death subtracts, except a Drone that died with no
    killer (it became a structure, already counted)."""
    supplies = {k: _seconds(v) or Fraction(0) for k, v in exposed.tables.supplies}  # "-" (none) reads as 0
    for cocoon, result in UNIT_MORPH_COCOONS.items():
        supplies.setdefault(cocoon, supplies.get(result, Fraction(0)))
    times = {k: _seconds(v) for k, v in exposed.tables.build_times}
    zerg = {p.pid for p in exposed.game.players if p.race.startswith("Z")}
    returning = _returning_drones(exposed.units)
    changes_of: dict[int, list[TypeChange]] = defaultdict(list)
    for c in exposed.type_changes:
        changes_of[c.unit_id].append(c)
    deltas: dict[int, list[tuple[Fraction, Fraction]]] = defaultdict(list)
    for u in exposed.units:
        if u.hallucinated:
            continue
        own = supplies.get(u.first_type, Fraction(0))
        if 0 in (u.born_loop, u.init_loop):
            start = Fraction(0)
        elif u.init_loop is not None:
            start = Fraction(u.init_loop)
        elif u.unit_id in returning or u.born_loop is None:
            start = Fraction(u.born_loop or 0)
        else:
            seconds = times.get(u.first_type)
            start = Fraction(u.born_loop) - (loops_of(seconds) if seconds is not None and own else 0)
        if own:
            deltas[u.owner].append((start, own))
        if (
            u.owner in zerg
            and u.init_loop not in (None, 0)
            and not own
            and not NO_DRONE.fullmatch(u.first_type)
            and u.first_type not in ("Larva", "Egg")
            and not u.first_type.endswith("Cocoon")
        ):
            deltas[u.owner].append((Fraction(u.init_loop), Fraction(-1)))
        current = own
        for c in changes_of.get(u.unit_id, []):
            after = supplies.get(c.after, current)
            if after != current:
                deltas[u.owner].append((Fraction(c.loop), after - current))
                current = after
        if u.died_loop is not None and current:
            if u.owner in zerg and u.first_type == "Drone" and u.killer is None:
                continue
            deltas[u.owner].append((Fraction(u.died_loop), -current))
    samples: dict[int, list[tuple[int, Fraction]]] = defaultdict(list)
    for s in exposed.stats:
        samples[s.player].append((s.loop, _food(s.food_used)))
    out = {}
    for p in exposed.game.players:
        rows = sorted(samples.get(p.pid, []))
        out[p.pid] = SupplyReading(
            tuple(loop for loop, _ in rows),
            tuple(food for _, food in rows),
            tuple(sorted(deltas.get(p.pid, []), key=lambda d: d[0])),
        )
    return out


def _chrono_marks(exposed: Exposed) -> dict[int, list[tuple[int, str]]]:
    """Per player, each Chrono Boost's loop and its target's producer type at that loop (its first type and every
    change up to and including that loop)."""
    first_type = {u.unit_id: u.first_type for u in exposed.units}
    out: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for c in exposed.chronos:
        target = first_type.get(c.target_unit_id)
        for change in exposed.type_changes:  # in game order
            if change.unit_id == c.target_unit_id and change.loop <= c.loop:
                target = change.after
        if target is not None:
            out[c.player].append((c.loop, _SAME_PRODUCER.get(target, target)))
    return out


def _chrono_possible(members: list[_Start], chronos: list[tuple[int, str]]) -> bool:
    """Rex's rule (D59a): a chrono on a producer of the item, active at ``[L, L + 448)``, overlaps a member's
    production ``[start, done)``: ``L < done`` and ``start < L + 448``."""
    for m in members:
        if m.done is None:
            continue
        for loop, producer in chronos:
            if m.item in PRODUCERS.get(producer, ()) and loop < m.done and m.start < loop + CHRONO_LOOPS:
                return True
    return False


def build_order(exposed: Exposed, fixes: Iterable[str]) -> BuildOrder:
    """Every player's numbered steps up to the horizon, and the building morphs of the whole game."""
    names = frozenset(fixes)
    estimated: list[str] = []
    starts = _starts(exposed, estimated)
    horizon = min(HORIZON_SECOND, second_of(Fraction(exposed.game.loops)))
    morphs = tuple(sorted((s.morph for s in starts if s.morph is not None), key=lambda m: (m.start, m.unit_id)))
    supply = supply_reading(exposed)
    chronos = _chrono_marks(exposed)

    def key(s: _Start) -> tuple[Fraction, int, str]:
        return (s.start, s.unit_id if s.unit_id is not None else 0, s.item)

    steps: list[BuildStep] = []
    for player in sorted({p.pid for p in exposed.game.players}):
        lines: list[list[_Start]] = []
        open_lines: dict[tuple[str, str, bool], list[_Start]] = {}
        mine = sorted((s for s in starts if s.player == player and second_of(s.start) <= horizon), key=key)
        for s in mine:
            group = (s.kind, s.item, s.cancelled)
            line = open_lines.get(group)
            if s.kind != "upgrade" and line is not None and s.start - line[0].start <= GROUP_LOOPS:
                line.append(s)
            else:
                open_lines[group] = [s]
                lines.append(open_lines[group])
        reading = supply.get(player, SupplyReading((), (), ()))
        for number, members in enumerate(lines, start=1):
            first = members[0]
            at_supply, supply_range = reading.at(first.start)
            steps.append(
                BuildStep(
                    player=player,
                    number=number,
                    kind=first.kind,
                    item=first.item,
                    name=first.name or clean_name(first.item, True, names),
                    start=first.start,
                    supply=at_supply,
                    supply_range=supply_range,
                    unit_ids=tuple(m.unit_id for m in members if m.unit_id is not None),
                    done_loop=first.done if first.kind == "upgrade" else None,
                    cancelled=first.cancelled,
                    chrono_possible=_chrono_possible(members, chronos.get(player, [])),
                    estimated=first.estimated,
                )
            )
    return BuildOrder(tuple(steps), morphs, horizon, tuple(estimated))


def _morph_node(morph: BuildingMorph, node_id: str, player: str, fixes: frozenset[str], step: BuildStep | None) -> Node:
    """A building morph as a Building node of its result at its start (D53b), named like the layer's
    Building nodes by its type."""
    name = clean_name(morph.after, True, fixes)
    start = GameTime.from_seconds(second_of(morph.start))
    return Node(
        kind="Building",
        id=node_id,
        name=name,
        description="",
        images=(),
        values=(("time", start), ("player", player), ("type", name)),
        start=start,
        source=NodeSource(unit_ids=(morph.unit_id,)),
        steps=(step,) if step is not None else (),
    )


def with_build_order(graph: Graph, order: BuildOrder, fixes: Iterable[str]) -> Graph:
    """``graph`` with each step on the node holding its first unit (or its upgrade), the building-morph nodes
    after the last Building node (their IDs continue the Building sequence, in start order), and each player's
    list after his Player node's description and one blank line (AC-10; no list when he has no step)."""
    names = frozenset(fixes)
    holder: dict[tuple[str, object], int] = {}
    for i, node in enumerate(graph.nodes):
        if node.source is None:
            continue
        if node.kind in ("Building", "Units"):
            for unit_id in node.source.unit_ids:
                holder[(node.kind, unit_id)] = i
        elif node.kind == "Upgrade":
            holder[("Upgrade", (node.source.pid, node.source.upgrade, node.source.loop))] = i
    held: dict[int, list[BuildStep]] = defaultdict(list)
    morph_steps: dict[tuple[int, Fraction], BuildStep] = {}
    for step in order.steps:
        if step.kind == "building morph":
            morph_steps[(step.unit_ids[0], step.start)] = step
            continue
        kind = _HELD_BY.get(step.kind)
        if kind is None:  # a unit morph has no node of its own
            continue
        target = (kind, (step.player, step.item, step.done_loop) if kind == "Upgrade" else step.unit_ids[0])
        if target in holder:  # a cancelled building has no Building node either
            held[holder[target]].append(step)
    nodes = [replace(n, steps=tuple(held[i])) if i in held else n for i, n in enumerate(graph.nodes)]

    buildings = [i for i, n in enumerate(nodes) if n.kind == "Building"]
    next_id = max((int(nodes[i].id.rsplit("-", 1)[1]) for i in buildings), default=0) + 1
    added = []
    for k, morph in enumerate(order.morphs):
        at = holder.get(("Building", morph.unit_id))
        if at is None:
            raise ValueError(f"CR-034: no Building node holds unit {morph.unit_id}, which became a {morph.after}")
        numbered = morph_steps.get((morph.unit_id, morph.start))
        added.append(_morph_node(morph, f"Building-{next_id + k}", nodes[at].value("player"), names, numbered))
    insert_at = buildings[-1] + 1 if buildings else len(nodes)
    nodes[insert_at:insert_at] = added

    for i, node in enumerate(nodes):
        if node.kind == "Player" and node.source is not None and node.source.pid is not None:
            lines = [s.line() for s in order.of(node.source.pid)]
            if lines:
                block = X_LD.join([order.heading(), *lines])
                description = f"{node.description}{X_LD}{X_LD}{block}" if node.description else block
                nodes[i] = replace(node, description=description)
    return replace(graph, nodes=tuple(nodes))
