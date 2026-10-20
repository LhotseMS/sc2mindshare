"""CR-068 (P10c): Leo's layout cases for a structure death that now counts in battles (his notes on CR-068),
both modes. The layout itself does not change; these pin what a counted death can and cannot move."""

import pytest

from sc2mindshare.domain.models import Node
from sc2mindshare.domain.time import GameTime
from sc2mindshare.layout.items import item
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutItem, layout

MODES = ("compressed", "linear")


def approx(pos):
    return pytest.approx(pos, abs=1e-9)


def anchors():
    return [
        LayoutItem("Game-1", "Game", None, 0),
        LayoutItem("Player-1", "Player", None, 1, player="A"),
        LayoutItem("Player-2", "Player", None, 2, player="B"),
    ]


def battle(node_id, t, order, supply_dead):
    return LayoutItem(node_id, "Battle", t, order, player="Common", size_basis=supply_dead)


def battle_node(dead, p2_dead, description):
    values = (
        ("time", GameTime.from_seconds(468)),
        ("player", "Common"),
        ("dead", str(dead)),
        ("p1 dead", "6"),
        ("p2 dead", str(p2_dead)),
        ("supply dead", "34.5"),
        ("end time", GameTime.from_seconds(477)),
    )
    return Node("Battle", "Battle-12", "a battle", description, (), values, GameTime.from_seconds(456))


@pytest.mark.parametrize("mode", MODES)
def test_a_a_death_inside_a_battle_moves_nothing(mode):
    """(a) The battle's dead, its owner's dead and its text change; its start and supply dead do not, so its
    layout item, and so every position and size, is the same."""
    before = battle_node(22, 16, "blacksquall lost 16 units, 24 supply, 1375 min 275 gas.")
    after = battle_node(23, 17, "blacksquall lost 17 units, 24 supply, 1475 min 275 gas.")
    assert item(before, 3) == item(after, 3)
    others = [*anchors(), LayoutItem("Units-1", "Units", 470, 4, player="A", size_basis=2)]
    r1 = layout([*others, item(before, 3)], Profile(timeline=mode), {})
    r2 = layout([*others, item(after, 3)], Profile(timeline=mode), {})
    assert (r1.positions, r1.sizes) == (r2.positions, r2.sizes)


def b_items(with_new):
    items = [
        *anchors(),
        battle("Battle-1", 12, 3, 5),  # window 1, radius 1.2
        battle("Battle-2", 45, 4, 5),  # window 4
        LayoutItem("Units-1", "Units", 75, 5, player="A", size_basis=2),  # window 7
    ]
    return items + [battle("Battle-new", 25, 6, 0)] if with_new else items  # window 2, empty before


def test_b_a_lone_death_in_an_empty_window_compressed_moves_every_later_row():
    before = layout(b_items(False), Profile(), {})
    after = layout(b_items(True), Profile(), {})
    assert after.positions["Battle-new"] == approx((2.5, 0)) and after.sizes["Battle-new"] == 0.7
    assert after.positions["Battle-1"] == before.positions["Battle-1"] == approx((0, 0))
    for later in ("Battle-2", "Units-1"):
        assert after.positions[later] == approx((before.positions[later][0] + 2.5, before.positions[later][1]))


def test_b_a_lone_death_in_an_empty_window_linear_adds_only_its_row():
    before = layout(b_items(False), Profile(timeline="linear"), {})
    after = layout(b_items(True), Profile(timeline="linear"), {})
    assert after.positions["Battle-new"] == approx((5.0, 0))
    assert {k: v for k, v in after.positions.items() if k != "Battle-new"} == before.positions


def c_items(with_new):
    items = [
        *anchors(),
        battle("Battle-1", 5, 3, 5),  # window 0, radius 1.2
        battle("Battle-2", 25, 4, 50),  # window 2, radius 2.5 (>= 1.6: it shifts its smaller neighbour)
    ]
    return items + [battle("Battle-new", 15, 5, 0)] if with_new else items  # window 1, radius 0.7


def test_c_compressed_the_new_battle_takes_the_shift_and_the_old_neighbour_returns_to_0():
    before = layout(c_items(False), Profile(), {})
    after = layout(c_items(True), Profile(), {})
    assert before.positions["Battle-1"] == approx((0, 9.75**0.5))  # rows 0 and 1: 2.5 apart, under 1.2 + 2.5
    assert after.positions["Battle-1"] == approx((0, 0))
    assert after.positions["Battle-new"] == approx((2.5, 6**0.5))  # sqrt((0.7 + 2.5 + 0.3)^2 - 2.5^2)
    assert after.positions["Battle-2"] == approx((5.0, 0))


def test_c_linear_the_new_battle_takes_the_shift_its_neighbour_never_had():
    before = layout(c_items(False), Profile(timeline="linear"), {})
    after = layout(c_items(True), Profile(timeline="linear"), {})
    assert before.positions["Battle-1"] == approx((0, 0))  # windows 0 and 2: 5.0 apart, no shift
    assert after.positions["Battle-1"] == approx((0, 0))
    assert after.positions["Battle-new"] == approx((2.5, 6**0.5))
    assert after.positions["Battle-2"] == before.positions["Battle-2"] == approx((5.0, 0))
