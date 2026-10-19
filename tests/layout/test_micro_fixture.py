"""Leo's hand-computed micro fixture (layout-spec.md §9.3): the first layout golden, both modes."""

import pytest

from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutItem, layout

CLOCKS = {"0-10.png": "c" * 24, "0-50.png": "d" * 24}


def fixture_items():
    return [
        LayoutItem("Game-1", "Game", None, 0),
        LayoutItem("Player-1", "Player", None, 1, player="A"),
        LayoutItem("Player-2", "Player", None, 2, player="B"),
        LayoutItem("Building-1", "Building", 5, 3, player="A"),
        LayoutItem("Building-2", "Building", 8, 4, player="A"),
        LayoutItem("Units-1", "Units", 0, 5, player="A", size_basis=2),
        LayoutItem("Units-2", "Units", 0, 6, player="A", size_basis=5),
        LayoutItem("Battle-1", "Battle", 12, 7, player="Common", size_basis=0),
        LayoutItem("Battle-2", "Battle", 14, 8, player="Common", size_basis=50),
        LayoutItem("Stats-1", "Stats", 15, 9, player="B"),
        LayoutItem("Units-3", "Units", 40, 10, player="B", size_basis=2),
        LayoutItem("Chat-1", "Chat", 45, 11, player="A"),
        LayoutItem("Supply Block-1", "Supply Block", 3, 12, player="A", t_end=44),
        LayoutItem("Energy Excess-1", "Energy Excess", 30, 13, player="A"),
    ]


def approx(pos):
    return pytest.approx(pos, abs=1e-9)


def test_compressed():
    r = layout(fixture_items(), Profile(), CLOCKS)
    assert r.positions["Building-1"] == approx((0, -8.0))
    assert r.positions["Building-2"] == approx((0, -9.05))
    assert r.positions["Units-1"] == approx((0, -13.55)) and r.sizes["Units-1"] == 0.75
    assert r.positions["Units-2"] == approx((0, -15.3)) and r.sizes["Units-2"] == 1.0
    assert r.positions["Battle-1"] == approx((2.5, 3.5)) and r.sizes["Battle-1"] == 0.7
    assert r.positions["Battle-2"] == approx((2.5, 0)) and r.sizes["Battle-2"] == 2.5
    assert r.positions["Stats-1"] == approx((2.5, 5.76))
    assert r.positions["Units-3"] == approx((5, 13.55)) and r.sizes["Units-3"] == 0.75
    assert r.positions["Chat-1"] == approx((5, -3.84))
    assert r.positions["Supply Block-1"] == approx((2.5, -12.16)) and r.sizes["Supply Block-1"] == approx([7.5, 1])
    assert [(c.file_name, c.side, c.x, c.y) for c in r.extra_nodes] == [
        ("0-10.png", 1, 0, -5.76),
        ("0-10.png", 2, 0, 5.76),
        ("0-50.png", 1, 5, -5.76),
        ("0-50.png", 2, 5, 5.76),
    ]
    assert r.positions["Energy Excess-1"] == approx((18, 3))
    assert r.positions["Game-1"] == (-12, 0)
    assert r.positions["Player-1"] == (-6, -9) and r.positions["Player-2"] == (-6, 9)
    assert r.warnings == []


def test_linear():
    r = layout(fixture_items(), Profile(timeline="linear"), CLOCKS)
    assert r.positions["Units-3"] == approx((10, 13.55))
    assert r.positions["Chat-1"] == approx((10, -3.84))
    assert [(c.file_name, c.x) for c in r.extra_nodes][2:] == [("0-50.png", 10), ("0-50.png", 10)]
    assert r.positions["Supply Block-1"] == approx((5, -12.16)) and r.sizes["Supply Block-1"] == approx([12.5, 1])
    # everything else is where it is in compressed mode (windows 0 and 1 are rows 0 and 1 in both)
    assert r.positions["Battle-1"] == approx((2.5, 3.5)) and r.positions["Building-2"] == approx((0, -9.05))
