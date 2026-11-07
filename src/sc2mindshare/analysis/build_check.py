"""The build check: a player's steps compared with a build order guide (CR-035, S2-2; AC2-AC7, AC10).

The rules are P0-3's as amended by Leo's CR-035 algorithm notes §2-§3 and Stefan's D2a-D8a (Step 5), and the
reference computation is Leo's ``compare.py`` (``.scratch/leo/cr-035/``), which QA's oracle was made from:

- **Occurrences, not lines:** a step of n units is n occurrences on both sides (Zerglings per unit, TD-39). A
  cancelled step never pairs (call 6). A building morph pairs on what was made (a Lair with a guide's Lair, call 7).
- **Pairing, per item** (an item and its alternatives together): order kept, the most pairs, then the least total
  cost, then the earliest player occurrences (a DP; TD-36). Cost: |Δt| / 10 s with a guide time (Δt in whole
  seconds, O-2), else the distance of R to the guide's supply (range) / 2. Two passes: the steps with a supply or a
  time first, then the steps that wait on an event (a trigger), one by one in guide order, each paired at or after
  its moment (ε 0 for an exact start, 1 s for a derived one, no test for a chrono-possible one).
- **Verdicts:** by time (TD-35: on time ±10 s, a bit late 11-30 s, late beyond, early before -10 s), by supply
  (TD-43: on supply ±2, a bit late 3-5, late beyond, early below -2; over a ≈ range, the band nearest on supply the
  range touches, ≈ when it straddles two, D6a), done (a trigger step made), not compared (an estimated start),
  missing (with done later: the first start after the reach + 30 s, over the whole game, call 8), not compared
  (game ended) when the game did not last to the reach + 30 s, and an optional step not made is no verdict.
- **Extras:** a building, building morph or upgrade the guide does not pair, or a unit of a type the guide has;
  other units are counted, not graded, as are the Warp Gates the game makes after Warp Gate research (O-12).
- **Suggestion score** (Leo §3): per guide step, the mean over its occurrences of 1 (missing), 0 (done) or
  min(1, cost / 3); plus 1 per item type of an extra building, morph or upgrade the guide lacks; divided by their
  count. Exact fractions; the closest guide has the lowest score, ties broken by an exact matchup before ``vs:
  Any``, then the guide id.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from sc2mindshare.analysis.build_steps import WARP_IN_UNITS, _seconds, every_start
from sc2mindshare.domain.exposed import Exposed
from sc2mindshare.domain.guides import (
    A_BIT_LATE,
    DONE,
    EARLY,
    GAME_ENDED,
    LATE,
    MISSING,
    NOT_COMPARED,
    ON_SUPPLY,
    ON_TIME,
    OPTIONAL,
    BuildCheck,
    Guide,
    GuideStep,
    Later,
    Occurrence,
    Row,
)
from sc2mindshare.domain.steps import BuildOrder

LOOPS_PER_SECOND = Fraction(112, 5)
#: The trigger "@100% <building>": its building's name as the guides write it, to the item id.
TRIGGER_NAMES = {"Core": "CyberneticsCore", "Pool": "SpawningPool"}
#: O-12: the morphs the game makes by itself after an upgrade: counted, not graded.
AUTOMATIC_MORPHS = frozenset({"WarpGate"})
#: The rank of a band, nearest on time first (TD-38's interval rule).
_RANK = {ON_SUPPLY: 0, ON_TIME: 0, A_BIT_LATE: 1, EARLY: 1, LATE: 2}


def supply_band(d: int) -> str:
    """TD-43, Δ supply (player - guide)."""
    if -2 <= d <= 2:
        return ON_SUPPLY
    if 3 <= d <= 5:
        return A_BIT_LATE
    return LATE if d > 5 else EARLY


def time_band(d: int) -> str:
    """TD-35, Δ whole seconds (player - guide)."""
    if -10 <= d <= 10:
        return ON_TIME
    if 10 < d <= 30:
        return A_BIT_LATE
    return LATE if d > 30 else EARLY


def interval_verdict(low: int, high: int, band: Callable[[int], str]) -> tuple[str, int, bool]:
    """TD-38 over a Δ interval: the band nearest on time (on supply) it touches; ≈ when it touches two or more; the
    Δ shown is the end nearest the guide's value."""
    bands = sorted({band(d) for d in range(low, high + 1)}, key=lambda b: _RANK[b])
    nearest = low if abs(low) <= abs(high) else high
    return bands[0], nearest, len(bands) > 1


def occurrences(order: BuildOrder, player: int) -> list[Occurrence]:
    """The player's occurrences up to the build order's horizon: each unit of each step (a cancelled step none)."""
    out = []
    for st in order.of(player):
        if st.cancelled:
            continue
        exact = st.kind == "building" or (st.kind == "unit" and st.item in WARP_IN_UNITS)
        for _ in range(st.count):
            out.append(
                Occurrence(
                    st.item,
                    st.number,
                    st.start,
                    st.supply,
                    st.supply_range,
                    st.kind,
                    exact,
                    st.chrono_possible,
                    st.estimated,
                )
            )
    return out


@dataclass
class _Slot:
    """One occurrence of a guide step during the pairing."""

    step: GuideStep
    occurrence: int
    paired: Occurrence | None = None
    cost: Fraction | None = None
    moment: Fraction | None = None


def _pair(slots: Sequence[_Slot], players: Sequence[Occurrence], cost: Callable[[_Slot, Occurrence], Fraction | None]) -> None:
    """Order kept; the most pairs, then the least total cost, then the earliest player occurrences (Leo's DP)."""
    m, n = len(slots), len(players)
    best: dict[tuple[int, int], tuple[int, Fraction, tuple[tuple[int, int], ...]]] = {}
    for i in range(m, -1, -1):
        for j in range(n, -1, -1):
            if i == m or j == n:
                best[(i, j)] = (0, Fraction(0), ())
                continue
            candidates = [best[(i + 1, j)], best[(i, j + 1)]]
            c = cost(slots[i], players[j])
            if c is not None:
                count, total, pairs = best[(i + 1, j + 1)]
                candidates.append((count + 1, total + c, ((i, j), *pairs)))
            best[(i, j)] = min(candidates, key=lambda x: (-x[0], x[1], x[2]))
    for i, j in best[(0, 0)][2]:
        slots[i].paired = players[j]
        slots[i].cost = cost(slots[i], players[j])


def _moment(slot: _Slot, slots: Sequence[_Slot], exposed: Exposed, player: int, times: dict[str, Fraction]) -> Fraction | None:
    """A trigger's moment in seconds, or None when it never came or cannot be evaluated (Leo §2, Iris O-3):
    ``@100% <building>``: the guide's earlier step of that building, as the player made it, plus its build time;
    ``@n gas`` / ``@n minerals``: the first stats sample with that much."""
    trigger = slot.step.trigger or ""
    match = re.fullmatch(r"@100% (.+)", trigger)
    if match:
        ref = re.sub(r"[^A-Za-z]", "", match.group(1))
        ref = TRIGGER_NAMES.get(ref, ref)
        earlier = [s for s in slots if ref in s.step.items and s.step.number < slot.step.number and s.paired]
        if earlier and ref in times:
            paired = earlier[-1].paired
            assert paired is not None
            return paired.seconds + times[ref]
        return None
    match = re.fullmatch(r"@(\d+) (gas|minerals)", trigger)
    if match:
        need, resource = int(match.group(1)), match.group(2)
        for s in sorted((s for s in exposed.stats if s.player == player), key=lambda s: s.loop):
            if (s.vespene if resource == "gas" else s.minerals) >= need:
                return Fraction(s.loop) / LOOPS_PER_SECOND
    return None


def _supply_distance(r: int, step: GuideStep) -> Fraction:
    bounds = step.supply_bounds
    assert bounds is not None
    low, high = bounds
    return Fraction(r - high if r > high else (r - low if r < low else 0))


def compare(exposed: Exposed, order: BuildOrder, guide: Guide, player: int, picked: bool) -> BuildCheck:
    """The player's build compared with ``guide`` (AC2-AC6)."""
    window = guide.window
    times = {k: t for k, v in exposed.tables.build_times if (t := _seconds(v)) is not None}
    players = [o for o in occurrences(order, player) if o.seconds <= window]
    slots = [_Slot(step, k) for step in guide.steps for k in range(1, step.count + 1)]
    used: set[int] = set()  # ids of paired player occurrences

    def cost(slot: _Slot, o: Occurrence) -> Fraction | None:
        step = slot.step
        if step.time is not None:
            return Fraction(abs(int(o.seconds // 1) - step.time), 10)
        if step.time_interval is not None:
            low, high = step.time_interval
            second = int(o.seconds // 1)
            return Fraction(max(0, low - second, second - high), 10)
        if step.trigger is not None:
            if slot.moment is None:
                return Fraction(0)
            epsilon = Fraction(0) if o.exact else (None if o.chrono_possible else Fraction(1))
            if epsilon is not None and o.seconds < slot.moment - epsilon:
                return None
            return max(Fraction(0), o.seconds - slot.moment) / 10
        return abs(_supply_distance(o.supply, step)) / 2

    def run(group: list[_Slot]) -> None:
        items = group[0].step.items
        free = sorted((o for o in players if o.item in items and id(o) not in used), key=lambda o: (o.start, o.step))
        _pair(group, free, cost)
        used.update(id(s.paired) for s in group if s.paired is not None)

    groups: dict[tuple[str, ...], list[_Slot]] = {}
    for slot in slots:
        if slot.step.trigger is None:
            groups.setdefault(slot.step.items, []).append(slot)
    for group in groups.values():
        run(group)
    for slot in slots:  # the steps that wait on an event, one by one in guide order
        if slot.step.trigger is not None:
            slot.moment = _moment(slot, slots, exposed, player, times)
            run([slot])

    game_second = int(Fraction(exposed.game.loops) / LOOPS_PER_SECOND // 1)
    later = [s for s in every_start(exposed, player) if s.start / LOOPS_PER_SECOND > window]
    taken: set[int] = set()
    rows = [_row(slot, game_second, window, later, taken) for slot in slots]

    guide_items = {i for step in guide.steps for i in step.items}
    paired_ids = {id(s.paired) for s in slots if s.paired is not None}
    extras: list[tuple[int, str]] = []
    structural: set[str] = set()
    counted: dict[str, int] = {}
    for o in players:
        if id(o) in paired_ids:
            continue
        if o.kind == "building morph" and o.item in AUTOMATIC_MORPHS and o.item not in guide_items:
            counted[o.item] = counted.get(o.item, 0) + 1
            structural.add(o.item)  # Leo's score counts it as an item type the guide lacks
        elif o.kind in ("building", "building morph", "upgrade") or o.item in guide_items:
            extras.append((o.step, o.item))
            if o.item not in guide_items:
                structural.add(o.item)
        else:
            counted[o.item] = counted.get(o.item, 0) + 1
    return BuildCheck(
        player=player,
        guide=guide,
        picked=picked,
        rows=tuple(rows),
        extras=tuple(extras),
        counted=tuple(counted.items()),
        score=_score(guide, slots, len(structural)),
        game_second=game_second,
    )


def _row(slot: _Slot, game_second: int, window: int, later: list[Later], taken: set[int]) -> Row:
    step, o = slot.step, slot.paired
    if o is None:
        if step.optional:
            return Row(step.number, slot.occurrence, OPTIONAL, moment=slot.moment)
        if game_second < window:
            return Row(step.number, slot.occurrence, GAME_ENDED, moment=slot.moment)
        done_later = next((s for k, s in enumerate(later) if s.item in step.items and k not in taken), None)
        if done_later is not None:
            taken.add(later.index(done_later))
        return Row(step.number, slot.occurrence, MISSING, moment=slot.moment, done_later=done_later)
    if o.estimated:
        return Row(step.number, slot.occurrence, NOT_COMPARED, paired=o, moment=slot.moment)
    if step.time is not None:
        d = int(o.seconds // 1) - step.time
        return Row(step.number, slot.occurrence, time_band(d), "time", o, d, moment=slot.moment)
    if step.time_interval is not None:
        low, high = step.time_interval
        second = int(o.seconds // 1)
        verdict, d, approx = interval_verdict(second - high, second - low, time_band)
        return Row(step.number, slot.occurrence, verdict, "time", o, d, approx, slot.moment)
    if step.trigger is not None:
        return Row(step.number, slot.occurrence, DONE, paired=o, moment=slot.moment)
    a, b = int(_supply_distance(o.low, step)), int(_supply_distance(o.high, step))
    verdict, d, approx = interval_verdict(min(a, b), max(a, b), supply_band)
    return Row(step.number, slot.occurrence, verdict, "supply", o, d, approx, slot.moment)


def _score(guide: Guide, slots: Sequence[_Slot], structural: int) -> Fraction:
    """Leo §3: lower is closer."""
    per: dict[int, list[Fraction]] = {}
    for slot in slots:
        if slot.step.optional:
            continue
        if slot.paired is None or slot.cost is None:
            x = Fraction(1)
        elif slot.step.trigger is not None and slot.step.time is None:
            x = Fraction(0)
        else:
            x = min(Fraction(1), slot.cost / 3)
        per.setdefault(slot.step.number, []).append(x)
    total = sum((sum(xs, Fraction(0)) / len(xs) for xs in per.values()), Fraction(0))
    return (total + structural) / (len(per) + structural)
