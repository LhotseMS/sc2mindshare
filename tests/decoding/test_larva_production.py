"""Zerg production chain: unit -> egg/larva -> town hall (CR-057, E2).

Per-hall literals from s2protocol's tracker events alone (orchestrator `.scratch/stream3/e2_oracle.py`),
independent of sc2reader and of the decoder.
"""

from collections import Counter

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.creators import TOWN_HALLS, larva_production, larva_use
from sc2mindshare.decoding.export import to_dict

# name -> {town hall id: (larvae, larvae used, units)}, all owned by the Zerg player
EXPECTED = {
    "alcyone": (
        1,
        {
            54788097: (112, 99, 116),
            66322433: (98, 89, 98),
            76283905: (72, 63, 72),
            108527622: (22, 19, 24),
            127926294: (35, 22, 28),
            129499155: (18, 15, 22),
            130023440: (18, 15, 22),
            164102153: (12, 0, 0),
        },
    ),
    "spores": (
        2,
        {
            38273026: (22, 11, 12),
            63438849: (113, 97, 105),
            63963140: (110, 91, 96),
            75497474: (88, 69, 71),
            95158273: (57, 39, 44),
            118489090: (50, 31, 34),
            145489922: (45, 34, 35),
        },
    ),
    "spine": (1, {47972353: (72, 68, 75), 60030977: (53, 48, 52), 64487425: (44, 41, 44)}),
}


@pytest.fixture(scope="module", params=sorted(EXPECTED))
def case(request, replays):
    name = request.param
    return name, load(replays[name]).replay


def test_every_larva_made_unit_has_one_town_hall(case):
    name, replay = case
    zerg, halls = EXPECTED[name]
    rows = larva_production(replay)
    assert len(rows) == sum(units for _l, _u, units in halls.values())
    assert all(r.town_hall_id is not None and r.town_hall_type in TOWN_HALLS for r in rows)
    assert {r.player_id for r in rows} == {zerg}


def test_larva_use_per_town_hall(case):
    name, replay = case
    zerg, halls = EXPECTED[name]
    rows = larva_use(replay)
    assert {r.town_hall_id: (r.larvae, r.larvae_used, r.units) for r in rows} == halls
    assert {r.player_id for r in rows} == {zerg}


def test_town_hall_type_at_the_birth_loop(alcyone):
    """The main hatchery became a Lair and then a Hive: its units carry the type of the moment."""
    rows = [r for r in larva_production(load(alcyone).replay) if r.town_hall_id == 54788097]
    assert Counter(r.town_hall_type for r in rows) == {"Hatchery": 43, "Lair": 62, "Hive": 11}
    frames = {t: [r.frame for r in rows if r.town_hall_type == t] for t in ("Hatchery", "Lair", "Hive")}
    assert max(frames["Hatchery"]) < min(frames["Lair"]) and max(frames["Lair"]) < min(frames["Hive"])


def test_export_has_the_larva_use(alcyone):
    rows = to_dict(load(alcyone))["larva_use"]
    assert rows[0] == {"player_id": 1, "town_hall_id": 54788097, "larvae": 112, "larvae_used": 99, "units": 116}
    assert len(rows) == 8
