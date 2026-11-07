"""CR-035 (D2a, D6a; Kevin's call 13): each step's supply is the supply at its start (Leo's reading R(L)), with the
range it lies in where the replay cannot pin it to one value.

The rules are Leo's algorithm notes §1 (CR-035 Notes for Developer); the expected values are QA's re-based oracle
(``.scratch/qa/cr-035/alcyone-expected-rebased.md`` §1.1-1.3, Vera, 2026-11-07), copied here as literals (S01-S04,
S08, S31). The synthetic games go through the real path (``build_order`` on an ``Exposed``).
"""

import contextlib
import io
import os
import pathlib
from fractions import Fraction

import pytest

from sc2mindshare.analysis.build_steps import build_order, supply_reading
from sc2mindshare.analysis.fixes import LAYER_FIXES
from sc2mindshare.analysis.run import analyse
from sc2mindshare.domain.exposed import (
    Exposed,
    GameContext,
    PlayerContext,
    StatsSample,
    TimeTables,
    TypeChange,
    UnitLife,
)
from sc2mindshare.export.view import supply_range_text
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"
FIXES = frozenset(LAYER_FIXES)
Z, P = 1, 2

# --- synthetic games ------------------------------------------------------------------------------------------------

BUILD = {"Drone": "12", "Probe": "12", "Zergling": "17", "Overlord": "18", "Queen": "36", "Roach": "19", "Ravager": "12"}
SUPPLY = {
    "Drone": "1", "Probe": "1", "Zergling": "0.5", "Overlord": "0", "Queen": "2", "Roach": "2", "Ravager": "3",
    "Hatchery": "", "SpawningPool": "", "Extractor": "", "Pylon": "", "Zealot": "2", "Larva": "-",
}  # fmt: skip


def uid(index, recycle=1):
    return index << 18 | recycle


def life(unit_id, owner, first_type, *, born=None, init=None, done=None, died=None, killer=None, killing=None):
    return UnitLife(unit_id, owner, first_type, born, init, done, died, killer, killing, 0, 0, False)


def sample(player, loop, food):
    return StatsSample(player, loop, food, 200, 0, 0, 0, 0, 0, 0, 0)


def game(units=(), changes=(), stats=(), loops=20000):
    players = (PlayerContext(Z, 0, "Zerg", "Protoss"), PlayerContext(P, 1, "Protoss", "Zerg"))
    tables = TimeTables(tuple(BUILD.items()), (), "", "", (), tuple(SUPPLY.items()))
    context = GameContext(92440, "5.0.13.92440", loops, "1v1", 1, True, players)
    return Exposed(context, tuple(units), tuple(changes), (), tuple(stats), (), (), tables)


def drone(index, start_loop, owner=Z, kind="Drone"):
    """A worker whose start (born - 12 s = 268.8 loops) is ``start_loop``."""
    return life(uid(index), owner, kind, born=round(start_loop + 268.8))


def steps(exposed, player=Z):
    return [(s.number, s.item, s.supply, s.supply_range) for s in build_order(exposed, FIXES).of(player)]


def test_a_unit_adds_its_supply_at_its_start_not_at_its_birth():
    """Two Drones started at 1000.2 and 1100.2 (born 268.8 loops later), a sample of 12 at loop 1: the second Drone
    reads 13, though neither is born yet. The sample reading said 12."""
    units = [drone(10, 1000.2), drone(11, 1100.2)]
    assert steps(game(units, stats=[sample(Z, 1, 12.0)])) == [(1, "Drone", 12, None), (2, "Drone", 13, None)]


def test_the_steps_own_effect_and_later_members_of_its_batch_do_not_count():
    """S03: a batch of three Zerglings' eggs (6 lings) at 1000.2-1004.2 reads the supply before its first egg."""
    units = [life(uid(20 + k), Z, "Zergling", born=1000 + k + 381) for k in range(6)]  # 17 s = 380.8 loops
    stats = [sample(Z, 1, 14.0)]
    assert steps(game(units, stats=stats)) == [(1, "Zergling", 14, None)]


def test_a_zerg_structure_takes_its_drone_and_a_protoss_one_does_not():
    units = [life(uid(1), Z, "SpawningPool", init=1000), drone(2, 1100.2)]
    assert steps(game(units, stats=[sample(Z, 1, 12.0)])) == [(1, "SpawningPool", 12, None), (2, "Drone", 11, None)]
    protoss = [life(uid(3), P, "Pylon", init=1000), drone(4, 1100.2, owner=P, kind="Probe")]
    assert steps(game(protoss, stats=[sample(P, 1, 12.0)]), P) == [(1, "Pylon", 12, None), (2, "Probe", 12, None)]


def test_a_death_subtracts_and_a_drone_that_became_a_structure_is_not_counted_twice():
    lost = [life(uid(1), Z, "Queen", born=500, died=900, killer=P), drone(2, 1100.2)]
    # the Queen started before the sample (it is in the 14) and dies at 900: 14 - 2
    assert steps(game(lost, stats=[sample(Z, 1, 14.0)]))[-1] == (2, "Drone", 12, None)
    consumed = [life(uid(3), Z, "Drone", born=0, died=1000), life(uid(4), Z, "Extractor", init=1000), drone(5, 1100.2)]
    assert steps(game(consumed, stats=[sample(Z, 1, 12.0)]))[-1] == (2, "Drone", 11, None)  # -1 once, not twice


def test_a_morph_adds_the_difference_at_its_change():
    roach = life(uid(1), Z, "Roach", born=1500)  # started at 1074.4, before the sample: in the sample's 14
    changes = [TypeChange(uid(1), 2000, "Roach", "RavagerCocoon"), TypeChange(uid(1), 2300, "RavagerCocoon", "Ravager")]
    after = drone(2, 2100.2)
    assert steps(game([roach, after], changes, stats=[sample(Z, 1100, 14.0)]))[-1][2] == 15  # + (3 - 2) at the cocoon


def test_a_change_at_exactly_the_start_does_not_count():
    units = [life(uid(1), Z, "SpawningPool", init=1000), life(uid(2), Z, "Extractor", init=1000)]
    assert steps(game(units, stats=[sample(Z, 1, 12.0)])) == [(1, "SpawningPool", 12, None), (2, "Extractor", 12, None)]


def test_before_the_first_sample_the_reading_starts_at_12():
    units = [life(uid(1), Z, "SpawningPool", init=5), drone(2, 6.2)]  # the first sample adds up: 12 - 1 + 1
    assert steps(game(units, stats=[sample(Z, 160, 12.0)])) == [(1, "SpawningPool", 12, None), (2, "Drone", 11, None)]


def test_a_window_whose_changes_do_not_add_up_gives_a_range():
    """D6a: 14 at loop 1000, 16 at loop 1160, and no visible change between: a Pylon at 1100 is R 14, range 14-16.
    Where the window adds up, there is no range."""
    units = [life(uid(1), P, "Pylon", init=1100)]
    assert steps(game(units, stats=[sample(P, 1000, 14.0), sample(P, 1160, 16.0)]), P) == [(1, "Pylon", 14, (14, 16))]
    assert steps(game(units, stats=[sample(P, 1000, 14.0), sample(P, 1160, 14.0)]), P) == [(1, "Pylon", 14, None)]


def test_the_reading_is_exact_between_samples():
    reading = supply_reading(game([drone(1, 1000.2)], stats=[sample(Z, 900, 12.0), sample(Z, 1100, 13.0)]))[Z]
    assert reading.exact(Fraction(1000)) == (Fraction(12), Fraction(12))
    assert reading.exact(Fraction(1001)) == (Fraction(13), Fraction(13))
    assert reading.at(Fraction(1001)) == (13, None)


def test_the_range_is_shown_low_to_high_with_an_en_dash():
    assert supply_range_text((17, 19)) == "17–19"
    assert supply_range_text(None) == ""


# --- the replays (QA's re-based oracle) -----------------------------------------------------------------------------


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")


def _order(path):
    _need(path)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(path), MS_SC)
    return result, build_order(result.exposed, result.fixes)


@pytest.fixture(scope="module")
def alcyone():
    return _order(ALCYONE)


@pytest.fixture(scope="module")
def spine():
    return _order(SPINE)


def _supplies(order, player):
    return {s.number: s.supply for s in order.of(player)}


def _ranges(order, player):
    return {s.number: s.supply_range for s in order.of(player) if s.supply_range}


def test_s01_alcyone_liltigger_the_changed_supplies(alcyone):
    """Oracle §1.1: the 14 steps whose supply changes from the sample reading, at their R (the others are in the
    CR-034 oracle lines, re-based in test_build_steps)."""
    _, order = alcyone
    got = _supplies(order, 1)
    expected = {2: 11, 8: 18, 10: 18, 14: 22, 16: 24, 17: 26, 21: 28, 25: 32, 26: 33, 29: 37, 36: 45, 39: 54, 41: 56, 42: 55}
    assert {n: got[n] for n in expected} == expected
    assert (got[1], got[6], got[7], got[9]) == (12, 14, 19, 17)  # S03: the Pool's own Drone; the batch's first egg


def test_s02_alcyone_blacksquall_the_changed_supplies(alcyone):
    _, order = alcyone
    got = _supplies(order, 2)
    expected = {
        4: 15, 6: 16, 8: 17, 12: 20, 18: 21, 24: 27, 25: 29, 29: 32, 33: 37, 39: 43, 42: 46, 47: 47, 50: 56, 51: 56,
        52: 58, 55: 62, 60: 64, 63: 66, 66: 74, 67: 75,
    }  # fmt: skip
    assert {n: got[n] for n in expected} == expected


def test_s03_s08_alcyone_the_steps_marked_with_a_range_are_exactly_the_oracles(alcyone):
    _, order = alcyone
    assert _ranges(order, 1) == {6: (14, 16), 7: (17, 19), 8: (16, 18), 9: (15, 17), 10: (16, 18)}
    assert _ranges(order, 2) == {
        3: (13, 14), 4: (14, 15), 11: (17, 19), 12: (18, 20), 13: (20, 22), 14: (20, 22), 16: (20, 22), 17: (22, 24),
        49: (48, 52), 50: (52, 56), 51: (52, 56), 52: (54, 58), 53: (54, 58), 56: (58, 62), 57: (58, 62), 61: (64, 68),
        62: (64, 68), 63: (66, 70),
    }  # fmt: skip
    hatchery, queen = (s for s in order.of(1) if s.number in (7, 10))
    assert (hatchery.item, hatchery.supply, hatchery.supply_range) == ("Hatchery", 19, (17, 19))  # S08
    assert (queen.item, queen.supply, queen.supply_range) == ("Queen", 18, (16, 18))


def test_s04_spine_both_players(spine):
    _, order = spine
    zerg, protoss = _supplies(order, 1), _supplies(order, 2)
    assert {n: zerg[n] for n in (8, 15, 24, 33, 59)} == {8: 15, 15: 22, 24: 35, 33: 49, 59: 65}
    assert {n: protoss[n] for n in (12, 19, 42)} == {12: 18, 19: 24, 42: 51}
    assert _ranges(order, 1) == {8: (15, 16)}
    protoss_ranges = _ranges(order, 2)
    assert (len(protoss_ranges), protoss_ranges[12], protoss_ranges[19]) == (21, (18, 20), (22, 24))
    assert (len(order.of(1)), len(order.of(2))) == (60, 74)


def test_s31_the_analysis_tables_carry_each_unit_types_supply(alcyone):
    result, _ = alcyone
    supplies = dict(result.exposed.tables.supplies)
    assert {k: supplies[k] for k in ("Zergling", "Drone", "Overlord", "Queen", "Roach", "Baneling")} == {
        "Zergling": "0.5",
        "Drone": "1",
        "Overlord": "0",
        "Queen": "2",
        "Roach": "2",
        "Baneling": "0.5",
    }
    assert {k: supplies[k] for k in ("Probe", "Zealot", "Adept", "VoidRay")} == {
        "Probe": "1",
        "Zealot": "2",
        "Adept": "2",
        "VoidRay": "4",
    }
    assert set(supplies) == set(dict(result.exposed.tables.build_times))  # keyed like the build times
