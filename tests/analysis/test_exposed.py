"""CR-021 (T20): the values the analysis exposes for stream 2 (Cam's P0-2 field list, TD-15, TD-18).

Literals measured on Alcyone with upstream sc2reader 1.9.0 (and cross-checked against the raw tracker
events with a plain load). Times are game loops; the clock reads loops / 22.4. The answers to P0-2's
V1-V7 are the tests named after them.
"""

import contextlib
import dataclasses
import io
import itertools
import json
import os
import pathlib
from collections import Counter

import pytest
from sc2mindshare.analysis.run import analyse
from sc2mindshare.domain import exposed as ex
from sc2mindshare.export.mindshare_json import analysis_doc
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
LIL, BLACK = 1, 2  # lilTiGGer (Zerg), blacksquall (Protoss)


@pytest.fixture(scope="module")
def x():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    with contextlib.redirect_stdout(io.StringIO()):
        return analyse(load_replay(ALCYONE), MS_SC, with_exposed=True).exposed


def unit(x, unit_id):
    return next(u for u in x.units if u.unit_id == unit_id)


def changes_of(x, unit_id):
    return [(c.loop, c.before, c.after) for c in x.type_changes if c.unit_id == unit_id]


# --- P0-2 §2: every field is there --------------------------------------------------------------------

P02_FIELDS = {
    "U1": (ex.UnitLife, "unit_id"),
    "U2": (ex.UnitLife, "owner"),
    "U3": (ex.UnitLife, "first_type"),
    "U4": (ex.UnitLife, "born_loop"),
    "U5": (ex.UnitLife, "init_loop"),
    "U6": (ex.UnitLife, "done_loop"),
    "U7": (ex.UnitLife, "died_loop"),
    "U7 killer": (ex.UnitLife, "killer"),
    "U7 killing unit": (ex.UnitLife, "killing_unit_id"),
    "U8": (ex.UnitLife, "x"),
    "U9": (ex.UnitLife, "base"),
    "U10": (ex.UnitLife, "hallucinated"),
    "M1": (ex.TypeChange, "unit_id"),
    "M2": (ex.TypeChange, "loop"),
    "M3": (ex.TypeChange, "before"),
    "UP1": (ex.UpgradeDone, "player"),
    "UP2": (ex.UpgradeDone, "upgrade"),
    "UP3": (ex.UpgradeDone, "loop"),
    "UP4": (ex.UpgradeDone, "count"),
    "PS1": (ex.StatsSample, "food_used"),
    "PS2": (ex.SupplyPoint, "limit"),
    "PS3": (ex.Chrono, "target_unit_id"),
    "C1": (ex.GameContext, "base_build"),
    "C2": (ex.GameContext, "loops"),
    "C3": (ex.PlayerContext, "opponent_race"),
    "C4": (ex.GameContext, "team_size"),
    "C5": (ex.TimeTables, "build_times"),
}


@pytest.mark.parametrize("item", sorted(P02_FIELDS))
def test_every_p0_2_field_is_exposed(item):
    cls, name = P02_FIELDS[item]
    assert name in {f.name for f in dataclasses.fields(cls)}


def test_everything_is_filled_on_alcyone(x):
    assert (len(x.units), len(x.type_changes), len(x.upgrades), len(x.stats), len(x.supply), len(x.chronos)) == (
        1232,
        783,
        65,
        283,
        1113,
        15,
    )
    assert x.game == ex.GameContext(
        base_build=92440,
        version="5.0.13.92440",
        loops=22369,
        game_type="1v1",
        team_size=1,
        is_ladder=True,
        players=(ex.PlayerContext(1, 0, "Zerg", "Protoss"), ex.PlayerContext(2, 1, "Protoss", "Zerg")),
    )
    assert (len(x.tables.build_times), len(x.tables.research_times)) == (120, 117)  # 128 rows less the 8 base rows
    assert len(x.tables.units_source_sha256) == len(x.tables.upgrades_source_sha256) == 64
    assert all(u.base is None for u in x.units)  # U9 waits for the fixed base detector (T22 P1)
    assert not any(u.hallucinated for u in x.units)


# --- the done-when: type at birth, never the final type (TD-13) ----------------------------------------


def test_c5_the_tables_are_keyed_by_the_ids_the_units_carry(x):
    """Vera's G7 (a) on CR-021: the build times join with U3 (internal ids such as "VoidRay"), not the
    sheet's display names ("Void Ray"); the five names that are not their id are aliased."""
    keys = set(dict(x.tables.build_times))
    assert {"VoidRay", "Hatchery", "SpawningPool", "Drone", "Zergling", "Overlord", "Gateway", "BattleHellion"} <= keys
    assert {"LocustMPFlying", "Locust", "OverlordTransport", "OracleStasisTrap"} <= keys  # the other aliases
    assert not keys & {"Void Ray", "Hellbat", "Natural", "3rd base"}  # no display name, no base row
    assert x.tables.unmapped_units == ()
    built = {u.first_type for u in x.units if u.init_loop is not None}  # every building the players placed
    # no row in unitsInfo.csv for a Queen's creep tumor or a rich-gas extractor: gaps in the sheet, not in the keying
    assert built - keys == {"CreepTumorQueen", "ExtractorRich"}
    assert dict(x.tables.build_times)["VoidRay"] == "43"


def test_every_morph_starts_from_the_type_before_it(x):
    """Morgan's G6 N1 on c312162: each TypeChange's ``before`` is the previous change's ``after``, or the
    unit's first type for its first change, for every unit (a wrong ``before`` anywhere shows here)."""
    first = {u.unit_id: u.first_type for u in x.units}
    current = dict(first)
    checked = 0
    for change in sorted(x.type_changes, key=lambda c: c.loop):  # stable: same-loop changes keep their order
        assert change.before == current[change.unit_id], change
        current[change.unit_id] = change.after
        checked += 1
    assert checked == len(x.type_changes) == 783


def test_the_overlord_born_at_2_46_reads_as_an_overlord_with_a_later_overseer_morph(x):
    overlord = unit(x, 71303169)
    assert (overlord.first_type, overlord.born_loop, overlord.owner) == ("Overlord", 3718, LIL)  # 3718 / 22.4 = 2:46
    assert changes_of(x, 71303169) == [(14615, "Overlord", "OverlordCocoon"), (14881, "OverlordCocoon", "Overseer")]


# --- P0-2 §7: the Alcyone checks ------------------------------------------------------------------------


def test_v1_a_zerg_building_raises_an_init_at_placement(x):
    pool = next(u for u in x.units if u.first_type == "SpawningPool")
    assert (pool.owner, pool.init_loop, pool.born_loop, pool.done_loop) == (LIL, 420, None, 1460)  # init 0:18


def test_the_hatcheries_extractor_and_lair(x):
    hatcheries = sorted((u for u in x.units if u.first_type == "Hatchery" and u.owner == LIL), key=lambda u: u.unit_id)
    assert [(u.born_loop, u.init_loop) for u in hatcheries[:3]] == [(0, None), (None, 1801), (None, 4582)]  # main; natural 1:20
    first_extractor = min(u.init_loop for u in x.units if u.first_type == "Extractor")
    assert first_extractor == 4166  # 3:05
    assert [(c.unit_id, c.loop) for c in x.type_changes if c.after == "Lair"] == [(54788097, 8145)]  # 6:03, before the 6:45 Den


def test_v2_which_morphs_pass_through_an_in_progress_type(x):
    """Overseer, Ravager, Baneling go through a cocoon; Lair, Hive, Greater Spire and WarpGate change once."""
    sequences = Counter()
    for u in x.units:
        types = (u.first_type, *[after for _l, _b, after in changes_of(x, u.unit_id)])
        if len(types) > 1:
            sequences[" > ".join(types)] += 1
    assert sequences["Overlord > OverlordCocoon > Overseer"] == 10
    assert sequences["Zergling > BanelingCocoon > Baneling"] == 5
    assert sequences["Roach > RavagerCocoon > Ravager"] == 2
    assert sequences["Roach > RavagerCocoon"] == 1  # a cocoon that never finished
    assert sequences["Hatchery > Lair > Hive"] == 1
    assert sequences["Spire > GreaterSpire"] == 1
    assert sequences["Gateway > WarpGate"] == 14


def test_the_ravager_cocoons_are_later_than_the_legacy_csv_suggests(x):
    """P0-2 §7 expected a cocoon about 6:00, from the legacy CSV's "Ravager Cocoon completed ... from
    00:06:00". That row is a Roach born at 6:00 that the legacy layer names by its final type (F3-007).
    The cocoons start at 7:58 (one never finished), 7:59 and 14:55."""
    assert [(c.unit_id, c.loop) for c in x.type_changes if c.after == "RavagerCocoon"] == [
        (91226116, 10726),
        (112984065, 10741),
        (172752898, 20054),
    ]
    assert [(c.unit_id, c.loop) for c in x.type_changes if c.after == "Ravager"] == [(112984065, 11012), (172752898, 20325)]


def test_v3_a_drone_that_becomes_a_building_dies_at_the_buildings_completion(x):
    """No death at the init: the Drone's UnitDiedEvent (no killer) comes at the building's done loop, at its
    position. Each of the 30 buildings pairs with exactly one such Drone, within 2 loops and 2 cells (Vera's
    G7 (c): the position is checked, from the death events, which UnitLife does not carry)."""
    drones = [u for u in x.units if u.first_type == "Drone" and u.owner == LIL and u.died_loop is not None and u.killer is None]
    built = [u for u in x.units if u.owner == LIL and u.init_loop is not None and not u.first_type.startswith("CreepTumor")]
    assert len(drones) == len(built) == 30
    ids = {d.unit_id for d in drones}
    died_at = {
        e.unit_id: (e.x, e.y)
        for e in load_replay(ALCYONE).tracker_events
        if type(e).__name__ == "UnitDiedEvent" and e.unit_id in ids
    }
    unpaired = {d.unit_id: d for d in drones}
    for b in sorted(built, key=lambda u: u.done_loop):
        match = [
            d
            for d in unpaired.values()
            if abs(d.died_loop - b.done_loop) <= 2
            and max(abs(died_at[d.unit_id][0] - b.x), abs(died_at[d.unit_id][1] - b.y)) <= 2
        ]
        assert len(match) == 1, (b.first_type, b.done_loop, b.x, b.y, [(m.died_loop, died_at[m.unit_id]) for m in match])
        del unpaired[match[0].unit_id]
    assert not unpaired


def test_v4_stats_samples_every_160_loops_and_food_used_can_be_fractional(x):
    mine = [s for s in x.stats if s.player == LIL]
    gaps = Counter(b.loop - a.loop for a, b in itertools.pairwise(mine))
    assert gaps.most_common(1) == [(160, 138)]
    assert not all(s.food_used.is_integer() for s in x.stats)  # Zerglings count half
    at_pool = [s for s in mine if s.loop <= 420][-1]
    assert (at_pool.loop, at_pool.food_used) == (320, 12.0)  # §3.3: supply at the Pool's init is 12


def test_v5_no_cancellation_on_alcyone_only_two_killed_nexuses(x):
    unfinished = [
        (u.first_type, u.init_loop, u.died_loop, u.killer) for u in x.units if u.init_loop and not u.done_loop and u.died_loop
    ]
    assert unfinished == [("Nexus", 17080, 17613, 1), ("Nexus", 18551, 18859, 1)]  # killed by lilTiGGer, not cancelled


def test_v6_metabolic_boost_is_zerglingmovementspeed_and_the_table_has_it(x):
    assert [(u.player, u.loop, u.count) for u in x.upgrades if u.upgrade == "zerglingmovementspeed"] == [(LIL, 16916, 1)]
    assert "zerglingmovementspeed" in dict(x.tables.research_times)


def test_v7_the_warp_gate_morph_follows_warp_gate_research(x):
    first_gateway = min((u for u in x.units if u.first_type == "Gateway" and u.owner == BLACK), key=lambda u: u.init_loop)
    assert (first_gateway.unit_id, first_gateway.init_loop) == (55312386, 928)  # 0:41: the legacy "Warp Gate" at 1:20
    assert changes_of(x, 55312386) == [(9889, "Gateway", "WarpGate")]  # 7:21
    assert [(u.player, u.loop) for u in x.upgrades if u.upgrade == "WarpGateResearch"] == [(BLACK, 9728)]  # 7:14


def test_workers_at_3_12_and_the_starting_units(x):
    assert [(s.player, s.workers_active) for s in x.stats if s.loop == 4320] == [(LIL, 21), (BLACK, 24)]
    start = Counter((u.owner, u.first_type) for u in x.units if u.born_loop == 0 and not u.first_type.startswith("Beacon"))
    assert start == {
        (LIL, "Drone"): 12,
        (LIL, "Hatchery"): 1,
        (LIL, "Larva"): 3,
        (LIL, "Overlord"): 1,
        (BLACK, "Nexus"): 1,
        (BLACK, "Probe"): 12,
    }


def test_chrono_boosts_name_their_target(x):
    assert x.chronos[0] == ex.Chrono(BLACK, 518, 59244545)  # the first on blacksquall's main Nexus
    assert {c.player for c in x.chronos} == {BLACK}


def test_the_analysis_doc_is_plain_json(x):
    doc = analysis_doc(x)
    assert set(doc) == {"game", "units", "type_changes", "upgrades", "stats", "supply", "chronos", "tables"}
    assert json.loads(json.dumps(doc)) == doc
    assert doc["units"][0].keys() == {f.name for f in dataclasses.fields(ex.UnitLife)}
