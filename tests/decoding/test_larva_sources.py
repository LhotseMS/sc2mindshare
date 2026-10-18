"""Natural versus injected larvae per town hall (CR-061, F3-026), without durations.

Per-hall literals from s2protocol's tracker events alone (orchestrator `.scratch/stream3/e6_oracle.py`),
with the same run rule: births at a hall at most 4 loops apart, 3 or more = an inject pop.
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.creators import larva_sources, larva_use
from sc2mindshare.decoding.export import to_dict

# hall -> (start, natural, injected, unclassified, pops, first pop, longest between pops)
EXPECTED = {
    "alcyone": {
        54788097: (3, 43, 66, 0, 22, 4016, 1970),
        66322433: (0, 38, 60, 0, 20, 4951, 2219),
        76283905: (0, 24, 48, 0, 16, 8270, 2275),
        108527622: (0, 22, 0, 0, 0, None, None),
        127926294: (0, 14, 21, 0, 7, 16023, 2354),
        129499155: (0, 18, 0, 0, 0, None, None),
        130023440: (0, 18, 0, 0, 0, None, None),
        164102153: (0, 3, 9, 0, 3, 19983, 1615),
    },
    "spores": {
        38273026: (0, 4, 18, 0, 6, 17921, 3975),
        63438849: (3, 30, 78, 2, 26, 4410, 1923),
        63963140: (0, 30, 72, 8, 24, 5289, 3053),
        75497474: (0, 17, 69, 2, 23, 6501, 6197),
        95158273: (0, 22, 33, 2, 11, 12076, 7622),
        118489090: (0, 15, 33, 2, 11, 15966, 3205),
        145489922: (0, 12, 33, 0, 11, 18269, 3312),
    },
    "spine": {
        47972353: (3, 39, 30, 0, 10, 4409, 2921),
        60030977: (0, 35, 18, 0, 6, 5252, 5479),
        64487425: (0, 29, 15, 0, 5, 10809, 1306),
    },
}


@pytest.fixture(scope="module", params=sorted(EXPECTED))
def case(request, replays):
    name = request.param
    return name, load(replays[name]).replay


def test_larva_sources_per_hall(case):
    name, replay = case
    got = {
        r.town_hall_id: (
            r.start_larvae,
            r.natural_larvae,
            r.injected_larvae,
            r.unclassified_larvae,
            len(r.pops),
            r.pops[0] if r.pops else None,
            r.longest_between_pops,
        )
        for r in larva_sources(replay)
    }
    assert got == EXPECTED[name]


def test_every_larva_is_counted_once(case):
    _name, replay = case
    spawned = {u.town_hall_id: u.larvae for u in larva_use(replay)}
    for r in larva_sources(replay):
        total = r.start_larvae + r.natural_larvae + r.injected_larvae + r.unclassified_larvae
        assert total == spawned[r.town_hall_id]


def test_pops_follow_an_inject_command_on_that_hall(case):
    """Every pop has an earlier SpawnLarva command (or its retarget) on the same hall (sc2reader's names)."""
    _name, replay = case
    commands: dict[int, list[int]] = {}
    for e in replay.game_events:
        if type(e).__name__ in ("TargetUnitCommandEvent", "UpdateTargetUnitCommandEvent") and e.ability_name == "SpawnLarva":
            commands.setdefault(e.target_unit_id, []).append(e.frame)
    for r in larva_sources(replay):
        for pop in r.pops:
            assert any(f < pop for f in commands.get(r.town_hall_id, []))


def test_export_has_the_larva_sources(alcyone):
    rows = to_dict(load(alcyone))["larva_sources"]
    assert len(rows) == 8
    assert rows[0]["town_hall_id"] == 54788097 and rows[0]["injected_larvae"] == 66 and len(rows[0]["pops"]) == 22
