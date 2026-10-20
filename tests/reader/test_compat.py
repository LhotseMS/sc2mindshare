"""CR-010: the fork's core behaviour as functions over upstream objects (reader/compat.py)."""

from types import SimpleNamespace

import pytest

from sc2mindshare.reader import compat
from sc2mindshare.reader.compat import ControlGroupKind


def ev(frame, **kw):
    return SimpleNamespace(frame=frame, **kw)


def test_time_bases():
    assert compat.game_second(ev(2733)) == pytest.approx(122.0089, abs=1e-4)
    assert compat.tracker_second(ev(2733)) == 122
    assert compat.game_time(ev(2733)) == "02.02"
    assert compat.tracker_time(ev(2733)) == "02:02"
    assert compat.game_time(ev(int(3725 * 22.4) + 1)) == "01.02.05"  # past one hour: HH.MM.SS


@pytest.mark.parametrize(
    ("raw", "split", "expected"),
    [
        ("Zergling", False, "ling"),  # python bug 2, kept on purpose
        ("Zealot [1A2B3C4D] ", False, "Zealot"),
        ("ZerglingMovementSpeed", True, "ling Movement Speed"),
        ("Attack", False, "A move"),
        ("SiegeTankSieged", True, "Sieged Tank"),
        ("Player 1 - lilTiGGer (Zerg)", False, "lilTiGGer"),
    ],
)
def test_clean_name_is_the_forks(raw, split, expected):
    assert compat.clean_name(raw, split) == expected


def test_player_name():
    assert compat.player_name(SimpleNamespace(pid=16)) == "Global"
    assert compat.player_name(SimpleNamespace(pid=1, player=SimpleNamespace(name="", play_race="Zerg"))) == "Zerg"
    assert compat.player_name(SimpleNamespace(pid=1, player=SimpleNamespace(name="a", play_race="Zerg"))) == "a"
    assert compat.player_name(SimpleNamespace(pid=1, player=None)) == "no name"


@pytest.mark.parametrize(
    ("update_type", "kind"),
    [
        (0, ControlGroupKind.SET),
        (1, ControlGroupKind.ADD),
        (2, ControlGroupKind.GET),
        (3, ControlGroupKind.UNKNOWN_3),
        (4, ControlGroupKind.STEAL),
        (5, ControlGroupKind.WEIRD),
        (6, ControlGroupKind.OTHER),
    ],
)
def test_control_group_kind_follows_the_raw_update_type(update_type, kind):
    assert compat.control_group_kind(SimpleNamespace(update_type=update_type)) is kind
