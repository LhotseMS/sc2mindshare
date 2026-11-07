"""CR-035 (AC2-AC6): pairing and verdicts, a player's build against a build order guide.

The expected values are QA's re-based oracle (``.scratch/qa/cr-035/alcyone-expected-rebased.md`` §2-§4, Vera) and
the scenario rows S07-S09, S11, S13-S15, S18-S21, S34, S35 of CR-035's Notes for QA, copied here as literals. The
fixture guides are checked by the guide check like a shipped one (``analysis.guides.parse``).
"""

import contextlib
import io
import os
import pathlib
from collections import Counter
from fractions import Fraction

import pytest

from sc2mindshare.analysis.build_check import compare, interval_verdict, supply_band, time_band
from sc2mindshare.analysis.build_steps import build_order
from sc2mindshare.analysis.fixes import LAYER_FIXES
from sc2mindshare.analysis.guides import library, parse
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
LIL, BLACK = 1, 2
GUIDES = {g.id: g for g in library()}
POOL12 = "zvp-12-pool-economic-liquipedia"
HATCH3 = "zvp-3-hatch-before-pool-liquipedia"
HATCH1 = "zvx-17-hatch-17-gas-17-pool-liquipedia"
STARGATE = "pvz-stargate-opener-project"
GNC = "pvz-gate-nexus-core-project"


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")


def _replay(path):
    _need(path)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(path), MS_SC)
    return result.exposed, build_order(result.exposed, result.fixes)


@pytest.fixture(scope="module")
def alcyone():
    return _replay(ALCYONE)


@pytest.fixture(scope="module")
def spine():
    return _replay(SPINE)


def _check(game, guide, player):
    exposed, order = game
    return compare(exposed, order, guide, player, picked=True)


def _rows(check):
    """(guide step, paired player step or None, verdict, Δ, ≈) per guide occurrence."""
    return [(r.guide_step, r.paired.step if r.paired else None, r.verdict, r.off, r.approx) for r in check.rows]


def _card(check):
    """The card's counts: one per guide step (AC2), and the extra steps."""
    counts = Counter(check.step_verdict(s) for s in check.guide.steps)
    return dict(counts), len({step for step, _ in check.extras})


def _guide(steps, horizon="3:00", race="Zerg", vs="Protoss", gid="fixture"):
    return parse(
        {
            "format_version": "1",
            "id": gid,
            "name": "Fixture",
            "race": race,
            "vs": vs,
            "era": "LotV",
            "patch": None,
            "as_of": "2026-11-07",
            "horizon": horizon,
            "source": {"kind": "project", "author": "QA", "created": "2026-11-07", "licence": "project"},
            "steps": steps,
        }
    )


# --- the bands (TD-35, TD-43, TD-38) ---------------------------------------------------------------------------------


def test_the_supply_bands():
    assert [supply_band(d) for d in (-3, -2, 2, 3, 5, 6)] == [
        "early",
        "on supply",
        "on supply",
        "a bit late",
        "a bit late",
        "late",
    ]


def test_s14_the_time_bands_at_their_edges():
    """O-2: Δt in whole seconds: +10 on time, +11 and +30 a bit late, +31 late, -10 on time, -11 early."""
    assert [time_band(d) for d in (10, 11, 30, 31, -10, -11)] == [
        "on time",
        "a bit late",
        "a bit late",
        "late",
        "on time",
        "early",
    ]


def test_an_interval_takes_the_band_nearest_on_supply_it_touches_and_straddling_is_approx():
    assert interval_verdict(1, 3, supply_band) == ("on supply", 1, True)  # Alcyone's natural Hatchery, 17-19 vs 16
    assert interval_verdict(-4, -2, supply_band) == ("on supply", -2, True)  # the Queen, 16-18 vs 20
    assert interval_verdict(0, 1, supply_band) == ("on supply", 0, False)  # one band: no ≈
    assert interval_verdict(3, 5, supply_band) == ("a bit late", 3, False)


# --- Alcyone (oracle §2-§3) -----------------------------------------------------------------------------------------


def test_s05_s07_s08_s20_liltigger_against_12_pool(alcyone):
    check = _check(alcyone, GUIDES[POOL12], LIL)
    assert _rows(check) == [
        (1, 1, "on supply", 0, False),
        *[(2, 6, "done", None, False)] * 6,
        (3, 20, "late", 15, False),  # S07: "15 supply late", the Extractor at 29 against 14
        (4, 5, "on supply", 0, False),
        (5, 7, "on supply", 1, True),  # S08: 17-19 against 16, Δ from 17
        (6, None, "missing", None, False),
        (7, 14, "a bit late", 3, False),  # S07: 22 against 19
        (8, 10, "on supply", -2, True),  # S08: the Queen pairs step 10, not 15 (the tie goes to the earlier)
    ]
    missing = check.rows_of(6)[0]
    assert (missing.done_later.item, int(missing.done_later.start / Fraction(112, 5))) == ("zerglingmovementspeed", 676)
    assert missing.moment == 250  # first 100 gas at 4:10
    assert _card(check) == ({"on supply": 4, "a bit late": 1, "late": 1, "done": 1, "missing": 1}, 7)
    assert sorted({step for step, _ in check.extras}) == [8, 9, 15, 16, 22, 23, 26]  # S20
    assert [item for item, _ in check.counted] == ["Drone"]  # counted, not graded
    assert check.graded_by == "supply"


def test_s06_s20_blacksquall_against_the_stargate_draft(alcyone):
    check = _check(alcyone, GUIDES[STARGATE], BLACK)
    assert _rows(check) == [
        (1, 4, "on supply", 0, False),
        (2, 6, "on supply", 0, False),
        (3, 8, "on supply", 0, False),
        (4, 13, "on supply", 1, True),
        (5, 14, "on supply", 0, False),
        (6, 27, "late", 10, False),
        (7, 15, "on supply", 0, False),
        (8, None, "missing", None, False),
        (9, 40, "done", None, False),
        (10, 49, "done", None, False),  # Oracle or Void Ray: the Void Ray
    ]
    assert int(check.rows_of(8)[0].done_later.start / Fraction(112, 5)) == 334  # Warp Gate done later at 5:34
    assert _card(check) == ({"on supply": 6, "late": 1, "done": 2, "missing": 1}, 13)
    assert sorted({step for step, _ in check.extras}) == [17, 20, 42, 43, 44, 45, 50, 52, 55, 56, 57, 58, 60]
    assert sorted(item for item, _ in check.counted) == ["Adept", "Probe", "Stalker", "Zealot"]


def test_s13_liltigger_against_the_mixed_3_hatch_guide(alcyone):
    check = _check(alcyone, GUIDES[HATCH3], LIL)
    assert _rows(check) == [
        (1, 5, "on supply", 1, False),
        (2, 7, "a bit late", 28, False),  # by time: 1:20 against 0:52
        (3, 26, "late", 119, False),  # by time: 3:24 against 1:25
        (4, 20, "late", 7, False),
        (5, 1, "early", -11, False),
        (6, 14, "on supply", -1, False),
        (7, None, "missing", None, False),
    ]
    assert [r.graded_by for r in check.rows[:3]] == ["supply", "time", "time"]
    assert check.graded_by == "time and supply"
    assert sorted({step for step, _ in check.extras}) == [22, 23]


TIMED = [
    {"item": "SpawningPool", "text": "12 Pool", "kind": "building", "supply": 12, "time": "0:08", "time_source": "source"},
    {"item": "Zergling", "text": "6 Lings", "kind": "unit", "count": 6, "trigger": "@100% Spawning Pool"},
    {"item": "Overlord", "text": "14 Overlord", "kind": "unit", "supply": 14, "time": "0:28", "time_source": "source"},
    {"item": "Hatchery", "text": "16 Hatchery", "kind": "building", "supply": 16, "time": "0:50", "time_source": "source"},
    {"item": "Queen", "text": "20 Queen", "kind": "unit", "supply": 20, "time": "1:43", "time_source": "source"},
    {"item": "Extractor", "text": "14 Extractor", "kind": "building", "supply": 14, "time": "2:34", "time_source": "source"},
    {"item": "Overlord", "text": "19 Overlord", "kind": "unit", "supply": 19, "time": "2:37", "time_source": "source"},
    {"item": "zerglingmovementspeed", "text": "@100 gas Metabolic Boost", "kind": "upgrade", "trigger": "@100 gas"},
]


def test_s14_a_timed_guide_is_graded_by_time_on_the_same_pairs(alcyone):
    check = _check(alcyone, _guide(TIMED, gid="zvp-12-pool-timed-test"), LIL)
    assert _rows(check) == [
        (1, 1, "on time", 10, False),
        *[(2, 6, "done", None, False)] * 6,
        (3, 5, "a bit late", 11, False),
        (4, 7, "a bit late", 30, False),
        (5, 10, "early", -11, False),
        (6, 20, "late", 31, False),
        (7, 14, "on time", -10, False),
        (8, None, "missing", None, False),
    ]
    assert check.graded_by == "time"
    assert int(check.rows_of(8)[0].done_later.start / Fraction(112, 5)) == 676  # 11:16


def test_s15_supply_and_time_inside_one_item_keep_the_order(alcyone):
    steps = [
        {"item": "Overlord", "text": "14 Overlord", "kind": "unit", "supply": 14},
        {"item": "Overlord", "text": "Overlord at 2:20", "kind": "unit", "time": "2:20", "time_source": "source"},
        {"item": "Overlord", "text": "31 Overlord", "kind": "unit", "supply": 31},
    ]
    check = _check(alcyone, _guide(steps, gid="zvp-overlord-mixed-test"), LIL)
    assert _rows(check) == [(1, 5, "on supply", 0, False), (2, 14, "on time", 7, False), (3, 22, "on supply", 0, False)]
    assert (23, "Overlord") in check.extras
    assert check.graded_by == "time and supply"


def test_s18_a_supply_step_never_made_is_missing_with_no_done_later(alcyone):
    """S18 names a 16 Spire, but lilTiGGer starts a Spire at 10:26 (the full start list): that one is done later. A
    Nydus Network, which he never makes, is the never-made case."""
    raw = [{"item": "NydusNetwork", "text": "16 Nydus Network", "kind": "building", "supply": 16}]
    check = _check(alcyone, _guide(raw), LIL)
    assert _rows(check) == [(1, None, "missing", None, False)] and check.rows[0].done_later is None
    spire = [{"item": "Spire", "text": "16 Spire", "kind": "building", "supply": 16}]
    assert int(_check(alcyone, _guide(spire), LIL).rows[0].done_later.start / Fraction(112, 5)) == 626


def test_s21_a_morph_pairs_on_what_was_made(alcyone):
    steps = [{"item": "Lair", "text": "54 Lair", "kind": "morph", "supply": 54}]
    check = _check(alcyone, _guide(steps, horizon="5:00"), LIL)
    assert _rows(check) == [(1, 39, "on supply", 0, False)]
    assert check.rows[0].paired.kind == "building morph"


def test_s35_a_trigger_inside_the_reach_and_minerals_read_like_gas(alcyone):
    """(a) 12 Pool with a 5:00 reach: 100 gas at 4:10, the window ends 5:30, Metabolic Boost started 11:16: missing,
    at its moment, done later. (e) @n minerals: the first sample with that many minerals."""
    raw = [{"item": "zerglingmovementspeed", "text": "@100 gas, Metabolic Boost", "kind": "upgrade", "trigger": "@100 gas"}]
    row = _check(alcyone, _guide(raw, horizon="5:00"), LIL).rows[0]
    assert (row.verdict, row.moment, int(row.done_later.start / Fraction(112, 5))) == ("missing", 250, 676)
    never = [{"item": "zerglingmovementspeed", "text": "@9000 gas", "kind": "upgrade", "trigger": "@9000 gas"}]
    assert _check(alcyone, _guide(never), LIL).rows[0].moment is None  # (b) the moment never came
    minerals = [{"item": "zerglingmovementspeed", "text": "@50 minerals", "kind": "upgrade", "trigger": "@50 minerals"}]
    assert _check(alcyone, _guide(minerals), LIL).rows[0].moment is not None
    other = [{"item": "zerglingmovementspeed", "text": "when ready", "kind": "upgrade", "trigger": "when you feel like it"}]
    assert _check(alcyone, _guide(other), LIL).rows[0].moment is None  # (d) other text cannot be evaluated


def test_s22_alcyone_suggestion_scores_as_exact_fractions(alcyone):
    scores = {gid: _check(alcyone, GUIDES[gid], LIL).score for gid in (POOL12, HATCH1, HATCH3)}
    assert scores == {POOL12: Fraction(5, 12), HATCH1: Fraction(1, 2), HATCH3: Fraction(79, 105)}
    scores = {gid: _check(alcyone, GUIDES[gid], BLACK).score for gid in (STARGATE, GNC)}
    assert scores == {STARGATE: Fraction(10, 33), GNC: Fraction(13, 30)}


# --- spine (oracle §4) ----------------------------------------------------------------------------------------------


def test_s20_s34_s36_spine_zerg_against_hatch_first(spine):
    check = _check(spine, GUIDES[HATCH1], 1)
    rows = _rows(check)
    assert rows[0] == (1, 2, "on supply", 0, False)
    assert rows[1] == (2, 7, "on supply", -1, False)
    assert rows[2] == (3, 14, "late", 6, False)  # Leo's re-base: the cancelled Extractor (step 8) never pairs
    assert rows[3:] == [
        (4, 5, "on supply", -1, False),
        (5, 11, "on supply", 0, False),
        (6, 24, "done", None, False),  # 21 @100 gas: a step with a trigger is done when made
        (7, 17, "done", None, False),  # the 2:37 Queen
        (7, None, "missing", None, False),  # the second Queen ...
    ]
    second = check.rows[-1]
    assert int(second.done_later.start / Fraction(112, 5)) == 588  # ... done later at 9:48 (O-9)
    assert (second.done_later.item, second.done_later.kind) == ("Queen", "unit")
    assert check.step_verdict(GUIDES[HATCH1].steps[6]) == "missing"  # a partly made count step counts once, missing
    assert check.extras == ((10, "Queen"), (15, "Hatchery"))  # the 1:37 Queen, before the Hatchery; no Extractor extra
    assert _card(check) == ({"on supply": 4, "late": 1, "done": 1, "missing": 1}, 2)  # Leo's re-base (S34)


def test_s19_spine_the_cancelled_extractor_never_pairs(spine):
    """Call 6, AC5: spine Zerg's step 8, the Extractor cancelled at 1:15, never counts as made: the guide's 17 Extractor
    pairs the next Extractor (step 14)."""
    check = _check(spine, GUIDES[HATCH1], 1)
    assert check.rows[2].paired.step == 14
    assert all(r.paired is None or r.paired.step != 8 for r in check.rows)


def test_s20_spine_protoss_against_gate_nexus_core(spine):
    check = _check(spine, GUIDES[GNC], 2)
    assert _rows(check) == [
        (1, 3, "on supply", 0, False),
        (2, 6, "on supply", 0, False),
        (3, 8, "on supply", 0, False),
        (4, 19, "a bit late", 3, False),  # 22-24 against 19: one band, no ≈
        (5, 12, "on supply", 0, False),
        (6, 16, "on supply", 0, False),
        (7, 14, "on supply", -2, False),
        (8, 24, "done", None, False),
        (9, None, "optional", None, False),  # the optional Adept, not made: no verdict, not missing
    ]
    extras = Counter(item for _, item in check.extras)
    assert extras == {"Pylon": 4, "Gateway": 7, "RoboticsFacility": 1}
    assert dict(check.counted)["WarpGate"] == 4  # O-12: counted, not graded


def test_s22_spine_suggestion_scores_as_exact_fractions(spine):
    """spine Protoss as Leo's O-11; spine Zerg as Leo re-based it with the cancelled Extractor never pairing (call 6):
    hatch-first ahead of 12 Pool by 5/168."""
    protoss = {gid: _check(spine, GUIDES[gid], 2).score for gid in (GNC, STARGATE)}
    assert protoss == {GNC: Fraction(7, 20), STARGATE: Fraction(11, 24)}
    zerg = {gid: _check(spine, GUIDES[gid], 1).score for gid in (HATCH1, POOL12, HATCH3)}
    assert zerg == {HATCH1: Fraction(11, 42), POOL12: Fraction(7, 24), HATCH3: Fraction(31, 70)}
    assert zerg[POOL12] - zerg[HATCH1] == Fraction(5, 168)


def test_spine_zerg_against_12_pool_pairs_the_extractor_after_the_cancelled_one(spine):
    check = _check(spine, GUIDES[POOL12], 1)
    assert _rows(check)[7] == (3, 14, "late", 9, False)


# --- synthetic games ------------------------------------------------------------------------------------------------

Z, P = 1, 2
BUILD = {"Drone": "12", "Zergling": "17", "Queen": "36", "Extractor": "21", "SpawningPool": "46", "Hatchery": "71"}


def uid(index, recycle=1):
    return index << 18 | recycle


def life(unit_id, owner, first_type, *, born=None, init=None, done=None, died=None, killer=None, killing=None):
    return UnitLife(unit_id, owner, first_type, born, init, done, died, killer, killing, 0, 0, False)


def game(units=(), changes=(), loops=20000, build=BUILD):
    players = (PlayerContext(Z, 0, "Zerg", "Protoss"), PlayerContext(P, 1, "Protoss", "Zerg"))
    tables = TimeTables(tuple(build.items()), (), "", "", (), ())
    context = GameContext(92440, "5.0.13.92440", loops, "1v1", 1, True, players)
    stats = (StatsSample(Z, 1, 12.0, 14, 12, 50, 0, 0, 0, 0, 0),)
    return Exposed(context, tuple(units), tuple(changes), (), stats, (), (), tables)


def _synthetic(exposed, steps, horizon="3:00"):
    return compare(exposed, build_order(exposed, LAYER_FIXES), _guide(steps, horizon=horizon), Z, picked=True)


EXTRACTOR = [{"item": "Extractor", "text": "14 Extractor", "kind": "building", "supply": 14}]


def test_s19_a_cancelled_step_never_pairs_and_a_later_one_is_done_later():
    cancelled = life(uid(1), Z, "Extractor", init=1000, died=1200, killer=Z, killing=uid(1))
    check = _synthetic(game([cancelled]), EXTRACTOR)
    assert _rows(check) == [(1, None, "missing", None, False)] and check.rows[0].done_later is None
    later = life(uid(2), Z, "Extractor", init=6000)  # 4:27, after the 3:30 window
    check = _synthetic(game([cancelled, later]), EXTRACTOR)
    assert check.rows[0].verdict == "missing" and check.rows[0].done_later.start == 6000
    assert check.extras == ()  # the cancelled Extractor is not an extra either


def test_s09_a_step_whose_start_is_only_estimated_is_not_compared():
    no_time = dict(BUILD)
    no_time.pop("Queen")
    queen = life(uid(1), Z, "Queen", born=2000)
    check = _synthetic(game([queen], build=no_time), [{"item": "Queen", "text": "17 Queen", "kind": "unit", "supply": 17}])
    assert _rows(check) == [(1, 1, "not compared", None, False)]
    assert _card(check)[0] == {"not compared": 1}


def test_s11_a_unit_morph_pairs_with_a_guide_step_of_its_result():
    ling = life(uid(1), Z, "Zergling", born=1000)
    changes = [TypeChange(uid(1), 2000, "Zergling", "BanelingCocoon"), TypeChange(uid(1), 2300, "BanelingCocoon", "Baneling")]
    steps = [{"item": "Baneling", "text": "Baneling", "kind": "morph", "trigger": "when you like"}]
    check = _synthetic(game([ling], changes), steps)
    assert check.rows[0].verdict == "done" and check.rows[0].paired.kind == "unit morph"


def test_a_game_that_ends_before_the_reach_marks_the_unmade_steps_not_compared():
    pool = life(uid(1), Z, "SpawningPool", init=400)
    steps = [
        {"item": "SpawningPool", "text": "12 Pool", "kind": "building", "supply": 12},
        {"item": "Extractor", "text": "14 Extractor", "kind": "building", "supply": 14},
    ]
    check = _synthetic(game([pool], loops=3000), steps)  # the game ends at 2:13, before 3:30
    assert [r.verdict for r in check.rows] == ["on supply", "not compared (game ended)"]
    assert check.game_second == 133


def test_s34_a_count_step_made_in_full_counts_once_as_done():
    pool = life(uid(1), Z, "SpawningPool", init=400)  # done at 400 + 1030.4 loops
    queens = [life(uid(10 + k), Z, "Queen", born=2300 + 806 + k * 30) for k in range(3)]
    steps = [
        {"item": "SpawningPool", "text": "12 Pool", "kind": "building", "supply": 12},
        {"item": "Queen", "text": "3 Queens", "kind": "unit", "count": 3, "trigger": "@100% Spawning Pool"},
    ]
    check = _synthetic(game([pool, *queens]), steps)
    assert [r.verdict for r in check.rows_of(2)] == ["done", "done", "done"]
    assert check.step_verdict(check.guide.steps[1]) == "done"
    two = _synthetic(game([pool, *queens[:2]]), steps)
    assert [r.verdict for r in two.rows_of(2)] == ["done", "done", "missing"]
    assert two.step_verdict(two.guide.steps[1]) == "missing" and two.rows_of(2)[2].done_later is None


# --- the guide for each player (AC7, AC10; S22, S23, S25, S26) -----------------------------------------------------

from sc2mindshare.analysis.build_check import checks, suggestion_key
from sc2mindshare.domain.guides import BuildCheck, NoBuildCheck

NAMES = {LIL: "lilTiGGer", BLACK: "blacksquall"}


def _picks(game, named=None, guides=None):
    exposed, order = game
    out = checks(exposed, order, NAMES, named or {}, guides if guides is not None else tuple(GUIDES.values()))
    return [(c.guide.id, c.picked) if isinstance(c, BuildCheck) else (c.value, c.line) for c in out]


def test_s22_with_no_guide_named_each_player_gets_the_closest_suggested(alcyone, spine):
    assert _picks(alcyone) == [(POOL12, False), (STARGATE, False)]
    assert _picks(spine) == [(HATCH1, False), (GNC, False)]  # vs Any counts as a match


def test_s22_a_named_guide_is_picked_and_the_other_player_still_gets_a_suggestion(alcyone):
    assert _picks(alcyone, {LIL: HATCH3}) == [(HATCH3, True), (STARGATE, False)]


def test_s23_the_library_order_does_not_change_the_picks(alcyone):
    assert _picks(alcyone, guides=tuple(reversed(list(GUIDES.values())))) == _picks(alcyone)


def test_s23_an_exact_tie_goes_to_the_exact_matchup_then_the_id(alcyone):
    """Two guides with the same steps tie exactly; the key is (score, exact matchup before vs Any, id)."""
    steps = [{"item": "Overlord", "text": "14 Overlord", "kind": "unit", "supply": 14}]
    a, b = _guide(steps, gid="tie-b"), _guide(steps, gid="tie-a")
    assert _picks(alcyone, guides=(a, b))[0] == ("tie-a", False)
    any_vs = _guide(steps, gid="tie-0", vs="Any")
    assert _picks(alcyone, guides=(any_vs, a))[0] == ("tie-b", False)  # the exact matchup beats a lower id with vs Any


def test_s23_the_scores_and_their_key_are_exact_fractions(alcyone):
    """The score is a Fraction (1/10 + 2/10 equals 3/10 as fractions, not as floats), and so is the key's first part."""
    check = _check(alcyone, GUIDES[POOL12], LIL)
    assert type(check.score) is Fraction and suggestion_key(check) == (Fraction(5, 12), 0, POOL12)


def test_s25_a_guide_for_another_matchup_gives_no_build_check_and_the_other_player_is_unchanged(alcyone):
    assert _picks(alcyone, {LIL: STARGATE}) == [
        (
            "none, other matchup",
            (
                'No build check: the build order guide "Gate, Nexus, Core into Stargate (PvZ)" is for Protoss vs Zerg, '
                "and lilTiGGer played Zerg vs Protoss."
            ),
        ),
        (STARGATE, False),
    ]
    exposed, order = alcyone
    alone = checks(exposed, order, NAMES, {}, tuple(GUIDES.values()))[1]
    faulted = checks(exposed, order, NAMES, {LIL: STARGATE}, tuple(GUIDES.values()))[1]
    assert alone == faulted


def test_s25_a_named_file_not_found_or_unreadable(alcyone, tmp_path):
    missing = tmp_path / "nope.benchmark.json"
    assert _picks(alcyone, {LIL: str(missing)})[0] == (
        "none, file not found",
        f'No build check: the build order guide file "{missing}" was not found.',
    )
    bad = tmp_path / "bad.benchmark.json"
    bad.write_text("{not json", encoding="utf-8")
    assert _picks(alcyone, {LIL: str(bad)})[0] == (
        "none, file unreadable",
        f'No build check: the build order guide file "{bad}" could not be read: it is not a JSON file.',
    )
    import json

    v5 = tmp_path / "v5.benchmark.json"
    data = json.loads((CHECKOUT / "src/sc2mindshare/config/guides" / f"{POOL12}.benchmark.json").read_text(encoding="utf-8"))
    data["steps"][2].pop("supply")
    v5.write_text(json.dumps(data), encoding="utf-8")
    value, line = _picks(alcyone, {LIL: str(v5)})[0]
    assert (value, line.endswith("could not be read: Step 3: give one of supply, time or trigger.")) == (
        "none, file unreadable",
        True,
    )
    assert "benchmark" not in line.replace(str(v5), "")


def test_s25_a_matchup_no_guide_covers():
    players = (PlayerContext(Z, 0, "Zerg", "Terran"), PlayerContext(P, 1, "Terran", "Zerg"))
    exposed = game()
    exposed = Exposed(
        GameContext(92440, "5.0.13.92440", 20000, "1v1", 1, True, players),
        exposed.units,
        exposed.type_changes,
        exposed.upgrades,
        exposed.stats,
        exposed.supply,
        exposed.chronos,
        exposed.tables,
    )
    out = checks(exposed, build_order(exposed, LAYER_FIXES), {}, {}, tuple(GUIDES.values()))
    # vs Any covers Zerg vs Terran; the empty game runs past the window (14:52), so it is compared: every step missing
    assert isinstance(out[0], BuildCheck) and out[0].guide.id == HATCH1
    assert {r.verdict for r in out[0].rows} == {"missing"}
    assert out[1] == NoBuildCheck(
        P, "none, no build order guide for TvZ", "No build check: there is no build order guide for Terran vs Zerg yet."
    )


def test_s25_a_game_too_short_for_the_first_step():
    """Nothing paired, and the game ended (0:15) before the moment of the guide's first step (20 supply, which the
    player never reaches)."""
    steps = [{"item": "Queen", "text": "20 Queen", "kind": "unit", "supply": 20}]
    exposed = game(loops=336)
    out = checks(exposed, build_order(exposed, LAYER_FIXES), {Z: "Zed"}, {}, (_guide(steps),))
    assert out[0] == NoBuildCheck(
        Z,
        "none, game too short",
        "No build check: the game ended at 0:15, before the first step of the build order guide (20 Queen).",
    )


def test_s26_a_fault_in_the_comparison_is_raised_not_turned_into_a_reason(alcyone, monkeypatch):
    import sc2mindshare.analysis.build_check as bc

    def broken(*args, **kwargs):
        raise RuntimeError("injected")

    monkeypatch.setattr(bc, "compare", broken)
    exposed, order = alcyone
    with pytest.raises(RuntimeError, match="injected"):
        checks(exposed, order, NAMES, {LIL: POOL12}, tuple(GUIDES.values()))


# --- commit 6c: Leo's and Kevin's answers of 2026-11-07 -------------------------------------------------------------


def test_too_short_takes_the_earlier_of_the_first_moment_and_the_window_edge():
    """Nothing paired, a first step whose moment never comes: too short only if the game ends before the reach + 30 s
    (3:30); a game past it is compared, every step missing."""
    steps = [{"item": "Queen", "text": "20 Queen", "kind": "unit", "supply": 20}]
    short = game(loops=4700)  # 3:29
    out = checks(short, build_order(short, LAYER_FIXES), {Z: "Zed"}, {}, (_guide(steps),))
    assert isinstance(out[0], NoBuildCheck) and out[0].value == "none, game too short"
    long = game(loops=4704)  # 3:30
    out = checks(long, build_order(long, LAYER_FIXES), {Z: "Zed"}, {}, (_guide(steps),))
    assert isinstance(out[0], BuildCheck) and [r.verdict for r in out[0].rows] == ["missing"]


def test_a_rich_geyser_building_pairs_as_its_base_and_takes_its_drone():
    rich = life(uid(1), Z, "ExtractorRich", init=1000)
    drone = life(uid(2), Z, "Drone", born=1369)  # started at 1100.2
    exposed = game([rich, drone])
    order = build_order(exposed, LAYER_FIXES)
    assert [s.supply for s in order.of(Z)] == [12, 11]  # the rich Extractor takes its Drone, like an Extractor
    check = compare(exposed, order, _guide(EXTRACTOR), Z, picked=True)
    assert _rows(check) == [(1, 1, "on supply", -2, False)]
    assert check.rows[0].paired.item == "Extractor"
    trigger = [*EXTRACTOR, {"item": "Drone", "text": "Drone", "kind": "worker", "trigger": "@100% Extractor"}]
    moment = compare(exposed, order, _guide(trigger), Z, picked=True).rows[1].moment
    assert moment == Fraction(1000) / Fraction(112, 5) + 21  # the base Extractor's build time


def test_s35c_a_trigger_on_a_building_the_guide_does_not_list_uses_the_players_own(alcyone):
    """@100% Spire with no Spire step: lilTiGGer's own Spire, started at loop 14039 (10:26), plus 71 s."""
    steps = [{"item": "Mutalisk", "text": "@100% Spire: Mutalisks", "kind": "unit", "trigger": "@100% Spire"}]
    row = _check(alcyone, _guide(steps), LIL).rows[0]
    assert row.moment == Fraction(14039) / Fraction(112, 5) + 71


def test_the_trigger_fallback_skips_a_cancelled_building_and_has_no_moment_without_one():
    cancelled = life(uid(1), Z, "Extractor", init=1000, died=1200, killer=Z, killing=uid(1))
    steps = [{"item": "Drone", "text": "Drone", "kind": "worker", "trigger": "@100% Extractor"}]
    assert _synthetic(game([cancelled]), steps).rows[0].moment is None
    built = life(uid(2), Z, "Extractor", init=1500)
    assert _synthetic(game([cancelled, built]), steps).rows[0].moment == Fraction(1500) / Fraction(112, 5) + 21


def test_the_kth_missing_occurrence_takes_the_kth_later_start():
    pool = life(uid(1), Z, "SpawningPool", init=400)
    queens = [life(uid(10), Z, "Queen", born=3106), life(uid(11), Z, "Queen", born=10000)]  # 2:22 in, 7:10 later
    steps = [
        {"item": "SpawningPool", "text": "12 Pool", "kind": "building", "supply": 12},
        {"item": "Queen", "text": "3 Queens", "kind": "unit", "count": 3, "trigger": "@100% Spawning Pool"},
    ]
    rows = _synthetic(game([pool, *queens]), steps).rows_of(2)
    assert [r.verdict for r in rows] == ["done", "missing", "missing"]
    assert rows[1].done_later is not None and rows[1].done_later.start == 10000 - Fraction(4032, 5)
    assert rows[2].done_later is None  # the later starts ran out
