"""layout-spec.md §9.2: one small fixture per lane rule (both modes where the rule differs)."""

import math

import pytest

from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutItem, layout, win


def players():
    return [LayoutItem("Player-1", "Player", None, 0, player="A"), LayoutItem("Player-2", "Player", None, 1, player="B")]


def lay(extra, mode="compressed", clocks=None):
    items = players() + [LayoutItem(i.id, i.type, i.t, n + 2, i.player, i.t_end, i.size_basis) for n, i in enumerate(extra)]
    return layout(items, Profile(timeline=mode), clocks)


def it(id_, type_, t, player="A", **kw):
    return LayoutItem(id_, type_, t, 0, player=player, **kw)


@pytest.mark.parametrize(("t", "w"), [(-71, 0), (0, 0), (10, 0), (11, 1), (20, 1), (21, 2), (3600, 359), (10.9, 0)])
def test_1_win(t, w):
    assert win(t) == w  # 10.9 is floored first (G11)


def test_2_rows_compressed_linear_and_empty_windows():
    extra = [it("Chat-1", "Chat", 5), it("Chat-2", "Chat", 45), it("Supply Block-1", "Supply Block", 25, t_end=26)]
    c = lay(extra)
    assert c.positions["Chat-2"][0] == 2.5  # windows 0 and 4 are rows 0 and 1
    assert c.positions["Supply Block-1"][0] == 2.5  # empty window 2 maps to the next occupied row
    assert len({r for r, _, _ in c.rows}) == len(c.rows)  # no two occupied windows share a row (B2)
    assert lay(extra, "linear").positions["Chat-2"][0] == 10


def test_3_battles():
    small_then_big = [
        it("Battle-1", "Battle", 12, "Common", size_basis=0),
        it("Battle-2", "Battle", 14, "Common", size_basis=50),
    ]
    r = lay(small_then_big)
    assert r.positions["Battle-1"][1] == pytest.approx(0.7 + 2.5 + 0.3)  # same window: r1 + r2 + 0.3
    no_shift = lay([it("Battle-1", "Battle", 12, "Common", size_basis=50), it("Battle-2", "Battle", 14, "Common", size_basis=0)])
    assert no_shift.positions["Battle-2"][1] == 0 and no_shift.positions["Battle-1"][1] == 0  # r_cur < 1.6
    adjacent = lay(
        [it("Battle-1", "Battle", 12, "Common", size_basis=30), it("Battle-2", "Battle", 22, "Common", size_basis=30)]
    )
    assert adjacent.positions["Battle-1"][1] == pytest.approx(math.sqrt((1.6 + 1.6 + 0.3) ** 2 - 2.5**2))
    over = lay([it("Battle-1", "Battle", 12, "Common", size_basis=200), it("Battle-2", "Battle", 14, "Common", size_basis=300)])
    # r 4 and 5: s = 9.3, s + r_small = 13.3 > 5.76: the small one ends at 5.76 - 4, the other moves down
    assert over.positions["Battle-1"][1] == pytest.approx(5.76 - 4)
    assert over.positions["Battle-2"][1] == pytest.approx(-(9.3 + 4 - 5.76))


def test_3_battle_collision_depends_on_the_mode():
    """Leo's CR-017 check: the collision distance is measured along x, so an empty window between two
    battles changes it. Windows 0 and 2 (window 1 empty): radii 1.2 (supply lost 10) and 2.5 (50), so
    r1 + r2 = 3.7. Compressed: rows 0 and 1, d = 2.5 < 3.7, the smaller (first) battle moves to
    sqrt((3.7 + 0.3)^2 - 2.5^2) = 3.1225. Linear: d = 5.0 >= 3.7, no shift."""
    pair = [it("Battle-1", "Battle", 5, "Common", size_basis=10), it("Battle-2", "Battle", 25, "Common", size_basis=50)]
    c, lin = lay(pair), lay(pair, "linear")
    assert c.positions["Battle-1"] == pytest.approx((0, math.sqrt(4.0**2 - 2.5**2))) and c.positions["Battle-2"] == (2.5, 0)
    assert math.sqrt(4.0**2 - 2.5**2) == pytest.approx(3.1225, abs=5e-5)
    assert lin.positions["Battle-1"] == (0, 0) and lin.positions["Battle-2"] == (5.0, 0)


def test_4_bau_stack():
    r = lay([it(f"Building-{k}", "Building", 1 + k) for k in range(3)] + [it("Upgrade-1", "Upgrade", 2, "B")])
    assert [r.positions[f"Building-{k}"][1] for k in range(3)] == pytest.approx([-8.0, -9.05, -10.1])
    assert r.positions["Upgrade-1"][1] == 8.0


def test_5_units_packing_pad_lag_and_end_flush():
    six = [it(f"Building-{k}", "Building", 1) for k in range(6)]
    r = lay([*six, it("Units-1", "Units", 1, size_basis=2), it("Units-2", "Units", 1, size_basis=12)])
    assert r.positions["Units-1"][1] == pytest.approx(-(12.8 + 0.75 + 1.05))  # pad 1.05 with 6 buildings
    assert r.positions["Units-2"][1] == pytest.approx(-(12.8 + 0.75 + 0.75 + 1.4 + 1.05))  # tangent
    lag = lay([it("Chat-1", "Chat", 5), it("Units-1", "Units", 15, size_basis=2), it("Chat-2", "Chat", 75)])
    # windows 1, 2, 3 empty: no flush; window 4 is the 4th unoccupied window after 0: lag flush, its own row
    assert lag.positions["Units-1"][0] == 2.5 and lag.positions["Chat-2"][0] == 5.0
    end = lay([it("Chat-1", "Chat", 5), it("Units-1", "Units", 15, size_basis=2)])
    assert end.positions["Units-1"] == pytest.approx((2.5, -13.55))
    assert any("left in the buffer" in w for w in end.warnings)


def test_6_clocks():
    clocks = {"0-10.png": "a" * 24, "61-30.png": "b" * 24}
    r = lay([it("Chat-1", "Chat", 5), it("Stats-1", "Stats", 15), it("Chat-2", "Chat", 3685)], clocks=clocks)
    names = [c.file_name for c in r.extra_nodes]
    assert names == ["0-10.png", "0-10.png", "61-30.png", "61-30.png"]  # none in the Stats window; total minutes (B7)
    assert r.clock_names == ["0-10.png", "61-30.png"]  # CR-069: the clocks the sweep wants, one per window
    missing = lay([it("Chat-1", "Chat", 5)], clocks={})
    # CR-069: one warning per missing clock, pointing to the command that uploads it
    assert missing.extra_nodes == [] and missing.warnings == ["no clock image for 0-10.png: run sc2mindshare upload-clocks (G6)"]
    assert missing.clock_names == ["0-10.png"]  # wanted, map or not
    assert lay([it("Chat-1", "Chat", 5)]).clock_names == ["0-10.png"]


# the block starts in empty window 1: compressed, that is the next occupied row (window 4)
@pytest.mark.parametrize(("mode", "centre", "width"), [("compressed", 2.5, 2.5), ("linear", 6.25, 10.0)])
def test_7_supply_blocks(mode, centre, width):
    r = lay([it("Chat-1", "Chat", 5), it("Chat-2", "Chat", 45), it("Supply Block-1", "Supply Block", 15, t_end=44)], mode)
    assert r.positions["Supply Block-1"] == pytest.approx((centre, -12.16)) and r.sizes["Supply Block-1"] == pytest.approx(
        [width, 1]
    )


def test_7_two_concurrent_blocks_are_both_placed():
    r = lay(
        [
            it("Chat-1", "Chat", 5),
            it("Supply Block-1", "Supply Block", 1, t_end=8),
            it("Supply Block-2", "Supply Block", 3, t_end=9),
        ]
    )
    assert "Supply Block-1" in r.positions and "Supply Block-2" in r.positions
    assert any("overlap" in w for w in r.warnings)


def test_8_grid():
    # CR-073: every type the export writes has a lane, so the grid example is a type with none, and it is reported
    r = lay([it(f"Mystery-{k}", "Mystery", 5) for k in range(5)])
    assert [r.positions[f"Mystery-{k}"] for k in range(5)] == [(18, 3), (21, 3), (24, 3), (27, 3), (18, 6)]
    assert r.warnings == [f"Mystery-{k}: type 'Mystery' has no lane: placed on the grid" for k in range(5)] + [
        "no items to sweep (G4)"
    ]
