"""CR-015 (T14b): lanes for stream 2's new node types (layout-spec.md §13; TD-41, TD-44, TD-45).

Stream 2 does not produce these nodes yet, so every test builds its items. Types: Build Comparison and
Coaching (player-column anchors, §13.2), Missing Step and Checkpoint (ghosts in the building stack that
never occupy a window, §13.3), Scouting Gap (the outer interval rail, §13.4). The tech-reaction link and
the Worker Checkpoint have no placement. Every rule applies in both timeline modes.
"""

import contextlib
import csv
import importlib.util
import io
import os
import pathlib

import pytest

from sc2mindshare.layout.items import ghost_time
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutItem, layout

_spec = importlib.util.spec_from_file_location("micro_fixture", pathlib.Path(__file__).with_name("test_micro_fixture.py"))
assert _spec and _spec.loader
_micro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_micro)
CLOCKS, fixture_items = _micro.CLOCKS, _micro.fixture_items

MODES = ("compressed", "linear")


def approx(value):
    return pytest.approx(value, abs=1e-9)


# --- the micro fixture (spec §9.3) with one row per new type --------------------------------------------

NEW = [
    LayoutItem("Coaching-1", "Coaching", None, 14, player="A"),
    LayoutItem("Build Comparison-2", "Build Comparison", None, 15, player="B"),
    LayoutItem("Missing Step-1", "Missing Step", 7, 16, player="A", step=3),
    LayoutItem("Checkpoint-1", "Checkpoint", 35, 17, player="B", step=1),
    LayoutItem("Scouting Gap-1", "Scouting Gap", 12, 18, player="A", t_end=35),
]
# Hand-computed (windows 0, 1 and 4 are occupied: rows 0, 1, 2 in compressed mode):
# - the cards: (-6, S x 11.5) and (-6, S x 14.0), [7.8, 2.2]; Coaching of B and Build Comparison of A are
#   absent and leave the other card where it is;
# - Missing Step-1 (t 7, window 0, side A): after Building-1 and -2, slot 2: y = -(8.0 + 2.1) = -10.1;
# - Checkpoint-1 (t 35, window 3, empty): compressed -> the next occupied row (window 4, x 5); linear -> its
#   own row, x 7.5; side B has no real item there: slot 0, y = 8.0;
# - Scouting Gap-1 (t 12 -> 35, windows 1 -> 3): compressed x 2.5 -> 5, centre 3.75, width 5.0; linear
#   x 2.5 -> 7.5, centre 5.0, width 7.5; side A's widest unit row spans 2 x (0.75 + 1.0) = 3.5 < 5.8, so
#   the floor applies: y = -(12.8 + 5.8 + 0.5 + 0.3) = -19.4; height 0.6.
EXPECTED = {
    "compressed": {
        "Coaching-1": ((-6, -11.5), [7.8, 2.2]),
        "Build Comparison-2": ((-6, 14.0), [7.8, 2.2]),
        "Missing Step-1": ((0, -10.1), [2.65, 1]),
        "Checkpoint-1": ((5, 8.0), [2.65, 1]),
        "Scouting Gap-1": ((3.75, -19.4), [5.0, 0.6]),
    },
    "linear": {
        "Coaching-1": ((-6, -11.5), [7.8, 2.2]),
        "Build Comparison-2": ((-6, 14.0), [7.8, 2.2]),
        "Missing Step-1": ((0, -10.1), [2.65, 1]),
        "Checkpoint-1": ((7.5, 8.0), [2.65, 1]),
        "Scouting Gap-1": ((5.0, -19.4), [7.5, 0.6]),
    },
}


@pytest.mark.parametrize("mode", MODES)
def test_micro_fixture_rows_for_the_new_types(mode):
    base = layout(fixture_items(), Profile(timeline=mode), CLOCKS)
    r = layout(fixture_items() + NEW, Profile(timeline=mode), CLOCKS)
    for node_id, (position, size) in EXPECTED[mode].items():
        assert r.positions[node_id] == approx(position), node_id
        assert r.sizes[node_id] == approx(size), node_id
    # nothing that was there before moves, and no row or clock is added
    assert {k: v for k, v in r.positions.items() if k in base.positions} == base.positions
    assert {k: v for k, v in r.sizes.items() if k in base.sizes} == base.sizes
    assert r.rows == base.rows and r.extra_nodes == base.extra_nodes
    assert r.warnings == []


# --- lane tests (spec §13.6) ----------------------------------------------------------------------------------


def players():
    return [LayoutItem("Player-1", "Player", None, 0, player="A"), LayoutItem("Player-2", "Player", None, 1, player="B")]


def lay(extra, mode="compressed", clocks=None):
    items = players() + [
        LayoutItem(i.id, i.type, i.t, n + 2, i.player, i.t_end, i.size_basis, i.step) for n, i in enumerate(extra)
    ]
    return layout(items, Profile(timeline=mode), clocks)


def it(id_, type_, t, player="A", **kw):
    return LayoutItem(id_, type_, t, 0, player=player, **kw)


def buildings(n, t=1, player="A"):
    return [it(f"Building-{player}{k}", "Building", t, player) for k in range(n)]


@pytest.mark.parametrize(("mode", "x"), [("compressed", 2.5), ("linear", 5.0)])
def test_a_ghost_in_an_empty_window_maps_to_the_next_row_and_adds_no_row(mode, x):
    base = [it("Chat-1", "Chat", 5), it("Chat-2", "Chat", 45)]
    clocks = {"0-10.png": "c", "0-50.png": "d"}
    without = lay(base, mode, clocks)
    with_ghost = lay([*base, it("Missing Step-1", "Missing Step", 25)], mode, clocks)
    assert with_ghost.positions["Missing Step-1"] == approx((x, -8.0))  # window 2 is empty
    assert with_ghost.rows == without.rows  # a ghost never makes a window occupied
    assert with_ghost.extra_nodes == without.extra_nodes  # so no clock either
    assert with_ghost.positions["Chat-2"] == without.positions["Chat-2"]


@pytest.mark.parametrize("mode", MODES)
def test_ghosts_follow_the_real_items_in_time_kind_and_step_order(mode):
    extra = [
        *buildings(2),
        it("Checkpoint-1", "Checkpoint", 5, step=1),
        it("Missing Step-2", "Missing Step", 5, step=2),
        it("Missing Step-9", "Missing Step", 2, step=9),
    ]
    r = lay(extra, mode)
    ys = {k: r.positions[k][1] for k in ("Building-A0", "Building-A1", "Missing Step-9", "Missing Step-2", "Checkpoint-1")}
    # real items keep slots 0 and 1; then the earlier ghost, then Missing Step before Checkpoint at t = 5
    assert ys == approx(
        {"Building-A0": -8.0, "Building-A1": -9.05, "Missing Step-9": -10.1, "Missing Step-2": -11.15, "Checkpoint-1": -12.2}
    )


@pytest.mark.parametrize("mode", MODES)
def test_ghosts_count_toward_the_pad(mode):
    unit = it("Units-1", "Units", 1, size_basis=2)  # radius 0.75
    alone = lay([*buildings(4), unit], mode)
    assert alone.positions["Units-1"][1] == approx(-13.55)  # 4 real items: no pad
    crowded = lay([*buildings(4), it("Missing Step-1", "Missing Step", 2), it("Checkpoint-1", "Checkpoint", 3), unit], mode)
    assert crowded.positions["Checkpoint-1"][1] == approx(-(8.0 + 5 * 1.05))  # slot 5
    assert crowded.positions["Units-1"][1] == approx(-13.55 - 1.05)  # the 6th slot pushes the units out by 1.05


@pytest.mark.parametrize("mode", MODES)
def test_slot_4_is_skipped_when_a_supply_block_covers_the_row(mode):
    ghost = it("Missing Step-1", "Missing Step", 2)
    unit = it("Units-1", "Units", 1, size_basis=2)
    covered = lay([*buildings(4), ghost, unit, it("Supply Block-1", "Supply Block", 1, t_end=8)], mode)
    assert covered.positions["Missing Step-1"][1] == approx(-(8.0 + 5 * 1.05))  # slot 5, not 4
    assert covered.positions["Units-1"][1] == approx(-13.55 - 1.05)  # the skipped slot counts for the pad
    free = lay([*buildings(4), ghost, unit], mode)
    assert free.positions["Missing Step-1"][1] == approx(-(8.0 + 4 * 1.05))  # slot 4
    other_side = lay([*buildings(4), ghost, it("Supply Block-2", "Supply Block", 1, player="B", t_end=8)], mode)
    assert other_side.positions["Missing Step-1"][1] == approx(-(8.0 + 4 * 1.05))
    elsewhere = lay([*buildings(4), ghost, it("Chat-1", "Chat", 45), it("Supply Block-1", "Supply Block", 41, t_end=44)], mode)
    assert elsewhere.positions["Missing Step-1"][1] == approx(-(8.0 + 4 * 1.05))  # the block covers another row


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"guide_time": 150}, 150),  # a step with a time: the guide time
        ({"guide_time": 150, "guide_supply": 20}, 150),
        ({"guide_supply": 20}, 95),  # supply only: the first sample with food_used >= 20
        ({"guide_supply": 99}, 400),  # never reached: the horizon
        ({"trigger_time": 210}, 210),  # trigger only, evaluated
        ({}, 400),  # trigger only, not evaluable: the horizon
    ],
)
def test_ghost_placement_time(kwargs, expected):
    food_used = [(0, 12), (40, 14), (80, 19), (95, 20), (120, 23)]
    assert ghost_time(food_used=food_used, horizon=400, **kwargs) == expected


@pytest.mark.parametrize("mode", MODES)
def test_the_rail_is_measured_from_the_widest_unit_row_with_a_floor(mode):
    # side B: 5 units of supply 21 (radius 1.7) in one window: 2 x 5 x 1.7 = 17.0 beyond 12.8
    units = [it(f"Units-{k}", "Units", 5, "B", size_basis=21) for k in range(5)]
    gaps = [it("Scouting Gap-A", "Scouting Gap", 1, "A", t_end=8), it("Scouting Gap-B", "Scouting Gap", 1, "B", t_end=8)]
    r = lay([it("Chat-1", "Chat", 5), *units, *gaps], mode)
    assert r.positions["Scouting Gap-B"][1] == approx(12.8 + 17.0 + 0.8)
    assert r.positions["Scouting Gap-A"][1] == approx(-(12.8 + 5.8 + 0.8))  # no units on side A: the floor
    # the pad of a crowded row counts in the spread: 6 buildings on side B push its units 1.05 further out
    padded = lay([it("Chat-1", "Chat", 5), *buildings(6, 5, "B"), *units, *gaps], mode)
    assert padded.positions["Scouting Gap-B"][1] == approx(12.8 + 17.0 + 1.05 + 0.8)


@pytest.mark.parametrize("mode", MODES)
def test_scouting_gaps_never_occupy_and_overlaps_are_warned(mode):
    base = [it("Chat-1", "Chat", 5), it("Chat-2", "Chat", 45)]
    gaps = [it("Scouting Gap-1", "Scouting Gap", 12, t_end=30), it("Scouting Gap-2", "Scouting Gap", 25, t_end=40)]
    r = lay([*base, *gaps], mode)
    assert r.rows == lay(base, mode).rows
    assert "Scouting Gap-1 and Scouting Gap-2 overlap (G5)" in r.warnings
    assert all(k in r.positions for k in ("Scouting Gap-1", "Scouting Gap-2"))  # both are placed


@pytest.mark.parametrize("mode", MODES)
def test_a_third_players_new_items_go_to_the_grid(mode):
    extra = [
        it("Chat-1", "Chat", 5),
        it("Missing Step-1", "Missing Step", 5, "C"),
        it("Scouting Gap-1", "Scouting Gap", 5, "C", t_end=8),
        it("Coaching-1", "Coaching", None, "C"),
    ]
    r = lay(extra, mode)
    assert [r.positions[k] for k in ("Missing Step-1", "Scouting Gap-1", "Coaching-1")] == [(18, 3), (21, 3), (24, 3)]
    assert sum("is neither side" in w for w in r.warnings) == 3


@pytest.mark.parametrize("mode", MODES)
def test_a_pre_game_ghost_goes_to_window_0(mode):
    r = lay([it("Chat-1", "Chat", 5), it("Missing Step-1", "Missing Step", -30)], mode)
    assert r.positions["Missing Step-1"] == approx((0, -8.0))


# --- Alcyone: Leo's measured rail offsets (spec §13.4) ----------------------------------------------------------

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"


@pytest.fixture(scope="module")
def alcyone_items():
    for needed in (ALCYONE, MS_SC / "TimeImageTracking.csv"):
        if not needed.exists():
            if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
                pytest.fail(f"missing input {needed} (SC2MS_REQUIRE_GOLDEN=1)")
            pytest.skip(f"missing input {needed}")
    from sc2mindshare.analysis.run import analyse
    from sc2mindshare.analysis.to_domain import to_graph
    from sc2mindshare.layout.items import items
    from sc2mindshare.reader.loader import load_replay

    with (MS_SC / "TimeImageTracking.csv").open(encoding="utf-8") as f:
        clock_map = {r["imageName"]: r["imageID"] for r in csv.DictReader(f)}
    with contextlib.redirect_stdout(io.StringIO()):
        graph = to_graph(analyse(load_replay(ALCYONE), MS_SC))
    return items(graph), clock_map


@pytest.mark.parametrize("mode", MODES)
def test_alcyone_rails_at_the_measured_offsets_and_nothing_else_moves(alcyone_items, mode):
    """Leo's measured maxima: lilTiGGer (side A) 6.0, blacksquall (side B) 9.0 -> -19.6 and +22.6."""
    its, clock_map = alcyone_items
    n = len(its)
    gaps = [
        LayoutItem("Scouting Gap-A", "Scouting Gap", 179, n, player="lilTiGGer", t_end=286),
        LayoutItem("Scouting Gap-B", "Scouting Gap", 179, n + 1, player="blacksquall", t_end=286),
    ]
    base = layout(its, Profile(timeline=mode), clock_map)
    r = layout(its + gaps, Profile(timeline=mode), clock_map)
    assert r.positions["Scouting Gap-A"][1] == pytest.approx(-19.6)
    assert r.positions["Scouting Gap-B"][1] == pytest.approx(22.6)
    assert {k: v for k, v in r.positions.items() if k in base.positions} == base.positions
    assert r.rows == base.rows and r.extra_nodes == base.extra_nodes
