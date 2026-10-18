"""CR-048 (T3-8): command flag bits and camera zoom.

Literals measured on s2protocol's raw events (independent of sc2reader):
- F3-013: bit 3 (smart) is set exactly on the commands without an ability (395/395, 541/541, 234/234; never
  mixed): a smart (right-click) command;
- F3-014: bit 16 (minimap) commands target a point more than 20 map units from the player's camera in
  66/76, 121/133, 66/67 cases, while other point commands are within 20 units in 556/570, 568/573, 267/268:
  the target was clicked on the minimap;
- bits 5 and 10 occur together, only on data commands (0, 5, 3);
- camera zoom (distance or pitch present) only from one player in one replay (Alcyone player 1, 34 events).
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.command_flags import FlagSummary, command_flag_summary, flag_names, zoom_events

EXPECTED = {
    "alcyone": FlagSummary(
        commands=1080,
        queued=93,
        smart=395,
        minimap=76,
        repeat=54,
        data=0,
        smart_without_ability=395,
        smart_with_ability=0,
        minimap_far=66,
        minimap_near=10,
        other_far=14,
        other_near=556,
    ),
    "spores": FlagSummary(
        commands=1363,
        queued=138,
        smart=541,
        minimap=133,
        repeat=4,
        data=5,
        smart_without_ability=541,
        smart_with_ability=0,
        minimap_far=121,
        minimap_near=12,
        other_far=5,
        other_near=568,
    ),
    "spine": FlagSummary(
        commands=601,
        queued=27,
        smart=234,
        minimap=67,
        repeat=0,
        data=3,
        smart_without_ability=234,
        smart_with_ability=0,
        minimap_far=66,
        minimap_near=1,
        other_far=1,
        other_near=267,
    ),
}
ZOOM = {"alcyone": {1: 34}, "spores": {}, "spine": {}}


def test_flag_names_use_upstreams_bit_names():
    assert flag_names(0b1_0000_0001_0000_1010) == ("queued", "smart_click", "user", "minimap")
    assert flag_names(1 << 26) == ("attack_once",)
    assert flag_names(1 << 30) == ("bit30",)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_flag_summary_totals(replays, name):
    assert sum(command_flag_summary(load(replays[name]).replay).values(), FlagSummary()) == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_smart_means_no_ability(replays, name):
    total = sum(command_flag_summary(load(replays[name]).replay).values(), FlagSummary())
    assert total.smart_with_ability == 0 and total.smart_without_ability == total.smart


@pytest.mark.parametrize("name", sorted(ZOOM))
def test_zoom_events_per_player(replays, name):
    assert zoom_events(load(replays[name]).replay) == ZOOM[name]


def _event(cls, frame, player, **attrs):
    """A sc2reader event of the given class with only the attributes the summary reads (no replay needed)."""
    event = object.__new__(cls)
    event.__dict__.update(frame=frame, player=player, **attrs)
    return event


def test_a_zoom_only_camera_update_does_not_move_the_camera():
    """CR-048 review (Rex's G6): sc2reader reads a camera update without a target as (0, 0), which must not
    replace the camera point. On Alcyone the 34 zoom updates never sit between a camera move and a point
    command far from the origin, so this is pinned on a constructed sequence."""
    from types import SimpleNamespace

    from sc2reader.events.game import CameraEvent, TargetPointCommandEvent

    player = SimpleNamespace(pid=1)
    point = {"has_ability": True, "flags": 0}
    events = [
        _event(CameraEvent, 10, player, location=(100.0, 100.0), x=100.0, y=100.0, distance=None, pitch=None),
        _event(CameraEvent, 20, player, location=(0.0, 0.0), x=0.0, y=0.0, distance=7682, pitch=None),
        _event(TargetPointCommandEvent, 30, player, x=105.0, y=100.0, **point),
        _event(TargetPointCommandEvent, 40, player, x=150.0, y=100.0, **point),
    ]
    summary = command_flag_summary(SimpleNamespace(game_events=events))[1]
    assert (summary.commands, summary.other_near, summary.other_far) == (2, 1, 1)
    assert zoom_events(SimpleNamespace(game_events=events)) == {1: 1}
