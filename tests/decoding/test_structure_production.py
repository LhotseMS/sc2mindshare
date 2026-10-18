"""Production per structure, without durations (CR-058, E3 part 1).

Literals from s2protocol's tracker events alone (orchestrator `.scratch/stream3/e3_oracle.py`): births whose
creator ability is a structure's own train ability (`*Train`, `Train*`, not the egg's `LarvaTrain`).
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.creators import is_production_ability, structure_production
from sc2mindshare.decoding.export import to_dict

# id -> (player, type when started, started, finished, died, units, first unit loop, last unit loop)
ALCYONE = {
    33030151: (2, "Nexus", 12703, 14303, None, 3, 14811, 21314),
    54788097: (1, "Hatchery", 0, 0, None, 3, 2881, 5997),
    55312386: (2, "Gateway", 928, 1968, None, 6, 2630, 8416),
    59244545: (2, "Nexus", 0, 0, None, 44, 287, 22340),
    66322433: (1, "Hatchery", 1801, 3401, None, 2, 4228, 6003),
    67895297: (2, "Nexus", 2118, 3718, 19612, 26, 4125, 15091),
    68943874: (2, "Nexus", 7627, 9227, 10893, 2, 9900, 10171),
    69730306: (2, "Gateway", 2789, 3829, None, 3, 4542, 8420),
    76283905: (1, "Hatchery", 4582, 6182, 21529, 1, 7555, 7555),
    82575361: (2, "Stargate", 5614, 6574, None, 5, 7377, 15913),
    100401157: (2, "RoboticsFacility", 8586, 9626, None, 10, 10845, 19300),
    109051912: (2, "RoboticsFacility", 8552, 9592, None, 10, 10849, 18522),
    127926294: (1, "Hatchery", 11982, 13582, None, 1, 15256, 15256),
    129236994: (2, "Nexus", 10715, 12315, None, 2, 14891, 21315),
    164102153: (1, "Hatchery", 15654, 17254, None, 1, 19245, 19245),
}
TOTALS = {"alcyone": (15, 119), "spores": (16, 140), "spine": (8, 75)}


def test_every_structure_on_alcyone(alcyone):
    rows = structure_production(load(alcyone).replay)
    assert {
        r.structure_id: (
            r.player_id,
            r.structure_type,
            r.started_at,
            r.finished_at,
            r.died_at,
            r.units,
            r.first_unit_frame,
            r.last_unit_frame,
        )
        for r in rows
    } == ALCYONE


@pytest.mark.parametrize("name", sorted(TOTALS))
def test_structures_and_units_per_replay(replays, name):
    rows = structure_production(load(replays[name]).replay)
    assert (len(rows), sum(r.units for r in rows)) == TOTALS[name]


@pytest.mark.parametrize(
    ("ability", "expected"),
    [("NexusTrain", True), ("TrainQueen", True), ("LarvaTrain", False), ("", False), (None, False), ("CarrierHangar", False)],
)
def test_production_abilities(ability, expected):
    assert is_production_ability(ability) is expected


def test_export_has_the_structure_production(alcyone):
    rows = to_dict(load(alcyone))["structure_production"]
    assert len(rows) == 15
    assert rows[0] == {
        "player_id": 2,
        "structure_id": 33030151,
        "structure_type": "Nexus",
        "started_at": 12703,
        "finished_at": 14303,
        "died_at": None,
        "units": 3,
        "first_unit_frame": 14811,
        "last_unit_frame": 21314,
    }
