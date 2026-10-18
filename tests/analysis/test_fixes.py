"""Ledger fixes on the domain graph (analysis/fixes.py)."""

import pytest
from sc2mindshare.analysis.fixes import FIXES, pre_game_display, pre_game_note, signed_hhmmss, unique_harassment_ids
from sc2mindshare.domain.models import Graph, Link, Node
from sc2mindshare.domain.time import GameTime
from sc2mindshare.export.time_text import text_values

S = GameTime.from_seconds


def harass(nid, t):
    return Node("Harrasment", nid, "h", "", (), (("time", S(t)), ("player", "p"), ("end time", S(t)), ("deaths", "1")), S(t))


def chat(nid):
    return Node("Chat", nid, "c", "", (), (("time", S(60)), ("player", "p")), S(60))


def test_h1_numbers_harassment_game_wide_in_node_order():
    graph = Graph((harass("Harrasment-0", 1), chat("Chat-1"), harass("Harrasment-0", 2), harass("Harrasment-1", 3)), ())
    fixed = unique_harassment_ids(graph)
    assert [n.id for n in fixed.nodes] == ["Harrasment-1", "Chat-1", "Harrasment-2", "Harrasment-3"]
    assert [n.start.seconds for n in fixed.nodes] == [1, 60, 2, 3]  # nothing else moves


def test_h1_follows_links_to_unique_ids_and_refuses_ambiguous_ones():
    graph = Graph((harass("Harrasment-5", 1), chat("Chat-1")), (Link("Harrasment-5", "Chat-1", "a", "b", "", 0),))
    assert unique_harassment_ids(graph).links[0].node1 == "Harrasment-1"
    ambiguous = Graph((harass("Harrasment-0", 1), harass("Harrasment-0", 2)), (Link("Harrasment-0", "Chat-1", "a", "b", "", 0),))
    with pytest.raises(ValueError, match="repeated Harrasment IDs"):
        unique_harassment_ids(ambiguous)


def building(nid, t, description=""):
    return Node("Building", nid, "Main base", description, (), (("time", S(t)), ("player", "p"), ("type", "Hive")), S(t))


def test_p3d_pre_game_items_show_zero_and_keep_the_real_time_in_the_description():
    """P3d, amended by P3e (D3c): no extra property (Mindshare needs one key list per type); the real
    start goes into the description."""
    graph = Graph((building("Building-1", -71), building("Building-3", 30), chat("Chat-1")), ())
    assert dict(text_values(graph.nodes[0]))["time"] == "23:58:49"  # the legacy text wraps (B9)
    fixed = pre_game_display(graph)
    main = fixed.nodes[0]
    assert dict(main.values) == {"time": GameTime(0), "player": "p", "type": "Hive"}  # the kind's own fields only
    assert dict(text_values(main)) == {"time": "00:00:00", "player": "p", "type": "Hive"}
    assert main.description == "Started 71 s before the game (real start -00:01:11)."
    assert main.start == S(-71)  # the layout still places it by its real start (B9)
    assert fixed.nodes[1:] == graph.nodes[1:]  # in-game nodes are untouched
    assert pre_game_display(fixed) == fixed  # applying it twice changes nothing more


@pytest.mark.parametrize(("seconds", "text"), [(-71, "-00:01:11"), (-3725, "-01:02:05"), (-1, "-00:00:01"), (0, "00:00:00")])
def test_signed_hhmmss(seconds, text):
    assert signed_hhmmss(seconds) == text


def test_the_ledger_order():
    assert FIXES == (unique_harassment_ids, pre_game_display)


def test_the_pre_game_note_follows_an_existing_description():
    fixed = pre_game_display(Graph((building("Building-1", -3725, "built first"),), ())).nodes[0]
    assert fixed.description == "built firstX_LDX_LDStarted 3725 s before the game (real start -01:02:05)."
    assert pre_game_note(-71) == "Started 71 s before the game (real start -00:01:11)."


def test_the_time_is_reset_even_when_the_note_is_already_there():
    """Morgan's CR-014c N0: the 00:00:00 reset does not depend on the description check."""
    node = building("Building-1", -71, "Started 71 s before the game (real start -00:01:11).")
    fixed = pre_game_display(Graph((node,), ())).nodes[0]
    assert fixed.time("time") == GameTime(0) and fixed.start == S(-71)
    assert fixed.description == "Started 71 s before the game (real start -00:01:11)."  # not added twice
