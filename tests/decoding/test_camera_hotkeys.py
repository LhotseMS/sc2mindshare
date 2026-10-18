"""CR-044 (T3-4): camera hotkeys. sc2reader parses SCameraSaveEvent (id 14) and drops it.

Hypothesis: `which` is the hotkey slot and the target is the saved camera point; a later
camera update of the same player landing exactly on a saved point is a recall of that slot.
Literal values measured on the three replays.
"""

from collections import Counter
from pathlib import Path

import pytest
import sc2reader
from sc2mindshare.decoding import load
from sc2mindshare.decoding.camera_hotkeys import CameraSaveEvent, camera_recalls


def saves_of(decoded):
    return [e for e in decoded.replay.game_events if isinstance(e, CameraSaveEvent)]


def test_alcyone_has_27_typed_saves(alcyone):
    saves = saves_of(load(alcyone))
    assert len(saves) == 27
    first = min(saves, key=lambda e: e.frame)
    assert (first.slot, first.saved_x, first.saved_y) == (3, 36736 / 256, 35010 / 256)
    assert Counter(e.slot for e in saves) == {3: 7, 2: 6, 1: 6, 0: 4, 4: 4}
    assert Counter(e.player.pid for e in saves) == {1: 20, 2: 7}


@pytest.mark.parametrize(("name", "count"), [("alcyone", 27), ("spores", 24), ("spine", 5)])
def test_save_counts_match_the_inventory(replays, name, count):
    assert len(saves_of(load(replays[name]))) == count


def test_camera_save_event_is_a_plain_game_event(alcyone):
    """TD-12: no CameraEvent subclass and no location/ability/unit, so no existing filter picks it up."""
    event = saves_of(load(alcyone))[0]
    assert isinstance(event, sc2reader.events.game.GameEvent)
    assert not isinstance(event, sc2reader.events.game.CameraEvent)
    for attr in ("location", "ability", "unit", "x", "y"):
        assert not hasattr(event, attr), attr


def test_other_game_events_are_unchanged(alcyone):
    """Keeping event 14 adds only the 27 saves; every other event class count stays as sc2reader 1.9.0 gives it."""
    plain = Counter(type(e).__name__ for e in sc2reader.load_replay(alcyone, load_level=4, load_map=False).game_events)
    ours = Counter(type(e).__name__ for e in load(alcyone).replay.game_events)
    assert ours - plain == Counter({"CameraSaveEvent": 27})
    assert plain - ours == Counter()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # measured independently on s2protocol's raw events (exact target match, same user)
        ("alcyone", {1: 253, 2: 22}),
        ("spores", {1: 21, 2: 155}),
        ("spine", {1: 121}),
    ],
)
def test_exact_recalls_per_player(replays, name, expected):
    """Recall = a later camera update of the same player exactly on a saved point (distance 0).

    Every recall on the three replays matches exactly one slot.
    """
    recalls = camera_recalls(load(replays[name]).replay)
    assert Counter(r.player_id for r in recalls) == expected


def test_recalls_point_at_the_latest_save_of_their_slot(alcyone):
    replay = load(alcyone).replay
    saves = sorted(saves_of(load(alcyone)), key=lambda e: e.frame)
    for recall in camera_recalls(replay):
        earlier = [s for s in saves if s.player.pid == recall.player_id and s.slot == recall.slot and s.frame <= recall.frame]
        assert earlier, recall
        assert (earlier[-1].saved_x, earlier[-1].saved_y) == (recall.x, recall.y)


CHECKOUT_ROOT = Path(__file__).resolve().parents[2]


# Rex's CR-044 review (P2): readers older than GameEventsReader_24247 have no event id 14, and the
# registration applies to every replay. Wings of Liberty replays from the upstream corpus must load.
CORPUS = CHECKOUT_ROOT / "test_replays"
OLD_READER_REPLAYS = ["1.2.2.17811/13.SC2Replay", "1.2.2.17811/1.SC2Replay"]


@pytest.mark.parametrize("relative", OLD_READER_REPLAYS)
def test_replays_whose_reader_has_no_camera_save_event_still_load(relative):
    path = CORPUS / relative
    if not path.exists():
        pytest.skip(f"corpus replay not in this checkout: {relative}")
    decoded = load(str(path))
    assert decoded.replay.game_events
    assert saves_of(decoded) == []
