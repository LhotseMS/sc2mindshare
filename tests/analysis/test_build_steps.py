"""CR-034 (S2-1): each player's build order as numbered steps, on the nodes that show them.

The rules are P0-2's (``sources/specs/stream2-build-step-extraction.md``, revised 2026-10-21) and Stefan's
decisions (D47a-D62b); the scenarios are Vera's (``.scratch/qa/cr-034/test-scenarios.md``, S03-S19), the
reference is QA's re-based Alcyone oracle (P0-5 §1, ``ALCYONE_LIL`` and ``ALCYONE_BLACK`` below, copied from
it: lilTiGGer 50 steps, blacksquall 68, with the Chrono column). Synthetic games go through the real path
(``build_order`` on an ``Exposed``), with unit ids in sc2reader's index/recycle form. A start is in loops;
the second shown is ``floor(start / 22.4)``: 6:00 is loop 8064, 6:01 is loop 8086.4.

CR-035 (D2a) re-based the supplies to the supply at each step's start (QA's re-based oracle §1.1-1.2,
``.scratch/qa/cr-035/alcyone-expected-rebased.md``); the reading itself is tested in test_supply_reading.py.
"""

import contextlib
import io
import json
import os
import pathlib
from dataclasses import replace
from fractions import Fraction

import pytest

from sc2mindshare.analysis.build_check import annotate, checks
from sc2mindshare.analysis.build_steps import PRODUCERS, RETURN_LOOPS, build_order, supply_reading, with_build_order
from sc2mindshare.analysis.exposed import UPGRADE_ALIASES, research_row
from sc2mindshare.analysis.fixes import LAYER_FIXES
from sc2mindshare.analysis.guides import library
from sc2mindshare.analysis.run import AnalysisResult, analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.exposed import (
    Chrono,
    Exposed,
    GameContext,
    PlayerContext,
    StatsSample,
    TimeTables,
    TypeChange,
    UnitLife,
    UpgradeDone,
)
from sc2mindshare.domain.models import Graph, Node
from sc2mindshare.domain.steps import BuildStep, NodeSource
from sc2mindshare.domain.time import GameTime
from sc2mindshare.export.mindshare_json import build_document, load_config
from sc2mindshare.export.view import node_view
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
EXPORT = frozenset({"P13", "BO1"})
Z, P = 1, 2  # the synthetic games' players: Zerg, Protoss

ALCYONE_LIL = """
1. 12 0:18 Spawning Pool
2. 11 0:21 Drone
3. 12 0:26 Drone
4. 13 0:29 Drone
5. 14 0:39 Overlord
6. 14 1:06 Zergling ×6
7. 19 1:20 Hatchery
8. 18 1:24 Zergling ×2
9. 17 1:28 Zergling ×2
10. 18 1:32 Queen
11. 20 1:40 Drone
12. 21 1:51 Drone
13. 20 2:25 Drone ×2
14. 22 2:27 Overlord
15. 22 2:31 Queen
16. 24 2:32 Queen
17. 26 2:35 Drone
18. 26 2:46 Drone ×2
19. 28 2:54 Drone ×2
20. 29 3:05 Extractor
21. 28 3:08 Drone ×3
22. 31 3:17 Overlord
23. 31 3:19 Overlord
24. 31 3:21 Drone
25. 32 3:23 Drone
26. 33 3:24 Hatchery
27. 32 3:30 Drone ×2
28. 34 3:51 Queen ×2
29. 37 3:56 Drone ×4
30. 41 4:05 Drone ×4
31. 45 4:17 Overlord
32. 45 4:25 Overlord
33. 45 4:27 Drone ×2
34. 47 4:38 Extractor
35. 46 4:47 Roach Warren
36. 45 4:51 Drone ×8
37. 53 4:54 Extractor
38. 52 5:01 Queen
39. 54 5:06 Lair
40. 54 5:10 Drone ×2
41. 56 5:11 Spore Crawler
42. 55 5:12 Spore Crawler
43. 54 5:12 Drone
44. 55 5:20 Overlord ×2
45. 55 5:27 Roach ×5
46. 65 5:34 Overlord
47. 65 5:35 Overlord
48. 65 5:42 Roach ×4
49. 73 5:55 Overlord
50. 73 5:56 Roach ×5
""".strip().splitlines()
ALCYONE_BLACK = """
1. 12 0:00 Probe
2. 13 0:12 Probe · chrono possible
3. 14 0:20 Probe · chrono possible
4. 15 0:20 Pylon
5. 15 0:38 Probe · chrono possible
6. 16 0:41 Gateway
7. 16 0:50 Probe
8. 17 0:52 Assimilator
9. 17 1:02 Probe
10. 18 1:14 Probe
11. 19 1:26 Probe
12. 20 1:30 Zealot · chrono possible
13. 20 1:34 Nexus
14. 20 1:37 Cybernetics Core
15. 22 1:47 Pylon
16. 22 1:58 Zealot · chrono possible
17. 22 2:04 Gateway
18. 21 2:20 Probe
19. 22 2:28 Adept
20. 24 2:31 Shield Battery
21. 24 2:32 Probe
22. 25 2:44 Probe
23. 26 2:52 Probe
24. 27 2:52 Adept
25. 29 2:56 Probe
26. 30 3:04 Probe
27. 31 3:07 Assimilator
28. 31 3:08 Probe
29. 32 3:11 Adept
30. 34 3:16 Probe
31. 35 3:20 Probe
32. 36 3:28 Probe
33. 37 3:33 Probe
34. 38 3:40 Probe
35. 39 3:45 Probe
36. 40 3:52 Probe
37. 41 3:57 Probe
38. 42 4:04 Probe
39. 43 4:09 Probe
40. 44 4:10 Stargate
41. 44 4:12 Stalker
42. 46 4:13 Pylon
43. 46 4:17 Pylon
44. 46 4:17 Assimilator
45. 46 4:19 Assimilator
46. 46 4:31 Probe ×2 · chrono possible
47. 47 4:31 Stalker
48. 50 4:39 Probe ×2 · chrono possible
49. 52 4:46 Void Ray · chrono possible
50. 56 4:47 Pylon
51. 56 4:47 Probe ×2 · chrono possible
52. 58 4:50 Pylon
53. 54 4:57 Probe ×2 · chrono possible
54. 60 5:09 Probe ×2
55. 62 5:11 Pylon
56. 62 5:15 Pylon
57. 62 5:21 Void Ray · chrono possible
58. 62 5:21 Pylon
59. 62 5:21 Probe ×2
60. 64 5:25 Pylon
61. 64 5:31 Pylon
62. 64 5:33 Probe ×2
63. 66 5:34 Warp Gate Research · chrono possible
64. 70 5:40 Nexus
65. 70 5:45 Adept ×2
66. 74 5:46 Probe
67. 75 5:47 Probe
68. 76 5:55 Shield Battery
""".strip().splitlines()

# --- synthetic games ------------------------------------------------------------------------------------------------

BUILD = {
    "Drone": "12", "Probe": "12", "SCV": "12", "Zergling": "17", "Overlord": "18", "Queen": "36", "Roach": "19",
    "Zealot": "27", "Stalker": "30", "Adept": "30 (20)", "Archon": "8.57", "Marine": "18", "Baneling": "14",
    "Ravager": "12", "Overseer": "12", "Lair": "57", "Hive": "71", "GreaterSpire": "71", "WarpGate": "7",
    "OrbitalCommand": "25", "PlanetaryFortress": "36", "Hatchery": "71", "SpawningPool": "46", "Extractor": "21",
    "Gateway": "46", "Nexus": "71", "Pylon": "18", "BarracksTechLab": "18", "Larva": "-", "Broodling": "-",
}  # fmt: skip
RESEARCH = {"WarpGateResearch": "100", "zerglingmovementspeed": "79"}
PROBE = 268.8  # 12 s in loops


def uid(index, recycle=1):
    """A unit id in sc2reader's form: index << 18 | recycle (60293121 is index 230, recycle 1)."""
    return index << 18 | recycle


def life(
    unit_id, owner, first_type, *, born=None, init=None, done=None, died=None, killer=None, killing=None, hallucinated=False
):
    return UnitLife(unit_id, owner, first_type, born, init, done, died, killer, killing, 0, 0, hallucinated)


def game(units=(), changes=(), upgrades=(), stats=(), chronos=(), loops=20000):
    players = (PlayerContext(Z, 0, "Zerg", "Protoss"), PlayerContext(P, 1, "Protoss", "Zerg"))
    tables = TimeTables(tuple(BUILD.items()), tuple(RESEARCH.items()), "", "")
    context = GameContext(92440, "5.0.13.92440", loops, "1v1", 1, True, players)
    return Exposed(context, tuple(units), tuple(changes), tuple(upgrades), tuple(stats), (), tuple(chronos), tables)


def lines(exposed, player=Z):
    return [s.line() for s in build_order(exposed, FIXES).of(player)]


def sample(player, loop, food):
    return StatsSample(player, loop, food, 200, 0, 0, 0, 0, 0, 0, 0)


def drone(index, start_loop, owner=Z, kind="Drone"):
    """A worker whose start (born - 12 s) is ``start_loop``; ``start_loop`` + 268.8 must be whole."""
    born = round(start_loop + PROBE, 6)
    assert born == int(born), born
    return life(uid(index), owner, kind, born=int(born))


# --- S03 · AC-1: order and ties -------------------------------------------------------------------------------------


def test_s03_two_items_at_the_same_loop_are_ordered_by_unit_id():
    units = [life(61079553, Z, "Extractor", init=2000), life(60817409, Z, "SpawningPool", init=2000)]
    assert lines(game(units)) == ["1. 12 1:29 Spawning Pool", "2. 12 1:29 Extractor"]


def test_s03_close_starts_of_different_items_are_ordered_by_loop_not_by_kind():
    first = [life(uid(900), Z, "SpawningPool", init=2000), drone(100, 2006.2)]  # the building's id is higher
    # CR-035 (D2a): the Pool's Drone is counted off from its init, so the Drone after it is at 11
    assert lines(game(first)) == ["1. 12 1:29 Spawning Pool", "2. 11 1:29 Drone"]
    later = [life(uid(900), Z, "SpawningPool", init=2010), drone(100, 2006.2)]
    assert lines(game(later)) == ["1. 12 1:29 Drone", "2. 12 1:29 Spawning Pool"]


def test_s03_each_player_is_numbered_alone():
    units = [drone(100, 1000.2), drone(101, 900.2, owner=P, kind="Probe"), life(uid(102), P, "Pylon", init=950)]
    order = build_order(game(units), FIXES)
    assert [s.line() for s in order.of(Z)] == ["1. 12 0:44 Drone"]
    assert [s.line() for s in order.of(P)] == ["1. 12 0:40 Probe", "2. 12 0:42 Pylon"]


# --- S04 · AC-1: the 6:00 horizon -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (life(uid(10), Z, "SpawningPool", init=8064), ["1. 12 6:00 Spawning Pool"]),  # loop 8064.0: in
        (drone(11, 8086.2), ["1. 12 6:00 Drone"]),  # in
        (life(uid(12), Z, "Roach", born=8512), []),  # 8512 - 425.6 = 8086.4: 6:01, out
        (life(uid(13), Z, "Overlord", born=8467), ["1. 12 5:59 Overlord"]),  # 8467 - 403.2 = 8063.8: in
        (life(uid(14), Z, "Roach", born=8511), ["1. 12 6:00 Roach"]),  # 8085.4: in
    ],
)
def test_s04_a_start_that_floors_to_6_00_is_in_and_6_01_is_out(unit, expected):
    assert lines(game([unit])) == expected


def test_s04_a_group_meeting_the_edge_keeps_only_its_starts_up_to_6_00():
    """F4(b), Cam's reading of AC-1: the cut is per start, before grouping; the count is never split."""
    units = [drone(20, 8086.2), drone(21, 8089.2)]  # 3 loops apart; the second is at 6:01
    assert lines(game(units)) == ["1. 12 6:00 Drone"]


def test_s04_a_building_morph_after_6_00_is_a_morph_but_no_step():
    units = [life(uid(30), P, "Gateway", init=1000, done=2030)]
    changes = [TypeChange(uid(30), 8244, "Gateway", "WarpGate")]  # 8244 - 156.8 = 8087.2: 6:01
    order = build_order(game(units, changes), FIXES)
    assert [s.line() for s in order.of(P)] == ["1. 12 0:44 Gateway"]
    assert [(m.after, round(float(m.start), 6)) for m in order.morphs] == [("WarpGate", 8087.2)]


# --- S05 · AC-1, AC-6, AC-7: the units existing at loop 0 -----------------------------------------------------------


def test_s05_the_starting_units_are_not_steps_but_a_worker_started_at_0_00_is():
    start = [life(uid(i), Z, "Drone", born=0) for i in range(1, 13)]
    start += [life(uid(20), Z, "Hatchery", born=0), life(uid(21), Z, "Overlord", born=0), life(uid(22), Z, "Larva", born=0)]
    start += [life(uid(30 + i), P, "Probe", born=0) for i in range(12)] + [life(uid(50), P, "Nexus", born=0)]
    first_probe = life(uid(60), P, "Probe", born=287)  # born 0:12, started at loop 18.2: 0:00
    order = build_order(game([*start, first_probe]), FIXES)
    assert order.of(Z) == ()
    assert [s.line() for s in order.of(P)] == ["1. 12 0:00 Probe"]


# --- S06 · AC-6: grouping, 8 loops anchored to the first start ------------------------------------------------------


@pytest.mark.parametrize(
    ("gap", "expected"),
    [(0, ["1. 12 0:44 Drone ×2"]), (8, ["1. 12 0:44 Drone ×2"]), (9, ["1. 12 0:44 Drone", "2. 12 0:45 Drone"])],
)
def test_s06_starts_within_8_loops_of_the_first_share_a_line(gap, expected):
    assert lines(game([drone(100, 1000.2), drone(101, 1000.2 + gap)])) == expected


def test_s06_a_group_may_cross_a_second_boundary_and_shows_its_first_member():
    units = [life(uid(1), P, "Pylon", init=1340), life(uid(2), P, "Pylon", init=1347)]  # 59.8 s and 60.1 s
    stats = [sample(P, 1300, 14.0), sample(P, 1345, 15.0)]
    assert lines(game(units, stats=stats), P) == ["1. 14 0:59 Pylon ×2 · about 14–15 supply"]  # CR-035 F1: the range


def test_s06_the_grouping_is_anchored_not_chained():
    """Members 1 loop apart from 1000 to 1012: one line of 9 (1000-1008), then a new line from 1009. A chain
    from the previous member would make one line of 13."""
    units = [drone(100 + k, 1000.2 + k) for k in range(13)]
    assert lines(game(units)) == ["1. 12 0:44 Drone ×9", "2. 12 0:45 Drone ×4"]


def test_s06_other_players_and_other_items_are_never_merged_and_numbers_count_lines():
    units = [drone(100, 1000.2), drone(101, 1000.2, owner=P), life(uid(102), Z, "Zergling", born=1381)]  # 1381 - 380.8
    units += [drone(103, 1001.2), drone(104, 1002.2), drone(105, 1003.2), life(uid(106), Z, "SpawningPool", init=1100)]
    assert lines(game(units)) == ["1. 12 0:44 Drone ×4", "2. 12 0:44 Zergling", "3. 12 0:49 Spawning Pool"]
    assert lines(game(units), P) == ["1. 12 0:44 Drone"]


# --- supply (Leo's reading) -----------------------------------------------------------------------------------------


def test_the_supply_is_food_used_at_the_last_sample_at_or_before_the_start_rounded_down():
    stats = [sample(Z, 1, 12.0), sample(Z, 160, 13.5), sample(Z, 320, 14.0), sample(P, 100, 30.0)]
    units = [
        life(uid(1), Z, "SpawningPool", init=159),
        life(uid(2), Z, "Extractor", init=160),
        life(uid(3), Z, "Hatchery", init=330),
    ]
    # CR-035 F1: a step whose supply the samples cannot pin carries its range in its line
    assert lines(game(units, stats=stats)) == [
        "1. 12 0:07 Spawning Pool · about 12–15 supply",
        "2. 13 0:07 Extractor · about 13–15 supply",
        "3. 14 0:14 Hatchery",
    ]
    before_any = game([life(uid(4), Z, "SpawningPool", init=5)], stats=[sample(Z, 10, 20.0)])
    assert lines(before_any) == ["1. 12 0:00 Spawning Pool · about 12–21 supply"]


# --- S12 · AC-4: morphs ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "cocoon", "result", "name"),
    [
        ("Zergling", "BanelingCocoon", "Baneling", "Baneling"),
        ("Roach", "RavagerCocoon", "Ravager", "Ravager"),
        ("Overlord", "OverlordCocoon", "Overseer", "Overseer"),
        ("Hydralisk", "LurkerMPEgg", "LurkerMP", "Lurker MP"),
        ("Corruptor", "BroodLordCocoon", "BroodLord", "Brood Lord"),
    ],
)
def test_s12_a_unit_morph_starts_when_its_cocoon_does(first, cocoon, result, name):
    units = [life(uid(1), Z, first, init=1000)]  # its own start at init, so the morph is the second line
    changes = [TypeChange(uid(1), 3000, first, cocoon), TypeChange(uid(1), 3300, cocoon, result)]
    morph = build_order(game(units, changes), FIXES).of(Z)[1]
    # loop 3000: 2:13; CR-035 (D2a): the synthetic unit has an init and no supply in the tables, so it reads as a Zerg
    # structure and takes its Drone (-1)
    assert (morph.kind, morph.item, morph.line()) == ("unit morph", result, f"2. 11 2:13 {name}")


def test_s12_a_cancelled_unit_morph_is_no_step_and_the_roach_keeps_its_own():
    units = [life(uid(1), Z, "Roach", born=1426)]  # started at 1000.4
    changes = [TypeChange(uid(1), 3000, "Roach", "RavagerCocoon"), TypeChange(uid(1), 3100, "RavagerCocoon", "Roach")]
    assert lines(game(units, changes)) == ["1. 12 0:44 Roach"]
    unfinished = [TypeChange(uid(1), 3000, "Roach", "RavagerCocoon")]  # the game ends (or it dies) in the cocoon
    assert lines(game(units, unfinished)) == ["1. 12 0:44 Roach"]


@pytest.mark.parametrize(
    ("before", "after", "seconds", "shown"),
    [
        ("CommandCenter", "OrbitalCommand", 25, "Orbital Command"),
        ("CommandCenter", "PlanetaryFortress", 36, "Planetary Fortress"),
        ("Gateway", "WarpGate", 7, "Warp Gate"),
        ("Hatchery", "Lair", 57, "Lair"),
        ("Lair", "Hive", 71, "Hive"),
        ("Spire", "GreaterSpire", 71, "Greater Spire"),
    ],
)
def test_s12_a_building_morph_starts_at_its_change_minus_its_morph_time(before, after, seconds, shown):
    units = [life(uid(1), Z, before, born=0)]  # a starting building: not a step itself
    change_loop = 6000
    order = build_order(game(units, [TypeChange(uid(1), change_loop, before, after)]), FIXES)
    start = change_loop - seconds * 22.4
    second = int(start // 22.4)
    assert [s.line() for s in order.of(Z)] == [f"1. 12 {second // 60}:{second % 60:02d} {shown}"]
    assert [(m.after, round(float(m.start), 6)) for m in order.morphs] == [(after, round(start, 6))]


def test_s12_a_morph_started_at_5_59_that_finishes_after_6_00_is_a_step():
    units = [life(uid(1), Z, "Hatchery", born=0)]
    order = build_order(game(units, [TypeChange(uid(1), 9340, "Hatchery", "Lair")]), FIXES)  # 9340 - 1276.8 = 8063.2
    assert [s.line() for s in order.of(Z)] == ["1. 12 5:59 Lair"]


@pytest.mark.parametrize(
    ("first", "after"),
    [
        ("SiegeTank", "SiegeTankSieged"),
        ("Barracks", "BarracksFlying"),
        ("SupplyDepot", "SupplyDepotLowered"),
        ("Hellion", "BattleHellion"),
        ("WarpPrism", "WarpPrismPhasing"),
        ("Drone", "DroneBurrowed"),
        ("Observer", "ObserverSiegeMode"),
        ("VikingFighter", "VikingAssault"),
        ("Overlord", "TransportOverlordCocoon"),
    ],
)
def test_s12_type_changes_that_are_not_a_build_decision_are_no_step(first, after):
    units = [life(uid(1), Z, first, born=0)]
    order = build_order(game(units, [TypeChange(uid(1), 3000, first, after)]), FIXES)
    assert order.of(Z) == () and order.morphs == ()


def test_s12_a_terran_add_on_is_a_step_under_its_first_type_and_its_later_hosts_are_not():
    units = [life(uid(1), Z, "BarracksTechLab", init=3000, done=3400)]
    changes = [TypeChange(uid(1), 5000, "BarracksTechLab", "TechLab"), TypeChange(uid(1), 5600, "TechLab", "FactoryTechLab")]
    assert lines(game(units, changes)) == ["1. 12 2:13 Barracks Tech Lab"]


# --- S13 · AC-5: units at their production start --------------------------------------------------------------------


def test_s13_a_unit_starts_at_born_minus_its_build_time_in_loops_rounded_only_for_display():
    """An Archon born at loop 1990 (88.84 s) started 8.57 s earlier, at 80.27 s: 1:20. Rounding the birth to
    its second first (88 s) would give 79.43 s: 1:19."""
    assert lines(game([life(uid(1), P, "Archon", born=1990)]), P) == ["1. 12 1:20 Archon"]


def test_s13_a_warped_in_unit_starts_at_its_init():
    units = [life(uid(1), P, "Zealot", init=5000, done=5112)]
    assert [(s.kind, s.line()) for s in build_order(game(units), FIXES).of(P)] == [("unit", "1. 12 3:43 Zealot")]


# --- S14 · AC-7: things nobody builds -------------------------------------------------------------------------------

NOBODY_BUILDS = (
    "Larva", "Egg", "BanelingCocoon", "RavagerCocoon", "OverlordCocoon", "TransportOverlordCocoon", "BroodLordCocoon",
    "LurkerMPEgg", "CreepTumor", "CreepTumorQueen", "CreepTumorBurrowed", "Broodling", "BroodlingEscort", "Locust",
    "LocustMPFlying", "Changeling", "ChangelingZealot", "MULE", "AutoTurret", "Interceptor", "AdeptPhaseShift",
    "DisruptorPhased", "OracleStasisTrap", "ParasiticBombDummy", "BeaconArmy",
)  # fmt: skip


def test_s14_nothing_nobody_builds_is_a_step_and_the_numbering_is_the_same_without_it():
    real = [drone(100, 1000.2), life(uid(101), Z, "SpawningPool", init=1100), drone(102, 1200.2)]
    noise = [life(uid(200 + k), Z, t, born=1050 + k) for k, t in enumerate(NOBODY_BUILDS)]
    noise += [
        life(uid(300), Z, "Zergling", born=1150, hallucinated=True),
        life(uid(301), Z, "Pylon", init=1150, hallucinated=True),
    ]
    cosmetic = [
        UpgradeDone(Z, "SprayZerg", 1300, 1),
        UpgradeDone(Z, "RewardDanceRoach", 0, 1),
        UpgradeDone(Z, "GameHeartActive", 1400, 1),
    ]
    with_noise = lines(game([*real, *noise], upgrades=cosmetic))
    # CR-035 (D2a): the Pool's Drone is counted off, so the last Drone is at 11
    assert with_noise == lines(game(real)) == ["1. 12 0:44 Drone", "2. 12 0:49 Spawning Pool", "3. 11 0:53 Drone"]


# --- S16 · AC-8: cancels and the Drone that comes back -------------------------------------------------------------


def _cancelled(index=230, owner=Z, first="Extractor"):
    return life(uid(index), owner, first, init=1699, died=1896, killer=owner, killing=uid(index))


def test_s16_a_cancelled_building_is_a_step_and_its_returning_drone_is_not():
    back = life(uid(230, 2), Z, "Drone", born=1896 + 17)  # same index, recycle + 1 (spine: 60293121 -> 60293122)
    assert lines(game([_cancelled(), back])) == ["1. 12 1:15 Extractor · cancelled"]


def test_s16_the_return_window_and_the_unit_index_decide():
    late = life(uid(230, 2), Z, "Drone", born=1896 + RETURN_LOOPS + 1)
    other_index = life(uid(231, 2), Z, "Drone", born=1896 + 17)  # a larva Drone in the same window
    assert lines(game([_cancelled(), late])) == ["1. 12 1:14 Drone", "2. 12 1:15 Extractor · cancelled"]  # 1673.2
    assert lines(game([_cancelled(), other_index])) == ["1. 12 1:13 Drone", "2. 12 1:15 Extractor · cancelled"]  # 1644.2


def test_s16_a_finished_building_its_owner_destroys_later_is_not_cancelled():
    destroyed = life(uid(230), Z, "Extractor", init=1699, done=2170, died=3000, killer=Z, killing=uid(230))
    back = life(uid(230, 2), Z, "Drone", born=3010)
    assert lines(game([destroyed, back])) == ["1. 12 1:15 Extractor", "2. 11 2:02 Drone"]  # CR-035: the Extractor's Drone


def test_s16_a_death_before_done_with_no_killer_or_another_killer_is_not_a_cancel():
    for killer, killing in ((None, None), (P, uid(999))):
        killed = life(uid(230), Z, "Extractor", init=1699, died=1896, killer=killer, killing=killing)
        assert lines(game([killed])) == ["1. 12 1:15 Extractor"]


def test_s16_a_cancelled_hatchery_too_and_a_cancelled_protoss_building_returns_no_worker():
    back = life(uid(230, 2), Z, "Drone", born=1913)
    assert lines(game([_cancelled(first="Hatchery"), back])) == ["1. 12 1:15 Hatchery · cancelled"]
    probe = life(uid(230, 2), P, "Probe", born=1913)  # even with the cancelled Gateway's index and recycle + 1
    assert lines(game([_cancelled(owner=P, first="Gateway"), probe]), P) == [
        "1. 12 1:13 Probe",
        "2. 12 1:15 Gateway · cancelled",
    ]


# --- S17 · AC-9: Chrono Boost (Rex's rule, D59a) --------------------------------------------------------------------

CORE, GATEWAY, NEXUS, FORGE = 68157441, 55312386, 59244545, uid(400)


def _wgr(chrono, target):
    units = [
        life(CORE, P, "CyberneticsCore", init=2179, done=3000),
        life(GATEWAY, P, "Gateway", init=928, done=1958),
        life(NEXUS, P, "Nexus", born=0),
        life(FORGE, P, "Forge", init=1000, done=1700),
    ]
    upgrades = [UpgradeDone(P, "WarpGateResearch", 9728, 1)]  # research [7488, 9728)
    return game(units, upgrades=upgrades, chronos=[Chrono(P, chrono, target)])


@pytest.mark.parametrize(
    ("chrono", "target", "marked"),
    [
        (7725, CORE, True),  # inside [7488, 9728)
        (7041, CORE, True),  # its last active loop, 7488, is the research's first
        (7040, CORE, False),  # 7040 + 448 = 7488 is not > 7488
        (9727, CORE, True),  # one loop before done
        (9728, CORE, False),  # at done: finished
        (9729, CORE, False),
        (7725, GATEWAY, False),  # a Gateway does not research it
    ],
)
def test_s17_a_chrono_on_the_researching_type_overlapping_the_research_marks_it(chrono, target, marked):
    step = next(s for s in build_order(_wgr(chrono, target), FIXES).of(P) if s.item == "WarpGateResearch")
    assert step.chrono_possible is marked
    assert step.line().startswith("4. 12 5:34 Warp Gate Research")  # the start never moves (loop 7488)
    assert step.line().endswith(" · chrono possible") is marked


def test_s17_units_are_marked_by_their_producer_type_and_the_window_is_half_open():
    probe = life(uid(500), P, "Probe", born=545)  # [276.2, 545)
    zealot = life(uid(501), P, "Zealot", born=2630)  # [2025.2, 2630)
    units = [
        life(NEXUS, P, "Nexus", born=0),
        life(GATEWAY, P, "Gateway", init=928, done=1958),
        life(FORGE, P, "Forge", init=10, done=500),
    ]
    marked = build_order(game([*units, probe, zealot], chronos=[Chrono(P, 518, NEXUS), Chrono(P, 2242, GATEWAY)]), FIXES)
    assert [s.line() for s in marked.of(P) if s.kind != "building"] == [
        "2. 12 0:12 Probe · chrono possible",
        "4. 12 1:30 Zealot · chrono possible",
    ]
    ends_before = build_order(game([*units, probe], chronos=[Chrono(P, 276 - 448, NEXUS)]), FIXES)  # last active 275
    wrong_type = build_order(game([*units, probe], chronos=[Chrono(P, 518, FORGE)]), FIXES)
    for order in (ends_before, wrong_type):
        assert not any(s.chrono_possible for s in order.of(P))


def test_s17_a_chrono_reads_its_targets_type_at_the_time_and_a_warp_gate_counts_as_a_gateway():
    units = [life(GATEWAY, P, "Gateway", init=928, done=1958), life(uid(502), P, "Zealot", born=6000)]  # [5395.2, 6000)
    changes = [TypeChange(GATEWAY, 5000, "Gateway", "WarpGate")]
    order = build_order(game(units, changes, chronos=[Chrono(P, 5500, GATEWAY)]), FIXES)
    assert [s.line() for s in order.of(P) if s.item == "Zealot"] == ["3. 12 4:00 Zealot · chrono possible"]


def test_s17_zerg_steps_are_never_marked():
    units = [life(uid(1), Z, "Hatchery", born=0), drone(2, 1000.2)]
    order = build_order(game(units, chronos=[Chrono(Z, 1000, uid(1))]), FIXES)
    assert [s.line() for s in order.of(Z)] == ["1. 12 0:44 Drone"]


# --- the graph: steps on nodes, morph nodes, the Player list (S08, S09, S11, S18, S19) ----------------------------


def _node(kind, node_id, *, source=None, start=0, player="Zed", type_="Drone", description=""):
    t = GameTime.from_seconds(start)
    values = {
        "Building": (("time", t), ("player", player), ("type", type_)),
        "Units": (("time", t), ("player", player), ("type", type_), ("count", "1"), ("supply", "1"), ("total at time", "1")),
        "Upgrade": (("time", t), ("player", player)),
        "Player": (("name", player), ("race", "Zerg"), ("region", "eu"), ("subregion", "1")),
        "Battle": (
            ("time", t),
            ("player", player),
            ("dead", "1"),
            ("p1 dead", "1"),
            ("p2 dead", "0"),
            ("supply dead", "1"),
            ("end time", t),
        ),
    }[kind]
    return Node(kind, node_id, node_id, description, (), values, None if kind == "Player" else t, source)


def _graph(*nodes):
    return Graph(nodes=tuple(nodes), links=())


def _steps(node):
    props = node_view(node, EXPORT)["properties"]
    return {k: props[k] for k in ZEROS if k in props}


ZEROS = {"step #": 0, "at supply": 0, "started at": "00:00:00", "steps": "", "supply range": ""}  # CR-035: + supply range


def test_s08_s09_each_step_sits_on_the_node_of_its_first_unit_and_every_node_of_the_kinds_carries_the_four_keys():
    units = [drone(100, 1000.2), drone(101, 1004.2), drone(102, 1100.2), life(uid(110), Z, "SpawningPool", init=1200, done=2230)]
    units += [drone(103, 1300.2)]
    order = build_order(game(units, upgrades=[UpgradeDone(Z, "zerglingmovementspeed", 4970, 1)]), FIXES)  # 4970 - 1769.6
    graph = _graph(
        _node("Player", "Player-1", source=NodeSource(pid=Z), description="Red Zerg build 9 units and killed 0 units."),
        _node("Units", "Units-1", source=NodeSource(unit_ids=(uid(100), uid(101), uid(102))), start=50),  # two lines
        _node("Units", "Units-2", source=NodeSource(unit_ids=(uid(103),)), start=60),  # one line
        _node("Units", "Units-3", source=NodeSource(unit_ids=(uid(999),)), start=500),  # no step
        _node("Building", "Building-1", source=NodeSource(unit_ids=(uid(110),)), start=53, type_="Spawning Pool"),
        _node("Upgrade", "Upgrade-1", source=NodeSource(pid=Z, upgrade="zerglingmovementspeed", loop=4970), start=142),
        _node("Battle", "Battle-1", start=70),
    )
    nodes = {n.id: n for n in with_build_order(graph, order, FIXES).nodes}
    assert _steps(nodes["Units-1"]) == {
        "step #": 1,
        "at supply": 12,
        "started at": "00:00:44",
        "steps": "1. 12 0:44 Drone ×2 / 2. 12 0:49 Drone",
        "supply range": "",
    }
    # CR-035 (D2a): the Pool (0:53) takes its Drone, so the steps after it are at 11
    assert _steps(nodes["Units-2"]) == {"step #": 4, "at supply": 11, "started at": "00:00:58", "steps": "", "supply range": ""}
    assert _steps(nodes["Units-3"]) == ZEROS
    assert _steps(nodes["Building-1"]) == {
        "step #": 3,
        "at supply": 12,
        "started at": "00:00:53",
        "steps": "",
        "supply range": "",
    }
    assert _steps(nodes["Upgrade-1"]) == {
        "step #": 5,
        "at supply": 11,
        "started at": "00:02:22",
        "steps": "",
        "supply range": "",
    }
    assert _steps(nodes["Battle-1"]) == {} and _steps(nodes["Player-1"]) == {}
    listed = [
        "Red Zerg build 9 units and killed 0 units.",
        "",
        "Build order to 6:00 (supply, time, item):",
        "1. 12 0:44 Drone ×2",
        "2. 12 0:49 Drone",
        "3. 12 0:53 Spawning Pool",
        "4. 11 0:58 Drone",
        "5. 11 2:22 Zergling Movement Speed",
    ]
    assert nodes["Player-1"].description.split("X_LD") == listed
    assert node_view(nodes["Player-1"], EXPORT)["description"].split("\n")[:3] == [
        "Red Zerg build 9 units and killed 0 units.",
        "",
        "Build order to 6:00 (supply, time, item):",
    ]


def test_d58a_a_line_whose_units_finish_in_two_windows_sits_only_on_the_first_units_node():
    order = build_order(game([drone(100, 1000.2), drone(101, 1005.2)]), FIXES)
    graph = _graph(
        _node("Units", "Units-1", source=NodeSource(unit_ids=(uid(100),)), start=50),
        _node("Units", "Units-2", source=NodeSource(unit_ids=(uid(101),)), start=60),
    )
    nodes = {n.id: n for n in with_build_order(graph, order, FIXES).nodes}
    assert [len(nodes[i].steps) for i in ("Units-1", "Units-2")] == [1, 0]
    assert nodes["Units-1"].steps[0].count == 2


def test_without_the_export_fix_no_node_gets_the_keys():
    node = _node("Units", "Units-1", source=NodeSource(unit_ids=(uid(1),)))
    assert not set(ZEROS) & set(node_view(node, frozenset({"P13"}))["properties"])


def test_s11_a_building_morph_is_a_building_node_at_its_start_its_id_continuing_the_building_sequence():
    units = [life(uid(1), Z, "Hatchery", born=0), life(uid(2), P, "Gateway", init=928, done=1958)]
    changes = [TypeChange(uid(1), 8145, "Hatchery", "Lair"), TypeChange(uid(2), 9888, "Gateway", "WarpGate")]
    order = build_order(game(units, changes), FIXES)
    graph = _graph(
        _node("Building", "Building-1", source=NodeSource(unit_ids=(uid(1),)), start=-71, player="Zed", type_="Hatchery"),
        _node("Building", "Building-7", source=NodeSource(unit_ids=(uid(2),)), start=41, player="Pat", type_="Gateway"),
        _node("Battle", "Battle-1", start=70),
    )
    nodes = with_build_order(graph, order, FIXES).nodes
    assert [n.id for n in nodes] == ["Building-1", "Building-7", "Building-8", "Building-9", "Battle-1"]
    lair, gate = nodes[2], nodes[3]
    assert (lair.name, lair.value("player"), lair.value("type"), lair.start.seconds) == (
        "Lair",
        "Zed",
        "Lair",
        306,
    )  # 8145 - 1276.8
    assert (gate.name, gate.value("player"), gate.value("type"), gate.start.seconds) == ("Warp Gate", "Pat", "Warp Gate", 434)
    assert _steps(lair) == {"step #": 1, "at supply": 12, "started at": "00:05:06", "steps": "", "supply range": ""}
    assert _steps(gate) == ZEROS  # after 6:00: a node, no step (D53b)
    assert _steps(nodes[0]) == ZEROS  # the Hatchery keeps its node, holds no step


def test_s11_a_morph_with_no_building_node_to_take_its_player_from_is_refused():
    order = build_order(game([life(uid(1), Z, "Hatchery", born=0)], [TypeChange(uid(1), 8145, "Hatchery", "Lair")]), FIXES)
    with pytest.raises(ValueError, match="no Building node holds unit"):
        with_build_order(_graph(), order, FIXES)


@pytest.mark.parametrize(("loops", "heading"), [(4032, "3:00"), (6205, "4:37"), (8064, "6:00"), (20000, "6:00")])
def test_s19_a_short_game_lists_its_steps_to_its_end(loops, heading):
    order = build_order(game([life(uid(1), Z, "SpawningPool", init=400)], loops=loops), FIXES)
    assert order.heading() == f"Build order to {heading} (supply, time, item):"


def test_s19_a_game_with_no_step_adds_no_list_and_every_node_carries_zeros():
    start = [life(uid(1), Z, "Hatchery", born=0), life(uid(2), Z, "Drone", born=0)]
    order = build_order(game(start, loops=100), FIXES)
    graph = _graph(
        _node("Player", "Player-1", source=NodeSource(pid=Z), description="Red Zerg."),
        _node("Player", "Player-2", source=NodeSource(pid=P), description="Blue Protoss."),
        _node("Building", "Building-1", source=NodeSource(unit_ids=(uid(1),)), start=-71),
        _node("Units", "Units-1", source=NodeSource(unit_ids=(uid(2),))),
    )
    after = with_build_order(graph, order, FIXES)
    assert [n.description for n in after.nodes[:2]] == ["Red Zerg.", "Blue Protoss."]
    assert [_steps(n) for n in after.nodes[2:]] == [ZEROS, ZEROS]


def test_s19_only_the_player_with_steps_gets_a_list():
    order = build_order(game([drone(100, 1000.2)]), FIXES)
    graph = _graph(
        _node("Player", "Player-1", source=NodeSource(pid=Z), description="Red Zerg."),
        _node("Player", "Player-2", source=NodeSource(pid=P), description="Blue Protoss."),
    )
    descriptions = [n.description for n in with_build_order(graph, order, FIXES).nodes]
    assert descriptions == ["Red Zerg.X_LDX_LDBuild order to 6:00 (supply, time, item):X_LD1. 12 0:44 Drone", "Blue Protoss."]


def test_the_step_properties_are_declared_after_the_workbooks_data_types():
    data_types = build_document(Graph((), (), export_fixes=frozenset({"BO1"})), config=load_config())["dataTypes"]
    assert list(data_types.items())[-5:] == [
        ("step #", "int"),
        ("at supply", "int"),
        ("started at", "time[h:m:s]"),
        ("steps", "string"),
        ("supply range", "string"),  # CR-035 (call 13)
    ]
    assert set(ZEROS).isdisjoint(build_document(Graph((), ()), config=load_config())["dataTypes"])


def test_the_current_graph_needs_the_exposed_values():
    with pytest.raises(ValueError, match="need the exposed values"):
        to_graph(AnalysisResult((), (), None, fixes=FIXES))


# --- Alcyone and spine (S01, S02, S07, S08, S09, S10, S11, S15, S17, S18) -----------------------------------------


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")


@pytest.fixture(scope="module")
def alcyone():
    _need(ALCYONE)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(ALCYONE), MS_SC)
        graph = to_graph(result)
    order = build_order(result.exposed, result.fixes)
    doc = json.loads(json.dumps(build_document(graph)))
    return result, order, graph, doc


@pytest.fixture(scope="module")
def alcyone_annotated(alcyone):
    """CR-035: the build order as the graph holds it, each compared step with its verdict (``to_graph``'s own steps)."""
    result, order, graph, _ = alcyone
    names = {n.source.pid: n.value("name") for n in graph.nodes if n.kind == "Player" and n.source and n.source.pid}
    return annotate(order, checks(result.exposed, order, names, {}, library()), supply_reading(result.exposed))


def test_s01_s02_s17_alcyone_matches_the_oracle_line_for_line(alcyone):
    _, order, _, _ = alcyone
    # CR-035 F1: a ≈ step's line also carries its range (the ≈ sets are S03's literals); without it, CR-034's oracle
    assert [replace(s, supply_range=None).line() for s in order.of(1)] == ALCYONE_LIL  # lilTiGGer: 50 steps
    assert [replace(s, supply_range=None).line() for s in order.of(2)] == ALCYONE_BLACK  # blacksquall: 68
    assert order.of(1)[5].line() == "6. 14 1:06 Zergling ×6 · about 14–16 supply"
    assert (len(ALCYONE_LIL), len(ALCYONE_BLACK)) == (50, 68)


def test_s01_alcyone_counts_and_anchors(alcyone):
    _, order, _, _ = alcyone
    lil = order.of(1)
    drones = [s for s in lil if s.item == "Drone"]
    assert (len(drones), sum(s.count for s in drones)) == (19, 40)
    counts = {i: sum(s.count for s in lil if s.item == i) for i in ("Overlord", "Queen", "Zergling", "Roach")}
    assert counts == {"Overlord": 11, "Queen": 6, "Zergling": 10, "Roach": 14}
    assert [(s.number, float(s.start)) for s in lil if s.item == "SporeCrawler"] == [(41, 6986.0), (42, 7003.0)]
    assert not any(s.chrono_possible for s in lil)


def test_s07_a_drone_later_used_for_a_building_is_still_its_own_step(alcyone):
    _, order, _, _ = alcyone
    lil = {s.number: s for s in order.of(1)}
    assert lil[2].unit_ids == (64225281,) and lil[2].line() == "2. 11 0:21 Drone"  # CR-035: the Pool's Drone is off
    # Vera's S07 example: 84148225 is in step 30's four (83886081 shares its start loop and has the lower id)
    assert sorted(lil[30].unit_ids) == [83886081, 84148225, 84410369, 84672513] and lil[30].line() == "30. 41 4:05 Drone ×4"


def test_s10_names_are_the_type_at_the_time(alcyone):
    _, order, _, _ = alcyone
    names = {s.name for s in order.steps}
    assert not names & {"Overseer", "Ravager", "Ravager Cocoon", "Hive", "Main base", "Warp Gate", "Adept Phase Shift"}
    assert next(s for s in order.of(2) if s.kind == "building" and s.item != "Pylon").name == "Gateway"
    assert order.of(1)[13].line() == "14. 22 2:27 Overlord"  # the legacy "Overseer"; CR-035 oracle §1.1: 22


def test_s11_alcyone_has_17_building_morph_nodes_and_only_the_lair_is_a_step(alcyone):
    _, order, graph, _ = alcyone
    assert [m.after for m in order.morphs].count("WarpGate") == 14
    assert sorted({m.after for m in order.morphs}) == ["GreaterSpire", "Hive", "Lair", "WarpGate"]
    morph_nodes = [n for n in graph.nodes if n.kind == "Building" and int(n.id.split("-")[1]) > 113]
    assert len(morph_nodes) == 17
    assert [(n.name, n.steps[0].number) for n in morph_nodes if n.steps] == [("Lair", 39)]
    assert (morph_nodes[0].start.seconds, morph_nodes[0].value("type")) == (306, "Lair")  # 6:03.6 - 57 s
    for morph, node in zip(order.morphs, morph_nodes, strict=True):  # each at its change - morph time
        assert node.start.seconds == int(morph.start // 22.4)


def test_s08_alcyone_spot_values_and_the_same_four_keys_on_every_node_of_a_type(alcyone):
    _, _, _, doc = alcyone
    by_id = {n["ID"]: n for n in doc["nodes"]}

    def steps_of(node):
        return {k: node["properties"][k] for k in ZEROS}

    pool = next(n for n in doc["nodes"] if n["name"] == "Spawning Pool · on supply")  # CR-035: its verdict ending
    assert steps_of(pool) == {"step #": 1, "at supply": 12, "started at": "00:00:18", "steps": "", "supply range": ""}
    assert pool["properties"]["time"] == "00:00:19"  # the existing value is unchanged
    lair = next(n for n in doc["nodes"] if n["name"] == "Lair")  # 5:06: after the 3:30 the build check covers
    # CR-035 (D2a, D6a; QA's re-based oracle §1.1, §1.2): the supply at the start, and the range on ≈ steps
    assert steps_of(lair) == {"step #": 39, "at supply": 54, "started at": "00:05:06", "steps": "", "supply range": ""}
    natural = next(n for n in doc["nodes"] if n["name"] == "Natural · on supply ≈")
    assert steps_of(natural) == {"step #": 7, "at supply": 19, "started at": "00:01:20", "steps": "", "supply range": "17–19"}
    gateway = next(n for n in doc["nodes"] if n["name"] == "Gateway · on supply" and n["properties"]["player"] == "blacksquall")
    assert steps_of(gateway) == {"step #": 6, "at supply": 16, "started at": "00:00:41", "steps": "", "supply range": ""}
    wgr = next(n for n in doc["nodes"] if n["name"] == "Warp Gate Research · done later")
    assert steps_of(wgr) == {  # one step: no list
        "step #": 63,
        "at supply": 66,
        "started at": "00:05:34",
        "steps": "",
        "supply range": "66–70",
    }
    lings = next(n for n in doc["nodes"] if n["type"] == "Units" and n["properties"]["step #"] == 6)
    assert (lings["name"], lings["properties"]["time"], lings["properties"]["at supply"]) == (
        "6 Zerglings · done",
        "00:01:20",
        14,
    )
    assert steps_of(by_id["Building-1"]) == ZEROS  # lilTiGGer's "Main base"
    for kind in ("Building", "Upgrade", "Units"):
        shapes = {tuple((k, type(v).__name__) for k, v in n["properties"].items()) for n in doc["nodes"] if n["type"] == kind}
        assert len(shapes) == 1, kind
        assert [(k, t) for k, t in next(iter(shapes)) if k in ZEROS] == [
            ("step #", "int"),
            ("at supply", "int"),
            ("started at", "str"),
            ("steps", "str"),
            ("supply range", "str"),
        ]
    for n in doc["nodes"]:
        if n["type"] not in ("Building", "Upgrade", "Units"):
            assert set(ZEROS).isdisjoint(n["properties"]), n["ID"]
    assert not [d for d in doc["detail"] if set(d["properties"]) & set(ZEROS)]  # none on the node face


def test_s09_alcyone_nodes_with_several_steps_list_them_in_order(alcyone, alcyone_annotated):
    _, _, graph, _ = alcyone
    line_of = {(s.player, s.number): s.line() for s in alcyone_annotated.steps}  # CR-035: with their verdicts
    multi = [n for n in graph.nodes if len(n.steps) > 1]
    assert multi and all(n.kind == "Units" for n in multi)
    for n in multi:
        assert [s.number for s in n.steps] == sorted(s.number for s in n.steps)
        assert _steps(n)["steps"] == " / ".join(line_of[(s.player, s.number)] for s in n.steps)
        assert _steps(n)["step #"] == n.steps[0].number


def test_s08_every_alcyone_step_is_on_exactly_one_node(alcyone):
    _, order, graph, _ = alcyone
    placed = [(s.player, s.number) for n in graph.nodes for s in n.steps]
    assert len(placed) == len(set(placed)) == 118
    assert set(placed) == {(s.player, s.number) for s in order.steps}


def test_s18_the_player_lists_are_the_node_steps(alcyone, alcyone_annotated):
    _, _, graph, doc = alcyone
    lil, black = (n["description"].split("\n") for n in doc["nodes"] if n["type"] == "Player")
    assert lil[:3] == ["Red Zerg build 938 units and killed 358 units.", "", "Build order to 6:00 (supply, time, item):"]
    # CR-035 (call 4): each list is the build order with each compared step's verdict added, in the same words as on
    # the nodes; without the verdicts it is CR-034's oracle, line for line
    assert lil[3:] == [s.line() for s in alcyone_annotated.of(1)] and lil[-1] == "50. 73 5:56 Roach ×5"
    assert [replace(s, verdict=None, supply_range=None).line() for s in alcyone_annotated.of(1)] == ALCYONE_LIL
    assert lil[3:8] == ["1. 12 0:18 Spawning Pool · on supply", "2. 11 0:21 Drone", "3. 12 0:26 Drone", "4. 13 0:29 Drone",
                        "5. 14 0:39 Overlord · on supply"]  # fmt: skip
    assert black[1:3] == ["", "Build order to 6:00 (supply, time, item):"]
    assert black[3:] == [s.line() for s in alcyone_annotated.of(2)]
    assert [replace(s, verdict=None, supply_range=None).line() for s in alcyone_annotated.of(2)] == ALCYONE_BLACK
    on_nodes = sorted(((s.player, s.number), s.line()) for n in graph.nodes for s in n.steps)
    assert [line for (player, _), line in on_nodes if player == 1] == lil[3:]
    assert [line for (player, _), line in on_nodes if player == 2] == black[3:]


def test_s21_building_alcyone_twice_gives_the_same_steps(alcyone):
    _, order, _, _ = alcyone
    with contextlib.redirect_stdout(io.StringIO()):
        again = build_order(analyse(load_replay(ALCYONE), MS_SC).exposed, FIXES)
    assert again == order


def test_d60a_an_estimated_start_goes_to_the_log_only():
    order = build_order(game(upgrades=[UpgradeDone(Z, "MadeUpUpgrade", 3000, 1)]), FIXES)
    assert order.estimated == (
        "CR-034: no build or research time for MadeUpUpgrade (player 1): its start is estimated at loop 3000",
    )
    assert [s.line() for s in order.of(Z)] == ["1. 12 2:13 Made Up Upgrade"]  # no note on the step (D60a)


def test_d63a_every_alcyone_upgrade_has_its_research_time(alcyone, capsys):
    result, order, _, _ = alcyone
    assert order.estimated == ()
    to_graph(result)
    assert "no build or research time" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("upgrade", "row"),
    [
        ("WarpGateResearch", ("WarpGateResearch", "100")),  # the id itself
        ("zerglingmovementspeed", ("zerglingmovementspeed", "79")),
        ("GlialReconstitution", ("Glial Reconstitution", "79")),  # a display-name row
        ("EvolveMuscularAugments", ("Muscular Augments", "64")),  # without "Evolve"
        ("AnabolicSynthesis", ("Anabolic Synthesis", "42.9")),
        ("ProtossGroundArmorsLevel2", ("ProtossGroundArmorLevel2", "145")),  # Armors / Armor
        ("ZergMeleeWeaponsLevel1", ("Melee Attacks Level 1", "114")),  # UPGRADE_ALIASES
        ("ZergGroundArmorsLevel3", ("Ground Carapace Level 3", "157")),
        ("overlordspeed", ("Pneumatized Carapace", "43")),
        ("MadeUpUpgrade", None),  # not in the sheet: D60a
    ],
)
def test_d63a_research_times_are_found_by_upgrade_id(alcyone, upgrade, row):
    result, _, _, _ = alcyone
    assert research_row(upgrade, result.exposed.tables.research_times) == row


def test_d63a_every_upgrade_the_chrono_table_names_and_every_alias_finds_its_row(alcyone):
    """Rex's round-2 P2: each upgrade id ``PRODUCERS`` names, the replay ids of his probe, and every alias reach a
    row of upgradesInfo.csv. sc2reader's data cannot give the full list for this replay version: it lists research
    commands (``ResearchCombatShield``), not the ids an UpgradeCompleteEvent writes (``ShieldWall``)."""
    result, _, _, _ = alcyone
    rows = result.exposed.tables.research_times
    units = {u for producer in ("Nexus", "Gateway", "RoboticsFacility", "Stargate") for u in PRODUCERS[producer]}
    upgrades = {u for made in PRODUCERS.values() for u in made} - units
    probe = {
        "ShieldWall", "PunisherGrenades", "zerglingattackspeed", "CentrificalHooks", "LurkerRange", "DiggingClaws",
        "overlordtransport", "BansheeCloak", "DrillClaws", "TerranBuildingArmor", "HighCapacityBarrels", "Burrow",
        "TunnelingClaws", "ChitinousPlating", "NeuralParasite", "Stimpack", "PersonalCloaking", "HiSecAutoTracking",
        "SmartServos", "TerranInfantryWeaponsLevel1", "TerranInfantryArmorsLevel1", "ZergFlyerWeaponsLevel3",
    }  # fmt: skip
    aliased = {a + ("Level1" if a.startswith("Zerg") else "") for a in UPGRADE_ALIASES}
    missing = sorted(u for u in upgrades | probe | aliased if research_row(u, rows) is None)
    assert missing == []
    assert research_row("AdeptPiercingAttack", rows) == ("Resonating Glaives", "100")
    assert research_row("ShieldWall", rows) == ("Combat Shield", "79")


def test_d63a_the_name_match_ignores_case():
    """The squash lowers the case: a replay id may differ from its row only in case (``zerglingmovementspeed``, all
    lower case, against a CamelCase row)."""
    assert research_row("zerglingmovementspeed", (("ZerglingMovementSpeed", "79"),)) == ("ZerglingMovementSpeed", "79")
    assert research_row("WARPGATERESEARCH", (("WarpGateResearch", "100"),)) == ("WarpGateResearch", "100")


def test_d63a_a_display_name_row_names_the_step():
    research = (("Pneumatized Carapace", "43"), ("Melee Attacks Level 1", "114"))
    exposed = replace(game(upgrades=[UpgradeDone(Z, "overlordspeed", 7206, 1)]), tables=TimeTables((), research, "", ""))
    assert lines(exposed) == ["1. 12 4:38 Pneumatized Carapace"]  # 7206 - 963.2 = 6242.8


def test_n0_a_start_before_the_game_keeps_its_sign():
    step = BuildStep(Z, 1, "unit", "Zergling", "Zergling", Fraction(-112), 12, (uid(1),))
    assert step.line() == "1. 12 -0:05 Zergling"
    node = _node("Units", "Units-1", source=NodeSource(unit_ids=(uid(1),)))
    assert _steps(replace(node, steps=(step,)))["started at"] == "00:00:00"


def test_p3_a_step_no_node_holds_is_logged(capsys):
    _need(SPINE)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(SPINE), MS_SC)
    to_graph(result)
    out = capsys.readouterr().out
    assert "CR-034: step 8 of player 1 (building Extractor) has no node; it is in the list only" in out  # cancelled
    assert "CR-034: step 60 of player 1 (upgrade GlialReconstitution) has no node; it is in the list only" in out


def test_the_exposed_values_are_computed_for_the_run_with_every_layer_fix_only():
    _need(SPINE)
    with contextlib.redirect_stdout(io.StringIO()):
        fixed = analyse(load_replay(SPINE), MS_SC)
        faithful = analyse(load_replay(SPINE), MS_SC, fixes=())
        partial = analyse(load_replay(SPINE), MS_SC, fixes=("P1",))
        asked = analyse(load_replay(SPINE), MS_SC, fixes=(), with_exposed=True)
    assert fixed.exposed is not None and asked.exposed is not None
    assert faithful.exposed is None and partial.exposed is None


def test_s15_spine_the_cancelled_extractor_and_the_returning_drone():
    _need(SPINE)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(SPINE), MS_SC)
    order = build_order(result.exposed, result.fixes)
    piliskner = order.of(1)
    assert [s.number for s in piliskner] == list(range(1, len(piliskner) + 1))
    cancelled = [s for s in piliskner if s.cancelled]
    assert [(s.item, s.unit_ids, s.second) for s in cancelled] == [("Extractor", (60293121,), 75)]
    assert cancelled[0].line().endswith(" 1:15 Extractor · cancelled · about 15–16 supply")  # CR-035 F1: after the notes
    assert not [s for s in order.steps if 60293122 in s.unit_ids]  # the Drone born at 1:25 comes back; nobody built it


def test_d63a_spine_upgrades_start_at_done_minus_their_research_time():
    """Rex's P2 on 6a92031: Pneumatized Carapace (``overlordspeed``) was step 52 at its finish, 5:21, under its raw
    id; Glial Reconstitution (done 7:39 - 79 s) was missing. Both are now steps at their start."""
    _need(SPINE)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(SPINE), MS_SC)
    order = build_order(result.exposed, result.fixes)
    upgrades = [s.line() for s in order.of(1) if s.kind == "upgrade"]
    assert upgrades == [
        "24. 35 3:23 Zergling Movement Speed",  # CR-035 oracle §1.3: 35
        "38. 57 4:38 Pneumatized Carapace",
        "60. 65 5:59 Glial Reconstitution",
    ]
    assert len(order.of(1)) == 60 and order.estimated == ()
