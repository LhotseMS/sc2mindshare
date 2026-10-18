"""CR-020 (T19): the Mindshare layer leaves sc2reader's objects as upstream made them.

After our load and the whole analysis, every event, unit and player has exactly the instance
attributes, with the same values, as a fresh upstream sc2reader 1.9.0 load with the same upstream
plugins (GameHeartNormalizer, ContextLoader, SelectionTracker). The fork's fields the layer needs
(``unit.initEvent``, ``event.updateEvents``, ``event.second`` as frame / 22.4, ...) live in
``reader.side_fields``, a map keyed by the object, read and written through the fork-flavoured
classes' properties.

Still swapped (a later step, not T19's done-when): each object's ``__class__`` is a fork-flavoured
subclass of its upstream class, and the replay's datetimes are made naive.
"""

import contextlib
import io
import os
import pathlib

import pytest
import sc2reader
from sc2mindshare.analysis.run import analyse
from sc2mindshare.reader import side_fields
from sc2mindshare.reader.loader import load_replay
from sc2reader.engine import GameEngine
from sc2reader.engine.plugins import ContextLoader, GameHeartNormalizer, SelectionTracker

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
GAMES = {
    "alcyone": MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
    "spine": MS_SC / "200k dmg spine crawler ZvP.SC2Replay",
}


def _plain(value):
    """Plain data compared by value; objects (units, players, events, abilities) by their class only,
    since each load has its own instances."""
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return "<object>"  # the flavoured class differs from upstream's by design (still swapped, see above)


def _state(obj):
    return {k: _plain(v) for k, v in vars(obj).items()}


@pytest.fixture(scope="module", params=sorted(GAMES))
def loads(request):
    path = GAMES[request.param]
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    engine = GameEngine(plugins=[GameHeartNormalizer(), ContextLoader(), SelectionTracker()])
    upstream = sc2reader.load_replay(str(path), load_level=4, load_map=False, engine=engine)
    ours = load_replay(path)
    with contextlib.redirect_stdout(io.StringIO()):
        analyse(ours, MS_SC)
    return upstream, ours


def test_events_keep_upstreams_attributes_and_values(loads):
    upstream, ours = loads
    assert len(ours.events) == len(upstream.events)
    for i, (mine, theirs) in enumerate(zip(ours.events, upstream.events, strict=True)):
        assert _state(mine) == _state(theirs), f"event {i} ({type(theirs).__name__})"


def test_units_keep_upstreams_attributes_and_values(loads):
    upstream, ours = loads
    assert ours.objects.keys() == upstream.objects.keys()
    for unit_id, unit in ours.objects.items():
        assert _state(unit) == _state(upstream.objects[unit_id]), f"unit {unit_id}"


def test_players_keep_upstreams_attributes_and_values(loads):
    upstream, ours = loads
    for mine, theirs in zip(ours.players, upstream.players, strict=True):
        assert _state(mine) == _state(theirs)


def test_the_forks_fields_are_still_there_through_the_flavoured_classes(loads):
    """The layer still reads what the fork set, now from side_fields: a few spot checks."""
    _upstream, ours = loads
    born = next(u for u in ours.objects.values() if side_fields.get(u, "doneEvent") is not None)
    assert born.doneEvent is side_fields.get(born, "doneEvent")
    assert "doneEvent" not in vars(born)
    event = ours.events[-1]
    assert event.second == event.frame / 22.4 or event.second == int(event.frame / 22.4)
    assert "second" in vars(event) and vars(event)["second"] == event.frame >> 4  # upstream's own value, kept


def test_side_fields_follow_identity_not_equality():
    """sc2reader's Unit compares and hashes by unit id, so units of two replays with the same id are
    equal; their fork fields must stay apart (a WeakKeyDictionary mixed them, CR-020)."""
    from sc2reader.data import Unit

    a, b = Unit(42), Unit(42)
    assert a == b and hash(a) == hash(b)
    side_fields.set(a, "baseName", "Main")
    assert side_fields.get(a, "baseName") == "Main"
    assert side_fields.get(b, "baseName") is None and not side_fields.has(b, "baseName")
    side_fields.set(b, "baseName", "Natural")
    assert (side_fields.get(a, "baseName"), side_fields.get(b, "baseName")) == ("Main", "Natural")


def test_an_entry_goes_with_its_object():
    import gc

    from sc2reader.data import Unit

    unit = Unit(7)
    side_fields.set(unit, "baseName", "x")
    key = id(unit)
    assert key in side_fields._STORE
    del unit
    gc.collect()
    assert key not in side_fields._STORE
