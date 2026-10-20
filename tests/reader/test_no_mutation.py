"""CR-020 (T19): the Mindshare layer leaves sc2reader's objects as upstream made them.

After our load and the whole analysis, every event, unit and player has exactly the instance
attributes, with the same values, as a fresh upstream sc2reader 1.9.0 load with the same upstream
plugins (GameHeartNormalizer, ContextLoader, SelectionTracker). The fork's fields the layer needs
(``unit.initEvent``, ``event.updateEvents``, ``event.second`` as frame / 22.4, ...) live in
``reader.side_fields``, a map keyed by the object, read and written through the fork-flavoured
classes' properties.

Still swapped (CR-064, not T19's done-when): each object's ``__class__`` is a fork-flavoured
subclass of its upstream class, and the replay's datetimes are made naive.
"""

import contextlib
import io
import os
import pathlib

import pytest
import sc2reader
from sc2reader.engine import GameEngine
from sc2reader.engine.plugins import ContextLoader, GameHeartNormalizer, SelectionTracker

from sc2mindshare.analysis.run import analyse
from sc2mindshare.reader import side_fields
from sc2mindshare.reader.loader import load_replay

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


def _upstream_class(cls):
    """The nearest sc2reader class: the flavoured subclass differs from upstream's by design (CR-064)."""
    base = next((c for c in cls.__mro__ if c.__module__.startswith("sc2reader")), cls)
    return f"{base.__module__}.{base.__qualname__}"


class _Canon:
    """Each load has its own instances, so a reference is compared by what it points to in its replay:
    an event by its index, a unit by its id, an entity or player by its index (Vera's G7 on 303898b).
    Any other object compares by its nearest sc2reader class and its own attributes."""

    def __init__(self, replay):
        roles = {id(replay): ("replay",)}
        for i, e in enumerate(replay.events):
            roles[id(e)] = ("event", i)
        for uid, u in replay.objects.items():
            roles[id(u)] = ("unit", uid)
        for i, p in enumerate(replay.entities):
            roles.setdefault(id(p), ("entity", i))
        for i, p in enumerate(replay.players):
            roles.setdefault(id(p), ("player", i))
        self._roles = roles

    def __call__(self, value, depth=0):
        if value is None or isinstance(value, (bool, int, float, str, bytes)):
            return value
        role = self._roles.get(id(value))
        if role is not None:
            return role
        if isinstance(value, (list, tuple)):
            return [self(v, depth + 1) for v in value]
        if isinstance(value, (set, frozenset)):
            return sorted((self(v, depth + 1) for v in value), key=repr)
        if isinstance(value, dict):
            return {repr(self(k, depth + 1)): self(v, depth + 1) for k, v in value.items()}
        if not hasattr(value, "__dict__"):
            return (_upstream_class(type(value)), repr(value))
        if depth >= 3:
            return (_upstream_class(type(value)),)
        return (_upstream_class(type(value)), {k: self(v, depth + 1) for k, v in sorted(vars(value).items())})


def _state(obj, canon):
    return {k: canon(v) for k, v in vars(obj).items()}


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
    co, cu = _Canon(ours), _Canon(upstream)
    for i, (mine, theirs) in enumerate(zip(ours.events, upstream.events, strict=True)):
        assert _state(mine, co) == _state(theirs, cu), f"event {i} ({type(theirs).__name__})"


@pytest.mark.parametrize("attribute", ["unit", "player"])
def test_the_comparison_sees_a_repointed_reference(loads, attribute):
    """Vera's G7 control on 303898b: an event whose unit (or player) points at another one of the same
    replay must not compare equal to upstream's, though the class and every plain value still match."""
    import copy

    upstream, ours = loads
    co, cu = _Canon(ours), _Canon(upstream)
    targets = list(ours.objects.values()) if attribute == "unit" else list(ours.players)
    i, mine = next((i, e) for i, e in enumerate(ours.events) if vars(e).get(attribute) is not None)
    moved = copy.copy(mine)
    vars(moved)[attribute] = next(t for t in targets if t is not vars(mine)[attribute])
    assert _state(mine, co) == _state(upstream.events[i], cu)
    assert _state(moved, co) != _state(upstream.events[i], cu)


def test_units_keep_upstreams_attributes_and_values(loads):
    upstream, ours = loads
    assert ours.objects.keys() == upstream.objects.keys()
    co, cu = _Canon(ours), _Canon(upstream)
    for unit_id, unit in ours.objects.items():
        assert _state(unit, co) == _state(upstream.objects[unit_id], cu), f"unit {unit_id}"


def test_players_keep_upstreams_attributes_and_values(loads):
    upstream, ours = loads
    co, cu = _Canon(ours), _Canon(upstream)
    for mine, theirs in zip(ours.players, upstream.players, strict=True):
        assert _state(mine, co) == _state(theirs, cu)


def test_the_forks_fields_are_still_there_through_the_flavoured_classes(loads):
    """The layer still reads what the fork set, now from side_fields: a few spot checks."""
    _upstream, ours = loads
    born = next(u for u in ours.objects.values() if side_fields.get(u, "doneEvent") is not None)
    assert born.doneEvent is side_fields.get(born, "doneEvent")
    assert "doneEvent" not in vars(born)
    event = ours.events[-1]
    assert event.second == event.frame / 22.4 or event.second == int(event.frame / 22.4)
    assert "second" in vars(event) and vars(event)["second"] == event.frame >> 4  # upstream's own value, kept


class _Owner:
    """Stands in for a replay: the owner of side fields (weak-referenceable)."""


def test_a_write_needs_an_owner():
    """An object no replay adopted cannot get side fields by accident (they would belong to no replay)."""
    from sc2reader.data import Unit

    with pytest.raises(LookupError, match="pass the replay"):
        side_fields.set(Unit(1), "baseName", "x")


def test_the_owner_takes_its_entries_with_it():
    import gc

    from sc2reader.data import Unit

    owner, units = _Owner(), [Unit(i) for i in range(3)]
    for u in units:
        side_fields.set(u, "initEvent", units[0], owner)  # values pointing at keyed objects, as in a replay
    keys = {id(u) for u in units}
    assert keys <= set(side_fields._STORE)
    del owner
    gc.collect()
    assert not keys & set(side_fields._STORE)


def test_side_fields_follow_identity_not_equality():
    """sc2reader's Unit compares and hashes by unit id, so units of two replays with the same id are
    equal; their fork fields must stay apart (a WeakKeyDictionary mixed them, CR-020)."""
    from sc2reader.data import Unit

    a, b = Unit(42), Unit(42)
    assert a == b and hash(a) == hash(b)
    owner = _Owner()
    side_fields.set(a, "baseName", "Main", owner)
    assert side_fields.get(a, "baseName") == "Main"
    assert side_fields.get(b, "baseName") is None and not side_fields.has(b, "baseName")
    side_fields.set(b, "baseName", "Natural", owner)
    assert (side_fields.get(a, "baseName"), side_fields.get(b, "baseName")) == ("Main", "Natural")


def test_an_entry_goes_with_its_object():
    import gc

    from sc2reader.data import Unit

    unit = Unit(7)
    owner = _Owner()
    side_fields.set(unit, "baseName", "x", owner)
    key = id(unit)
    assert key in side_fields._STORE
    del unit
    gc.collect()
    assert key not in side_fields._STORE


def _load_analyse_drop(path):
    """Load and analyse a replay, keep a weak reference to one event and one unit, drop everything."""
    import gc
    import weakref

    replay = load_replay(path)
    with contextlib.redirect_stdout(io.StringIO()):
        analyse(replay, MS_SC)
    event, unit = weakref.ref(replay.events[100]), weakref.ref(next(iter(replay.objects.values())))
    del replay
    gc.collect()  # the replay goes, and its finalizer drops its generation's entries
    gc.collect()  # the objects those entries held are freed in the next pass
    return event, unit


def test_a_dropped_replay_leaves_nothing_in_the_store():
    """Morgan's CR-020 P1: the stored values point back at the keyed objects (initEvent -> event -> unit),
    so per-object weak references never fired and every replay stayed alive. The store now belongs to the
    replay: when the replay goes, its entries go, and so do its objects."""
    for name in ("alcyone", "spine", "alcyone"):
        path = GAMES[name]
        if not path.exists():
            pytest.fail(f"missing input {path}")
        before = len(side_fields._STORE)  # other tests' replays may still be alive
        event, unit = _load_analyse_drop(path)
        assert event() is None and unit() is None, name  # the replay's objects are gone
        assert len(side_fields._STORE) == before, (name, before, len(side_fields._STORE))  # and the store does not grow
