"""The decoding export: one JSON document per replay, additive to stream 1's output (G1 for stream 3)."""

import json
from pathlib import Path

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.export import to_dict, to_json

GOLDEN = Path(__file__).resolve().parent / "golden"


def test_export_has_the_metadata_with_neutral_and_named_units(alcyone):
    doc = to_dict(load(alcyone))
    assert doc["format"] == "sc2mindshare.decoding/1"
    assert doc["replay"] == {"base_build": 92440, "game_loops": 22369}
    meta = doc["gamemetadata"]
    assert meta["duration_game_seconds"] == 1398
    assert meta["players"][0] == {
        "player_id": 1,
        "mmr": 3098,
        "apm_client": 286.0,
        "result": "Loss",
        "selected_race": "Zerg",
        "assigned_race": "Zerg",
        "extra": {},
    }
    assert doc["mmr"] == [
        {"player_id": 1, "mmr": 3098, "gamemetadata": 3098, "init_data": 3098, "agree": True},
        {"player_id": 2, "mmr": 3115, "gamemetadata": 3115, "init_data": 3115, "agree": True},
    ]


def test_export_is_deterministic_json(alcyone):
    text = to_json(load(alcyone))
    assert text == to_json(load(alcyone))
    assert json.loads(text) == to_dict(load(alcyone))


@pytest.mark.parametrize("name", ["alcyone", "spores", "spine"])
def test_export_matches_its_golden(replays, name):
    """The decoding output's own golden (Ada's G1 for additive streams); regenerate only on purpose."""
    expected = (GOLDEN / f"{name}.decoded.json").read_text(encoding="utf-8")
    assert to_json(load(replays[name])) == expected


@pytest.mark.parametrize("name", ["alcyone", "spores", "spine"])
def test_golden_holds_no_player_names(replays, name):
    from decoding_support import load_tool

    names = load_tool("inventory").player_names(replays[name])
    text = (GOLDEN / f"{name}.decoded.json").read_text(encoding="utf-8")
    assert names and not any(n in text for n in names)
