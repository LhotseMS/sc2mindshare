"""Research completions without cosmetics, and research commands (CR-060, E5 part 1, no durations).

Completion counts match s2protocol's SUpgradeEvent names with the RewardDance*/Spray* entries removed.
Command ability names are sc2reader's (its datapack); s2protocol has only ability links, so the command
counts are pinned literals, not an independent oracle.
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.export import to_dict
from sc2mindshare.decoding.research import (
    ResearchEvent,
    is_research_ability,
    research_commands,
    research_completions,
)

# name -> (completions per player, commands per player)
EXPECTED = {
    "alcyone": ({1: 14, 2: 8}, {1: 15, 2: 10}),
    "spores": ({1: 10, 2: 22}, {1: 11, 2: 24}),
    "spine": ({1: 3, 2: 1}, {1: 5, 2: 4}),
}


def _per_player(rows):
    out: dict[int, int] = {}
    for row in rows:
        out[row.player_id] = out.get(row.player_id, 0) + 1
    return out


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_counts(replays, name):
    replay = load(replays[name]).replay
    completions, commands = EXPECTED[name]
    assert _per_player(research_completions(replay)) == completions
    assert _per_player(research_commands(replay)) == commands


def test_no_cosmetics_among_the_completions(any_replay):
    names = {r.name for r in research_completions(load(any_replay).replay)}
    assert names and not any(n.startswith(("RewardDance", "Spray")) for n in names)


def test_first_research_on_alcyone(alcyone):
    replay = load(alcyone).replay
    assert research_commands(replay)[0] == ResearchEvent(7712, 2, "ResearchWarpGate")
    assert research_completions(replay)[0] == ResearchEvent(9728, 2, "WarpGateResearch")


@pytest.mark.parametrize(
    ("ability", "expected"),
    [
        ("ResearchBurrow", True),
        ("EvolveMetabolicBoost", True),
        ("UpgradeGroundWeapons1", True),
        ("UpgradeToLair", False),
        ("BurrowDrone", False),
        (None, False),
    ],
)
def test_research_abilities(ability, expected):
    assert is_research_ability(ability) is expected


def test_export_has_the_research(alcyone):
    doc = to_dict(load(alcyone))["research"]
    assert len(doc["completions"]) == 22 and len(doc["commands"]) == 25
    assert doc["completions"][0] == {"frame": 9728, "player_id": 2, "name": "WarpGateResearch"}
