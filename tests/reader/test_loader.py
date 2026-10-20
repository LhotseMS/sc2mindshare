"""CR-010: the loader, MindshareReplay and the two stream 3 hooks (TD-2).

The hook test follows Morgan's specification (stream3-plan.md, TD-2): a sentinel reader
registered through ``register_readers(replay)`` must be the reader that produced
``replay.game_events``. Coded by Rex so that Morgan stays T10's independent reviewer.
"""

import os
import pathlib

import pytest

from sc2mindshare.reader import extensions, loader
from sc2mindshare.reader.plugins.mindshare_context import MindshareContextLoader

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


ALCYONE = (
    pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
    / "Alcyone LE__lilTiGGer_vs_blacksquall"
    / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
)


@pytest.fixture
def alcyone():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"replay not found: {ALCYONE}")
        pytest.skip(f"replay not found: {ALCYONE}")
    return ALCYONE


def test_a_reader_registered_through_the_hook_produces_the_game_events(alcyone, monkeypatch):
    sentinel_events = []

    class SentinelReader:
        def __call__(self, data, replay):
            default = next(
                r for accepts, r in replay.registered_readers["replay.game.events"] if r is not self and accepts(replay)
            )
            events = default(data, replay)
            sentinel_events.append(events)
            return events

    def register_readers(replay):
        replay.register_reader("replay.game.events", SentinelReader(), lambda r: True)

    monkeypatch.setattr(extensions, "register_readers", register_readers)
    replay = loader.load_replay(alcyone)
    assert isinstance(replay, loader.MindshareReplay)
    assert len(sentinel_events) == 1
    produced = {id(e) for e in sentinel_events[0]}
    assert replay.game_events
    assert all(id(e) in produced for e in replay.game_events)


def test_a_plugin_registered_through_the_hook_sees_the_events_after_the_mindshare_plugins(alcyone, monkeypatch):
    seen = []

    class SentinelPlugin:
        name = "Sentinel"

        def handleUnitBornEvent(self, event, replay):
            seen.append(event.unit.doneEvent is event)  # the Mindshare ContextLoader ran first

    monkeypatch.setattr(extensions, "register_plugins", lambda engine: engine.register_plugin(SentinelPlugin()))
    loader.load_replay(alcyone)
    assert seen and all(seen)


def test_the_engine_has_the_mindshare_plugins_in_the_forks_order_and_no_creep_tracker():
    names = [type(p).__name__ for p in loader.build_engine().plugins()]
    assert names == ["GameHeartNormalizer", "MindshareContextLoader", "SelectionTracker"]
    assert MindshareContextLoader.name == "ContextLoader"  # the engine re-raises its errors


def test_maps_are_not_loaded_by_default(alcyone):
    replay = loader.load_replay(alcyone)
    assert getattr(replay, "map", None) is None


def test_the_empty_hooks_do_nothing():
    assert extensions.register_readers(object()) is None
    assert extensions.register_plugins(object()) is None
