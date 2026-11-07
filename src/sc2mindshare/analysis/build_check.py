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
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from sc2mindshare.analysis.build_steps import (
    HORIZON_SECOND,
    RICH_GEYSERS,
    WARP_IN_UNITS,
    SupplyReading,
    _cancelled,
    _seconds,
    build_order,
    every_start,
    supply_reading,
)
from sc2mindshare.analysis.exports.node import X_LD  # the layer's line break in descriptions
from sc2mindshare.analysis.exposed import research_row
from sc2mindshare.analysis.guides import GuideError, load
from sc2mindshare.domain.exposed import Exposed
from sc2mindshare.domain.guides import (
    A_BIT_LATE,
    DONE,
    DONE_LATER,
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
    NoBuildCheck,
    Occurrence,
    Row,
)
from sc2mindshare.domain.models import Added, Graph, Link, Node
from sc2mindshare.domain.steps import BuildOrder, BuildStep, StepVerdict
from sc2mindshare.domain.time import GameTime
from sc2mindshare.reader.compat import clean_name

LOOPS_PER_SECOND = Fraction(112, 5)
#: The trigger "@100% <building>": its building's name as the guides write it, to the item id.
TRIGGER_NAMES = {"Core": "CyberneticsCore", "Pool": "SpawningPool"}
#: O-12: the morphs the game makes by itself after an upgrade: counted, not graded.
AUTOMATIC_MORPHS = frozenset({"WarpGate"})
#: A trigger on the bank (``@100 gas``, ``@150 minerals``): read from the 7-second samples, so not a pairing bound.
RESOURCE_TRIGGER = re.compile(r"@\d+ (gas|minerals)")
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
                    RICH_GEYSERS.get(st.item, st.item),  # a rich geyser's building pairs as its base building
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
    ``@100% <building>``: the guide's earlier step of that building, as the player made it, plus its build time; with no
    such step, the player's own first building of that type started after loop 0 and not cancelled, plus its build time
    (Leo, 2026-11-07); ``@n gas`` / ``@n minerals``: the first stats sample with that much.

    A resource moment is read from the 7-second samples of the bank, so it is never early but can be up to one sample
    (160 loops, 7.1 s) late, and later still, or never, when the gas or minerals were spent between two samples. It is
    therefore used only for a missing entry's text and place, never as a pairing bound (Leo, review round 1, finding 4);
    an ``@100% <building>`` moment is exact and stays a bound."""
    trigger = slot.step.trigger or ""
    match = re.fullmatch(r"@100% (.+)", trigger)
    if match:
        ref = re.sub(r"[^A-Za-z]", "", match.group(1))
        ref = TRIGGER_NAMES.get(ref, ref)
        earlier = [s for s in slots if ref in s.step.items and s.step.number < slot.step.number and s.paired]
        if ref not in times:
            return None
        if earlier:
            paired = earlier[-1].paired
            assert paired is not None
            return paired.seconds + times[ref]
        own = [
            u.init_loop
            for u in exposed.units
            if u.owner == player
            and RICH_GEYSERS.get(u.first_type, u.first_type) == ref
            and u.init_loop
            and not u.hallucinated
            and not _cancelled(u)
        ]
        return Fraction(min(own)) / LOOPS_PER_SECOND + times[ref] if own else None
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
    if window > HORIZON_SECOND:  # Stefan's D1a (review round 1): every start up to the window, whatever the reach
        order = build_order(exposed, (), horizon_second=window)  # items and starts only: names are not compared
    players = [o for o in occurrences(order, player) if o.seconds <= window]
    slots = [_Slot(step, k) for step in guide.steps for k in range(1, step.count + 1)]
    used: set[int] = set()  # ids of paired player occurrences

    def cost(slot: _Slot, o: Occurrence) -> Fraction | None:
        step = slot.step
        if step.time is not None:
            return Fraction(abs(int(o.seconds // 1) - step.time), 10)
        if step.time_interval is not None:
            return Fraction(abs(interval_distance(int(o.seconds // 1), step.time_interval)), 10)
        if step.trigger is not None:
            if slot.moment is None or RESOURCE_TRIGGER.fullmatch(step.trigger):  # finding 4: no pairing bound
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
        k = next((k for k, s in enumerate(later) if s.item in step.items and k not in taken), None)
        if k is not None:
            taken.add(k)
        done_later = None if k is None else later[k]
        return Row(step.number, slot.occurrence, MISSING, moment=slot.moment, done_later=done_later)
    if o.estimated:
        return Row(step.number, slot.occurrence, NOT_COMPARED, paired=o, moment=slot.moment)
    if step.time is not None:
        d = int(o.seconds // 1) - step.time
        return Row(step.number, slot.occurrence, time_band(d), "time", o, d, moment=slot.moment)
    if step.time_interval is not None:  # Leo, finding 10: by the distance to the nearest edge; the start is exact
        d = interval_distance(int(o.seconds // 1), step.time_interval)
        return Row(step.number, slot.occurrence, time_band(d), "time", o, d, moment=slot.moment)
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


# --- the guide for each player: named or suggested, or the reason there is none (AC7, AC10) ---------------------------

RACE_LETTER = {"Zerg": "Z", "Protoss": "P", "Terran": "T"}


def _mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _matchup(race: str, opponent: str | None) -> str:
    return f"{race} vs {opponent or 'nobody'}"


def first_moment(guide: Guide, check: BuildCheck, reading: SupplyReading) -> Fraction | None:
    """The moment of the guide's first step, in seconds (Leo §2, per step kind): its time; the moment the player first
    had its supply (R); its trigger's moment. None when it never came."""
    step = guide.steps[0]
    if step.time is not None:
        return Fraction(step.time)
    if step.time_interval is not None:
        return Fraction(step.time_interval[0])
    return due(step, check.rows_of(step.number)[0].moment, reading)


def due(step: GuideStep, moment: Fraction | None, reading: SupplyReading) -> Fraction | None:
    """When a guide step without a time is due, in seconds (Leo, review round 1, finding 1): the later of its trigger's
    moment and the moment the player first reached its supply (R, the lower edge), whichever of the two it has; None
    when either never came."""
    parts: list[Fraction] = []
    if step.trigger is not None:
        if moment is None:
            return None
        parts.append(moment)
    if step.supply_bounds is not None:
        loop = reading.reached(step.supply_bounds[0])
        if loop is None:
            return None
        parts.append(loop / LOOPS_PER_SECOND)
    return max(parts) if parts else None


def interval_distance(second: int, interval: tuple[int, int]) -> int:
    """A start's distance in whole seconds to a guide time interval: 0 inside, else to the nearest edge (Leo, finding
    10; the pairing cost and the verdict both read it)."""
    low, high = interval
    return second - high if second > high else (second - low if second < low else 0)


def _too_short(guide: Guide, check: BuildCheck, reading: SupplyReading) -> bool:
    """AC10 (Leo, amended 2026-11-07): nothing paired, and the game ended before the earlier of the first step's moment
    and the window's edge (the reach + 30 s); a moment that never comes counts as the window's edge. A game that runs
    past the window and pairs nothing is compared: every step missing."""
    if any(r.paired is not None for r in check.rows):
        return False
    moment = first_moment(guide, check, reading)
    edge = Fraction(guide.window) if moment is None else min(moment, Fraction(guide.window))
    return check.game_second < edge


def _gradable(guide: Guide) -> bool:
    """A guide with at least one step that is not optional: one there is something to compare with (Iris R1)."""
    return any(not s.optional for s in guide.steps)


def suggestion_key(check: BuildCheck) -> tuple[Fraction, int, str]:
    """D1a, Leo §3: the lowest score; a guide for this exact matchup before one for any opponent; then the id."""
    return (check.score, 0 if check.guide.vs != "Any" else 1, check.guide.id)


def resolve(argument: str, guides: Sequence[Guide]) -> Guide:
    """A guide named on the command line: a shipped guide's id, or a guide file. ``FileNotFoundError`` when it is
    neither; ``GuideError`` (with the player-facing message) when the file cannot be read or fails the check."""
    shipped = {g.id: g for g in guides}
    if argument in shipped:
        return shipped[argument]
    path = Path(argument)
    if not path.is_file():
        raise FileNotFoundError(argument)
    return load(path)


def checks(
    exposed: Exposed,
    order: BuildOrder,
    names: dict[int, str],
    named: dict[int, str],
    guides: Sequence[Guide],
) -> tuple[BuildCheck | NoBuildCheck, ...]:
    """Each player's build check, in pid order: with the guide named for him (``named``: pid -> a guide id or file),
    else the closest guide for his race and matchup, marked suggested (D1a); or why there is none (AC10). Only
    finding and reading a named guide can turn into a reason: a fault in the comparison itself is raised (call 10)."""
    readings = supply_reading(exposed)
    out: list[BuildCheck | NoBuildCheck] = []
    for context in sorted(exposed.game.players, key=lambda p: p.pid):
        pid, race, opponent = context.pid, context.race, context.opponent_race
        name = names.get(pid, f"player {pid}")
        reading = readings[pid]
        if pid in named:
            argument = named[pid]
            try:
                guide = resolve(argument, guides)
            except FileNotFoundError:
                out.append(
                    NoBuildCheck(
                        pid, "none, file not found", f'No build check: the build order guide file "{argument}" was not found.'
                    )
                )
                continue
            except GuideError as exc:
                line = f'No build check: the build order guide file "{argument}" could not be read: {exc}.'
                out.append(NoBuildCheck(pid, "none, file unreadable", line))
                continue
            if not guide.matches(race, opponent):
                line = (
                    f'No build check: the build order guide "{guide.name}" is for {_matchup(guide.race, guide.vs)}, '
                    f"and {name} played {_matchup(race, opponent)}."
                )
                out.append(NoBuildCheck(pid, "none, other matchup", line))
                continue
            if not guide.steps:  # Iris R1 (Stefan's D1a, AC10): nothing to compare
                line = (
                    f'No build check: the build order guide "{guide.name}" is a link to Spawning Tool, with no steps to compare.'
                )
                out.append(NoBuildCheck(pid, "none, link only", line))
                continue
            if not _gradable(guide):
                line = (
                    f'No build check: every step of the build order guide "{guide.name}" is optional, so there is '
                    "nothing to compare."
                )
                out.append(NoBuildCheck(pid, "none, only optional steps", line))
                continue
            candidates = [compare(exposed, order, guide, pid, picked=True)]
        else:  # a guide with no required step is never suggested (Iris R1)
            candidates = [
                compare(exposed, order, g, pid, picked=False) for g in guides if g.matches(race, opponent) and _gradable(g)
            ]
            if not candidates:
                letters = f"{RACE_LETTER.get(race, race)}v{RACE_LETTER.get(opponent or '', opponent or '?')}"
                line = f"No build check: there is no build order guide for {_matchup(race, opponent)} yet."
                out.append(NoBuildCheck(pid, f"none, no build order guide for {letters}", line))
                continue
        check = min(candidates, key=suggestion_key)
        if _too_short(check.guide, check, reading):
            line = (
                f"No build check: the game ended at {_mmss(check.game_second)}, before the first step of the build "
                f"order guide ({check.guide.steps[0].text})."
            )
            out.append(NoBuildCheck(pid, "none, game too short", line))
            continue
        out.append(check)
    return tuple(out)


# --- the verdict rows, as the build-check golden keeps them (CR-035, approach §2 form d) -------------------------------


def _text(value: Fraction | None) -> str | None:
    return None if value is None else str(value)


def check_doc(result: BuildCheck | NoBuildCheck) -> dict[str, Any]:
    """One player's build check as plain JSON: every guide occurrence with its verdict, the extras and the counted
    units; or the reason there is none. Fractions as text ("5/12")."""
    if isinstance(result, NoBuildCheck):
        return {"player": result.player, "build check": result.value, "line": result.line}
    return {
        "player": result.player,
        "build check": result.guide.name,
        "guide": result.guide.id,
        "picked": result.picked,
        "score": str(result.score),
        "graded by": result.graded_by,
        "game second": result.game_second,
        "rows": [
            {
                "guide step": r.guide_step,
                "occurrence": r.occurrence,
                "verdict": r.verdict,
                "graded by": r.graded_by,
                "step": r.paired.step if r.paired else None,
                "off": r.off,
                "approx": r.approx,
                "moment": _text(r.moment),
                "done later": None
                if r.done_later is None
                else {"item": r.done_later.item, "start": _text(r.done_later.start), "unit": r.done_later.unit_id},
            }
            for r in result.rows
        ],
        "extras": [[step, item] for step, item in result.extras],
        "counted": [[item, n] for item, n in result.counted],
    }


# --- the build check in the graph: the verdicts, the card and the missing entries (CR-035 BC1; P0-6, Iris) -----------

#: A guide step's verb, by its kind (Iris O-3: "starts Metabolic Boost", "builds an Evolution Chamber", "makes 2 Queens").
_VERB = {"building": "builds", "morph": "makes", "upgrade": "starts", "unit": "makes", "worker": "makes"}
_SUPPLY_LABEL = {
    ON_SUPPLY: "On supply",
    A_BIT_LATE: "A bit late (by supply)",
    LATE: "Late (by supply)",
    EARLY: "Early (by supply)",
}
_TIME_LABEL = {ON_TIME: "On time", A_BIT_LATE: "A bit late", LATE: "Late", EARLY: "Early"}
_EXTRA = "Extra: not in the build order guide at this point. That can be the right call, for example to defend early pressure."
_NOT_COMPARED = "Not compared: we could only estimate when you started it, so it is not compared with the build order guide."
_APPROX_LINE = "A step marked ≈ is one where we know your supply only roughly."
#: O-12: how the card names a morph the game makes by itself.
_AUTOMATIC_NOTE = {"WarpGate": "they follow from Warp Gate research"}
#: The card's count line, in this order (Iris's mockup); "on time" and "on supply" share the card's ``on time`` entry.
_COUNT_ORDER = (ON_SUPPLY, ON_TIME, DONE, A_BIT_LATE, LATE, EARLY, NOT_COMPARED, MISSING)


class UnknownPlayer(ValueError):
    """A --guide names a player the replay does not have (a usage error, exit 2)."""


def named_guides(requests: Sequence[str], names: dict[int, str], numbers: dict[str, int]) -> dict[int, str]:
    """The ``--guide PLAYER=GUIDE`` requests as pid -> guide; PLAYER is the name on his Player node, or his number in
    the game (1 or 2). ``UnknownPlayer`` for a player the replay does not have."""
    named: dict[int, str] = {}
    for request in requests:
        player, _, guide = request.partition("=")
        pid = next((p for p, name in names.items() if name == player), numbers.get(player))
        if pid is None:
            raise UnknownPlayer(f"--guide {request}: no player {player!r} in this replay (players: {', '.join(names.values())})")
        named[pid] = guide
    return named


def _mmss_of(seconds: Fraction | float) -> str:
    return _mmss(int(seconds // 1))


def _signed(d: int) -> str:
    return "0" if d == 0 else f"{d:+d}"


def _guide_time(step: GuideStep) -> str:
    if step.time is not None:
        return _mmss(step.time)
    if step.time_interval is not None:
        return f"{_mmss(step.time_interval[0])}–{_mmss(step.time_interval[1])}"
    return ""


def _guide_supply(step: GuideStep) -> str:
    if step.supply is not None:
        return str(step.supply)
    if step.supply_range is not None:
        return f"{step.supply_range[0]}–{step.supply_range[1]}"
    return ""


def ending(row: Row) -> str:
    """A compared step's name ending (Iris; Stefan's Q2 (a)): "on supply", "15 supply late", "3 supply early", "on time",
    "28 s late" under 60 s and "1:59 late" from 60 s, "done", "not compared"; " ≈" added to an ending graded by supply
    whenever the step's supply is only known as a range (Iris A1; Stefan's D1a: never on done, extra or a time
    verdict). At most 15 characters, 17 with " ≈" (e.g. "15 supply early ≈"); never truncated (Iris R2)."""
    if row.verdict in (ON_SUPPLY, ON_TIME, DONE, NOT_COMPARED):
        text = row.verdict
    else:
        assert row.off is not None and row.graded_by is not None
        size = abs(row.off)
        amount = f"{size} supply" if row.graded_by == "supply" else (f"{size} s" if size < 60 else _mmss(size))
        text = f"{amount} {'late' if row.off > 0 else 'early'}"
    ranged = row.paired is not None and row.paired.supply_range is not None
    return f"{text} ≈" if row.graded_by == "supply" and (ranged or row.approx) else text


def _condition(step: GuideStep) -> str:
    """When a guide step that waits on an event is due, in the player's words (Iris O-3)."""
    trigger = step.trigger or ""
    match = re.fullmatch(r"@(\d+) (gas|minerals)", trigger)
    if match:
        return f"as soon as you have {match.group(1)} {match.group(2)}"
    match = re.fullmatch(r"@100% (.+)", trigger)
    if match:
        return f"as soon as your {match.group(1)} finishes"
    return f'when the build order guide says: "{trigger}"'


def _sentence(row: Row, step: GuideStep) -> str:
    """The sentence a compared step's node gets, after one blank line (Iris)."""
    o = row.paired
    assert o is not None
    if row.verdict == NOT_COMPARED:
        return _NOT_COMPARED
    if row.verdict == DONE:
        return f"Done: the build order guide asks for this step {_condition(step)}, and you made it."
    if row.graded_by == "time":
        label = _TIME_LABEL[row.verdict]
        return f"{label}: you started it at {_mmss_of(o.seconds)}; the build order guide has it at {_guide_time(step)}."
    supply = f"about {o.low}–{o.high}" if o.supply_range else str(o.supply)
    text = (
        f"{_SUPPLY_LABEL[row.verdict]}: you were at {supply} supply when you started it; the build order guide has it "
        f"at {_guide_supply(step)}."
    )
    if row.verdict in (A_BIT_LATE, LATE):
        text += " You made more units first, so it came later in your build order."
    elif row.verdict == EARLY:
        text += " You started it before some of what the build order guide makes first."
    return text


def _row_verdict(row: Row, step: GuideStep) -> StepVerdict:
    return StepVerdict(
        verdict=row.verdict,
        ending=ending(row),
        guide_time=_guide_time(step),
        off_by_s=_signed(row.off) if row.graded_by == "time" and row.off is not None else "",
        guide_supply=_guide_supply(step),
        sentence=_sentence(row, step),
    )


def _done_later_verdict(missing_at: float) -> StepVerdict:
    """The real step of a guide step that was missing at its moment and made later (Iris: ends ``· done later``)."""
    sentence = f"Done later: the build order guide has this step earlier; it was missing at {_mmss_of(missing_at)}."
    # Iris R3; F2 (qa-fix.md): the verdict and its sentence only, the guide's values stay on the missing entry
    return StepVerdict(DONE_LATER, DONE_LATER, "", "", "", sentence)


def ghost_seconds(row: Row, step: GuideStep, guide: Guide, reading: SupplyReading) -> float:
    """Where a missing entry sits, in seconds (spec §13.3 rule 1, TD-43, TD-44; Kevin's call 5): the guide's time (an
    interval's middle); else when the step is due (``due``: the later of its trigger's moment and the moment the
    player first reached its supply by the exact reading R; Leo, finding 1); else the guide's horizon (Leo §4, S35). The
    rule of
    ``layout.items.ghost_time``, applied here because analysis may not import layout (CR-009); moving that function
    into domain is a follow-up."""
    if step.time is not None:
        return float(step.time)
    if step.time_interval is not None:
        return (step.time_interval[0] + step.time_interval[1]) / 2
    moment = due(step, row.moment, reading)
    return float(guide.horizon) if moment is None else float(moment)


def _same_start(later: Later, step: BuildStep) -> bool:
    if later.kind == "upgrade":
        return step.kind == "upgrade" and step.item == later.item and step.done_loop == later.done_loop
    return later.unit_id is not None and later.unit_id in step.unit_ids


def annotate(order: BuildOrder, results: Sequence[BuildCheck | NoBuildCheck], readings: dict[int, SupplyReading]) -> BuildOrder:
    """``order`` with each compared step's verdict (call 4: ``BuildStep.line`` then shows it in the steps line and the
    Player list alike). A step of several occurrences takes its first paired occurrence's verdict, else extra, else done
    later (a guide step missing at its moment and made later, at this step)."""
    verdicts: dict[tuple[int, int], StepVerdict] = {}
    for check in results:
        if not isinstance(check, BuildCheck):
            continue
        by_number = {s.number: s for s in check.guide.steps}
        mine = order.of(check.player)
        for row in check.rows:
            if row.paired is not None:
                verdicts.setdefault((check.player, row.paired.step), _row_verdict(row, by_number[row.guide_step]))
        for number, _item in check.extras:
            verdicts.setdefault((check.player, number), StepVerdict("extra", "extra", sentence=_EXTRA))
        for row in check.rows:
            if row.done_later is None:
                continue
            step = next((s for s in mine if _same_start(row.done_later, s)), None)
            if step is not None:
                guide_step = by_number[row.guide_step]
                missing_at = ghost_seconds(row, guide_step, check.guide, readings[check.player])
                verdicts.setdefault((check.player, step.number), _done_later_verdict(missing_at))
    steps = tuple(
        replace(s, verdict=verdicts[(s.player, s.number)]) if (s.player, s.number) in verdicts else s for s in order.steps
    )
    return replace(order, steps=steps)


def _plural(name: str, n: int) -> str:
    if n == 1:
        return name
    if name.endswith("y") and name[-2:-1] not in "aeiou":
        return name[:-1] + "ies"
    return name + ("es" if name.endswith(("s", "x", "ch", "sh")) else "s")


def _article(name: str) -> str:
    return f"{'an' if name[:1].lower() in 'aeiou' else 'a'} {name}"


def item_name(item: str, kind: str, order: BuildOrder, exposed: Exposed, fixes: frozenset[str]) -> str:
    """An item's name as the nodes and the steps name it: a step of the item's, else the research sheet's display name
    (an upgrade), else the cleaned id."""
    step = next((s for s in order.steps if RICH_GEYSERS.get(s.item, s.item) == item), None)
    if step is not None:
        return step.name
    if kind == "upgrade":
        row = research_row(item, exposed.tables.research_times)
        if row is not None and " " in row[0]:
            return row[0]
    return clean_name(item, True, fixes)


def _patch(version: str) -> tuple[int, ...] | None:
    parts = version.split(".")
    return tuple(int(p) for p in parts[:3]) if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]) else None


def age_line(guide: Guide, game_version: str) -> tuple[bool, str]:
    """AC9 (D8a; Iris, Leo (e)): whether the guide is old, and the card's age line ("" for a guide within 2 patches).
    Patches are counted on the third number of the same major.minor (5.0.11 -> 5.0.14 is 3); a guide for an older
    major.minor is always more than 2 behind, and a guide for a newer one (or a newer patch) is never old (Leo)."""
    if guide.patch is None:
        written = "last edited" if guide.source.get("kind") == "liquipedia" else "written"
        line = (
            "Patch unknown: the build order guide does not say which patch it was written for "
            f"({written} {guide.as_of}), so some timings may have changed since."
        )
        if guide.source.get("kind") == "liquipedia":
            line += " Most community build orders carry this note."
        return True, line
    game, own = _patch(game_version), _patch(guide.patch)
    if game is None or own is None:
        return False, "Patch not compared: we could not read this game's patch, so some timings may differ."
    behind = game[2] - own[2] if game[:2] == own[:2] else (0 if own > game else 3)
    if behind <= 2:
        return False, ""
    shown = ".".join(str(p) for p in game)
    return True, (
        f"Older build order guide: written for patch {guide.patch}, more than 2 patches before this game ({shown}), "
        "so some timings may have changed since."
    )


def _source_line(guide: Guide) -> str:
    source = guide.source
    if source.get("kind") == "liquipedia":
        return (
            f'Source: Liquipedia, "{source.get("title")}", revision {source.get("revision")}, {source.get("url")}. '
            f"Text by Liquipedia contributors, licensed {source.get('licence')}. We turned it into steps."
        )
    if guide.team_draft:
        return f"Source: Mindshare team draft, {source.get('created', guide.as_of)}."
    return f"Source: {guide.attribution or source.get('kind')}."


def _graded_line(check: BuildCheck) -> str:
    timed = sum(1 for s in check.guide.steps if s.timed)
    if check.graded_by == "time":
        return "By time: each step is compared with the time in the build order guide."
    if check.graded_by == "time and supply":
        return (
            f"Mostly by supply: this build order guide gives times for {timed} {'step' if timed == 1 else 'steps'}, "
            "and those are compared by time; "
            f"the rest by the supply you were on. {_APPROX_LINE}"
        )
    return (
        "By supply: this build order guide gives supply counts, not times, so each step is compared by the supply you "
        f"were on when you started it. {_APPROX_LINE}"
    )


def card(
    check: BuildCheck, race: str, opponent: str | None, order: BuildOrder, exposed: Exposed, fixes: frozenset[str]
) -> tuple[str, str, tuple[tuple[str, Added], ...]]:
    """The card's name, description and entries (AC2, AC4, AC7-AC9; Iris's four paragraphs)."""
    guide = check.guide
    verdicts = {s.number: check.step_verdict(s) for s in guide.steps}
    graded = {n: v for n, v in verdicts.items() if v != OPTIONAL}
    counts = {v: sum(1 for x in graded.values() if (x == v or (v == NOT_COMPARED and x == GAME_ENDED))) for v in _COUNT_ORDER}
    partly = [s for s in guide.steps if graded.get(s.number) == MISSING and any(r.paired for r in check.rows_of(s.number))]
    # Iris A4: a partly made step is counted once, as partly made; its own line says when the rest came
    done_later = sum(
        1
        for s in guide.steps
        if graded.get(s.number) == MISSING and s not in partly and any(r.done_later for r in check.rows_of(s.number))
    )
    parts = [f"{counts[v]} {v}" for v in _COUNT_ORDER if counts[v]]
    if counts[MISSING]:
        notes = [f"{n} {label}" for n, label in ((done_later, "done later"), (len(partly), "partly made")) if n]
        if notes:
            parts[-1] += f" ({', '.join(notes)})"
    lines = [f"{len(graded)} steps in the build order guide: {' · '.join(parts)}."]
    for s in partly:
        rows = check.rows_of(s.number)
        made = sum(1 for r in rows if r.paired)
        later = [r.done_later for r in rows if r.verdict == MISSING]
        name = item_name(s.item, s.kind, order, exposed, fixes)
        rest = "the other" if len(later) == 1 else "the others"
        if all(x is not None for x in later):
            when = ", ".join(_mmss_of(x.start / LOOPS_PER_SECOND) for x in later if x is not None)
            tail = f"and {rest} later, at {when}."
        else:
            tail = f"and {rest} {'was' if len(later) == 1 else 'were'} not made in this game."
        lines.append(f"{s.count} {_plural(name, s.count)}: you made {made} of the {s.count} in time, {tail}")
    if any(r.verdict == GAME_ENDED for r in check.rows):
        lines.append(
            f"The game ended at {_mmss(check.game_second)}, before the end of the build order guide "
            f"({_mmss(guide.horizon)}). Later steps are not counted."
        )
    names = {s.number: s.name for s in order.of(check.player)}
    extra_counts: dict[str, int] = {}
    for number, item in check.extras:  # a start after 6:00 (a guide reaching past 5:30) has no step in the order
        name = names.get(number) or item_name(item, "unit", order, exposed, fixes)
        extra_counts[name] = extra_counts.get(name, 0) + 1
    if extra_counts:
        ranked = sorted(extra_counts.items(), key=lambda kv: -kv[1])  # stable: first made first among equals
        lines.append("Extra, not in the build order guide: " + ", ".join(f"{n} {_plural(k, n)}" for k, n in ranked) + ".")
    if check.counted:
        counted = []
        for item, n in check.counted:
            text = f"{n} {_plural(item_name(item, 'unit', order, exposed, fixes), n)}"
            counted.append(f"{text} ({_AUTOMATIC_NOTE[item]})" if item in _AUTOMATIC_NOTE else text)
        lines.append("Counted, not graded: " + ", ".join(counted) + ".")
    old, age = age_line(guide, exposed.game.version)
    how = (
        "Picked by you."
        if check.picked
        else "Suggested: you did not name a build order guide, so we used the one closest to your opening."
    )
    first = [
        (
            f'Your opening compared with the build order guide "{guide.name}" for {_matchup(race, opponent)}. '
            f"It covers the first {_mmss(guide.horizon)} of the game."
        ),
        how,
        _graded_line(check),
    ]
    if guide.team_draft:
        first.append(
            f"Team draft: written by the Mindshare team and not yet checked by a {guide.race} player, so take its "
            "verdicts as a first pointer."
        )
    paragraphs = [X_LD.join(first), X_LD.join(lines)]
    if age:
        paragraphs.append(age)
    paragraphs.append(_source_line(guide))
    added: tuple[tuple[str, Added], ...] = (
        ("build order guide", guide.name),
        ("graded by", check.graded_by),
        ("picked", "picked" if check.picked else "suggested"),
        ("team draft", guide.team_draft),
        ("patch", guide.patch or "patch unknown"),
        ("old guide", old),
        ("covers to", GameTime.from_seconds(guide.horizon)),
        ("on time", counts[ON_TIME] + counts[ON_SUPPLY]),
        ("a bit late", counts[A_BIT_LATE]),
        ("late", counts[LATE]),
        ("early", counts[EARLY]),
        ("done", counts[DONE]),
        ("missing", counts[MISSING]),
        ("extra", len({number for number, _ in check.extras})),
        ("not compared", counts[NOT_COMPARED]),
    )
    return f"Build check · {guide.name}", (X_LD + X_LD).join(paragraphs), added


def _ghost_text(row: Row, step: GuideStep, guide: Guide, name: str, check: BuildCheck) -> str:
    """A missing entry's description (AC5; Iris O-3 and the partly made step): what the guide asks and when the moment
    came, then what the player did later."""
    window = _mmss(guide.window)
    verb = _VERB.get(step.kind, "makes")
    thing = (
        name if step.kind == "upgrade" else (f"{step.count} {_plural(name, step.count)}" if step.count > 1 else _article(name))
    )
    rows = check.rows_of(step.number)
    made = sum(1 for r in rows if r.paired)
    missing = [r for r in rows if r.verdict == MISSING]
    if step.trigger is not None:
        first = f"Missing: the build order guide {verb} {thing} {_condition(step)}."
    elif step.timed:
        first = f"Missing: the build order guide {verb} {thing} at {_guide_time(step)}."
    else:
        first = f"Missing: expected at {_guide_supply(step)} supply, where the build order guide {verb} {thing}."
    if made:
        second = f"You made {made} of the {step.count} by {window}."
    elif step.trigger is not None and (gas := re.fullmatch(r"@(\d+) (gas|minerals)", step.trigger)):
        what = f"{gas.group(1)} {gas.group(2)}"
        if row.moment is None:
            second = f"You never had {what} in this game."
        elif row.moment > guide.window:
            second = f"You first had {what} at {_mmss_of(row.moment)}, after the {window} this build check covers."
        else:
            second = f"You had {what} at {_mmss_of(row.moment)}, and had not started it by {window}."
    elif step.trigger is not None and (building := re.fullmatch(r"@100% (.+)", step.trigger)):
        if row.moment is None:
            second = f"Your {building.group(1)} never finished in this game."
        elif row.moment > guide.window:
            second = f"Your {building.group(1)} finished at {_mmss_of(row.moment)}, after the {window} this build check covers."
        else:
            second = f"Your {building.group(1)} finished at {_mmss_of(row.moment)}, and you had not started it by {window}."
    else:  # Iris A6: a step of several units, none made
        second = f"You had not started {'them' if step.count > 1 else 'it'} by {window}."
    if row.done_later is not None:
        when = _mmss_of(row.done_later.start / LOOPS_PER_SECOND)
        if made:
            later = f"You made {'the other one' if len(missing) == 1 else 'one more'} later, at {when}."
        else:
            later = f"You started it later, at {when}."
    elif made:
        later = f"You did not make {'the other one' if len(missing) == 1 else 'this one'} in this game."
    else:
        later = {"building": "You did not build one in this game.", "upgrade": "You did not start it in this game."}.get(
            step.kind, "You did not make one in this game."
        )
    return f"{first} {second}{X_LD}{later}"


def with_build_check(
    graph: Graph, order: BuildOrder, results: Sequence[BuildCheck | NoBuildCheck], exposed: Exposed, fixes: Iterable[str]
) -> Graph:
    """``graph`` (with ``order`` annotated and placed by ``with_build_order``) with the build check (AC2-AC10): each
    compared node's name ending, its sentence and its four entries; each Player node's ``build check`` (and, without a
    comparison, the reason as one line); then, after every existing node, one card per compared player and one missing
    entry per guide occurrence not made in time, each linked ``done later`` to the node of its later start."""
    names = frozenset(fixes)
    readings = supply_reading(exposed)
    contexts = {p.pid: p for p in exposed.game.players}
    nodes = list(graph.nodes)
    holder: dict[tuple[str, object], int] = {}
    players: dict[int, int] = {}
    for i, node in enumerate(nodes):
        if node.source is None:
            continue
        if node.kind == "Player" and node.source.pid is not None:
            players[node.source.pid] = i
        elif node.kind in ("Building", "Units"):
            for unit_id in node.source.unit_ids:
                holder.setdefault((node.kind, unit_id), i)
        elif node.kind == "Upgrade":
            holder[("Upgrade", (node.source.pid, node.source.upgrade, node.source.loop))] = i

    def target(pid: int, later: Later) -> int | None:
        if later.kind == "upgrade":
            return holder.get(("Upgrade", (pid, later.item, later.done_loop)))
        if later.unit_id is None:
            return None
        return holder.get(("Building", later.unit_id), holder.get(("Units", later.unit_id)))

    cards: list[Node] = []
    ghosts: list[tuple[Node, int | None, float]] = []
    marked: dict[int, StepVerdict] = {}  # the node of a later start with no step of its own (after 6:00)
    for pid in sorted(contexts):
        check = next((c for c in results if c.player == pid), None)
        if pid in players:
            node = nodes[players[pid]]
            value = check.value if isinstance(check, NoBuildCheck) else (check.guide.name if check else "")
            description = node.description
            if isinstance(check, NoBuildCheck):
                description = f"{description}{X_LD}{X_LD}{check.line}" if description else check.line
            nodes[players[pid]] = replace(node, description=description, added=(("build check", value),))
        if not isinstance(check, BuildCheck):
            continue
        player_name = nodes[players[pid]].value("name") if pid in players else ""
        name, description, added = card(check, contexts[pid].race, contexts[pid].opponent_race, order, exposed, names)
        cards.append(  # numbered by the player's number in the game, so one player's card never renumbers the other's
            Node(
                "Build Comparison",
                f"Build Comparison-{contexts[pid].order + 1}",
                name,
                description,
                (),
                (("player", player_name),),
                None,
                added=added,
            )
        )
        by_number = {s.number: s for s in check.guide.steps}
        number = 0  # Stefan's D2a: numbered per player, as the cards are, so no player renumbers the other's
        for row in check.rows:
            if row.verdict != MISSING:
                continue
            number += 1
            step = by_number[row.guide_step]
            seconds = ghost_seconds(row, step, check.guide, readings[pid])
            item = item_name(step.item, step.kind, order, exposed, names)
            at = target(pid, row.done_later) if row.done_later is not None else None
            done_later = "" if row.done_later is None else _mmss_of(row.done_later.start / LOOPS_PER_SECOND)
            start = GameTime.from_seconds(int(seconds // 1))
            ghost = Node(
                "Missing Step",
                f"Missing Step-{contexts[pid].order + 1}-{number}",
                f"{item} · missing",
                _ghost_text(row, step, check.guide, item, check),
                (),
                (("time", start), ("player", player_name)),
                start,
                added=(
                    ("item", item),
                    ("guide supply", _guide_supply(step)),
                    ("done later at", done_later),
                    ("build order guide", check.guide.name),
                ),
            )
            ghosts.append((ghost, at, seconds))
            if at is not None and not any(s.verdict for s in nodes[at].steps):
                marked.setdefault(at, _done_later_verdict(seconds))

    for i, node in enumerate(nodes):
        if node.kind not in ("Building", "Upgrade", "Units"):
            continue
        verdict = next((s.verdict for s in node.steps if s.verdict is not None), marked.get(i))
        if verdict is None:
            continue
        description = f"{node.description}{X_LD}{X_LD}{verdict.sentence}" if node.description else verdict.sentence
        nodes[i] = replace(
            node,
            name=f"{node.name} · {verdict.ending}",
            description=description,
            added=(
                ("verdict", verdict.verdict),
                ("guide time", verdict.guide_time),
                ("off by s", verdict.off_by_s),
                ("guide supply", verdict.guide_supply),
            ),
        )
    links = list(graph.links)
    for ghost, at, seconds in ghosts:
        if at is not None:
            links.append(Link(ghost.id, nodes[at].id, "done later", f"was missing at {_mmss_of(seconds)}", "", 1))
    return replace(graph, nodes=(*nodes, *cards, *(g for g, _, _ in ghosts)), links=tuple(links), build_checks=tuple(results))
