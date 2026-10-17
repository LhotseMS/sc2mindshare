"""CR-041 (T3-1): replay inventory with s2protocol as the reference decoder.

Expected values are literals measured on the replays (stream3-plan.md §0, §3), never
computed by the code under test.
"""

import pytest
from decoding_support import CHECKOUT, load_tool

inv = load_tool("inventory")

ALCYONE_GAME_EVENTS = {
    "NNet.Game.SUserFinishedLoadingSyncEvent": 1,
    "NNet.Game.SUserOptionsEvent": 2,
    "NNet.Game.SCameraSaveEvent": 27,
    "NNet.Game.SCmdEvent": 1080,
    "NNet.Game.SSelectionDeltaEvent": 1452,
    "NNet.Game.SControlGroupUpdateEvent": 795,
    "NNet.Game.SCameraUpdateEvent": 3542,
    "NNet.Game.STriggerSoundLengthSyncEvent": 4,
    "NNet.Game.SDecrementGameTimeRemainingEvent": 1,
    "NNet.Game.SGameUserLeaveEvent": 1,
    "NNet.Game.SCommandManagerStateEvent": 2831,
    "NNet.Game.SCmdUpdateTargetPointEvent": 1490,
    "NNet.Game.SCmdUpdateTargetUnitEvent": 649,
    "NNet.Game.SSetSyncLoadingTimeEvent": 1,
    "NNet.Game.SSetSyncPlayingTimeEvent": 1,
}

ALCYONE_TRACKER_EVENTS = {
    "NNet.Replay.Tracker.SUnitBornEvent": 1153,
    "NNet.Replay.Tracker.SUnitDiedEvent": 863,
    "NNet.Replay.Tracker.SUnitTypeChangeEvent": 783,
    "NNet.Replay.Tracker.SPlayerStatsEvent": 283,
    "NNet.Replay.Tracker.SUnitInitEvent": 258,
    "NNet.Replay.Tracker.SUnitDoneEvent": 255,
    "NNet.Replay.Tracker.SUpgradeEvent": 65,
    "NNet.Replay.Tracker.SUnitPositionsEvent": 56,
    "NNet.Replay.Tracker.SPlayerSetupEvent": 2,
}


def test_header_and_protocol_choice(replays):
    assert inv.base_build(replays["alcyone"]) == 92440
    assert inv.base_build(replays["spores"]) == 81433
    assert inv.base_build(replays["spine"]) == 83830


def test_members_and_sizes(alcyone):
    sizes = {m.name: m.size for m in inv.members(alcyone)}
    assert sizes["replay.game.events"] == 142047
    assert sizes["replay.smartcam.events"] == 11463
    assert sizes["replay.server.battlelobby"] == 32121
    assert sizes["replay.sync.history"] == 0
    assert len(sizes) == 15


def test_s2protocol_game_event_counts(alcyone):
    assert dict(inv.s2p_counts(alcyone, "game")) == ALCYONE_GAME_EVENTS


def test_s2protocol_tracker_event_counts(alcyone):
    assert dict(inv.s2p_counts(alcyone, "tracker")) == ALCYONE_TRACKER_EVENTS


def test_sc2reader_parses_exactly_what_s2protocol_decodes(any_replay):
    """The CR-041 hypothesis: same event types, same count per type, on every replay."""
    assert inv.sc2reader_counts(any_replay).parsed == inv.s2p_counts(any_replay, "game")


def test_sc2reader_drops_six_types_on_alcyone(alcyone):
    assert inv.sc2reader_counts(alcyone).dropped == {
        "NNet.Game.SUserFinishedLoadingSyncEvent",
        "NNet.Game.SCameraSaveEvent",
        "NNet.Game.STriggerSoundLengthSyncEvent",
        "NNet.Game.SDecrementGameTimeRemainingEvent",
        "NNet.Game.SSetSyncLoadingTimeEvent",
        "NNet.Game.SSetSyncPlayingTimeEvent",
    }


def test_field_stats_flatten_nested_fields():
    events = [
        {"_event": "E", "_gameloop": 3, "m_a": 1, "m_b": {"x": 2, "y": 3}, "m_l": [4, 5]},
        {"_event": "E", "_gameloop": 4, "m_a": 1, "m_b": {"x": 7, "y": 3}, "m_l": []},
    ]
    stats = inv.field_stats(events)
    assert set(stats) == {("E", "m_a"), ("E", "m_b.x"), ("E", "m_b.y"), ("E", "m_l[]")}
    assert (stats[("E", "m_a")].count, stats[("E", "m_a")].distinct) == (2, 1)
    assert stats[("E", "m_b.x")].distinct == 2
    assert stats[("E", "m_l[]")].count == 2
    assert stats[("E", "m_a")].types == {"int"}


def test_fields_that_are_never_informative_on_alcyone(alcyone):
    stats = inv.field_stats(inv.s2p_events(alcyone, "game"))
    assert stats[("NNet.Game.SCmdEvent", "m_otherUnit")].top == [(None, 1080)]
    assert stats[("NNet.Game.SCmdEvent", "m_unitGroup")].top == [(None, 1080)]
    assert stats[("NNet.Game.SCommandManagerStateEvent", "m_state")].top == [(1, 2831)]
    assert stats[("NNet.Game.SCmdEvent", "m_data.TargetUnit.m_timer")].top == [(0, 207)]


def test_sc2reader_attribute_map():
    assert inv.sc2reader_attr("NNet.Game.SCmdEvent", "m_otherUnit") == "other_unit_id"
    assert inv.sc2reader_attr("NNet.Replay.Tracker.SPlayerStatsEvent", "m_stats.m_scoreValueFoodMade") == "food_made"
    # sc2reader 1.9.0 does not expose who created a unit
    assert inv.sc2reader_attr("NNet.Replay.Tracker.SUnitBornEvent", "m_creatorAbilityName") is None


def test_mindshare_use_is_a_static_attribute_search():
    sources = inv.mindshare_sources(CHECKOUT)
    assert sources, "no Mindshare sources found"
    assert inv.mindshare_uses("ability_name", sources)
    assert not inv.mindshare_uses("subgroup_index", sources)
    assert not inv.mindshare_uses("target_timer", sources)


def test_report_marks_dropped_and_unexposed_items(replays):
    report = inv.render_report(replays, CHECKOUT)
    assert "| NNet.Game.SCameraSaveEvent | 14 | 27 | 24 | 5 | dropped |" in report
    assert "| m_creatorAbilityName |" in report and "not exposed" in report
    names = [n for path in replays.values() for n in inv.player_names(path)]
    assert len(names) == 6
    for name in names:  # no player data in the report (names read from the replays, never written here)
        assert name not in report


def test_report_is_deterministic(replays):
    assert inv.render_report(replays, CHECKOUT) == inv.render_report(replays, CHECKOUT)


@pytest.mark.parametrize("name", ["alcyone", "spores", "spine"])
def test_gamemetadata_keys(replays, name):
    assert set(inv.gamemetadata(replays[name])) == {
        "Title",
        "GameVersion",
        "DataBuild",
        "DataVersion",
        "BaseBuild",
        "Duration",
        "Players",
    }
