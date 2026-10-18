"""The small side members and the user options (CR-050, T3-10).

Literal values from read-only probes on the raw archive members and on s2protocol's decode of
SUserOptionsEvent (the orchestrator's `.scratch/stream3/sidefiles_probe.py`, `sync_probe.py`,
`resumable_probe.py`), an oracle independent of sc2reader.
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.export import to_dict, to_json
from sc2mindshare.decoding.side_members import (
    PERSONAL_DATA_MEMBERS,
    SYNC_INTERVAL_LOOPS,
    FramingError,
    parse_resumable_events,
    parse_sync_events,
    side_members,
    user_options,
)

# name -> (member sizes, resume loop, first PlayerLeaveEvent loop, game loops, sync checksum count, first three checksums)
EXPECTED = {
    "alcyone": (
        {"resumable.events": 12, "load.info": 52, "sync.events": 1745, "sync.history": 0, "server.battlelobby": 32121},
        22368,
        22369,
        22369,
        349,
        (31831, 40199, 10016),
    ),
    "spores": (
        {"resumable.events": 12, "load.info": 52, "sync.events": 2535, "sync.history": 0, "server.battlelobby": 32089},
        32473,
        32474,
        32511,
        507,
        (50202, 53190, 59372),
    ),
    "spine": (
        {"resumable.events": 12, "load.info": 52, "sync.events": 1155, "sync.history": 0, "server.battlelobby": 31965},
        14764,
        14765,
        14805,
        231,
        (12054, 24940, 20343),
    ),
}
BASE_BUILD = {"alcyone": 92440, "spores": 81433, "spine": 83830}


@pytest.fixture(scope="module", params=sorted(EXPECTED))
def case(request, replays):
    name = request.param
    return name, load(replays[name]).replay


def test_member_sizes(case):
    name, replay = case
    assert dict(side_members(replay).member_bytes) == EXPECTED[name][0]


def test_load_info_is_all_zero_and_sync_history_is_empty(case):
    _name, replay = case
    members = side_members(replay)
    assert members.load_info_all_zero is True
    assert dict(members.member_bytes)["sync.history"] == 0
    assert members.warnings == ()


def test_resume_loop_is_the_loop_before_the_first_leave(case):
    """F3-016: resumable.events' first u32 (little-endian) is one loop before the first player leaves."""
    name, replay = case
    _sizes, resume, first_leave, _loops, _n, _first = EXPECTED[name]
    assert side_members(replay).resume_loop == resume
    leaves = [e.frame for e in replay.game_events if type(e).__name__ == "PlayerLeaveEvent"]
    assert min(leaves) == first_leave == resume + 1


def test_one_sync_checksum_per_64_loops(case):
    """F3-017: sync.events holds one 5-byte record per 64 game loops, each with a 16-bit value."""
    name, replay = case
    _sizes, _resume, _leave, loops, count, first = EXPECTED[name]
    checksums = side_members(replay).sync_checksums
    assert checksums is not None
    assert int(replay.frames) == loops
    assert len(checksums) == count == loops // SYNC_INTERVAL_LOOPS
    assert checksums[:3] == first
    assert all(0 <= c <= 0xFFFF for c in checksums)


def test_sync_record_framing():
    # 01 40, then a 24-bit little-endian field = (value << 1) | 1 (s2protocol-independent: raw bytes)
    assert parse_sync_events(bytes.fromhex("0140aff80001400f3a01")) == (31831, 40199)
    assert parse_sync_events(b"") == ()


@pytest.mark.parametrize(
    "data",
    [
        bytes.fromhex("0140aff8"),  # not a multiple of 5 bytes
        bytes.fromhex("0240aff800"),  # wrong prefix
        bytes.fromhex("0140aef800"),  # low bit clear
        bytes.fromhex("0140aff802"),  # value above 17 bits
    ],
)
def test_unknown_sync_framing_is_an_error_not_a_guess(data):
    with pytest.raises(FramingError):
        parse_sync_events(data)


def test_resumable_framing():
    assert parse_resumable_events(bytes.fromhex("605700000310ffffffff0000")) == 22368
    with pytest.raises(FramingError):
        parse_resumable_events(bytes.fromhex("6057000003"))  # not 12 bytes
    with pytest.raises(FramingError):
        parse_resumable_events(bytes.fromhex("605700000311ffffffff0000"))  # the constant tail differs


def test_user_options_match_s2protocol(case):
    """sc2reader's kept SUserOptionsEvent fields equal s2protocol's on all three replays (F3-018)."""
    name, replay = case
    rows = user_options(replay)
    assert [r.player_id for r in rows] == [1, 2]
    for row in rows:
        assert row.game_fully_downloaded is True
        assert row.development_cheats_enabled is False
        assert row.multiplayer_cheats_enabled is False
        assert row.sync_checksumming_enabled is False
        assert row.is_map_to_map_transition is False
        assert row.debug_pause_enabled is False
        assert row.base_build_num == BASE_BUILD[name]


def test_battlelobby_is_flagged_and_only_its_size_is_exported(case, replays):
    from decoding_support import load_tool

    name, _replay = case
    assert PERSONAL_DATA_MEMBERS == ("replay.server.battlelobby",)
    doc = to_dict(load(replays[name]))
    assert doc["side_members"]["member_bytes"]["server.battlelobby"] == EXPECTED[name][0]["server.battlelobby"]
    text = to_json(load(replays[name]))
    names = load_tool("inventory").player_names(replays[name])
    assert names and not any(n in text for n in names)
    assert "s2ma" not in text and "Cache" not in text


def test_export_has_the_side_members_and_user_options(alcyone):
    doc = to_dict(load(alcyone))
    assert doc["side_members"] == {
        "member_bytes": {
            "load.info": 52,
            "resumable.events": 12,
            "server.battlelobby": 32121,
            "sync.events": 1745,
            "sync.history": 0,
        },
        "load_info_all_zero": True,
        "resume_loop": 22368,
        "sync_checksum_count": 349,
        "warnings": [],
    }
    assert doc["user_options"][0] == {
        "player_id": 1,
        "game_fully_downloaded": True,
        "development_cheats_enabled": False,
        "multiplayer_cheats_enabled": False,
        "sync_checksumming_enabled": False,
        "is_map_to_map_transition": False,
        "debug_pause_enabled": False,
        "base_build_num": 92440,
    }
