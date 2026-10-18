"""layout-spec.md §10: the guards G1-G11 give defined answers."""

import pytest
from sc2mindshare.layout.sweep import LayoutItem, layout


def p(i, name):
    return LayoutItem(f"Player-{i}", "Player", None, i, player=name)


def test_g1_duplicate_id_names_the_id_and_its_type():
    with pytest.raises(ValueError, match=r"duplicate node ID 'Harrasment-0' \(type Harrasment\)"):
        layout([LayoutItem("Harrasment-0", "Harrasment", 5, 0, "A"), LayoutItem("Harrasment-0", "Harrasment", 6, 1, "A")])


def test_g2_sides_without_player_nodes_and_too_many_players():
    r = layout([LayoutItem("Chat-1", "Chat", 5, 0, "X"), LayoutItem("Chat-2", "Chat", 6, 1, "Y")])
    assert r.positions["Chat-1"][1] < 0 < r.positions["Chat-2"][1] and r.warnings[0].startswith("0 Player node")
    with pytest.raises(ValueError, match="more than two"):
        layout([p(1, "a"), p(2, "b"), p(3, "c")])


def test_g3_a_third_player_goes_to_the_grid():
    r = layout([p(1, "A"), p(2, "B"), LayoutItem("Chat-1", "Chat", 5, 3, "observer")])
    assert r.positions["Chat-1"] == (18, 3) and "neither side" in r.warnings[0]


def test_g4_nothing_to_sweep():
    r = layout([p(1, "A"), p(2, "B")])
    assert r.rows == [] and r.extra_nodes == [] and r.warnings == ["no items to sweep (G4)"]


def test_g5_block_ending_before_it_starts():
    r = layout(
        [
            p(1, "A"),
            p(2, "B"),
            LayoutItem("Chat-1", "Chat", 5, 3, "A"),
            LayoutItem("Supply Block-1", "Supply Block", 30, 4, "A", t_end=5),
        ]
    )
    assert r.sizes["Supply Block-1"] == [2.5, 1] and any("G5" in w for w in r.warnings)


def test_g7_negative_times_go_to_window_0():
    r = layout([p(1, "A"), p(2, "B"), LayoutItem("Building-1", "Building", -71, 3, "A")])
    assert r.positions["Building-1"] == (0, -8.0)


def test_g8_huge_battle_warns():
    r = layout([p(1, "A"), p(2, "B"), LayoutItem("Battle-1", "Battle", 5, 3, "Common", size_basis=400)])
    assert any("G8" in w for w in r.warnings)


def test_g9_long_games_use_total_minutes():
    r = layout([p(1, "A"), p(2, "B"), LayoutItem("Chat-1", "Chat", 4000, 3, "A")], clock_map={"66-40.png": "e" * 24})
    assert [c.file_name for c in r.extra_nodes] == ["66-40.png", "66-40.png"]  # E(399) = 4000 s
