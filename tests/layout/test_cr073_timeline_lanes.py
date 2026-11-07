"""CR-073: Harrasment, Scouting, Inject Delay and Energy Excess in lanes along the timeline (Leo's Algorithm
notes in CR-073; D7a bars, D8a outside, D1a bar height 1.0, D2b harassment on the attacker's side).

Every fixture here is hand-computed. With no units and no building stack, M = 5.8 on both sides, so the rail
band is reserved at 19.1-19.7, the events lane starts at 20.0 (card centres 20.5, 21.55, ...), and with one
events row the inject lane starts at 21.3 (bar centre 21.8) and the energy lane at 22.6 (bar centre 23.1).
"""

import pytest

from sc2mindshare.domain.models import FIELDS, Node
from sc2mindshare.domain.time import GameTime
from sc2mindshare.layout.items import item
from sc2mindshare.layout.profile import CARDS, GHOSTS, RAIL, TIMELINE_LANES, Profile
from sc2mindshare.layout.sweep import SWEPT, LayoutItem, layout

MODES = ("compressed", "linear")
GRID = {(18, 3), (21, 3), (24, 3), (27, 3), (18, 6)}


def approx(value):
    return pytest.approx(value, abs=1e-9)


def players():
    return [LayoutItem("Player-1", "Player", None, 0, player="A"), LayoutItem("Player-2", "Player", None, 1, player="B")]


class AllClocks(dict):
    """A clock map that has every clock, so the fixtures carry no G6 warning."""

    def get(self, key, default=None):
        return "c" * 24

    def __bool__(self):  # the layout reads ``clock_map or {}``
        return True


def lay(extra, mode="compressed", with_players=True):
    head = players() if with_players else []
    items = head + [
        LayoutItem(i.id, i.type, i.t, n + 2, i.player, i.t_end, i.size_basis, i.step, i.open_end) for n, i in enumerate(extra)
    ]
    return layout(items, Profile(timeline=mode), AllClocks())


def it(id_, type_, t, player="A", **kw):
    return LayoutItem(id_, type_, t, 0, player=player, **kw)


# windows 0 and 4 occupied: compressed columns 0 and 1 (x 0 and 2.5); linear x = 2.5 x window
BASE = [it("Chat-1", "Chat", 5), it("Chat-2", "Chat", 45)]


# --- AC-2, AC-3: cards at their start column, on their side ---------------------------------------------------


@pytest.mark.parametrize(("mode", "x"), [("compressed", 2.5), ("linear", 5.0)])
def test_a_scouting_card_in_an_empty_window_sits_at_the_next_column_on_its_players_side(mode, x):
    r = lay([*BASE, it("Scouting-1", "Scouting", 25)], mode)  # window 2 is empty
    assert r.positions["Scouting-1"] == approx((x, -20.5)) and r.sizes["Scouting-1"] == [2.65, 1]
    assert r.warnings == []


@pytest.mark.parametrize("mode", MODES)
def test_a_harassment_card_sits_on_the_attackers_side(mode):
    # D2b: the node's player (A) lost the workers; its card sits on the opponent's side (B, +y)
    a = lay([*BASE, it("Harrasment-1", "Harrasment", 5, "A", t_end=12)], mode)
    b = lay([*BASE, it("Harrasment-1", "Harrasment", 5, "B", t_end=12)], mode)
    assert a.positions["Harrasment-1"] == approx((0, 20.5)) and b.positions["Harrasment-1"] == approx((0, -20.5))
    assert a.sizes["Harrasment-1"] == [2.65, 1]  # its end is not used: one card at its start (D7a)
    assert a.warnings == [] and b.warnings == []


@pytest.mark.parametrize(
    ("t", "compressed_x", "linear_x"),
    [(-30, 0, 0), (9, 0, 0), (10, 0, 0), (11, 2.5, 2.5), (55, 5.0, 12.5)],  # 55: after the last column: last + 1
)
def test_start_columns(t, compressed_x, linear_x):
    for mode, x in (("compressed", compressed_x), ("linear", linear_x)):
        r = lay([*BASE, it("Scouting-1", "Scouting", t)], mode)
        assert r.positions["Scouting-1"][0] == x, (mode, t)


# --- AC-4: bars over their period ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "inject", "energy"),
    [
        # Inject Delay-1 windows 1-4: compressed columns 1-1; Energy Excess-1 windows 0-4: columns 0-1
        ("compressed", ((2.5, -21.8), [2.5, 1.0]), ((1.25, 23.1), [5.0, 1.0])),
        ("linear", ((6.25, -21.8), [10.0, 1.0]), ((5.0, 23.1), [12.5, 1.0])),
    ],
)
def test_bars_span_their_period_in_their_lanes(mode, inject, energy):
    r = lay(
        [*BASE, it("Inject Delay-1", "Inject Delay", 15, t_end=44), it("Energy Excess-1", "Energy Excess", 5, "B", t_end=45)],
        mode,
    )
    assert (r.positions["Inject Delay-1"], r.sizes["Inject Delay-1"]) == (approx(inject[0]), approx(inject[1]))
    assert (r.positions["Energy Excess-1"], r.sizes["Energy Excess-1"]) == (approx(energy[0]), approx(energy[1]))
    assert r.warnings == []


@pytest.mark.parametrize("mode", MODES)
def test_a_period_inside_one_window_is_one_column_wide(mode):
    r = lay([*BASE, it("Inject Delay-1", "Inject Delay", 12, t_end=18)], mode)
    assert r.positions["Inject Delay-1"] == approx((2.5, -21.8)) and r.sizes["Inject Delay-1"] == approx([2.5, 1.0])


# windows 0, 4 and 6 occupied: compressed columns 0, 1, 2
OPEN_BASE = [*BASE, it("Chat-3", "Chat", 65)]


@pytest.mark.parametrize(
    ("mode", "open_bar", "late_bar", "no_end"),
    [
        ("compressed", ((3.75, -23.1), [5.0, 1.0]), ((7.5, -23.1), [2.5, 1.0]), ((2.5, -23.1), [2.5, 1.0])),
        ("linear", ((8.75, -23.1), [15.0, 1.0]), ((17.5, -23.1), [2.5, 1.0]), ((2.5, -23.1), [2.5, 1.0])),
    ],
)
def test_an_open_end_runs_to_the_last_occupied_window_never_before_its_start(mode, open_bar, late_bar, no_end):
    # one item per layout, so stacking does not mix the cases
    open_ = lay([*OPEN_BASE, it("Energy Excess-1", "Energy Excess", 15, open_end=True)], mode)
    assert (open_.positions["Energy Excess-1"], open_.sizes["Energy Excess-1"]) == (approx(open_bar[0]), approx(open_bar[1]))
    late = lay([*OPEN_BASE, it("Energy Excess-1", "Energy Excess", 75, open_end=True)], mode)  # window 7 > 6
    assert (late.positions["Energy Excess-1"], late.sizes["Energy Excess-1"]) == (approx(late_bar[0]), approx(late_bar[1]))
    closed = lay([*OPEN_BASE, it("Energy Excess-1", "Energy Excess", 15)], mode)  # no end, not open (Rex F2)
    assert (closed.positions["Energy Excess-1"], closed.sizes["Energy Excess-1"]) == (approx(no_end[0]), approx(no_end[1]))


@pytest.mark.parametrize("mode", MODES)
def test_a_bar_ending_before_it_starts_is_one_column_with_a_warning(mode):
    r = lay(
        [*BASE, it("Inject Delay-1", "Inject Delay", 45, t_end=25), it("Energy Excess-1", "Energy Excess", 45, "B", t_end=25)],
        mode,
    )
    x = 2.5 if mode == "compressed" else 10.0
    assert r.positions["Inject Delay-1"] == approx((x, -21.8)) and r.sizes["Inject Delay-1"] == approx([2.5, 1.0])
    assert r.positions["Energy Excess-1"] == approx((x, 23.1)) and r.sizes["Energy Excess-1"] == approx([2.5, 1.0])
    assert r.warnings == ["Inject Delay-1: ends before it starts (G5)", "Energy Excess-1: ends before it starts (G5)"]


# --- AC-5: stacking, chosen on compressed columns and kept in both modes ---------------------------------------


@pytest.mark.parametrize(("mode", "xs"), [("compressed", (2.5, 2.5)), ("linear", (5.0, 10.0))])
def test_cards_sharing_a_compressed_column_stack_and_keep_their_y_in_linear(mode, xs):
    # windows 2 (empty) and 4 share compressed column 1; in linear they are apart, yet keep their levels
    r = lay([*BASE, it("Scouting-1", "Scouting", 25), it("Scouting-2", "Scouting", 45)], mode)
    assert r.positions["Scouting-1"] == approx((xs[0], -20.5))
    assert r.positions["Scouting-2"] == approx((xs[1], -21.55))


@pytest.mark.parametrize("mode", MODES)
def test_overlapping_bars_stack_and_disjoint_ones_share_a_level(mode):
    bars = [
        it("Inject Delay-1", "Inject Delay", 5, t_end=45),  # columns 0-1
        it("Inject Delay-2", "Inject Delay", 15, t_end=25),  # column 1: overlaps -1
        it("Inject Delay-3", "Inject Delay", 65, t_end=68),  # column 2: free again at level 0
    ]
    r = lay([*OPEN_BASE, *bars], mode)
    assert [r.positions[f"Inject Delay-{k}"][1] for k in (1, 2, 3)] == approx([-21.8, -22.85, -21.8])
    # two inject rows push the energy lane out: 21.3 + 1.0 + 1.05 + 0.3 = 23.65, centre 24.15
    r2 = lay([*OPEN_BASE, *bars, it("Energy Excess-1", "Energy Excess", 5, t_end=8)], mode)
    assert r2.positions["Energy Excess-1"][1] == approx(-24.15)


# --- AC-6: the lanes stand beyond the widest unit row and the tallest stack, past the reserved rail band --------


@pytest.mark.parametrize("mode", MODES)
def test_m_takes_the_tallest_building_stack(mode):
    # 12 buildings of A in window 0: slot 11's top is 8.0 + 11 x 1.05 + 0.5 = 20.05, so M = 7.25
    stack = [it(f"Building-{k}", "Building", 1) for k in range(12)]
    r = lay([*stack, it("Scouting-1", "Scouting", 5), it("Scouting Gap-1", "Scouting Gap", 1, t_end=8)], mode)
    assert r.positions["Scouting-1"] == approx((0, -21.95))  # 12.8 + 7.25 + 0.5 + 0.6 + 0.3 + 0.5
    assert r.positions["Scouting Gap-1"][1] == approx(-20.85)  # the rail stands on the same M
    plain = lay([*BASE, it("Scouting-1", "Scouting", 5)], mode)
    assert plain.positions["Scouting-1"] == approx((0, -20.5))  # neither: the floor 5.8


@pytest.mark.parametrize("mode", MODES)
def test_m_takes_the_widest_unit_row(mode):
    # side B: 5 units of supply 21 (radius 1.7) in one window reach 17.0 beyond 12.8
    units = [it(f"Units-{k}", "Units", 5, "B", size_basis=21) for k in range(5)]
    r = lay([*BASE, *units, it("Scouting-1", "Scouting", 5, "B")], mode)
    assert r.positions["Scouting-1"] == approx((0, 31.7))  # 12.8 + 17.0 + 0.5 + 0.6 + 0.3 + 0.5


# CR-035, L-A (Leo's rule; CR-073 review finding 1): the stack slots are counted on the compressed columns in
# both timelines, so a ghost in an empty window stacks on the next column's buildings in linear mode too, and
# M, the rail and every lane keep the same y in both timelines. Fixture: windows 0 and 4 occupied (BASE);
# 11 buildings of A in window 4 (slots 0-10), a Missing Step of A in the empty window 2: it takes slot 11.
L_A_STACK = [it(f"Building-{k}", "Building", 45) for k in range(11)]


@pytest.mark.parametrize(("mode", "ghost_x", "scouting_x"), [("compressed", 2.5, 2.5), ("linear", 5.0, 10.0)])
def test_a_ghost_in_an_empty_window_takes_the_next_columns_stack_slot_in_both_timelines(mode, ghost_x, scouting_x):
    r = lay([*BASE, *L_A_STACK, it("Missing Step-1", "Missing Step", 25), it("Scouting-1", "Scouting", 45)], mode)
    assert r.positions["Missing Step-1"] == approx((ghost_x, -19.55))  # 8.0 + 11 x 1.05
    # slot 11's top is 8.0 + 11 x 1.05 + 0.5 = 20.05, so M = 7.25 (linear before L-A: slot 10, M 6.2, y -20.9)
    assert r.positions["Scouting-1"] == approx((scouting_x, -21.95))  # 12.8 + 7.25 + 0.5 + 0.6 + 0.3 + 0.5


@pytest.mark.parametrize(("mode", "x"), [("compressed", 2.5), ("linear", 10.0)])
def test_the_units_pad_counts_a_ghost_from_an_empty_window_in_both_timelines(mode, x):
    unit = it("Units-1", "Units", 45, size_basis=21)  # radius 1.7
    r = lay([*BASE, *L_A_STACK, it("Missing Step-1", "Missing Step", 25), unit, it("Scouting-1", "Scouting", 45)], mode)
    # 12 slots used in the column: pad = 1.05 x (12 - 5) = 7.35; the unit at 12.8 + 1.7 + 7.35
    assert r.positions["Units-1"] == approx((x, -21.85))
    # M = the unit row, 1.7 x 2 + 7.35 = 10.75 (linear before L-A: pad 6.3, unit -20.8, Scouting -24.4)
    assert r.positions["Scouting-1"] == approx((x, -25.45))  # 12.8 + 10.75 + 0.5 + 0.6 + 0.3 + 0.5


# --- AC-9: every type has a lane; the grid is the fallback, with a warning -------------------------------------


def test_every_type_the_export_writes_has_a_lane():
    lanes = set(SWEPT) | set(CARDS) | set(GHOSTS) | set(RAIL) | set(TIMELINE_LANES)
    missing = sorted(set(FIELDS) - {"Game", "Player"} - lanes)
    assert missing == [], f"node types with no lane (they would fall to the grid): {missing}"


@pytest.mark.parametrize("kind", sorted(set(FIELDS) - {"Game", "Player"}))
@pytest.mark.parametrize("mode", MODES)
def test_every_type_is_laid_out_off_the_grid_without_a_warning(kind, mode):
    r = lay([it("Chat-0", "Chat", 5), it(f"{kind}-1", kind, 5, t_end=8, size_basis=2)], mode)
    assert r.positions[f"{kind}-1"] not in GRID and r.warnings == [], kind


@pytest.mark.parametrize("mode", MODES)
def test_an_unknown_type_and_a_third_players_card_go_to_the_grid_with_a_warning(mode):
    r = lay([*BASE, it("Mystery-1", "Mystery", 5), it("Scouting-1", "Scouting", 5, "C")], mode)
    assert [r.positions["Mystery-1"], r.positions["Scouting-1"]] == [(18, 3), (21, 3)]
    assert r.warnings == [
        "Mystery-1: type 'Mystery' has no lane: placed on the grid",
        "Scouting-1: player 'C' is neither side: placed on the grid (G3)",
    ]


@pytest.mark.parametrize("mode", MODES)
def test_a_harassment_with_no_single_opponent_or_a_loser_of_neither_side_goes_to_the_grid(mode):
    # fewer than two Player nodes and one player in the items: no single opponent (G2)
    alone = lay([it("Chat-1", "Chat", 5), it("Harrasment-1", "Harrasment", 5)], mode, with_players=False)
    assert alone.positions["Harrasment-1"] == (18, 3)
    assert [w for w in alone.warnings if "Harrasment-1" in w] == ["Harrasment-1: 'A' has no single opponent: placed on the grid"]
    neither = lay([*BASE, it("Harrasment-1", "Harrasment", 5, "C")], mode)
    assert neither.positions["Harrasment-1"] == (18, 3)
    assert neither.warnings == ["Harrasment-1: player 'C' is neither side: placed on the grid (G3)"]


# --- AC-10: without the four types nothing changes; one side only ----------------------------------------------


@pytest.mark.parametrize("mode", MODES)
def test_the_lanes_move_nothing_else_and_add_no_column(mode):
    others = [*OPEN_BASE, *(it(f"Building-{k}", "Building", 1) for k in range(3)), it("Units-1", "Units", 5, size_basis=2)]
    four = [
        it("Scouting-1", "Scouting", 25),
        it("Harrasment-1", "Harrasment", 35, "B", t_end=38),
        it("Inject Delay-1", "Inject Delay", 15, t_end=55),
        it("Energy Excess-1", "Energy Excess", 85, "B", open_end=True),
    ]
    without, with_ = lay(others, mode), lay([*others, *four], mode)
    assert {k: v for k, v in with_.positions.items() if k in without.positions} == without.positions
    assert {k: v for k, v in with_.sizes.items() if k in without.sizes} == without.sizes
    assert with_.rows == without.rows and with_.extra_nodes == without.extra_nodes and with_.clock_names == without.clock_names
    assert with_.warnings == without.warnings


@pytest.mark.parametrize("mode", MODES)
def test_an_empty_lane_keeps_its_row(mode):
    # B has no inject delay: its energy lane still starts beyond one reserved inject row
    r = lay([*BASE, it("Energy Excess-1", "Energy Excess", 5, "B", t_end=8)], mode)
    assert r.positions["Energy Excess-1"][1] == approx(23.1)


# --- precision (S18) -------------------------------------------------------------------------------------------


def test_y_and_sizes_are_rounded_to_6_decimals():
    # three stacked cards: 20.0 + 0.5 + 2 x 1.05 sums to 22.6 plus a float tail without the rounding
    r = lay([*BASE, *(it(f"Scouting-{k}", "Scouting", 5) for k in range(3)), it("Inject Delay-1", "Inject Delay", 5, t_end=8)])
    ys = [r.positions[f"Scouting-{k}"][1] for k in range(3)]
    assert ys == [-20.5, -21.55, -22.6]  # exact, not approx
    assert r.positions["Inject Delay-1"][1] == -23.9 and r.sizes["Inject Delay-1"] == [2.5, 1.0]


# --- the domain's open end reaches the layout (Morgan's finding 2) ---------------------------------------------


def _bar(kind, end):
    start = GameTime.from_seconds(30)
    values = (("time", start), ("player", "A"), ("end time", end), ("duration", "5"))
    return Node(kind, f"{kind}-1", kind, "", (), values, start)


def test_the_domains_open_end_reaches_the_layout():
    open_ = item(_bar("Energy Excess", None), 0)
    assert (open_.open_end, open_.t_end) == (True, None)
    closed = item(_bar("Energy Excess", GameTime.from_seconds(45)), 0)
    assert (closed.open_end, closed.t_end) == (False, 45)
    inject = item(_bar("Inject Delay", GameTime.from_seconds(45)), 0)
    assert (inject.open_end, inject.t_end) == (False, 45)


def test_an_inject_delay_cannot_be_open_ended():
    # only an Energy Excess may have no end (OPEN_ENDED); an Inject Delay without one is refused by the domain,
    # so the layout never sees it, and its item is never open-ended
    with pytest.raises(ValueError, match="must be a GameTime"):
        _bar("Inject Delay", None)
