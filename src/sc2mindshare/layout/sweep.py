"""The timeline placement as a pure function (CR-014, T14; layout-spec.md §5).

``layout(items, profile, clock_map)`` groups the items by 10-second window and walks the
windows in order, computing Mindshare coordinates directly (time along +x, side A on -y, side B
on +y, battles on y = 0; no rotation step). The defects B1, B2, B7, B8, B9 (layout part), B13
and L1-L7 are fixed as the spec describes; the guards G1-G11 give defined answers. Deterministic:
every sort uses the key ``(t, order)``, every per-side loop goes A then B.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from sc2mindshare.layout.profile import (
    BAR_LANES,
    BAU,
    CARDS,
    GHOSTS,
    LANE_ORDER,
    OCCUPYING,
    OPPONENT_SIDE,
    RAIL,
    SINGLE_POINT,
    TIMELINE_LANES,
    Profile,
)

Size = float | list[float]

SWEPT = OCCUPYING | {"Units", "Supply Block"}
ANCHORS = frozenset({"Game", "Player"})
#: Every type the layout has a place for; any other goes to the grid with a warning (CR-073, AC-9).
KNOWN = SWEPT | ANCHORS | set(CARDS) | set(GHOSTS) | RAIL | set(TIMELINE_LANES)


@dataclass(frozen=True)
class LayoutItem:
    id: str
    type: str
    t: float | None  # signed seconds; None for Game and Player
    order: int  # the tie-break: position in the node list
    player: str | None = None
    t_end: float | None = None  # Supply Block, Scouting Gap, Energy Excess and Inject Delay only
    size_basis: float | None = None  # Battle: supply lost; Units: supply
    step: int | None = None  # Missing Step and Checkpoint: the benchmark step index (ghost order, spec §13.3)
    open_end: bool = False  # CR-073: an Energy Excess still open when the game ends (t_end is then None)


@dataclass(frozen=True)
class ClockNode:
    file_name: str  # "0-50.png"
    media_id: str  # the clock's picture ID on the chosen server (CR-069: from the clock record)
    side: int  # 1 (A, -y) or 2 (B, +y)
    x: float
    y: float


@dataclass
class LayoutResult:
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    sizes: dict[str, Size] = field(default_factory=dict)
    extra_nodes: list[ClockNode] = field(default_factory=list)
    #: CR-069: the clocks the sweep wants, one per window, in window order, whether the map has them or not
    clock_names: list[str] = field(default_factory=list)
    rows: list[tuple[int, int, float]] = field(default_factory=list)  # (row, window, x)
    warnings: list[str] = field(default_factory=list)


def win(t: float, window_s: int = 10) -> int:
    """Window ``w`` covers ``(10w, 10w + 10]``; window 0 also takes every ``t <= 10`` (pre-game included)."""
    t = math.floor(t)  # G11
    return 0 if t <= window_s else math.ceil(t / window_s) - 1


def battle_radius(supply_lost: float) -> float:
    if supply_lost <= 1:
        return 0.7
    if supply_lost <= 3:
        return 0.95
    if supply_lost <= 10:
        return 1.2
    if supply_lost <= 30:
        return 1.6
    return 2 + supply_lost / 100


def units_radius(supply: float) -> float:
    if supply <= 3:
        return 0.75
    if supply <= 10:
        return 1.0
    if supply <= 20:
        return 1.4
    return 1.7


def _key(item: LayoutItem) -> tuple[float, int]:
    return (math.floor(item.t) if item.t is not None else 0, item.order)


def _sides(items: Sequence[LayoutItem], result: LayoutResult) -> tuple[str | None, str | None]:
    players = sorted((i for i in items if i.type == "Player"), key=lambda i: i.order)
    if len(players) > 2:
        raise ValueError(f"more than two Player nodes: {[p.id for p in players]}")
    if len(players) == 2:
        return players[0].player, players[1].player
    # G2: fewer than two Player nodes: the first two distinct players in (t, order) order
    found: list[str] = [p.player for p in players if p.player]
    for item in sorted((i for i in items if i.t is not None), key=_key):
        if item.player and item.player != "Common" and item.player not in found:
            found.append(item.player)
        if len(found) == 2:
            break
    result.warnings.append(f"{len(players)} Player node(s): sides taken from the items ({found})")
    return (found[0] if found else None), (found[1] if len(found) > 1 else None)


def layout(
    items: Sequence[LayoutItem], profile: Profile | None = None, clock_map: Mapping[str, str] | None = None
) -> LayoutResult:
    p = profile or Profile()
    result = LayoutResult()

    # G1: duplicate IDs
    counts = Counter(i.id for i in items)
    for item in items:
        if counts[item.id] > 1:
            raise ValueError(f"duplicate node ID {item.id!r} (type {item.type}): layout guard G1")

    side_a, side_b = _sides(items, result)

    def sign(player: str | None) -> int:
        return -1 if player == side_a else 1

    # anchors (spec §5.4)
    players_seen = 0
    for item in sorted(items, key=lambda i: i.order):
        if item.type == "Game":
            result.positions[item.id] = p.anchor_game
        elif item.type == "Player":
            result.positions[item.id] = p.anchor_players[players_seen]
            players_seen += 1

    # buckets (spec §5.1); G3: a swept non-battle item of a player that is neither side goes to the grid
    swept: list[LayoutItem] = []
    grid: list[LayoutItem] = []
    ghosts: list[LayoutItem] = []  # Missing Step, Checkpoint: never occupy a window (spec §13.3)
    gaps: list[LayoutItem] = []  # Scouting Gap: the outer rail, never occupying (spec §13.4)
    lanes: list[LayoutItem] = []  # CR-073: the timeline lanes beyond the rail, never occupying

    def neither_side(item: LayoutItem) -> bool:
        if item.player in (side_a, side_b):
            return False
        result.warnings.append(f"{item.id}: player {item.player!r} is neither side: placed on the grid (G3)")
        grid.append(item)
        return True

    for item in items:
        if item.type in ANCHORS:
            continue
        if item.type in CARDS:  # player-column cards (spec §13.2); an absent card leaves the other in place
            if not neither_side(item):
                anchors = getattr(p, CARDS[item.type])
                result.positions[item.id] = anchors[0 if item.player == side_a else 1]
            continue
        if (item.type in GHOSTS or item.type in RAIL) and item.t is not None:
            if not neither_side(item):
                (ghosts if item.type in GHOSTS else gaps).append(item)
            continue
        if item.type in TIMELINE_LANES and item.t is not None:
            if not neither_side(item):
                if item.type in OPPONENT_SIDE and side_b is None:  # D2b: no single opponent to sit with
                    result.warnings.append(f"{item.id}: {item.player!r} has no single opponent: placed on the grid")
                    grid.append(item)
                else:
                    lanes.append(item)
            continue
        if item.type in SWEPT and item.t is not None:
            if item.type != "Battle" and item.player not in (side_a, side_b):
                result.warnings.append(f"{item.id}: player {item.player!r} is neither side: placed on the grid (G3)")
                grid.append(item)
            else:
                swept.append(item)
        else:
            if item.type not in KNOWN:  # CR-073 (B-c): an unknown type is reported, not placed silently
                result.warnings.append(f"{item.id}: type {item.type!r} has no lane: placed on the grid")
            grid.append(item)
    swept.sort(key=_key)

    def w_of(item: LayoutItem) -> int:
        assert item.t is not None
        return win(item.t, p.window_s)

    # occupancy (spec §5.3) and the units buffers with lag and end flushes (§5.8, B1, L1)
    occupied = {w_of(i) for i in swept if i.type in OCCUPYING}
    units = [i for i in swept if i.type == "Units"]
    flushes: list[tuple[int, int, list[LayoutItem]]] = []  # (window, side sign, items)
    if units:
        last_window = max(w_of(i) for i in swept)
        buffers: dict[int, list[LayoutItem]] = {-1: [], 1: []}
        by_window: dict[int, list[LayoutItem]] = defaultdict(list)
        for u in units:
            by_window[w_of(u)].append(u)
        last_occupied = -1
        for w in range(last_window + 1):
            for u in by_window.get(w, []):
                buffers[sign(u.player)].append(u)
            lag = any(buffers.values()) and w - last_occupied >= p.unit_max_lag_windows + 1
            if w in occupied or lag:
                occupied.add(w)
                last_occupied = w
                for s in (-1, 1):
                    if buffers[s]:
                        flushes.append((w, s, buffers[s]))
                        buffers[s] = []
        for s in (-1, 1):  # end of the game: flush in the window of the newest unit
            if buffers[s]:
                w = max(w_of(u) for u in buffers[s])
                occupied.add(w)
                flushes.append((w, s, buffers[s]))
                result.warnings.append(f"units left in the buffer at the end: flushed in window {w}")

    # rows (spec §5.3, B2)
    ordered = sorted(occupied)
    rank = {w: r for r, w in enumerate(ordered)}

    def compressed_row(w: int) -> int:
        if w in rank:
            return rank[w]
        later = [x for x in ordered if x > w]
        return rank[later[0]] if later else len(ordered)

    def row(w: int) -> int:
        return w if p.timeline == "linear" else compressed_row(w)

    def x(w: int) -> float:
        return row(w) * p.row_pitch

    result.rows = [(row(w), w, x(w)) for w in ordered]

    def span(item: LayoutItem) -> tuple[int, int]:
        """The first and last window of an interval item (spec §5.10)."""
        ws = w_of(item)
        return ws, max(ws, win(item.t_end if item.t_end is not None else item.t or 0, p.window_s))

    # buildings, upgrades, initiated (spec §5.6); top_slot[(column, side)] is the highest stack slot used, keyed
    # by the compressed column in both timelines (CR-035, Leo's rule L-A), so a ghost in an empty window counts
    # on the same stack, and the units' pad, M, the rail and the lanes are the same in both timelines
    bau_count: Counter[tuple[int, int]] = Counter()
    top_slot: defaultdict[tuple[int, int], int] = defaultdict(lambda: -1)
    for item in (i for i in swept if i.type in BAU):
        w, s = w_of(item), sign(item.player)
        k = bau_count[(w, s)]
        bau_count[(w, s)] += 1
        top_slot[(compressed_row(w), s)] = k
        result.positions[item.id] = (x(w), s * (p.lane_building + k * p.building_stack_step))

    # ghosts (spec §13.3): after the real items of their row, ordered by (time, Missing Step before
    # Checkpoint, step); slot 4 is skipped where a supply block of the same side covers the ghost's compressed
    # column. In linear mode a ghost whose window is empty sits at that window's x, in an otherwise blank row
    # (row(w) = w): intended, confirmed by Leo (leo-cr014-check.md, CR-015 check, note 1); its slot and the
    # slot-4 skip are counted on the compressed columns, as in the compressed timeline (L-A)
    block_columns: defaultdict[int, list[tuple[int, int]]] = defaultdict(list)
    for item in (i for i in swept if i.type == "Supply Block"):
        ws, we = span(item)
        block_columns[sign(item.player)].append((compressed_row(ws), compressed_row(we)))
    for item in sorted(ghosts, key=lambda g: (g.t, GHOSTS.index(g.type), math.inf if g.step is None else g.step, g.order)):
        w, s = w_of(item), sign(item.player)
        column = compressed_row(w)
        k = top_slot[(column, s)] + 1
        if k == p.ghost_skip_slot and any(ca <= column <= cb for ca, cb in block_columns[s]):
            k += 1
        top_slot[(column, s)] = k
        result.positions[item.id] = (x(w), s * (p.lane_building + k * p.building_stack_step))

    # stats, chat, abilities (spec §5.7)
    for item in (i for i in swept if i.type in SINGLE_POINT):
        lane = getattr(p, SINGLE_POINT[item.type])
        result.positions[item.id] = (x(w_of(item)), sign(item.player) * lane)

    # units (spec §5.8); the pad counts every stack slot used in the row, ghosts too (spec §13.3 rule 4)
    spread: dict[int, float] = {}  # per side, the widest unit row beyond the lane's inner edge (§13.4)
    for w, s, buffered in flushes:
        pad = p.building_stack_step * max(0, top_slot[(compressed_row(w), s)] + 1 - p.building_stack_free)
        c = 0.0
        previous_r = 0.0
        for n, u in enumerate(buffered):
            r = units_radius(u.size_basis or 0.0)
            c = p.lane_units + r if n == 0 else c + previous_r + r
            previous_r = r
            result.positions[u.id] = (x(w), s * (c + pad))
            result.sizes[u.id] = r
        spread[s] = max(spread.get(s, 0.0), c + previous_r - p.lane_units + pad)

    # battles (spec §5.5)
    battles = [i for i in swept if i.type == "Battle"]
    pos: dict[str, list[float]] = {}
    radius: dict[str, float] = {}
    for b in battles:
        radius[b.id] = battle_radius(b.size_basis or 0.0)
        pos[b.id] = [x(w_of(b)), p.lane_battle]
        if radius[b.id] >= p.battle_shift_limit:
            result.warnings.append(f"{b.id}: battle radius {radius[b.id]} covers the stats lane (G8)")
    for prev, cur in itertools.pairwise(battles):
        r_cur, r_prev = radius[cur.id], radius[prev.id]
        d = abs(pos[cur.id][0] - pos[prev.id][0])
        if r_cur >= p.battle_shift_threshold and d < r_cur + r_prev:
            s_ = math.sqrt((r_cur + r_prev + p.battle_gap) ** 2 - d**2)
            small, other = (prev, cur) if r_prev <= r_cur else (cur, prev)
            r_small = radius[small.id]
            if s_ + r_small < p.battle_shift_limit:
                pos[small.id][1] += s_
            else:
                o = s_ + r_small - p.battle_shift_limit
                pos[small.id][1] += s_ - o
                pos[other.id][1] -= o
    for b in battles:
        result.positions[b.id] = (pos[b.id][0], pos[b.id][1])
        result.sizes[b.id] = radius[b.id]

    # supply blocks (spec §5.10, B8, G5)
    blocks = [i for i in swept if i.type == "Supply Block"]
    for item in blocks:
        ws, we = span(item)
        if item.t_end is not None and item.t is not None and item.t_end < item.t:
            result.warnings.append(f"{item.id}: ends before it starts (G5)")
        xa, xb = x(ws), x(we)
        result.positions[item.id] = ((xa + xb) / 2, sign(item.player) * p.lane_supply_block)
        result.sizes[item.id] = [xb - xa + p.row_pitch, 1]
    by_side: dict[int, list[LayoutItem]] = defaultdict(list)
    for item in blocks:
        by_side[sign(item.player)].append(item)
    for side_blocks in by_side.values():
        for a, b_ in itertools.pairwise(side_blocks):
            if a.t_end is not None and b_.t is not None and b_.t < a.t_end:
                result.warnings.append(f"{a.id} and {b_.id} overlap (G5)")

    # M per side for the whole game (spec §13.4; CR-073, Leo's Algorithm notes point 3): beyond the widest unit
    # row and the highest building or ghost stack top, floor 5.8; the rail and the timeline lanes stand on it
    stack_tops: dict[int, float] = {}
    for (_row, s), k in top_slot.items():
        if k >= 0:
            top = p.lane_building + k * p.building_stack_step + p.default_size[1] / 2
            stack_tops[s] = max(stack_tops.get(s, 0.0), top)

    def margin(s: int) -> float:
        return max(p.unit_spread_floor, spread.get(s, 0.0), stack_tops.get(s, 0.0) - p.lane_units)

    # the Scouting Gap rail (spec §13.4, TD-45): supply-block geometry, height 0.6, beyond M, so it stays one
    # straight band per side
    gaps.sort(key=_key)
    for item in gaps:
        s = sign(item.player)
        ws, we = span(item)
        xa, xb = x(ws), x(we)
        offset = p.lane_units + margin(s) + p.rail_clearance + p.rail_height / 2
        result.positions[item.id] = ((xa + xb) / 2, s * offset)
        result.sizes[item.id] = [xb - xa + p.row_pitch, p.rail_height]
    for side in (-1, 1):
        side_gaps = [g for g in gaps if sign(g.player) == side]
        for a, b_ in itertools.pairwise(side_gaps):
            if a.t_end is not None and b_.t is not None and b_.t < a.t_end:
                result.warnings.append(f"{a.id} and {b_.id} overlap (G5)")

    _timeline_lanes(lanes, p, result, w_of, compressed_row, x, ordered, margin, sign)

    # clock images (spec §5.9, B7, G6)
    stats_windows = {w_of(i) for i in swept if i.type == "Stats"}
    for w in ordered:
        if w in stats_windows:
            continue
        end = p.window_s * (w + 1)
        name = f"{end // 60}-{end % 60:02d}.png"
        result.clock_names.append(name)
        media = (clock_map or {}).get(name)
        if media is None:  # CR-069: one warning per missing clock, naming the command that uploads it
            result.warnings.append(f"no clock image for {name}: run sc2mindshare upload-clocks (G6)")
            continue
        result.extra_nodes.append(ClockNode(name, media, 1, x(w), -p.lane_clock))
        result.extra_nodes.append(ClockNode(name, media, 2, x(w), p.lane_clock))

    # grid (spec §5.11), in input order
    ox, oy = p.grid_origin
    for i, item in enumerate(sorted(grid, key=lambda it: it.order)):
        result.positions[item.id] = (
            ox + p.grid_step * (1 + i % p.grid_columns),
            oy + p.grid_step * (1 + i // p.grid_columns),
        )

    # sizes of everything else (spec §4.2)
    for item in items:
        if item.id not in result.sizes:
            fixed = p.fixed_sizes.get(item.type)
            result.sizes[item.id] = list(fixed) if isinstance(fixed, list) else list(p.default_size)

    if not swept:
        result.warnings.append("no items to sweep (G4)")
    return result


def _timeline_lanes(
    lanes: Sequence[LayoutItem],
    p: Profile,
    result: LayoutResult,
    w_of: Callable[[LayoutItem], int],
    compressed_row: Callable[[int], int],
    x: Callable[[int], float],
    ordered: Sequence[int],
    margin: Callable[[int], float],
    sign: Callable[[str | None], int],
) -> None:
    """CR-073: Harrasment, Scouting, Inject Delay and Energy Excess in lanes beyond the rail band (Leo's
    Algorithm notes, CR-073). They never occupy a window, so no column is added and no other node moves.

    Cards sit at their start column, bars span their start to their end column (supply-block geometry); an
    open end runs to the last occupied window, never before the start. Per side and lane, items are stacked
    first fit on their compressed columns, and the levels are used in both modes, so each y is the same in
    the compressed and the linear timeline. The rail band (12.8 + M + 0.5, 0.6 wide) is always reserved;
    then the events lane, the inject-delay lane and the spare-energy lane, each at least one row deep."""
    placed: list[tuple[LayoutItem, int, str, int, int]] = []  # (item, side, lane, first window, last window)
    for item in lanes:
        lane = TIMELINE_LANES[item.type]
        s = sign(item.player)
        if item.type in OPPONENT_SIDE:  # D2b: the attacker's side
            s = -s
        ws = w_of(item)
        if lane not in BAR_LANES:
            we = ws
        elif item.open_end:
            we = max(ws, ordered[-1]) if ordered else ws
        else:
            if item.t_end is not None and item.t is not None and item.t_end < item.t:
                result.warnings.append(f"{item.id}: ends before it starts (G5)")
            end = item.t_end if item.t_end is not None else item.t
            assert end is not None
            we = max(ws, win(end, p.window_s))
        placed.append((item, s, lane, ws, we))

    level: dict[str, int] = {}
    depth: dict[tuple[int, str], int] = {}
    for s in (-1, 1):
        for lane in LANE_ORDER:
            ends: list[int] = []  # per level, the last compressed column used
            group = [e for e in placed if e[1] == s and e[2] == lane]
            group.sort(key=lambda e: (compressed_row(e[3]), e[0].t or 0.0, compressed_row(e[4]), e[0].order))
            for item, _s, _lane, ws, we in group:
                cs, ce = compressed_row(ws), compressed_row(we)
                k = next((n for n, last in enumerate(ends) if last < cs), len(ends))
                if k == len(ends):
                    ends.append(ce)
                else:
                    ends[k] = ce
                level[item.id] = k
            depth[(s, lane)] = max(1, len(ends))  # an empty lane keeps its row

    card = p.default_size[1]
    for s in (-1, 1):
        start = p.lane_units + margin(s) + p.rail_clearance + p.rail_height + p.lane_clearance
        inner: dict[str, float] = {}
        for lane in LANE_ORDER:
            inner[lane] = start
            rows = depth[(s, lane)]
            if lane in BAR_LANES:
                start += p.bar_height + (p.bar_height + p.bar_gap) * (rows - 1)
            else:
                start += card + p.event_step * (rows - 1)
            start += p.lane_clearance
        for item, side, lane, ws, we in placed:
            if side != s:
                continue
            if lane in BAR_LANES:
                y = inner[lane] + p.bar_height / 2 + (p.bar_height + p.bar_gap) * level[item.id]
                xa, xb = x(ws), x(we)
                result.positions[item.id] = ((xa + xb) / 2, s * round(y, 6))
                result.sizes[item.id] = [round(xb - xa + p.row_pitch, 6), round(p.bar_height, 6)]
            else:
                y = inner[lane] + card / 2 + p.event_step * level[item.id]
                result.positions[item.id] = (x(ws), s * round(y, 6))
