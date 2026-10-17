"""CR-043 (T3-3): replay.gamemetadata.json (MMR, client APM, result, races, data version).

Literal expected values measured on the three replays (stream3-plan.md §0); never computed
from the code under test.
"""

from types import SimpleNamespace

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.metadata import GameMetadata, PlayerMetadata, mmr_by_player, mmr_consistency

EXPECTED = {
    "alcyone": {
        "title": "Alcyone LE",
        "game_version": "5.0.13.92440",
        "data_build": 92440,
        "base_build": 92440,
        "data_version": "79F6D78E27ED069D2D84FB14288B88B9",
        "duration_game_seconds": 1398,
        "players": (
            PlayerMetadata(1, 3098, 286.0, "Loss", "Zerg", "Zerg"),
            PlayerMetadata(2, 3115, 142.0, "Win", "Prot", "Prot"),
        ),
    },
    "spores": {
        "title": "Golden Wall LE",
        "game_version": "5.0.2.81433",
        "data_build": 81433,
        "base_build": 81433,
        "data_version": "5FD8D4B6B52723B44862DF29F232CF31",
        "duration_game_seconds": 2032,
        "players": (
            PlayerMetadata(1, 4337, 144.0, "Loss", "Prot", "Prot"),
            PlayerMetadata(2, 4284, 195.0, "Win", "Zerg", "Zerg"),
        ),
    },
    "spine": {
        "title": "Jagannatha LE",
        "game_version": "5.0.6.83830",
        "data_build": 83830,
        "base_build": 83830,
        "data_version": "B4745D6A4F982A3143C183D8ACB6C3E3",
        "duration_game_seconds": 925,
        "players": (
            PlayerMetadata(1, 3884, 148.0, "Win", "Zerg", "Zerg"),
            PlayerMetadata(2, 3822, 142.0, "Loss", "Prot", "Prot"),
        ),
    },
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_metadata_literals(replays, name):
    meta = GameMetadata.from_replay(load(replays[name]).replay)
    for key, value in EXPECTED[name].items():
        assert getattr(meta, key) == value, key
    assert meta.warnings == ()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_duration_is_in_game_seconds_loops_over_16_rounded(replays, name):
    """Duration = loops / 16 rounded to the nearest second (spores: 32511 / 16 = 2031.94 -> 2032)."""
    decoded = load(replays[name])
    assert decoded.metadata.duration_game_seconds == int(decoded.replay.frames / 16 + 0.5)
    assert decoded.metadata.duration_game_seconds != int(decoded.replay.frames / 22.4 + 0.5)


def test_load_attaches_the_metadata(alcyone):
    assert load(alcyone).metadata.players[0].mmr == 3098


def _replay_without(member):
    class Archive:
        def read_file(self, name):
            if name == "(listfile)":
                return b"replay.details\n"
            return None

    return SimpleNamespace(archive=Archive(), players=[])


def test_missing_member_gives_empty_metadata_and_a_warning():
    meta = GameMetadata.from_replay(_replay_without("replay.gamemetadata.json"))
    assert meta.players == ()
    assert meta.title is None and meta.duration_game_seconds is None
    assert meta.warnings == ("replay.gamemetadata.json not in archive",)


def test_unknown_keys_are_kept_not_dropped():
    meta = GameMetadata.from_json(
        b'{"Title": "M", "Duration": 10, "NewKey": 1, "Players": [{"PlayerID": 1, "MMR": 5, "Extra": true}]}'
    )
    assert meta.extra == (("NewKey", 1),)
    assert meta.players[0].mmr == 5 and meta.players[0].apm_client is None
    assert meta.players[0].extra == (("Extra", True),)


def test_malformed_json_is_a_warning_not_an_exception():
    meta = GameMetadata.from_json(b"{not json")
    assert meta.players == () and meta.warnings[0].startswith("replay.gamemetadata.json is not valid JSON")


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_mmr_sources_agree_matched_by_player_id(replays, name):
    """TD-28: initData scaled_rating equals gamemetadata MMR for every player (F3-008)."""
    decoded = load(replays[name])
    rows = mmr_consistency(decoded.replay, decoded.metadata)
    assert [r.player_id for r in rows] == [1, 2]
    assert all(r.agree for r in rows)


def test_gamemetadata_wins_and_initdata_is_the_fallback():
    meta = GameMetadata.from_json(b'{"Players": [{"PlayerID": 1, "MMR": 3000}, {"PlayerID": 2}]}')
    replay = SimpleNamespace(
        players=[
            SimpleNamespace(pid=1, init_data={"scaled_rating": 2900}),
            SimpleNamespace(pid=2, init_data={"scaled_rating": 3100}),
            SimpleNamespace(pid=3, init_data={}),
        ]
    )
    assert mmr_by_player(replay, meta) == {1: 3000, 2: 3100, 3: None}
