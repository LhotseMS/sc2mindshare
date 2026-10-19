"""Ledger fixes on the domain graph (analysis/fixes.py)."""

import pytest

from sc2mindshare.analysis.fixes import FIXES, unique_harassment_ids
from sc2mindshare.domain.models import Graph, Link, Node


def harass(nid, t):
    return Node(
        "Harrasment", nid, "h", "", (), (("time", "00:01:00"), ("player", "p"), ("end time", "00:01:00"), ("deaths", "1")), t
    )


def chat(nid):
    return Node("Chat", nid, "c", "", (), (("time", "00:01:00"), ("player", "p")), 60)


def test_h1_numbers_harassment_game_wide_in_node_order():
    graph = Graph((harass("Harrasment-0", 1), chat("Chat-1"), harass("Harrasment-0", 2), harass("Harrasment-1", 3)), ())
    fixed = unique_harassment_ids(graph)
    assert [n.id for n in fixed.nodes] == ["Harrasment-1", "Chat-1", "Harrasment-2", "Harrasment-3"]
    assert [n.start_seconds for n in fixed.nodes] == [1, 60, 2, 3]  # nothing else moves


def test_h1_follows_links_to_unique_ids_and_refuses_ambiguous_ones():
    graph = Graph((harass("Harrasment-5", 1), chat("Chat-1")), (Link("Harrasment-5", "Chat-1", "a", "b", "", 0),))
    assert unique_harassment_ids(graph).links[0].node1 == "Harrasment-1"
    ambiguous = Graph((harass("Harrasment-0", 1), harass("Harrasment-0", 2)), (Link("Harrasment-0", "Chat-1", "a", "b", "", 0),))
    with pytest.raises(ValueError, match="repeated Harrasment IDs"):
        unique_harassment_ids(ambiguous)


def test_the_ledger_order():
    assert FIXES == (unique_harassment_ids,)
