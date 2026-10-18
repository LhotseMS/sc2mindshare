"""Unit creator attribution from SUnitBornEvent (CR-055, T3-14).

Literal counts from s2protocol's decode of the tracker events (an oracle independent of sc2reader;
probe `.scratch/stream3/creator_probe.py` in the orchestrator root). The alive and owner checks below
use sc2reader's own unit objects, not the decoder.
"""

from collections import Counter

import pytest
import sc2reader
from sc2mindshare.decoding import load
from sc2mindshare.decoding.creators import creations
from sc2mindshare.decoding.export import to_dict

# name -> births, births with a creator, births without one {(at loop 0, player): n},
# births without one after loop 0 {(type, player): n}, births whose creator has another owner {(creator type, owner, unit type, player): n}
EXPECTED = {
    "alcyone": (
        1153,
        896,
        {(True, 0): 179, (True, 1): 29, (True, 2): 28, (False, 1): 21},
        {("Broodling", 1): 21},
        {},
    ),
    "spores": (
        1579,
        1307,
        {(True, 0): 199, (True, 1): 28, (True, 2): 29, (False, 2): 16},
        {("Broodling", 2): 15, ("ParasiticBombRelayDummy", 2): 1},
        {("Changeling", 2, "ChangelingZealot", 1): 1},
    ),
    "spine": (
        664,
        448,
        {(True, 0): 153, (True, 1): 29, (True, 2): 28, (False, 1): 6},
        {("Broodling", 1): 6},
        {("Sentry", 2, "ForceField", 0): 8},
    ),
}


@pytest.fixture(scope="module", params=sorted(EXPECTED))
def case(request, replays):
    name = request.param
    return name, load(replays[name]).replay


def test_one_creation_per_birth(case):
    name, replay = case
    rows = creations(replay)
    born = [e for e in replay.tracker_events if type(e).__name__ == "UnitBornEvent"]
    assert len(rows) == len(born) == EXPECTED[name][0]
    assert [(r.frame, r.unit_id) for r in rows] == [(e.frame, e.unit_id) for e in born]
    assert sum(r.creator_id is not None for r in rows) == EXPECTED[name][1]


def test_births_without_a_creator_are_start_units_map_units_and_spawned_effects(case):
    """Refines the hypothesis: besides the loop-0 units, Broodlings (and one bomb dummy) have no creator."""
    name, replay = case
    rows = [r for r in creations(replay) if r.creator_id is None]
    assert Counter((r.frame == 0, r.player_id) for r in rows) == EXPECTED[name][2]
    assert Counter((r.unit_type, r.player_id) for r in rows if r.frame) == EXPECTED[name][3]
    assert all(r.creator_ability is None for r in rows)


def test_every_creator_is_alive_and_the_owner_differs_only_for_the_listed_effects(case):
    name, replay = case
    other_owner: Counter = Counter()
    for row in creations(replay):
        if row.creator_id is None:
            continue
        creator = replay.objects[row.creator_id]  # sc2reader's own unit object
        assert creator.started_at <= row.frame
        assert creator.died_at is None or creator.died_at >= row.frame
        owner = creator.owner.pid if creator.owner is not None else 0
        if owner != row.player_id:
            other_owner[(_type_at(creator, row.frame), owner, row.unit_type, row.player_id)] += 1
    assert other_owner == Counter(EXPECTED[name][4])


def _type_at(unit, frame):
    """The unit's type at the loop (sc2reader's `name` is the final type, F3-007)."""
    name = unit.name
    for f, t in sorted(unit.type_history.items()):
        if f <= frame:
            name = t.name
    return name


def test_creator_abilities_on_alcyone(alcyone):
    rows = creations(load(alcyone).replay)
    assert Counter(r.creator_ability for r in rows if r.creator_id is not None) == {
        "": 387,  # larva spawned by a Hatchery, Lair or Hive carries an empty ability name
        "LarvaTrain": 382,  # the creator is the egg (the larva's own tag)
        "NexusTrain": 77,
        "RoboticsFacilityTrain": 20,
        "GatewayTrain": 9,
        "TrainQueen": 8,
        "AdeptPhaseShift": 5,
        "StargateTrain": 5,
        "PurificationNovaTargeted": 3,
    }


def test_the_reader_changes_nothing_in_the_tracker_events(alcyone):
    """The births stay plain sc2reader UnitBornEvents with the same attributes (G1 for stream 1)."""
    ours = load(alcyone).replay.tracker_events
    plain = sc2reader.load_replay(alcyone, load_level=4, load_map=False).tracker_events

    def shape(events):
        return [(type(e), {k: v for k, v in vars(e).items() if k not in _REFS}) for e in events]

    assert shape(ours) == shape(plain)


_REFS = {"unit", "player", "unit_upkeeper", "unit_controller", "killer", "killing_player", "killing_unit"}


def test_export_has_the_creator_summary(alcyone):
    doc = to_dict(load(alcyone))["creators"]
    assert {"player_id": 1, "creator_ability": "LarvaTrain", "count": 382} in doc["by_ability"]
    assert doc["without_creator"] == [
        {"player_id": 0, "at_game_start": True, "count": 179},
        {"player_id": 1, "at_game_start": False, "count": 21},
        {"player_id": 1, "at_game_start": True, "count": 29},
        {"player_id": 2, "at_game_start": True, "count": 28},
    ]
