"""CR-023 (T22): the layer fixes, each switched by its ledger id (analysis.fixes.LAYER_FIXES)."""

import contextlib
import dataclasses
import io
import os
import pathlib
from types import SimpleNamespace

import pytest

from sc2mindshare.analysis.build_check import annotate
from sc2mindshare.analysis.build_steps import build_order, supply_reading
from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.detectors.detectors import BaseDetector
from sc2mindshare.analysis.exports.node import X_LD
from sc2mindshare.analysis.fixes import FIXES, LAYER_FIXES
from sc2mindshare.analysis.run import AnalysisResult, analyse, legacy_csv
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.exposed import Exposed, GameContext, TimeTables
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"


def need(path):
    """A missing input skips, or fails under SC2MS_REQUIRE_GOLDEN=1 (the harness's rule, QA design §1.4)."""
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")


def test_the_layer_fixes_in_ledger_order():
    assert LAYER_FIXES == (
        "P1", "P1b", "P1c", "S1", "P8", "P2", "P11", "N1", "P10", "S6", "P9", "P10b", "S7", "S8", "P10c", "G1", "F1", "F2",
        "E1", "CG1",
    )  # fmt: skip


# --- the switch itself (Morgan's G6 on acd13bc) -------------------------------------------------------------


def test_a_result_carries_its_layer_fixes_and_a_fixed_one_cannot_feed_the_bug_faithful_outputs():
    """P2: the bug-faithful outputs (the legacy CSV oracle, the graph without fixes) need a result with no
    layer fix; a mixed run is refused, not only betrayed by P1's visible names."""
    fixed = AnalysisResult((), (), None, fixes=frozenset({"P1"}))
    with pytest.raises(ValueError, match="bug-faithful"):
        legacy_csv(fixed)
    with pytest.raises(ValueError, match="bug-faithful"):
        to_graph(fixed, fixes=())
    assert to_graph(AnalysisResult((), (), None), fixes=()).nodes == ()  # no layer fix: fine
    assert AnalysisResult((), (), None).fixes == frozenset()


def test_to_graph_takes_only_the_two_pure_combinations_unless_a_mix_is_asked_for():
    """Morgan's G6 N1 on d6ca6b3: the other direction too. Layer and graph fixes all on, or all off;
    any other combination (a faithful result with the graph fixes, a partial layer set, half the graph
    fixes) needs ``mixed=True``."""
    # CR-034: a graph with the graph fixes carries the build order, made from the exposed values (here: a game
    # with nothing in it)
    empty = Exposed(GameContext(0, "", 0, "1v1", 1, False, ()), (), (), (), (), (), (), TimeTables((), (), "", ""))
    faithful = AnalysisResult((), (), None, empty)
    full = AnalysisResult((), (), None, empty, fixes=frozenset(LAYER_FIXES))
    partial = AnalysisResult((), (), None, empty, fixes=frozenset({"P1", "P1b"}))  # any proper subset
    for result, fixes in ((faithful, None), (faithful, FIXES), (partial, None), (full, FIXES[:1]), (partial, ())):
        with pytest.raises(ValueError, match="mixed|bug-faithful"):
            to_graph(result, fixes=fixes)
    assert to_graph(full).nodes == () and to_graph(full, fixes=FIXES).nodes == ()
    assert to_graph(faithful, fixes=()).nodes == ()
    assert to_graph(partial, mixed=True).nodes == () and to_graph(faithful, fixes=FIXES, mixed=True).nodes == ()


def test_unknown_fix_ids_are_refused():
    """N1: a misspelt id would otherwise switch nothing on, silently."""
    with pytest.raises(ValueError, match="unknown layer fix"):
        analyse(object(), MS_SC, fixes=("p1",))
    with pytest.raises(ValueError, match="unknown layer fix"):
        detectors.createDetectors("replay", ("P1", "P99"))


def test_create_detectors_takes_its_fixes_explicitly():
    """N0: no default, since analyse's default (all on) and an 'off' default here would disagree."""
    with pytest.raises(TypeError):
        detectors.createDetectors("replay")  # type: ignore[call-arg]


# --- P1: getClosestBase compares real distances ------------------------------------------------------------


class _Base:
    def __init__(self, name, x, y, born_s=0):
        self.name, self.location = name, (x, y)
        self.bornEvent = SimpleNamespace(frame=int(born_s * 22.4) + 1)  # a loop inside that second

    def minDistance(self, loc):  # the legacy Base's method name
        return ((self.location[0] - loc[0]) ** 2 + (self.location[1] - loc[1]) ** 2) ** 0.5


BASES = {"p1": [_Base("Main", 0, 0), _Base("Natural", 100, 0)], "p2": [_Base("Main", 50, 50), _Base("Natural", 10, 10)]}


def _closest(location, fixes, bases=BASES, battle_start=None):
    detector = SimpleNamespace(bases=bases, ctx=SimpleNamespace(fixes=frozenset(fixes)))
    return BaseDetector.getClosestBase(detector, SimpleNamespace(location=location), battle_start)


@pytest.mark.parametrize(
    ("location", "nearest"), [((1, 1), ("p1", 0)), ((99, 2), ("p1", 1)), ((48, 47), ("p2", 0)), ((11, 9), ("p2", 1))]
)
def test_p1_the_nearest_base_wins(location, nearest):
    player, index = nearest
    assert _closest(location, {"P1"}) is BASES[player][index]


def test_p1_a_tie_keeps_the_first_base_iterated():
    assert _closest((50, -60), {"P1"}) is BASES["p1"][0]  # 78.1 from Main and from Natural; the others are farther


def test_p1_off_is_bug_faithful_the_second_base_iterated_always_wins():
    assert all(_closest(loc, ()) is BASES["p1"][1] for loc in [(1, 1), (48, 47), (11, 9)])


# --- P1b (D8a): only a base that existed at the battle's start --------------------------------------------

LATER = {"p1": [_Base("Main", 0, 0, born_s=0), _Base("Natural", 10, 0, born_s=120)]}


def test_p1b_a_base_started_after_the_battle_is_skipped():
    assert _closest((9, 0), {"P1", "P1b"}, LATER, battle_start=100) is LATER["p1"][0]  # Natural only at 120 s


def test_p1b_a_base_started_at_the_battle_start_counts():
    assert _closest((9, 0), {"P1", "P1b"}, LATER, battle_start=120) is LATER["p1"][1]


def test_p1b_off_or_without_a_battle_start_skips_nothing():
    assert _closest((9, 0), {"P1"}, LATER, battle_start=100) is LATER["p1"][1]
    assert _closest((9, 0), {"P1", "P1b"}, LATER) is LATER["p1"][1]


# --- P1c (D10a): only a base whose town hall stands at the battle's start ------------------------------------


def _town_hall(died_s=None):
    return SimpleNamespace(
        died_at=None if died_s is None else int(died_s * 22.4) + 1, _type_class=SimpleNamespace(name="Nexus"), id=1
    )


def _real_base(started_s, died_s=None):
    from sc2mindshare.analysis.mindshare import Base

    hall = _town_hall(died_s)
    event = SimpleNamespace(unit=hall, frame=int(started_s * 22.4) + 1, second=started_s, player="p", location=(0, 0))
    return Base(event, 2)


def test_p1c_a_town_hall_stands_from_its_start_until_its_death_second():
    base = _real_base(340, died_s=486)
    assert [base.standsAt(s) for s in (339, 340, 486, 487)] == [False, True, True, False]  # dies in 486: still stood


def test_p1c_a_rebuilt_town_hall_stands_again():
    base = _real_base(340, died_s=486)
    base.newBase(SimpleNamespace(unit=_town_hall(), frame=int(567 * 22.4) + 1, location=(0, 0)))
    assert [base.standsAt(s) for s in (514, 566, 567, 900)] == [False, False, True, True]


class _Standing(_Base):
    def __init__(self, name, x, y, standing):
        super().__init__(name, x, y)
        self.standing = standing

    def standsAt(self, second):
        return second in self.standing


def test_p1c_a_base_not_standing_at_the_start_is_skipped():
    bases = {"p": [_Standing("Main", 0, 0, range(999)), _Standing("3rd", 10, 0, range(486))]}
    assert _closest((9, 0), {"P1", "P1b"}, bases, battle_start=514) is bases["p"][1]  # founded, so P1b keeps it
    assert _closest((9, 0), {"P1", "P1b", "P1c"}, bases, battle_start=514) is bases["p"][0]


@pytest.fixture(scope="module")
def battle_names():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    names = {}
    rows = (("faithful", ()), ("p1", ("P1",)), ("p1b", ("P1", "P1b")), ("p1c", ("P1", "P1b", "P1c")), ("fixed", LAYER_FIXES))
    for label, fixes in rows:  # one run per row, so each test sees its own row's names (P2 also renames battles)
        with contextlib.redirect_stdout(io.StringIO()):
            result = analyse(load_replay(ALCYONE), MS_SC, fixes=fixes)
            graph = to_graph(result, fixes=() if not fixes else None, mixed=fixes != LAYER_FIXES)  # P1 alone is a mix
        names[label] = {n.id: n.name for n in graph.nodes if n.kind == "Battle"}
    return names


def test_p1_on_alcyone_the_battles_name_their_nearest_base(battle_names):
    """The predicted renames of the P1 entry (CHANGES.md), a few pinned; the goldens hold all 30."""
    assert len(battle_names["p1"]) == 30
    assert all(name.endswith(" near lilTiGGer Natural") for name in battle_names["faithful"].values())
    fixed = battle_names["p1"]
    assert fixed["Battle-1"] == "Zealot killed ling near blacksquall Natural"
    assert fixed["Battle-6"] == "Adept killed Drone near lilTiGGer 3rd base"
    assert fixed["Battle-22"] == "lings Roachs Hydralisks Overseers Overlords died near lilTiGGer Main base"
    assert fixed["Battle-28"] == "ling killed Pylon near blacksquall Main base"
    assert not any(name.endswith(" near lilTiGGer Natural") for name in fixed.values())
    strip = {k: v.rsplit(" near ", 1)[0] for k, v in fixed.items()}
    assert strip == {k: v.rsplit(" near ", 1)[0] for k, v in battle_names["faithful"].items()}  # only the base part


def test_p1b_on_alcyone_seven_battles_name_a_base_that_existed(battle_names):
    """The P1b entry (CHANGES.md): 7 names change from P1's, the other 23 stay."""
    p1, fixed = battle_names["p1"], battle_names["p1b"]
    changed = {k for k in fixed if fixed[k] != p1[k]}
    assert changed == {"Battle-8", "Battle-9", "Battle-10", "Battle-15", "Battle-16", "Battle-18", "Battle-19"}
    assert p1["Battle-9"] == "VoidRay killed Overlord near blacksquall 5th base"  # started at 762 s
    assert fixed["Battle-9"] == "VoidRay killed Overlord near blacksquall Natural"  # the battle starts at 384 s
    assert fixed["Battle-8"] == "Adept killed ling near blacksquall Main base"  # its 3rd base started 2 s later
    assert fixed["Battle-18"] == "VoidRay killed Overseer near lilTiGGer 5th base"


def test_p1c_on_alcyone_battle_15_names_the_standing_natural(battle_names):
    """The P1c entry (CHANGES.md): only Battle-15 changes from P1b's names; Battle-13, which starts in the
    second blacksquall's 3rd Nexus dies, keeps the 3rd base."""
    p1b, fixed = battle_names["p1b"], battle_names["p1c"]
    assert {k for k in fixed if fixed[k] != p1b[k]} == {"Battle-15"}
    assert (p1b["Battle-15"], fixed["Battle-15"]) == (
        "VoidRay killed Roach near blacksquall 3rd base",
        "VoidRay killed Roach near blacksquall Natural",
    )
    assert fixed["Battle-13"].endswith(" near blacksquall 3rd base")


# --- S1 (D9a, TD-27): the supply tracker -------------------------------------------------------------------


def test_type_at_reads_upstreams_type_history():
    from sc2mindshare.reader.compat import type_at

    unit = SimpleNamespace(
        name="Hive",
        type_history={
            0: SimpleNamespace(name="Hatchery"),
            8145: SimpleNamespace(name="Lair"),
            12000: SimpleNamespace(name="Hive"),
        },
    )
    assert [type_at(unit, f) for f in (0, 8144, 8145, 11999, 12000, 20000)] == [
        "Hatchery",
        "Hatchery",
        "Lair",
        "Lair",
        "Hive",
        "Hive",
    ]
    assert type_at(SimpleNamespace(name="Drone", type_history={}), 5) == "Drone"


def _tracker(fixes):
    from sc2mindshare.analysis.detectors.trackers import SupplyTracker

    return SupplyTracker("p1", "p2", frozenset(fixes))


def _event(name_now, history, frame, unit_id=1):
    return SimpleNamespace(unit=SimpleNamespace(name=name_now, type_history=history), frame=frame, unit_id=unit_id)


def test_s1_providers_by_their_type_at_the_event_and_their_real_value():
    hatch = {0: SimpleNamespace(name="Hatchery"), 9000: SimpleNamespace(name="Hive")}
    fixed, faithful = _tracker({"S1"}), _tracker(())
    assert fixed.providerOf(_event("Hive", hatch, 0)) == "Hatchery" and fixed.providedBy("Hatchery") == 6
    assert fixed.providerOf(_event("Overseer", {0: SimpleNamespace(name="Overseer")}, 100)) == "Overseer"
    assert fixed.providedBy("Overseer") == 8 and fixed.providedBy("Nexus") == 15
    assert faithful.providedBy("Hatchery") == 15  # the legacy table, kept for the bug-faithful run


def test_s1_the_series_starts_empty_and_a_block_is_judged_once_per_loop():
    fixed, faithful = _tracker({"S1"}), _tracker(())
    assert (faithful.getPreviousSupply("p1").supply, faithful.getPreviousSupply("p1").limit) == (12, 15)
    assert (fixed.getPreviousSupply("p1").supply, fixed.getPreviousSupply("p1").limit) == (0, 0)
    # loop 0: 12 workers born before the providers, in one loop: no zero-length block (Q-b2)
    fixed.changeSupply("p1", "00:00", 12, frame=0)
    fixed.increaseLimit("p1", "00:00", "Hatchery", frame=0)
    fixed.increaseLimit("p1", "00:00", "Overlord", frame=0)
    fixed.changeSupply("p1", "00:38", 2, frame=851)  # 14/14 at 00:38: blocked
    fixed.increaseLimit("p1", "00:57", "Overlord", frame=1277)  # 14/22: free again
    fixed.findSupplyBlocks("p1")
    assert [(b.start, b.end) for b in fixed.supplyBlocks["p1"]] == [("00:00:38", "00:00:57")]


@pytest.fixture(scope="module")
def supply():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    out = {}
    before_s6 = tuple(f for f in LAYER_FIXES if f not in ("S6", "S7"))  # the S1/S1b entries' input; S6, S7 came later
    for label, fixes in (("faithful", ()), ("before S6", before_s6), ("fixed", LAYER_FIXES)):
        with contextlib.redirect_stdout(io.StringIO()):
            result = analyse(load_replay(ALCYONE), MS_SC, fixes=fixes, with_exposed=True)
        graph = to_graph(result, fixes=() if not fixes else None, mixed=label == "before S6")
        blocks = [
            (n.value("player"), n.time("time").seconds, n.time("end time").seconds)
            for n in graph.nodes
            if n.kind == "Supply Block"
        ]
        out[label] = (result.exposed.supply, blocks)
    return out


def test_s1_on_alcyone_the_series_starts_as_playerstats_and_the_blocks_are_the_entrys(supply):
    """The S1 and S1b entries (CHANGES.md): 12/14 and 12/15 at 0:00 as PlayerStats; 7 blocks instead of 11,
    the 57 s block from 0:00 (TD-27) gone, and none from blacksquall's two Nexuses killed unfinished (S5)."""
    points, blocks = supply["before S6"]
    first = {p.player: (p.supply, p.limit) for p in points if p.time in ("00:00", "00:00:00")}  # the last status in second 0
    assert first == {1: (12.0, 14.0), 2: (12.0, 15.0)}
    assert blocks == [
        ("lilTiGGer", 38, 57),
        ("lilTiGGer", 128, 133),
        ("lilTiGGer", 402, 410),
        ("lilTiGGer", 760, 768),
        ("lilTiGGer", 798, 823),
        ("blacksquall", 32, 38),
        ("blacksquall", 887, 936),
    ]
    _faithful_points, faithful_blocks = supply["faithful"]
    assert len(faithful_blocks) == 11 and faithful_blocks[0] == ("lilTiGGer", 0, 57)  # bug-faithful: kept
    assert max(p.limit for p in points) == 336 and max(p.limit for p in _faithful_points) == 360


def test_s5_an_unfinished_provider_does_not_lower_the_limit():
    """Morgan's G6 on 5932f93: only a provider whose limit was added lowers it at its death."""
    from sc2mindshare.reader.fork_api import UnitDiedEvent

    tracker = _tracker({"S1"})
    nexus = {0: SimpleNamespace(name="Nexus")}
    assert tracker.providerOf(_event("Nexus", nexus, 100, unit_id=1)) == "Nexus"  # finished: its limit was added
    died = UnitDiedEvent.__new__(UnitDiedEvent)
    vars(died).update(unit=SimpleNamespace(name="Nexus", type_history=nexus), frame=200, unit_id=1)
    assert tracker.providerOf(died) == "Nexus"
    vars(died).update(unit_id=2)  # another Nexus, killed while building: never added
    assert tracker.providerOf(died) is None


def test_the_supply_tracker_takes_its_fixes_explicitly():
    """Morgan's G6 N0 on 93ec494: no default, like createDetectors."""
    from sc2mindshare.analysis.detectors.trackers import SupplyTracker

    with pytest.raises(TypeError):
        SupplyTracker("p1", "p2")  # type: ignore[call-arg]


# --- P8: the last Units interval is written ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("replay", "node_id", "player", "unit_type", "time", "total", "previous"),
    [
        (
            "Alcyone LE__lilTiGGer_vs_blacksquall/Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
            "Units-172",  # Units-193 before N1 merged 11 groups, P10 dropped 7 and P10b 3
            "blacksquall",
            "Probe",
            1000,
            "47",
            "Units-171",
        ),
        # Units-129 before P10 dropped spine's 7 spell-effect groups
        # (Units-122 before P10b made spine's Shield Battery group Buildings)
        ("200k dmg spine crawler ZvP.SC2Replay", "Units-121", "serega", "Probe", 660, "68", "Units-117"),
    ],
)
def test_p8_the_last_interval_gets_its_units_node(replay, node_id, player, unit_type, time, total, previous):
    """The P8 entry (CHANGES.md): the units of the last 10 s interval get their node and its link to the
    type's previous group; the bug-faithful run has neither."""
    path = MS_SC / replay
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    graphs = {}
    for label, fixes in (("faithful", ()), ("fixed", LAYER_FIXES)):
        with contextlib.redirect_stdout(io.StringIO()):
            graphs[label] = to_graph(analyse(load_replay(path), MS_SC, fixes=fixes), fixes=() if not fixes else None)
    fixed = {n.id: n for n in graphs["fixed"].nodes}
    # the bug-faithful run has no Units node in the last interval (N1 renumbers, so not by ID)
    assert not [n for n in graphs["faithful"].nodes if n.kind == "Units" and n.start.seconds == time]
    node = fixed[node_id]
    assert (node.value("player"), node.value("type"), node.value("count"), node.value("total at time")) == (
        player,
        unit_type,
        "1",
        total,
    )
    assert node.start.seconds == time
    assert [(lk.node1, lk.node2, lk.name1) for lk in graphs["fixed"].links if lk.node2 == node_id] == [
        (previous, node_id, "previous")
    ]
    # P8 adds this node; on Alcyone S1 leaves 4 Supply Blocks fewer, P11 drops 3 nodes (Harrasment-7, Scouting-0
    # and Scouting-1), N1 merges 11 Units groups; on spine S1 leaves 2 more (N1 only renames there); on both
    # P10 drops 7 spell-effect groups; P10b turns Units groups into Buildings (Alcyone 3 for 3, spine 1 for 2);
    # on Alcyone S6 and S7 leave 2 Supply Blocks fewer (7 -> 5); CR-034 (BO1) adds a Building node per building
    # morph (Alcyone 17: a Lair, a Hive, a Greater Spire and 14 Warp Gates; spine 9: a Lair and 8 Warp Gates); CR-035
    # (BC1) adds a build check card per player and the missing entries (Alcyone 2, spine 1); CR-080 (CG1) gives
    # Alcyone 2 scouting steps more (9 -> 11) and spine 1 fewer (7 -> 6)
    assert len(graphs["fixed"].nodes) == len(graphs["faithful"].nodes) + 1 - 7 - (
        4 + 3 + 11 + 2 if "Alcyone" in replay else 0
    ) + (2 + 1 if "spine" in replay else 0) + (17 if "Alcyone" in replay else 9) + 2 + (2 if "Alcyone" in replay else 1) + (
        2 if "Alcyone" in replay else -1
    )


# --- P2: race words are no longer stripped from inside names -----------------------------------------------


def test_p2_the_name_cleaning_takes_the_fixes_explicitly():
    from sc2mindshare.reader.compat import clean_name

    assert clean_name("Zergling", True) == "ling"  # bug-faithful without the fixes (python bug 2)
    assert clean_name("Zergling", True, frozenset({"P2"})) == "Zergling"
    assert clean_name("zerglingmovementspeed", True, frozenset({"P2"})) == "Zergling Movement Speed"
    assert clean_name("zerglingmovementspeed", True) == "ling Movement Speed"
    assert clean_name("Player 1 - lilTiGGer (Zerg)", False, frozenset({"P2"})) == "lilTiGGer"  # the explicit removals stay


#: Every name cleaning in analysis/ that does not pass the layer fixes, by (file, function): its count and why
#: its text never reaches the output (Morgan's ruling on P2). A new call without fixes fails here.
CLEANING_WITHOUT_FIXES = {
    ("detectors/detectors.py", "__init__"): (
        2,
        "SinglesDetector: the game heatmap name, a lookup key into the image tracker the legacy uploader wrote",
    ),
    ("detectors/detectors.py", "buildingsEligible"): (
        1,
        "the OMIT_BUILDINGS prefix test: P2 can't change it, no Zerg/Terran-named type is a building (Morgan)",
    ),
    ("detectors/detectors.py", "findSimpleNodes"): (1, "a debug print"),
    ("detectors/detectors.py", "addBuilding"): (
        1,
        "the unitsInfo.csv Build Time key: P2 can't change it, no Zerg/Terran-named type is a building (Morgan)",
    ),
    ("detectors/detectors.py", "createHeatMaps"): (4, "battle heatmap names, lookup keys into the image tracker"),
    ("detectors/trackers.py", "providerOf"): (1, "the bug-faithful provider lookup (S1 off)"),
    ("exports/energyNode.py", "__str__"): (1, "debug text"),
    ("fileHandler.py", "__init__"): (4, "local folder and video file names"),
    ("game.py", "__str__"): (1, "debug text"),
    ("utils.py", "replaceStrings"): (
        2,
        "Renamer.replaceStrings and MsUtils.replaceStrings, which nothing calls any more (Renamer has no subclass)",
    ),
}


def test_every_name_cleaning_without_the_fixes_is_listed_with_a_reason():
    import ast
    from collections import Counter

    root = CHECKOUT / "src" / "sc2mindshare" / "analysis"
    found = Counter()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)):
            for call in (c for c in ast.walk(fn) if isinstance(c, ast.Call)):
                func = call.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
                if name not in ("object_text", "clean_name", "replaceStrings", "nameC"):
                    continue
                if name == "replaceStrings" and not (
                    isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "MsUtils"
                ):
                    found[(str(path.relative_to(root)), f"{fn.name} (.replaceStrings)")] += (
                        1  # the fork's methods: no fixes at all
                    )
                    continue
                passes = any(k.arg == "fixes" for k in call.keywords) or len(call.args) >= (2 if name == "object_text" else 3)
                if not passes:
                    found[(str(path.relative_to(root)), fn.name)] += 1
    assert dict(found) == {k: n for k, (n, _why) in CLEANING_WITHOUT_FIXES.items()}


def test_no_fix_less_cleaning_is_left_on_the_fork_objects_or_read_by_the_layer():
    """Morgan's G6 on P2 (N1): the guard above sees calls only, so the fork's ``nameC`` property and ``replaceStrings``
    methods are deleted from ``reader.fork_api``, and the layer reads no ``.nameC`` attribute."""
    import ast

    from sc2mindshare.reader import fork_api

    members = ("nameC", "replaceStrings")
    on_objects = [
        f"{cls.__name__}.{m}"
        for cls in vars(fork_api).values()
        if isinstance(cls, type) and cls.__module__ == fork_api.__name__
        for m in members
        if m in vars(cls)
    ]
    root = CHECKOUT / "src" / "sc2mindshare" / "analysis"
    reads = [
        f"{path.relative_to(root)}:{node.lineno}"
        for path in sorted(root.rglob("*.py"))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Attribute) and node.attr == "nameC"
    ]
    assert (on_objects, reads) == ([], [])


@pytest.mark.parametrize(
    "replay",
    [
        "Alcyone LE__lilTiGGer_vs_blacksquall/Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
        "200k dmg spine crawler ZvP.SC2Replay",
    ],
)
def test_p2_no_standalone_ling_and_the_unit_counts_per_type_are_kept(replay):
    import re
    from collections import Counter

    path = MS_SC / replay
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    graphs = {}
    without_p2 = tuple(f for f in LAYER_FIXES if f != "P2")  # P2 alone makes the difference (an explicit mix)
    for label, fixes in (("faithful", without_p2), ("fixed", LAYER_FIXES)):
        with contextlib.redirect_stdout(io.StringIO()):
            graphs[label] = to_graph(analyse(load_replay(path), MS_SC, fixes=fixes), mixed=fixes != LAYER_FIXES)

    def texts(g):
        for n in g.nodes:
            yield n.name
            yield n.description
            yield from (v for _, v in n.values if isinstance(v, str))

    ling = re.compile(r"(?<![A-Za-z])lings?(?![a-z])")
    assert any(ling.search(t) for t in texts(graphs["faithful"]))  # the bug, without the fix
    assert not [t for t in texts(graphs["fixed"]) if ling.search(t)]

    def per_type(g):
        return Counter((n.value("player"), n.value("type")) for n in g.nodes if n.kind == "Units")

    faithful, fixed = per_type(graphs["faithful"]), per_type(graphs["fixed"])
    renamed = {k: k if k[1] != "ling" else (k[0], "Zergling") for k in faithful}
    assert Counter({renamed[k]: c for k, c in faithful.items()}) == Counter(
        {k: c for k, c in fixed.items() if k in renamed.values()}
    )


# --- P11 (D11a): a base needs a mineral field within 7 cells on both axes ------------------------------------


def _near(minerals, x, y, fixes):
    detector = SimpleNamespace(
        mineralLocations=minerals, ctx=SimpleNamespace(fixes=frozenset(fixes)), DISTANCE_FROM_MINERALS=5, P11_DISTANCE=7
    )
    return BaseDetector.isNearMinerals(detector, SimpleNamespace(x=x, y=y))


@pytest.mark.parametrize(
    ("mineral", "faithful", "fixed"),
    [
        ((54, 80), True, False),  # 4 cells on x, 50 on y: the bug's "or" takes it, D11a's "and" does not
        ((80, 54), True, False),  # the same on y
        ((57, 57), False, True),  # 7 cells on both axes: near under D11a (<= 7), not under the bug (< 5)
        ((58, 50), True, False),  # 8 cells on x, 0 on y: not near
        ((55, 55), False, True),  # 5 cells on both: the bug's "< 5" misses it, D11a takes it
    ],
)
def test_p11_a_mineral_field_counts_when_it_is_near_on_both_axes(mineral, faithful, fixed):
    assert _near([mineral], 50, 50, ()) is faithful
    assert _near([mineral], 50, 50, ("P11",)) is fixed


@pytest.fixture(scope="module")
def alcyone_bases():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    found = {}
    original = detectors.createDetectors
    for label, fixes in (("without P11", tuple(f for f in LAYER_FIXES if f != "P11")), ("fixed", LAYER_FIXES)):

        def capture(replay, fx, label=label):
            ctx = original(replay, fx)
            found[label] = sorted(tuple(b.location) for bases in ctx.bases.bases.values() for b in bases)
            return ctx

        detectors.createDetectors = capture
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                analyse(load_replay(ALCYONE), MS_SC, fixes=fixes)
        finally:
            detectors.createDetectors = original
    return found


def test_p11_on_alcyone_the_three_macro_hatcheries_are_no_bases(alcyone_bases):
    """The P11 entry's prediction: 14 bases without the fix, 11 with it; lilTiGGer's macro Hatcheries drop out."""
    macro = [(38, 40), (41, 34), (48, 31)]
    assert len(alcyone_bases["without P11"]) == 14 and len(alcyone_bases["fixed"]) == 11
    assert sorted(set(alcyone_bases["without P11"]) - set(alcyone_bases["fixed"])) == macro
    assert set(alcyone_bases["fixed"]) < set(alcyone_bases["without P11"])


# --- N1 (D6a): names by the type at the time of the event ---------------------------------------------------


def _unit(history, final):
    return SimpleNamespace(type_history={f: SimpleNamespace(name=n) for f, n in history}, name=final)


def test_n1_the_text_of_a_unit_at_a_frame_is_its_type_then():
    from sc2mindshare.reader.compat import unit_text_at

    gateway = _unit([(100, "Gateway"), (2000, "WarpGate")], "WarpGate")
    assert unit_text_at(gateway, 1999, frozenset()).strip() == "Gateway"
    assert unit_text_at(gateway, 2000, frozenset()).strip() == "Warp Gate"
    assert unit_text_at(gateway, 50, frozenset()).strip() == "Warp Gate"  # nothing yet: its current type


def test_n1_a_type_change_moves_the_unit_between_its_types_counts():
    p = object()
    detector = SimpleNamespace(unitTypeCount={p: {"Overlord": 3}}, ctx=SimpleNamespace(fixes=frozenset({"N1", "P2"})))
    change = SimpleNamespace(
        unit=SimpleNamespace(owner=p, type_history={1: SimpleNamespace(name="Overlord")}, name="Overseer"),
        frame=500,
        unit_type_name="Overseer",
    )
    detectors.SimpleDetector.moveUnitTypeCount(detector, change)
    assert detector.unitTypeCount[p] == {"Overlord": 2, "Overseer": 1}
    egg = SimpleNamespace(
        unit=SimpleNamespace(owner=p, type_history={1: SimpleNamespace(name="Egg")}, name="Drone"),
        frame=9,
        unit_type_name="Drone",
    )
    detectors.SimpleDetector.moveUnitTypeCount(detector, egg)  # an uncounted old type moves nothing
    assert detector.unitTypeCount[p] == {"Overlord": 2, "Overseer": 1}


@pytest.fixture(scope="module")
def n1_graphs():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    graphs = {}
    for label, fixes in (("without N1", tuple(f for f in LAYER_FIXES if f != "N1")), ("fixed", LAYER_FIXES)):
        with contextlib.redirect_stdout(io.StringIO()):
            graphs[label] = to_graph(analyse(load_replay(ALCYONE), MS_SC, fixes=fixes), mixed=fixes != LAYER_FIXES)
    return {label: {n.id: n for n in g.nodes} for label, g in graphs.items()}


def test_n1_on_alcyone_units_buildings_and_killers_take_the_type_at_the_time(n1_graphs):
    """The N1 entry's prediction (CHANGES.md), a few pinned; the goldens hold all of it."""
    before, after = n1_graphs["without N1"], n1_graphs["fixed"]
    units = {label: [n for n in g.values() if n.kind == "Units"] for label, g in n1_graphs.items()}
    assert (len(units["without N1"]), len(units["fixed"])) == (183, 172)  # 193 -> 182 before P10 and P10b dropped 10
    assert (before["Units-24"].value("type"), after["Units-24"].value("type")) == ("Overseer", "Overlord")
    # CR-035: the current graph's Gateway also carries its build check verdict
    assert (before["Building-6"].name, after["Building-6"].name) == ("Warp Gate", "Gateway · on supply")
    assert after["Building-6"].value("type") == "Gateway" and after["Building-6"].start.seconds == 41
    assert (before["Building-1"].value("type"), after["Building-1"].value("type")) == ("Hive", "Hatchery")
    assert "Ravager killed Stalker" in before["Battle-12"].description
    assert "Ravager killed" not in after["Battle-12"].description and "Roach killed Stalker(3)" in after["Battle-12"].description


# --- P10: spell effects are not counted as units -------------------------------------------------------------


def _finished(name_now, history, fixes):
    unit = SimpleNamespace(name=name_now, is_building=False, type_history={f: SimpleNamespace(name=n) for f, n in history})
    event = SimpleNamespace(player="p", unit=unit, time="03:00", frame=4000)
    detector = SimpleNamespace(
        OMIT_UNITS=detectors.EventsDetector.OMIT_UNITS,
        P10_OMIT_UNITS=detectors.EventsDetector.P10_OMIT_UNITS,
        ctx=SimpleNamespace(fixes=frozenset(fixes)),
    )
    return detectors.EventsDetector.unitFinishedEligble(detector, event)


@pytest.mark.parametrize(
    ("name_now", "history", "faithful", "fixed"),
    [
        ("DisruptorPhased", [(3990, "DisruptorPhased")], True, False),  # the Purification Nova
        ("AdeptPhaseShift", [(3990, "AdeptPhaseShift")], True, False),  # the Adept's shade
        ("RavagerCocoon", [(3990, "Roach"), (6000, "RavagerCocoon")], True, True),  # a Roach when it hatched
        ("RavagerCocoon", [(3990, "RavagerCocoon")], True, False),  # a cocoon at the event (Vera's V1)
        ("SiegeTankSieged", [(3990, "SiegeTank"), (5000, "SiegeTankSieged")], False, True),  # a tank, sieged later
        ("Zealot", [(3990, "Zealot")], True, True),
    ],
)
def test_p10_eligibility_by_the_type_at_the_event_without_the_spell_effects(name_now, history, faithful, fixed):
    assert _finished(name_now, history, ()) is faithful
    assert _finished(name_now, history, ("P10",)) is fixed


# --- P12: UNITS_FROM_STATE_CHANGE is a tuple ---------------------------------------------------------------


def test_p12_units_from_state_change_is_a_tuple_and_tests_whole_names():
    from sc2mindshare.analysis.detectors.trackers import EnergyTracker

    assert EnergyTracker.UNITS_FROM_STATE_CHANGE == ("OrbitalCommand",)
    tracker = SimpleNamespace(UNITS_FROM_STATE_CHANGE=EnergyTracker.UNITS_FROM_STATE_CHANGE)
    assert EnergyTracker.isEnergyUpgrade(tracker, SimpleNamespace(name="OrbitalCommand"))
    assert not EnergyTracker.isEnergyUpgrade(tracker, SimpleNamespace(name="Orbital"))  # a substring, not a name


# --- S6 (D15a): a unit's supply follows its type ----------------------------------------------------------------


def _typed(history):
    return SimpleNamespace(type_history={f: SimpleNamespace(name=n, supply=s) for f, n, s in history})


def test_s6_the_supply_at_a_frame_is_its_types_and_a_type_missing_from_the_datapack_keeps_it():
    from sc2mindshare.reader.compat import supply_at

    roach = _typed([(100, "Roach", 2), (900, "RavagerCocoon", 3), (1100, "Ravager", 3)])
    assert [supply_at(roach, f) for f in (100, 899, 900, 1200)] == [2, 2, 3, 3]
    observer = _typed([(100, "Observer", 1), (700, "ObserverSiegeMode", 0)])  # not in sc2reader's datapack
    assert [supply_at(observer, f) for f in (100, 700)] == [1, 1]


def test_s6_a_counted_unit_adds_the_difference_at_a_type_change():
    calls = []
    detector = SimpleNamespace(
        ctx=SimpleNamespace(fixes=frozenset({"S6"})),
        countedSupply={7: 2},
        st=SimpleNamespace(changeSupply=lambda player, time, change, frame=None: calls.append((player, change, frame))),
    )
    roach = _typed([(100, "Roach", 2), (900, "RavagerCocoon", 3)])
    roach.id, roach.owner = 7, "p"
    detectors.SimpleDetector.moveUnitSupply(detector, SimpleNamespace(unit=roach, frame=900, time="00:40"))
    assert calls == [("p", 1, 900)] and detector.countedSupply == {7: 3}
    stranger = _typed([(100, "Larva", 0), (300, "Egg", 0)])
    stranger.id, stranger.owner = 8, "p"
    detectors.SimpleDetector.moveUnitSupply(detector, SimpleNamespace(unit=stranger, frame=300, time="00:13"))
    assert calls == [("p", 1, 900)]  # a unit that was never counted moves nothing


def test_s6_on_alcyone_the_supply_blocks_follow_the_type_at_the_time(supply):
    """The S6 entry's prediction (CHANGES.md): lilTiGGer's 6:42 block goes, blacksquall gets one at 14:43."""
    blocks = supply["fixed"][1]
    assert ("lilTiGGer", 402, 410) not in blocks and ("blacksquall", 883, 885) in blocks


# --- P9 (D17a): the replay's time-zone offset ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("offset", "faithful", "fixed"),
    [(-5.0, "UTC", "UTC-5"), (1.0, "UTC+", "UTC+1"), (0.0, "UTC", "UTC"), (5.5, "UTC+", "UTC+5:30"), (-3.5, "UTC", "UTC-3:30")],
)
def test_p9_the_time_zone_value_is_the_recorders_offset_and_the_description_says_utc(offset, faithful, fixed):
    from sc2mindshare.analysis.exports.gameNode import GameNode

    players = [SimpleNamespace(result="Win", name="a"), SimpleNamespace(result="Loss", name="b")]
    replay = SimpleNamespace(
        map_name="M",
        players=players,
        time_zone=offset,
        date="2024-07-24 07:55:57",
        length="16.38",
        speed="Faster",
        is_ladder=True,
        type="1v1",
        category="Ladder",
    )
    for fixes, zone in (((), faithful), (("P9",), fixed)):
        game = GameNode(replay, "", fixes=frozenset(fixes))
        assert game.timeZone == zone
        assert game.getNodeDescription().startswith("Played on 2024-07-24 07:55:57 UTC" + ("" if fixes else zone[3:]) + " for")


# --- P10b (D18a): Shield Batteries and rich Extractors are structures ----------------------------------------------


@pytest.mark.parametrize("name", ["ShieldBattery", "ExtractorRich"])
def test_p10b_the_structures_the_datapack_does_not_mark_are_buildings_not_units(name):
    unit = SimpleNamespace(name=name, is_building=False, type_history={1: SimpleNamespace(name=name)})
    event = SimpleNamespace(player="p", unit=unit, time="03:00", frame=4000)
    for fixes, building in (((), False), (("P10", "P10b"), True)):
        detector = SimpleNamespace(
            OMIT_UNITS=detectors.EventsDetector.OMIT_UNITS,
            P10_OMIT_UNITS=detectors.EventsDetector.P10_OMIT_UNITS,
            OMIT_BUILDINGS=detectors.EventsDetector.OMIT_BUILDINGS,
            ctx=SimpleNamespace(fixes=frozenset(fixes)),
        )
        detector.isStructure = lambda u, d=detector: detectors.EventsDetector.isStructure(d, u)
        assert detectors.EventsDetector.buildingsEligible(detector, event) is building
        assert detectors.EventsDetector.unitFinishedEligble(detector, event) is not building


def test_p10b_on_alcyone_the_batteries_and_the_rich_extractor_are_buildings(n1_graphs):
    """The P10b entry's prediction (CHANGES.md): Building-12 and Building-33 are blacksquall's Shield Batteries
    (started 2:31 and 5:55), Building-101 lilTiGGer's Extractor Rich (started 13:54); no Units group of either."""
    g = n1_graphs["fixed"]
    assert [(g[i].name, g[i].value("player"), g[i].start.seconds) for i in ("Building-12", "Building-33", "Building-101")] == [
        ("Shield Battery · extra", "blacksquall", 151),  # CR-035: inside blacksquall's build check, not in its guide
        ("Shield Battery 1", "blacksquall", 355),
        ("Extractor Rich", "lilTiGGer", 834),
    ]
    assert not [n for n in g.values() if n.kind == "Units" and n.value("type") in ("Shield Battery", "Extractor Rich")]


def test_s6_a_counted_unit_takes_away_what_it_counted_at_death():
    """Morgan's G6 on S6 (N1): an Observer that dies in siege mode counted 1 (its final type has no supply in
    the datapack); it takes away 1, not its final type's 0. Without S6, or for a unit never counted, the final
    type's supply goes."""
    calls = []
    st = SimpleNamespace(changeSupply=lambda player, time, change, frame=None: calls.append(change))
    observer = SimpleNamespace(id=7, _type_class=SimpleNamespace(supply=0))
    death = SimpleNamespace(player="p", time="14:00", frame=19000, unit=observer)
    detector = SimpleNamespace(ctx=SimpleNamespace(fixes=frozenset({"S6"})), countedSupply={7: 1.0}, st=st)
    detectors.SimpleDetector.releaseUnitSupply(detector, death)
    assert calls == [-1.0] and detector.countedSupply == {}
    detectors.SimpleDetector.releaseUnitSupply(detector, death)  # no longer counted: the final type's supply
    faithful = SimpleNamespace(ctx=SimpleNamespace(fixes=frozenset()), countedSupply={7: 1.0}, st=st)
    detectors.SimpleDetector.releaseUnitSupply(faithful, death)
    assert calls == [-1.0, 0, 0]


def test_s6_the_detector_hands_every_type_change_of_a_counted_unit_to_the_supply(monkeypatch):
    """Morgan's G6 on S6 (N1): through the detector's own loop on Alcyone, the type changes reach moveUnitSupply,
    and the three Roaches that became Ravagers add 1 each at their cocoon."""
    need(ALCYONE)
    moves = []
    original = detectors.SimpleDetector.moveUnitSupply

    def spy(self, e):
        before = dict(self.countedSupply)
        original(self, e)
        if e.unit is not None and before.get(e.unit.id) != self.countedSupply.get(e.unit.id):
            moves.append((str(e.unit_type_name), before[e.unit.id], self.countedSupply[e.unit.id]))

    monkeypatch.setattr(detectors.SimpleDetector, "moveUnitSupply", spy)
    with contextlib.redirect_stdout(io.StringIO()):
        analyse(load_replay(ALCYONE), MS_SC)
    assert moves == [("RavagerCocoon", 2.0, 3.0)] * 3


# --- S7: a Drone's supply leaves at placement; the limit stops at 200 ---------------------------------------------


def test_s7_the_limit_stops_at_200_but_the_providers_still_add_up():
    from sc2mindshare.analysis.detectors.trackers import SupplyStatus, SupplyTracker

    for fixes, limits in ((("S1", "S7"), [196, 200, 200, 200, 196]), (("S1",), [196, 204, 212, 204, 196])):
        st = SupplyTracker("p1", "p2", frozenset(fixes))
        st.supplyHistory["p1"].append(SupplyStatus("10:00", 150, 196, 1))
        seen = []
        for change in (+1, +1, -1, -1):
            (st.increaseLimit if change > 0 else st.decreaseLimit)("p1", "10:01", "Pylon", 2)
            seen.append(st.supplyHistory["p1"][-1].limit)
        assert [196, *seen] == limits, fixes


def test_s7_on_alcyone_the_drones_leave_at_placement(supply):
    """The S7 entry's prediction (CHANGES.md): lilTiGGer's 2:08 and 12:40 blocks go, the first starts at 0:41."""
    blocks = supply["fixed"][1]
    assert [b for b in blocks if b[0] == "lilTiGGer"] == [("lilTiGGer", 41, 57), ("lilTiGGer", 798, 823)]


# --- S8: the missing-type supply rule names its modes and flags the rest -----------------------------------------


def test_s8_a_named_mode_keeps_its_supply_quietly_and_any_other_missing_type_is_flagged():
    from sc2mindshare.reader.compat import MODES_MISSING_FROM_THE_DATAPACK, unnamed_missing_type

    # the names are sc2reader's type titles (what the type history holds), each missing from its datapack
    assert set(MODES_MISSING_FROM_THE_DATAPACK) == {
        "ObserverSiegeMode", "OverseerSiegeMode", "OverlordTransport", "TransportOverlordCocoon",
        "LiberatorAG", "ThorAP", "RavagerBurrowed", "LurkerBurrowed",
    }  # fmt: skip
    from sc2reader.data import unit_lookup

    known = {n for race in ("Protoss", "Terran", "Zerg") for n in unit_lookup[race]}
    assert not [m for m in MODES_MISSING_FROM_THE_DATAPACK if m.lower() in known]
    observer = _typed([(100, "Observer", 1), (700, "ObserverSiegeMode", 0)])
    assert unnamed_missing_type(observer, 700) is None  # named: kept, no flag
    lurker = _typed([(100, "Hydralisk", 2), (700, "LurkerEgg", 0)])  # not in the datapack, not named
    assert unnamed_missing_type(lurker, 700) == "LurkerEgg"
    roach = _typed([(100, "Roach", 2), (900, "RavagerCocoon", 3)])
    assert unnamed_missing_type(roach, 900) is None  # in the datapack


def test_s8_the_detector_records_an_unnamed_missing_type():
    calls, flags = [], []
    detector = SimpleNamespace(
        ctx=SimpleNamespace(fixes=frozenset({"S6", "S8"})),
        countedSupply={7: 2.0},
        supplyFlags=flags,
        st=SimpleNamespace(changeSupply=lambda *a, **k: calls.append(a)),
    )
    hydra = _typed([(100, "Hydralisk", 2), (700, "LurkerMPEgg", 0)])
    hydra.id, hydra.owner = 7, "p"
    with contextlib.redirect_stdout(io.StringIO()) as out:
        detectors.SimpleDetector.moveUnitSupply(detector, SimpleNamespace(unit=hydra, frame=700, time="00:31"))
    assert calls == [] and detector.countedSupply == {7: 2.0}  # the supply is kept
    assert flags == [(7, "Hydralisk", "LurkerMPEgg", 700)] and "LurkerMPEgg" in out.getvalue()


# --- S7 follow-ups (Morgan's N1 on S7): the cancellation path ------------------------------------------------------


def test_s7_an_unfinished_placement_that_dies_gives_nothing_back_and_leaves_the_drone_matching():
    """Morgan's G6 on 169c1fb (P2): a cancel gives nothing back here, because the replay hands the Drone back as a
    new birth, which the birth path counts; a destroyed one's Drone is gone. Either way the placement leaves the
    Drone matching, so no later Drone death can be taken for it."""
    calls = []
    owner = "p"
    st = SimpleNamespace(changeSupply=lambda player, time, change, frame=None: calls.append(change))
    for killing_player in (owner, "q", None):  # cancelled, destroyed, unknown
        building = SimpleNamespace(name="Extractor", doneEvent=None, owner=owner, id=9)
        placed = SimpleNamespace(unit=building, frame=1680, x=10, y=10)
        detector = SimpleNamespace(
            ctx=SimpleNamespace(fixes=frozenset({"S7"})), placements={owner: [placed]}, countedSupply={}, st=st
        )
        death = SimpleNamespace(
            unit=building, killer_pid=None, killing_player=killing_player, frame=1880, time="01:24", x=10, y=10
        )
        assert detectors.SimpleDetector.settlePlacement(detector, death) is False
        assert detector.placements[owner] == []
        drone = SimpleNamespace(unit=SimpleNamespace(name="Drone", owner=owner, id=5), killer_pid=None, frame=1990, x=10, y=10)
        assert detectors.SimpleDetector.settlePlacement(detector, drone) is False  # not taken for the gone placement
    assert calls == []


def test_s7_on_spine_piliskners_cancelled_extractor_gives_its_drone_back():
    """Vera's G7 on S7, Morgan's G6 on 169c1fb: Piliskner places an Extractor at 1:15 and cancels it at 1:24; the
    Drone's supply leaves at the placement, and comes back once, at 1:25, when the replay hands the Drone back as
    a new birth (unit 60293122), which the birth path counts."""
    spine = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"
    need(spine)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(spine), MS_SC, with_exposed=True)
    zerg = next(p.pid for p in result.exposed.game.players if p.race == "Zerg")  # Piliskner
    piliskner = [p for p in result.exposed.supply if p.player == zerg and p.time in ("01:10", "01:15", "01:24", "01:25")]
    assert [(p.time, p.supply) for p in piliskner] == [
        ("01:10", 15.0),
        ("01:15", 14.0),
        ("01:24", 14.0),  # the cancelled Extractor's death: nothing back
        ("01:25", 15.0),  # the Drone back, as a new birth
    ]


# --- P10c (CR-068; D21a, D26a, D32a): a destroyed Shield Battery or Rich Extractor counts in battles ---------------

BATTLE_SITES_WITHOUT_THE_FIXES = {
    # (file under src/sc2mindshare/, function): (calls of countableUnitDeath / buildingDeath / isCounted that pass
    # no fixes, why)
    ("analysis/detectors/detectors.py", "findSimpleNodes"): (1, "the supply series and blocks (CR-068 out of scope)"),
    ("analysis/detectors/detectors.py", "processSelectionsAndCommands"): (
        1,
        "the actions' heatmap locations (CR-068 out of scope)",
    ),
    ("reader/fork_api.py", "isCounted"): (
        1,
        (
            "the fork's isCounted helper: no caller under src/ at 02d1019 (CR-071); "
            "new code asks countableUnitDeath with the fixes instead"
        ),
    ),
}


@pytest.mark.parametrize("name", ["ShieldBattery", "ExtractorRich"])
def test_p10c_the_two_structures_deaths_count_and_are_building_deaths(name):
    from sc2mindshare.reader.fork_api import _UnitDiedEventMixin as UnitDiedEvent  # the flavoured class's rules

    death = SimpleNamespace(unit=SimpleNamespace(name=name, is_army=False, is_building=False))
    for fixes, counted in (((), False), (("P10b",), False), (("P10c",), True)):
        assert UnitDiedEvent.countableUnitDeath(death, frozenset(fixes)) is counted
        assert UnitDiedEvent.buildingDeath(death, frozenset(fixes)) is counted
    assert UnitDiedEvent.countableUnitDeath(death) is False  # no fixes: the fork's rule


@pytest.mark.parametrize(
    ("name", "is_army", "is_building", "counted", "building"),
    [
        ("PhotonCannon", False, True, True, True),
        ("Zealot", True, False, True, False),
        ("Probe", False, False, True, False),
        ("BroodlingEscort", True, False, False, False),
        ("CreepTumorBurrowed", False, False, False, False),
    ],
)
def test_p10c_changes_no_other_types_death(name, is_army, is_building, counted, building):
    from sc2mindshare.reader.fork_api import _UnitDiedEventMixin as UnitDiedEvent  # the flavoured class's rules

    death = SimpleNamespace(unit=SimpleNamespace(name=name, is_army=is_army, is_building=is_building))
    for fixes in ((), ("P10c",)):
        assert UnitDiedEvent.countableUnitDeath(death, frozenset(fixes)) is counted
        assert UnitDiedEvent.buildingDeath(death, frozenset(fixes)) is building


@pytest.mark.parametrize(
    ("name", "fixes", "cost"),
    [
        ("ShieldBattery", ("P10c",), (100, 0, 0)),  # unitsInfo.csv's Shield Battery row
        ("ExtractorRich", ("P10c",), (75, 0, 0)),  # D34a: as the datapack values a Zerg Extractor (25 + the Drone's 50)
        ("ShieldBattery", (), (0, 0, 0)),  # faithful: sc2reader's 0, 0, 0
        ("PhotonCannon", ("P10c",), (150, 0, 0)),  # any other type: sc2reader's values, as before
    ],
)
def test_p10c_a_battle_values_the_two_structures_from_the_unit_table(name, fixes, cost):
    from sc2mindshare.analysis.battle import Battle

    need(MS_SC / "unitsInfo.csv")
    import csv

    with (MS_SC / "unitsInfo.csv").open(encoding="utf-8") as f:
        table = {row["Name"]: row for row in csv.DictReader(f)}
    extractor = SimpleNamespace(name="Extractor", minerals=75, vespene=0, supply=0)  # sc2reader's datapack row
    datapack = SimpleNamespace(units={111: extractor, 482: SimpleNamespace(name="ShieldBattery", minerals=0)})
    battle = SimpleNamespace(
        ctx=SimpleNamespace(
            fixes=frozenset(fixes), simple=SimpleNamespace(unitsInfoDict=table), replay=SimpleNamespace(datapack=datapack)
        )
    )
    sc2reader_cost = (150, 0, 0) if name == "PhotonCannon" else (0, 0, 0)
    unit = SimpleNamespace(name=name, minerals=sc2reader_cost[0], vespene=sc2reader_cost[1], supply=sc2reader_cost[2])
    assert Battle.deathCost(battle, SimpleNamespace(unit=unit)) == cost


def test_every_battle_death_rule_without_the_fixes_is_listed_with_a_reason():
    """Morgan's design on CR-068: the battle call sites pass ``ctx.fixes``; any other caller of the death rules is
    on the reviewed list, so a new one cannot silently skip P10c (as the P2 guard above does for the names).
    CR-071: the scan covers all of src/sc2mindshare/ (not legacy/ or tests/), so a new caller anywhere in the new
    code is caught, not only in analysis/."""
    import ast
    from collections import Counter

    root = CHECKOUT / "src" / "sc2mindshare"
    found = Counter()
    passing = Counter()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)):
            for call in (c for c in ast.walk(fn) if isinstance(c, ast.Call)):
                func = call.func
                if not (isinstance(func, ast.Attribute) and func.attr in ("countableUnitDeath", "buildingDeath", "isCounted")):
                    continue
                key = (str(path.relative_to(root)), fn.name)
                if call.args or call.keywords:
                    passing[key] += 1
                else:
                    found[key] += 1
    assert dict(found) == {k: n for k, (n, _why) in BATTLE_SITES_WITHOUT_THE_FIXES.items()}
    assert dict(passing) == {
        ("analysis/battle.py", "__init__"): 1,  # sorting the battle's events (LOST list, bases, workers)
        ("analysis/battle.py", "getCountableDeaths"): 1,
        ("analysis/battle.py", "processLocationEvent"): 1,  # LOST, not KILLS (D32a)
        ("analysis/detectors/detectors.py", "findBattles"): 1,  # a structure's death links to its Initiated node
        ("analysis/detectors/detectors.py", "sortDeaths"): 1,  # the deaths battles are formed from (Kevin's call)
    }


def _analysed_alcyone(fixes=LAYER_FIXES, second=None, as_type=None, support=MS_SC, edit_replay=None, log=None):
    """Alcyone analysed with ``fixes`` (CR-068's harness, lifted out of ``p10c_battles`` for CR-070). Each run may
    move blacksquall's 7:48 Shield Battery death to another second and give the battery another type for the whole
    game (a Photon Cannon, an Extractor or a Rich Extractor, the datapack's own type); ``support`` is the support
    root the tables are read from, ``edit_replay`` changes the loaded replay last, and the layer's prints go to
    ``log`` (a fresh buffer when None)."""
    import bisect
    import math

    replay = load_replay(ALCYONE)
    death = next(
        e
        for e in replay.tracker_events
        if type(e).__name__ == "UnitDiedEvent"
        and e.unit is not None
        and e.unit.name == "ShieldBattery"
        and e.unit.killing_unit is not None
    )
    assert (death.frame, death.unit.owner.name, death.unit.killing_unit.name) == (10502, "blacksquall", "Roach")
    if as_type is not None:
        kind = next(t for t in replay.datapack.units.values() if t.name == as_type)
        death.unit._type_class = kind
        death.unit.type_history = {frame: kind for frame in death.unit.type_history}
    if second is not None:
        frame = math.ceil(second * 22.4)
        assert int(frame / 22.4) == second
        for events in (replay.events, replay.tracker_events):
            events.remove(death)
        death.frame = death.unit.died_at = frame
        for events in (replay.events, replay.tracker_events):
            bisect.insort(events, death, key=lambda e: e.frame)
    if edit_replay is not None:
        edit_replay(replay)
    with contextlib.redirect_stdout(io.StringIO() if log is None else log):
        return analyse(replay, support, fixes=fixes)


def _alcyone_battles(fixes=LAYER_FIXES, second=None, as_type=None, support=MS_SC, edit_replay=None, log=None):
    """Alcyone's battles (``_analysed_alcyone``), as (start, end, dead, supply, minerals, gas, LOST, KILLS, name)
    by battle."""
    from sc2mindshare.analysis.exports.battleNode import BattleNode

    result = _analysed_alcyone(fixes, second, as_type, support, edit_replay, log)
    out = []
    for b in (n for n in result.nodes if isinstance(n, BattleNode)):
        ps = (b.player1, b.player2)
        out.append(
            {
                "start": b.startSec,
                "end": b.endSec,
                "dead": (b.p1dc, b.p2dc),
                "supply": tuple(b.supplyLost[p] for p in ps),
                "minerals": tuple(b.minLost[p] for p in ps),
                "gas": tuple(b.gasLost[p] for p in ps),
                "lost": tuple(dict(b.deadBuildingsTypes[p]) for p in ps),
                "kills": tuple(dict(b.killersTypes[p]) for p in ps),
                "name": b.getNodeName(),
            }
        )
    return out


@pytest.fixture(scope="module")
def p10c_battles():
    """Alcyone's battles per run (``_alcyone_battles``), with the 7:48 battery moved or retyped."""
    need(ALCYONE)
    run = _alcyone_battles
    without = tuple(f for f in LAYER_FIXES if f != "P10c")
    runs = {"fixed": run(), "without": run(without), "cannon": run(as_type="PhotonCannon")}
    # a gap between two battles after 7:48 wide enough for a lone death 6 s after the first (more than the 4 s
    # a battle extends by on either side) and for a death 2 s after it that extends it
    b = runs["without"]
    i = next(i for i in range(len(b) - 1) if b[i]["start"] > 468 and b[i + 1]["start"] - b[i]["end"] > 12)
    lone, extend = b[i]["end"] + 6, b[i]["end"] + 2
    for label, second in (("lone", lone), ("extend", extend)):
        runs[label] = run(second=second)
        runs[f"{label}-cannon"] = run(second=second, as_type="PhotonCannon")
        runs[f"{label}-without"] = run(without, second=second)
    runs["rich"] = run(as_type="ExtractorRich")
    runs["extractor"] = run(as_type="Extractor")
    runs["rich-without"] = run(without, as_type="ExtractorRich")
    return runs, i


def _differences(old, new):
    assert len(old) == len(new)
    return {i: sorted(k for k in o if o[k] != n[k]) for i, (o, n) in enumerate(zip(old, new, strict=True)) if o != n}


def test_p10c_on_alcyone_battle_12_and_27_count_the_battery(p10c_battles):
    """AC-1, AC-2 and the P10c entry: blacksquall's batteries at 7:48 and 14:33 (Battle-12, Battle-27); dead and
    his dead +1, minerals +100, supply unchanged, Shield Battery in his LOST list; nothing else in any battle."""
    runs, _ = p10c_battles
    old, new = runs["without"], runs["fixed"]
    assert _differences(old, new) == {11: ["dead", "lost", "minerals"], 26: ["dead", "lost", "minerals"]}
    for i in (11, 26):
        assert (old[i]["start"], old[i]["end"]) in ((456, 477), (871, 905))
        assert new[i]["dead"] == (old[i]["dead"][0], old[i]["dead"][1] + 1)
        assert new[i]["minerals"] == (old[i]["minerals"][0], old[i]["minerals"][1] + 100)
        assert new[i]["supply"] == old[i]["supply"]
        assert new[i]["lost"][1] == {**old[i]["lost"][1], "Shield Battery": 1}
        assert new[i]["kills"] == old[i]["kills"]  # D32a: KILLS stay units-only


def test_p10c_on_alcyone_the_battery_counts_as_a_photon_cannon_would(p10c_battles):
    """AC-1's differential: the same death as a Photon Cannon (sc2reader: a building, 150 minerals)."""
    runs, _ = p10c_battles
    _same_but_the_structure(runs["fixed"], runs["cannon"], 11)


def _same_but_the_structure(battery, cannon, swapped):
    """Every battle is the same, but in the one with the swapped death (index ``swapped``) the structure's name
    and blacksquall's minerals lost, by 50 (a Photon Cannon's 150, sc2reader's, minus the battery's 100). The
    other battery (14:33) is a battery in both runs."""
    for i, (b, o) in enumerate(zip(battery, cannon, strict=True)):
        same = ("start", "end", "dead", "supply", "gas", "kills")
        assert [b[k] for k in same] == [o[k] for k in same], i
        lost, name, gap = b["lost"], b["name"], 0
        if i == swapped:
            lost = (lost[0], {"Photon Cannon" if k == "Shield Battery" else k: v for k, v in lost[1].items()})
            name, gap = name.replace("ShieldBattery", "PhotonCannon"), 50
        assert (lost, name) == (o["lost"], o["name"]), i
        assert (o["minerals"][0], o["minerals"][1] - gap) == b["minerals"], i


def test_p10c_a_lone_battery_death_starts_a_battle_as_a_photon_cannon_does(p10c_battles):
    """AC-4: alone in a gap, the battery's death is a battle of its own, as a Photon Cannon's would be."""
    runs, i = p10c_battles
    assert len(runs["lone"]) == len(runs["lone-without"]) + 1  # without P10c the death starts nothing
    new = runs["lone"][i + 1]
    assert (new["dead"], new["minerals"][1], new["supply"], new["lost"][1]) == ((0, 1), 100, (0, 0), {"Shield Battery": 1})
    assert new["start"] == new["end"] == runs["lone-without"][i]["end"] + 6
    _same_but_the_structure(runs["lone"], runs["lone-cannon"], i + 1)


def test_p10c_a_battery_death_just_after_a_battle_extends_it_as_a_photon_cannon_does(p10c_battles):
    """AC-4: 2 s after a battle's last death, the battery's death extends that battle, as a Photon Cannon's would."""
    runs, i = p10c_battles
    old, new = runs["extend-without"][i], runs["extend"][i]
    assert len(runs["extend"]) == len(runs["extend-without"])
    assert (new["start"], new["end"]) == (old["start"], old["end"] + 2)
    assert new["dead"] == (old["dead"][0], old["dead"][1] + 1)
    _same_but_the_structure(runs["extend"], runs["extend-cannon"], i)


def test_p10c_a_rich_extractor_counts_exactly_as_an_extractor(p10c_battles):
    """AC-3 (D34a): the death as a Rich Extractor is counted as a normal Extractor's of the same race: the same
    battles, dead, LOST and losses (sc2reader's Zerg Extractor, 75: 25 plus the Drone's 50)."""
    runs, _ = p10c_battles
    rich, extractor, without = runs["rich"], runs["extractor"], runs["rich-without"]
    assert _differences(without, rich) == {11: ["dead", "lost", "minerals"], 26: ["dead", "lost", "minerals"]}
    assert rich[11]["minerals"][1] - without[11]["minerals"][1] == 75
    assert rich[11]["lost"][1] == {**without[11]["lost"][1], "Extractor Rich": 1}
    for i, (r, x) in enumerate(zip(rich, extractor, strict=True)):
        same = ("start", "end", "dead", "supply", "kills")
        assert [r[k] for k in same] == [x[k] for k in same], i
        assert x["minerals"] == r["minerals"], i


def test_p10c_off_the_battles_are_todays(p10c_battles):
    """AC-7: without P10c the battery's death counts nowhere, wherever it falls (the bug-faithful run's rule)."""
    runs, _ = p10c_battles
    assert all(
        "Shield Battery" not in d for run in ("without", "lone-without", "extend-without") for b in runs[run] for d in b["lost"]
    )


# --- G1 (CR-067): the Game node's game type, length and date are its own ------------------------------------------


def _game_replay(**overrides):
    """A stand-in replay for the Game node: Alcyone's values unless overridden."""
    import datetime

    from sc2reader.utils import Length

    players = [SimpleNamespace(result="Loss", name="lilTiGGer"), SimpleNamespace(result="Win", name="blacksquall")]
    values = {
        "map_name": "Alcyone LE",
        "players": players,
        "time_zone": -5.0,
        "date": datetime.datetime(2024, 7, 24, 7, 55, 57, tzinfo=datetime.UTC).replace(tzinfo=None),  # naive, as flavoured
        "length": Length(seconds=998),
        "speed": "Faster",
        "is_ladder": True,
        "type": "1v1",
        "category": "Ladder",
    }
    return SimpleNamespace(**(values | overrides))


def _game_values(game):
    """The seven values the Game node writes, by the domain's field names (FIELDS["Game"])."""
    from sc2mindshare.domain.models import FIELDS

    return dict(zip(FIELDS["Game"], game.getProperties(";").split(";")[:-1], strict=True))


def test_g1_the_game_type_is_the_replays_and_the_node_stays_a_game():
    from sc2mindshare.analysis.exports.gameNode import GameNode

    faithful = GameNode(_game_replay(), "", fixes=frozenset())
    fixed = GameNode(_game_replay(), "", fixes=frozenset({"P9", "G1"}))
    assert _game_values(faithful)["type"] == "Game"  # the bug: the node's own type overwrote the game type
    assert _game_values(fixed)["type"] == "1v1"
    assert faithful.getNodeType() == fixed.getNodeType() == "Game"  # the node is a Game node either way


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(998, "00:16:38"), (3909, "01:05:09"), (660, "00:11:00"), (0, "00:00:00"), (3599, "00:59:59"), (3600, "01:00:00")],
)
def test_g1_the_length_keeps_its_hours(seconds, text):
    """AC-3: a game of 1 h 5 min 9 s reads 01:05:09 (the legacy strptime('%M.%S') fails from an hour on)."""
    from sc2reader.utils import Length

    from sc2mindshare.analysis.exports.gameNode import GameNode

    game = GameNode(_game_replay(length=Length(seconds=seconds)), "", fixes=frozenset({"G1"}))
    assert _game_values(game)["duration"] == text
    if seconds < 3600:  # the bug-faithful text, where the legacy code works at all
        assert _game_values(GameNode(_game_replay(length=Length(seconds=seconds)), "", fixes=frozenset()))["duration"] == text


def test_g1_the_date_is_written_with_its_own_format_never_str():
    """AC-2: the replay's UTC date as YYYY-MM-DD HH:MM:SS, also when the datetime is time-zone-aware (CR-064 would
    otherwise add "+00:00" through str())."""
    import datetime

    from sc2mindshare.analysis.exports.gameNode import GameNode

    aware = datetime.datetime(2024, 7, 24, 7, 55, 57, tzinfo=datetime.UTC)
    for date in (aware.replace(tzinfo=None), aware):
        game = GameNode(_game_replay(date=date), "", fixes=frozenset({"P9", "G1"}))
        assert _game_values(game)["date"] == "2024-07-24 07:55:57"
        assert game.getNodeDescription().startswith("Played on 2024-07-24 07:55:57 UTC for 00:16:38.")
    assert _game_values(GameNode(_game_replay(date=aware), "", fixes=frozenset()))["date"] == "2024-07-24 07:55:57+00:00"


@pytest.mark.parametrize(
    ("replay", "values"),
    [
        (
            "Alcyone LE__lilTiGGer_vs_blacksquall/Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
            {"date": "2024-07-24 07:55:57", "timezone": "UTC-5", "duration": "00:16:38", "type": "1v1", "ladder": "True",
             "category": "Ladder", "speed": "Faster"},
        ),
        (
            "200k dmg spine crawler ZvP.SC2Replay",
            {"date": "2021-02-12 13:44:00", "timezone": "UTC+1", "duration": "00:11:00"},
        ),
    ],
)  # fmt: skip
def test_g1_the_game_values_on_the_replays(replay, values):
    """AC-1 and AC-2 at the domain: the replay's own UTC date with no offset applied, the recorder's offset beside it."""
    path = MS_SC / replay
    need(path)
    with contextlib.redirect_stdout(io.StringIO()):
        graph = to_graph(analyse(load_replay(path), MS_SC))
    game = next(n for n in graph.nodes if n.kind == "Game")
    assert {name: game.value(name) for name in values} == values


# --- F1 (Morgan's G6 F1 on S1): a lifted town hall and an Overlord in its cocoon still provide supply --------------


def _died(name_now, history, frame, unit_id):
    from sc2mindshare.reader.fork_api import UnitDiedEvent

    died = UnitDiedEvent.__new__(UnitDiedEvent)
    vars(died).update(unit=SimpleNamespace(name=name_now, type_history=history), frame=frame, unit_id=unit_id)
    return died


@pytest.mark.parametrize(
    ("finished", "mode", "value"),
    [
        ("CommandCenter", "CommandCenterFlying", 15),
        ("OrbitalCommand", "OrbitalCommandFlying", 15),
        ("Overlord", "OverseerCocoon", 8),  # the type history's name for an Overlord morphing into an Overseer
        ("Overlord", "TransportOverlordCocoon", 8),
    ],
)
def test_f1_a_provider_that_dies_in_a_mode_lowers_the_limit_by_what_it_provided(finished, mode, value):
    history = {0: SimpleNamespace(name=finished), 5000: SimpleNamespace(name=mode)}
    for fixes, lowered in ((("S1", "F1"), True), (("S1",), False)):
        tracker = _tracker(fixes)
        assert tracker.providerOf(_event(mode, history, 100, unit_id=1)) == finished  # finished: its limit was added
        assert tracker.providerOf(_died(mode, history, 6000, unit_id=1)) == (mode if lowered else None), fixes
        if lowered:
            assert tracker.providedBy(mode) == tracker.providedBy(finished) == value
        assert tracker.providerOf(_died(mode, history, 6000, unit_id=2)) is None  # never finished: never added


def test_f1_the_modes_are_those_four_and_no_planetary_fortress_lifts():
    from sc2reader.data import unit_lookup

    from sc2mindshare.analysis.detectors.trackers import PROVIDERS_IN_A_MODE

    assert PROVIDERS_IN_A_MODE == {
        "CommandCenterFlying": 15, "OrbitalCommandFlying": 15, "OverseerCocoon": 8, "TransportOverlordCocoon": 8,
    }  # fmt: skip
    assert not [n for n in unit_lookup["Terran"] if n.startswith("planetaryfortress") and n != "planetaryfortress"]


def test_f1_a_provider_death_lowers_the_limit_through_the_detector():
    from sc2mindshare.analysis.detectors.trackers import SupplyStatus

    for fixes, limit in ((("S1", "F1"), 7), (("S1",), 15)):
        st = _tracker(fixes)
        st.supplyHistory["p1"].append(SupplyStatus("05:00", 10, 15, 1))
        detector = SimpleNamespace(st=st)
        history = {0: SimpleNamespace(name="Overlord"), 5000: SimpleNamespace(name="TransportOverlordCocoon")}
        st.providerOf(_event("Overlord", history, 100, unit_id=1))
        death = _died("TransportOverlordCocoon", history, 6000, unit_id=1)
        vars(death).update(time="05:10", player="p1")  # the flavoured class reads the unit's owner
        assert detectors.SimpleDetector.providerDied(detector, death) is (limit == 7)
        assert st.supplyHistory["p1"][-1].limit == limit, fixes


@pytest.fixture(scope="module")
def uncounted_overlord_deaths():
    """Alcyone with every Overlord death made one the fork does not count (as the datapack makes a
    TransportOverlordCocoon's or an OverlordTransport's): the supply series with and without F1, and as it is."""
    need(ALCYONE)
    from sc2mindshare.reader.compat import type_at
    from sc2mindshare.reader.fork_api import _UnitDiedEventMixin

    original = _UnitDiedEventMixin.countableUnitDeath

    def uncounted(self, fixes=frozenset()):
        return False if type_at(self.unit, self.frame) == "Overlord" else original(self, fixes)

    others = {}  # every node but the supply blocks, and every link, per patched run (Morgan's finding 4 on F1)

    def series(fixes, patched):
        if patched:
            _UnitDiedEventMixin.countableUnitDeath = uncounted
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = analyse(load_replay(ALCYONE), MS_SC, fixes=fixes, with_exposed=True)
        finally:
            _UnitDiedEventMixin.countableUnitDeath = original
        if patched:
            graph = to_graph(result, mixed=fixes != LAYER_FIXES)
            others["F1" if "F1" in fixes else "without F1"] = (
                [n for n in graph.nodes if n.kind != "Supply Block"],
                list(graph.links),
            )
            if "F1" in fixes:  # the all-on graph carries the build order (CR-034) and its check (CR-035), the mixed none
                order = build_order(result.exposed, result.fixes)
                others["F1 build order"] = annotate(order, graph.build_checks, supply_reading(result.exposed))
        return [(p.player, p.time, p.supply, p.limit) for p in result.exposed.supply]

    without_f1 = tuple(f for f in LAYER_FIXES if f != "F1")
    out = {"as it is": series(LAYER_FIXES, False), "F1": series(LAYER_FIXES, True), "without F1": series(without_f1, True)}
    return out | {"others": others}


def _drops_of_8(series):
    last, drops = {}, 0
    for player, _time, _supply, limit in series:
        drops += player in last and last[player] - limit == 8
        last[player] = limit
    return drops


def test_f1_on_alcyone_an_uncounted_provider_death_still_lowers_the_limit(uncounted_overlord_deaths):
    """The fork counts every Overlord death on Alcyone; made uncounted, with F1 the supply series is the same as
    counted, and without F1 the limit does not go down at the 8 Overlord deaths."""
    s = uncounted_overlord_deaths
    assert s["F1"] == s["as it is"]
    assert _drops_of_8(s["as it is"]) - _drops_of_8(s["without F1"]) == 8


def _without_build_check(nodes, links):
    """``nodes`` and ``links`` without exactly what CR-035's ``with_build_check`` adds: the cards and missing entries
    (after every other node) and their links; on a compared node, its name ending, its sentence (the last paragraph of
    its description) and its entries; on a node with a ranged step, that last paragraph (G1); every node's entries. The steps' verdicts go with the steps
    (``_without_build_order``)."""
    added_kinds = ("Build Comparison", "Missing Step")
    ghosts = {n.id for n in nodes if n.kind == "Missing Step"}
    kept = [n for n in nodes if n.kind not in added_kinds]
    assert [n.kind for n in nodes[len(kept) :]] == [n.kind for n in nodes if n.kind in added_kinds]  # all at the end
    out = []
    for node in kept:
        verdict = dict(node.added).get("verdict")
        # G1 (D1b): a step whose supply is a range, and whose own sentence does not compare its supply, adds its supply
        # sentence to the same last paragraph, with or without a verdict
        ranged = any(s.supply_range is not None and not (s.verdict and s.verdict.supply_graded) for s in node.steps)
        if verdict:
            node = dataclasses.replace(node, name=node.name.rpartition(" · ")[0])
        if verdict or ranged:
            head, sep, _sentence = node.description.rpartition(X_LD + X_LD)
            node = dataclasses.replace(node, description=head if sep else "")
        out.append(dataclasses.replace(node, added=()))
    return out, [lk for lk in links if lk.node1 not in ghosts]


def _without_build_order(nodes, order):
    """``nodes`` without exactly what CR-034's ``with_build_order`` adds from ``order``: the steps on the nodes
    (the step #, at supply, started at and steps properties are written from them), the building-morph nodes (the
    last ``len(order.morphs)`` Building nodes, one per morph, in order) and each player's list at the end of his
    Player node's description. Each piece must be there to be taken out, so nothing else is ever ignored."""
    buildings = [i for i, n in enumerate(nodes) if n.kind == "Building"]
    morph_nodes = buildings[len(buildings) - len(order.morphs) :]
    assert [nodes[i].source.unit_ids for i in morph_nodes] == [(m.unit_id,) for m in order.morphs]
    out = []
    for i, node in enumerate(nodes):
        if i in morph_nodes:
            continue
        node = dataclasses.replace(node, steps=())
        if node.kind == "Player" and order.of(node.source.pid):
            listed = X_LD + X_LD + X_LD.join([order.heading(), *(s.line() for s in order.of(node.source.pid))])
            assert node.description.endswith(listed), node.id
            node = dataclasses.replace(node, description=node.description.removesuffix(listed))
        out.append(node)
    return out


def test_f1_an_uncounted_provider_death_changes_only_the_supply(uncounted_overlord_deaths):
    """Morgan's finding 4 on F1: with the 8 Overlord deaths uncounted, F1 changes the supply series and the supply
    blocks only: the battles, the Units nodes (counts and totals) and every other node and link are the same. The
    run with F1 is the current graph, so it carries the build order (CR-034); the run without F1 is a mixed one,
    which has none, so the build order is taken out of the first before the two are compared."""
    others = uncounted_overlord_deaths["others"]
    nodes, links = others["F1"]
    order = others["F1 build order"]
    assert order.steps and order.morphs and not any(n.steps for n in others["without F1"][0])
    nodes, links = _without_build_check(nodes, links)
    assert (_without_build_order(nodes, order), links) == others["without F1"]
    assert [n for n in nodes if n.kind == "Battle"] and [n for n in nodes if n.kind == "Units"]


# --- F2 (Morgan's G6 F2 on N1; Kevin's J7): a type change waits until the unit's interval is written ----------------


def test_f2_the_first_unit_of_a_type_that_changes_type_before_its_interval_is_written_moves_its_count(monkeypatch):
    """The first Widow Mine burrows within its 10 s interval: once the interval is written, it counts as a burrowed
    Widow Mine, and the Units node of the interval (1 Widow Mine) says 1 at the time."""
    from sc2mindshare.reader.compat import unit_text_at

    written = []

    class Node:  # a stand-in for UnitsNode: named by the type at the event (N1), counting its events
        def __init__(self, events, time, seq, fixes):
            self.name = unit_text_at(events[0].unit, events[0].frame, fixes).strip()
            self.count = len(events)
            written.append(self)

        def setCurrenCount(self, total):
            self.total = total

    monkeypatch.setattr(detectors, "UnitsNode", Node)
    p = "p"
    mine = SimpleNamespace(
        id=7, owner=p, name="WidowMineBurrowed",
        type_history={100: SimpleNamespace(name="WidowMine"), 300: SimpleNamespace(name="WidowMineBurrowed")},
    )  # fmt: skip
    for fixes, counts in (
        ({"N1", "P2", "F2"}, {"Widow Mine": 0, "Widow Mine Burrowed": 1}),
        ({"N1", "P2"}, {"Widow Mine": 1}),  # without F2 the move is skipped: the mine stays a Widow Mine
    ):
        written.clear()
        detector = detectors.SimpleDetector.__new__(detectors.SimpleDetector)
        vars(detector).update(
            ctx=SimpleNamespace(fixes=frozenset(fixes)),
            unitTypeCount={p: {}},
            currentIntervalEvents={p: {"WidowMine": [SimpleNamespace(unit=mine, frame=100, player=p)]}},
            waitingMoves=[],
            unitsByPlayerAndType={p: []},
            lastUnitsByType={p: {}},
            initDictByPlayer=lambda n: {p: {}},
            addLink=lambda a, b: None,
        )
        burrow = SimpleNamespace(unit=mine, frame=300, unit_type_name="WidowMineBurrowed")
        detector.moveUnitTypeCount(burrow)
        detector.flushUnitInterval("01:00", 0)
        assert [(n.name, n.count, n.total) for n in written] == [("Widow Mine", 1, 1)], fixes
        assert detector.unitTypeCount[p] == counts, fixes
        assert detector.waitingMoves == []


def test_f2_a_unit_already_written_moves_at_once():
    p = "p"
    tank = SimpleNamespace(
        id=8, owner=p, name="SiegeTankSieged",
        type_history={100: SimpleNamespace(name="SiegeTank"), 900: SimpleNamespace(name="SiegeTankSieged")},
    )  # fmt: skip
    other = SimpleNamespace(id=9, owner=p, name="SiegeTank", type_history={800: SimpleNamespace(name="SiegeTank")})
    for waiting in ({}, {"SiegeTank": [SimpleNamespace(unit=other, frame=800, player=p)]}):  # Morgan's P2 on F2
        detector = detectors.SimpleDetector.__new__(detectors.SimpleDetector)
        vars(detector).update(
            ctx=SimpleNamespace(fixes=frozenset({"N1", "P2", "F2"})),
            unitTypeCount={p: {"Siege Tank": 2}},
            currentIntervalEvents={p: waiting},  # another tank of the same owner and type waits: not this one
            waitingMoves=[],
        )
        detector.moveUnitTypeCount(SimpleNamespace(unit=tank, frame=900, unit_type_name="SiegeTankSieged"))
        assert detector.unitTypeCount[p] == {"Siege Tank": 1, "Sieged Tank": 1}, waiting
        assert detector.waitingMoves == []
        assert detector.isWaiting(other) is bool(waiting) and not detector.isWaiting(tank)


def test_f2_on_alcyone_the_roach_that_became_a_ravager_in_its_interval_counts_at_its_node(n1_graphs):
    """Alcyone's Units-162: lilTiGGer's one Roach of 14:50, which became a Ravager Cocoon before the interval was
    written; it said 0 Roaches at the time before F2."""
    node = n1_graphs["fixed"]["Units-162"]
    assert (node.name, node.value("count"), node.value("total at time")) == ("Roach", "1", "1")


def _waiting_detector(p, counts, waiting_unit, waiting_type, fixes=("N1", "P2", "F2")):
    """A SimpleDetector with ``waiting_unit`` finished in the unwritten interval, and Units nodes recorded."""
    from sc2mindshare.reader.compat import unit_text_at

    class Node:  # a stand-in for UnitsNode: named by the type at the event (N1), counting its events
        def __init__(self, events, time, seq, fixes):
            self.name = unit_text_at(events[0].unit, events[0].frame, fixes).strip()
            self.count = len(events)
            detector.written.append(self)

        def setCurrenCount(self, total):
            self.total = total

    detector = detectors.SimpleDetector.__new__(detectors.SimpleDetector)
    vars(detector).update(
        ctx=SimpleNamespace(fixes=frozenset(fixes)),
        unitTypeCount={p: dict(counts)},
        currentIntervalEvents={p: {waiting_type: [SimpleNamespace(unit=waiting_unit, frame=100, player=p)]}},
        waitingMoves=[],
        unitsByPlayerAndType={p: []},
        lastUnitsByType={p: {}},
        initDictByPlayer=lambda n: {p: {}},
        addLink=lambda a, b: None,
        written=[],
        Node=Node,
    )
    return detector


# Morgan's P1 on F2, Stefan's D1a (ledger entry F2b): a waiting unit's death waits in the same queue as its changes.


@pytest.mark.parametrize(
    ("counts", "after"),
    [
        ({"Roach": 1, "Ravager Cocoon": 1}, {"Roach": 1, "Ravager Cocoon": 1}),  # old and new type both counted
        ({"Roach": 1}, {"Roach": 1, "Ravager Cocoon": 0}),  # old counted, new not (Morgan's probe)
        ({}, {"Roach": 0, "Ravager Cocoon": 0}),  # the first Roach
    ],
)
def test_f2_a_waiting_unit_that_changes_type_and_dies_before_the_flush_is_not_counted_alive(monkeypatch, counts, after):
    """Morgan's P1 on F2: the Roach finishes, becomes a Ravager Cocoon and dies, all before its interval is
    written; its death waits in the same queue, in event order, so it leaves the count of its type at death."""
    p = "p"
    roach = SimpleNamespace(
        id=7, owner=p, name="RavagerCocoon",
        type_history={100: SimpleNamespace(name="Roach"), 300: SimpleNamespace(name="RavagerCocoon")},
    )  # fmt: skip
    detector = _waiting_detector(p, counts, roach, "Roach")
    monkeypatch.setattr(detectors, "UnitsNode", detector.Node)
    detector.moveUnitTypeCount(SimpleNamespace(unit=roach, frame=300, unit_type_name="RavagerCocoon"))
    detector.releaseUnitCount(SimpleNamespace(unit=roach, frame=350, player=p))
    detector.flushUnitInterval("01:00", 0)
    assert [(n.name, n.count, n.total) for n in detector.written] == [("Roach", 1, counts.get("Roach", 0) + 1)]
    assert detector.unitTypeCount[p] == after and detector.waitingMoves == []


def test_f2_a_written_unit_dies_at_once_and_without_f2_the_death_is_todays(monkeypatch):
    p = "p"
    roach = SimpleNamespace(id=7, owner=p, name="Roach", type_history={100: SimpleNamespace(name="Roach")})
    other = SimpleNamespace(id=8, owner=p, name="Roach", type_history={50: SimpleNamespace(name="Roach")})
    detector = _waiting_detector(p, {"Roach": 2}, roach, "Roach")
    detector.releaseUnitCount(SimpleNamespace(unit=other, frame=350, player=p))  # written: leaves at once
    assert detector.unitTypeCount[p] == {"Roach": 1} and detector.waitingMoves == []
    faithful = _waiting_detector(p, {}, roach, "Roach", fixes=("N1", "P2"))
    faithful.releaseUnitCount(SimpleNamespace(unit=roach, frame=350, player=p))  # the fork: no count yet, nothing
    assert faithful.unitTypeCount[p] == {}


def test_f2_a_widow_mine_that_burrows_and_unburrows_in_its_interval_ends_unburrowed(monkeypatch):
    """Morgan's P3 on F2: the waiting changes are applied in their order."""
    p = "p"
    mine = SimpleNamespace(
        id=7, owner=p, name="WidowMine",
        type_history={
            100: SimpleNamespace(name="WidowMine"),
            300: SimpleNamespace(name="WidowMineBurrowed"),
            500: SimpleNamespace(name="WidowMine"),
        },
    )  # fmt: skip
    detector = _waiting_detector(p, {}, mine, "WidowMine")
    monkeypatch.setattr(detectors, "UnitsNode", detector.Node)
    detector.moveUnitTypeCount(SimpleNamespace(unit=mine, frame=300, unit_type_name="WidowMineBurrowed"))
    detector.moveUnitTypeCount(SimpleNamespace(unit=mine, frame=500, unit_type_name="WidowMine"))
    detector.flushUnitInterval("01:00", 0)
    assert [(n.name, n.count, n.total) for n in detector.written] == [("Widow Mine", 1, 1)]
    assert detector.unitTypeCount[p] == {"Widow Mine": 1, "Widow Mine Burrowed": 0}


def test_f2b_on_alcyone_units_born_and_killed_in_their_interval_count_at_their_node(n1_graphs):
    """The F2b entry (CHANGES.md, Stefan's D1a): the units of a node that die before its interval is written are
    still counted at the node's time."""
    nodes = n1_graphs["fixed"]
    assert [tuple(nodes[i].value(k) for k in ("type", "count", "total at time")) for i in ("Units-169", "Units-92")] == [
        ("Roach", "2", "2"),
        ("Stalker", "2", "3"),
    ]


# --- CR-070 (Stefan's D1a): a battle death whose cost cannot be found stops the run ---------------------------------
# Every failure goes through a whole battle (``_analysed_alcyone``: Alcyone analysed with a broken support table or
# unit data), never ``Battle.deathCost`` alone: the defect was the order inside ``Battle.__init__`` (the death
# counted, then its cost looked up inside the catch-all handler), which a deathCost-only test cannot see.

SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"
_DEATH_7_48 = "ShieldBattery 72613891 (blacksquall) that died at 07:48 in Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
NO_ROW = f'cannot find the cost of {_DEATH_7_48}: unitsInfo.csv has no "Shield Battery" row'
NO_EXTRACTOR = (
    "cannot find the cost of ExtractorRich 72613891 (blacksquall) that died at 07:48 in "
    "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay: the replay's unit data has no Extractor"
)


def _bad_cell(minerals, gas):
    return (
        f'cannot find the cost of {_DEATH_7_48}: the "Shield Battery" row of unitsInfo.csv has Minerals {minerals!r} '
        f"and Gas {gas!r}; each must be a whole number or empty"
    )


def _support(tmp_path, battery):
    """A support root with copies of the support tables in which the Shield Battery row is ``battery(row)`` (the
    row's text without its line end), or removed when that is None; every other byte as in the real table."""
    import shutil

    need(MS_SC / "unitsInfo.csv")
    root = tmp_path / "support"
    root.mkdir()
    for name in ("upgradesInfo.csv", "ImageTracking.csv"):
        shutil.copyfile(MS_SC / name, root / name)
    with (MS_SC / "unitsInfo.csv").open(encoding="utf-8", newline="") as f:
        lines = f.read().splitlines(keepends=True)
    i = next(i for i, line in enumerate(lines) if line.startswith("Shield Battery,"))
    row = lines[i].rstrip("\r\n")
    new = battery(row)
    lines[i : i + 1] = [] if new is None else [new + lines[i][len(row) :]]
    with (root / "unitsInfo.csv").open("w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))
    return root


def _cells(minerals=None, gas=None):
    """The Shield Battery row with its Minerals and/or Gas cell replaced."""

    def edit(row):
        cells = row.split(",")
        cells[1] = cells[1] if minerals is None else minerals
        cells[2] = cells[2] if gas is None else gas
        return ",".join(cells)

    return edit


def _without_extractor(replay):
    """The replay's unit data without its Extractor. sc2reader shares one datapack object per game build across
    the process, so the replay gets a copy of its own: the shared one, and every later test, are left as they are."""
    import copy

    datapack = copy.copy(replay.datapack)
    datapack.units = {key: kind for key, kind in replay.datapack.units.items() if kind.name != "Extractor"}
    replay.datapack = datapack


def _without_battery_killers(replay):
    """Both of blacksquall's Shield Battery deaths with no killing unit, so no battle is formed from them."""
    for e in replay.tracker_events:
        if type(e).__name__ == "UnitDiedEvent" and e.unit is not None and e.unit.name == "ShieldBattery":
            e.unit.killing_unit = None


def _graph(result):
    return to_graph(
        result, () if not result.fixes else None, mixed=bool(result.fixes) and result.fixes != frozenset(LAYER_FIXES)
    )


@pytest.fixture(scope="module")
def cr070_intact():
    """The intact-data runs the CR-070 tests compare with, each made once, when first asked for."""
    need(ALCYONE)
    without = tuple(f for f in LAYER_FIXES if f != "P10c")
    makers = {
        "fixed": lambda: _analysed_alcyone(),
        "no battery killers": lambda: _analysed_alcyone(edit_replay=_without_battery_killers),
        "faithful": lambda: _analysed_alcyone(()),
        "faithful rich": lambda: _analysed_alcyone((), as_type="ExtractorRich"),
        "without P10c": lambda: _analysed_alcyone(without),
        "without P10c rich": lambda: _analysed_alcyone(without, as_type="ExtractorRich"),
    }
    cache = {}

    def get(label):
        if label not in cache:
            cache[label] = makers[label]()
        return cache[label]

    return get


def _stops(message, **run):
    """The run stops with exactly ``message`` (a ValueError leaving ``analyse``: no result, so no battle at all),
    and the catch-all handler never printed its line for the death (the error is not reduced to a log line)."""
    log = io.StringIO()
    with pytest.raises(ValueError) as stop:
        _analysed_alcyone(log=log, **run)
    assert type(stop.value) is ValueError and str(stop.value) == message
    swallowed = [line for line in log.getvalue().splitlines() if "ERR NO KILLING UNIT" in line]
    assert not [line for line in swallowed if "ShieldBattery" in line or "ExtractorRich" in line]
    return stop.value


@pytest.mark.parametrize(
    "battery",
    [
        lambda row: None,
        lambda row: "ShieldBattery" + row[len("Shield Battery") :],
        lambda row: "Shield battery" + row[len("Shield Battery") :],
    ],
    ids=["row removed", "named ShieldBattery", "named Shield battery"],
)
def test_cr070_ac1_a_missing_cost_row_stops_the_export_naming_the_replay_the_death_time_and_the_structure(tmp_path, battery):
    """AC-1: no "Shield Battery" row (a name differing only in case or spacing is no match): the export stops at
    blacksquall's 7:48 battery death (Battle-12 runs 7:36-7:57; the death's own time is named)."""
    need(ALCYONE)
    _stops(NO_ROW, support=_support(tmp_path, battery))


@pytest.mark.parametrize(
    ("minerals", "gas", "named"),
    [("100.0", None, ("100.0", "0")), ("n/a", None, ("n/a", "0")), ("   ", None, ("   ", "0")), (None, "n/a", ("100", "n/a"))],
    ids=["minerals 100.0", "minerals n/a", "minerals spaces", "gas n/a"],
)
def test_cr070_ac2_a_cost_that_is_not_a_whole_number_stops_the_export(tmp_path, minerals, gas, named):
    """AC-2: a Minerals or Gas cell that is not a whole number ("100.0", "n/a", only spaces) stops as in AC-1."""
    need(ALCYONE)
    _stops(_bad_cell(*named), support=_support(tmp_path, _cells(minerals, gas)))


def test_cr070_ac2_an_empty_cost_cell_still_reads_0(tmp_path, p10c_battles):
    """AC-2's boundary: an empty Minerals cell completes, and both batteries count at 0 minerals (100 less in
    Battle-12 and Battle-27 than with the table's 100); nothing else in any battle changes."""
    runs, _ = p10c_battles
    empty = _alcyone_battles(support=_support(tmp_path, _cells(minerals="")))
    assert _differences(runs["fixed"], empty) == {11: ["minerals"], 26: ["minerals"]}
    for i in (11, 26):
        assert empty[i]["minerals"] == (runs["fixed"][i]["minerals"][0], runs["fixed"][i]["minerals"][1] - 100)
        assert empty[i]["dead"] == runs["fixed"][i]["dead"] and "Shield Battery" in empty[i]["lost"][1]


def test_cr070_ac2_a_row_with_no_cost_cell_reads_0():
    """AC-2's other boundary: a short row with no Minerals or Gas cell (csv.DictReader gives None) reads 0 like an
    empty one. On the cost alone: a row that short has no Build Time either, and the Building node of a battery
    (P10b) needs it before any battle, so no whole export can carry such a row."""
    from sc2mindshare.analysis.battle import Battle

    battle = SimpleNamespace(
        ctx=SimpleNamespace(
            fixes=frozenset({"P10c"}),
            simple=SimpleNamespace(unitsInfoDict={"Shield Battery": {"Minerals": None, "Gas": None}}),
            replay=SimpleNamespace(filename="x.SC2Replay"),
        )
    )
    unit = SimpleNamespace(name="ShieldBattery", minerals=0, vespene=0, supply=0)
    assert Battle.deathCost(battle, SimpleNamespace(unit=unit)) == (0, 0, 0)


def test_cr070_ac3_a_replay_without_an_extractor_stops_the_export(tmp_path):
    """AC-3: the 7:48 battery made a Rich Extractor (CR-068's harness) and the replay's unit data without its
    Extractor: the export stops naming the Rich Extractor's death and what is missing."""
    need(ALCYONE)
    _stops(NO_EXTRACTOR, as_type="ExtractorRich", edit_replay=_without_extractor)


@pytest.mark.parametrize("route", ["no row", "bad cell", "no extractor"])
def test_cr070_ac4_a_death_is_never_counted_without_its_cost_and_its_killer(tmp_path, route):
    """AC-4: on each route the error leaves the analysis as the clear ValueError (never a bare KeyError, ValueError
    from int() or StopIteration, and never only a line in the log), so no battle with the death exists."""
    need(ALCYONE)
    if route == "no extractor":
        stop = _stops(NO_EXTRACTOR, as_type="ExtractorRich", edit_replay=_without_extractor)
        assert stop.__cause__ is None
    elif route == "bad cell":
        stop = _stops(_bad_cell("n/a", "0"), support=_support(tmp_path, _cells(minerals="n/a")))
        assert type(stop.__cause__) is ValueError  # int()'s own error, kept as the cause
    else:
        stop = _stops(NO_ROW, support=_support(tmp_path, lambda row: None))
        assert stop.__cause__ is None


def test_cr070_ac6_the_first_death_that_needs_the_missing_row_is_named_every_time(tmp_path):
    """AC-6: both batteries (7:48 in Battle-12, 14:33 in Battle-27) need the missing row; every run names 7:48."""
    need(ALCYONE)
    support = _support(tmp_path, lambda row: None)
    for _ in range(3):
        assert "14:33" not in str(_stops(NO_ROW, support=support))


@pytest.mark.parametrize("game", ["spine", "alcyone without an extractor", "alcyone batteries in no battle"])
def test_cr070_ac7_broken_data_no_death_needs_does_not_stop_the_export(tmp_path, cr070_intact, game):
    """AC-7: the Shield Battery's Minerals "n/a" on spine (its batteries all survive) and on Alcyone with both
    battery deaths in no battle (no killer); Alcyone's unit data without an Extractor (no Rich Extractor dies):
    each default export completes and equals the same game's with intact data."""
    if game == "spine":
        need(SPINE)
        with contextlib.redirect_stdout(io.StringIO()):
            intact = analyse(load_replay(SPINE), MS_SC)
            broken = analyse(load_replay(SPINE), _support(tmp_path, _cells(minerals="n/a")))
    elif game == "alcyone without an extractor":
        intact, broken = cr070_intact("fixed"), _analysed_alcyone(edit_replay=_without_extractor)
    else:
        intact = cr070_intact("no battery killers")
        broken = _analysed_alcyone(support=_support(tmp_path, _cells(minerals="n/a")), edit_replay=_without_battery_killers)
    assert to_graph(broken) == to_graph(intact)


def test_cr070_ac8_a_stopped_export_leaves_nothing_behind(tmp_path, cr070_intact):
    """AC-8: after the AC-1 stop, the intact table and a freshly loaded Alcyone in the same process give exactly
    a clean run's output (the clean run made before the stop)."""
    clean = to_graph(cr070_intact("fixed"))
    _stops(NO_ROW, support=_support(tmp_path, lambda row: None))
    assert to_graph(_analysed_alcyone()) == clean


@pytest.mark.parametrize("mode", ["bug-faithful", "every fix but P10c"])
@pytest.mark.parametrize("broken", ["no row", "no extractor"])
def test_cr070_ac10_the_bug_faithful_mode_never_stops_for_this(tmp_path, cr070_intact, mode, broken):
    """AC-10: with the AC-1 table or the AC-3 unit data, the bug-faithful run and the run with every fix but P10c
    complete. The bug-faithful output equals today's on intact data (also as the legacy CSV oracle), and so does the
    run without P10c, except that with no row its battery Building nodes are missing (P10b reads the same row
    for them and its KeyError is swallowed, detectors.py; the known bug beside CR-070, out of scope): there its
    battles are compared."""
    fixes = () if mode == "bug-faithful" else tuple(f for f in LAYER_FIXES if f != "P10c")
    label = ("faithful" if mode == "bug-faithful" else "without P10c") + (" rich" if broken == "no extractor" else "")
    if broken == "no row":
        result = _analysed_alcyone(fixes, support=_support(tmp_path, lambda row: None))
    else:
        result = _analysed_alcyone(fixes, as_type="ExtractorRich", edit_replay=_without_extractor)
    graph, intact = _graph(result), _graph(cr070_intact(label))
    if mode == "bug-faithful":
        assert graph == intact
        assert legacy_csv(result) == legacy_csv(cr070_intact(label))
    elif broken == "no row":
        assert [n for n in graph.nodes if n.kind == "Battle"] == [n for n in intact.nodes if n.kind == "Battle"]
        assert len(graph.nodes) < len(intact.nodes)
    else:
        assert graph == intact


# --- CR-072 (Stefan's D2a): a battle records the killer of every big unit it loses -------------------------------

CR072_REPLAYS = {"alcyone": ALCYONE, "spine": SPINE}
CR072_MODES = {"fixed": LAYER_FIXES, "faithful": ()}


@pytest.fixture(scope="module")
def cr072_runs():
    """Alcyone and spine analysed with every fix and bug-faithful, each made once, when first asked for: the
    battles (``BattleNode`` objects of the result) and the run log (the layer's prints)."""
    from sc2mindshare.analysis.exports.battleNode import BattleNode

    cache = {}

    def get(replay, mode):
        if (replay, mode) not in cache:
            path = CR072_REPLAYS[replay]
            need(path)
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                result = analyse(load_replay(path), MS_SC, fixes=CR072_MODES[mode])
            battles = [n for n in result.nodes if isinstance(n, BattleNode)]
            cache[replay, mode] = (battles, log.getvalue())
        return cache[replay, mode]

    return get


def _cr072_killer_record(battle):
    """The battle's record of who killed what: every killing unit in ``killersByPlayer``, as a multiset of
    identities."""
    from collections import Counter

    return Counter(id(killer) for killers in battle.killersByPlayer.values() for killer in killers)


def _cr072_dead(battle):
    return [e for player in (battle.player1, battle.player2) for e in battle.deadUnitsByPlayer[player]]


@pytest.mark.parametrize("mode", list(CR072_MODES))
def test_cr072_ac1_the_oracles_killer_is_recorded(cr072_runs, mode):
    """AC-1: on Alcyone the Oracle (3 supply) dies at 11:05 in the battle starting at 11:05 (665 s); in both modes
    that battle records the Oracle's killer, once, and counts one big unit lost for its owner, blacksquall."""
    from collections import Counter

    battles, _log = cr072_runs("alcyone", mode)
    (battle,) = [b for b in battles if b.startSec == 665]
    (oracle,) = _cr072_dead(battle)
    assert (oracle.unit.name, oracle.unit.owner.name, oracle.unit.killing_unit.name) == ("Oracle", "blacksquall", "Queen")
    assert _cr072_killer_record(battle) == Counter({id(oracle.unit.killing_unit): 1})
    assert {p.name: n for p, n in battle.bigUnitsLost.items()} == {"blacksquall": 1, "lilTiGGer": 0}


CR072_BIG_DEATHS = {  # (death second, type, killer type, the battle's start in seconds), AC-2
    "alcyone": [
        (489, "RavagerCocoon", "VoidRay", 486),
        (503, "Ravager", "VoidRay", 503),
        (615, "Disruptor", "Hydralisk", 605),
        (618, "Immortal", "Roach", 605),
        (665, "Oracle", "Queen", 665),
        (924, "VoidRay", "Mutalisk", 917),
    ],
    "spine": [(410, "Immortal", "Roach", 381), (432, "Immortal", "Roach", 381)],
}


@pytest.mark.parametrize("mode", list(CR072_MODES))
@pytest.mark.parametrize("replay", list(CR072_REPLAYS))
def test_cr072_ac2_every_battle_records_one_killer_for_each_of_its_dead(cr072_runs, replay, mode):
    """AC-2: in every battle the record of who killed what holds exactly one entry for each of the battle's dead,
    its killer (a multiset of unit identities), so it has as many entries as the battle has dead; and each big-unit
    death's killer is in its battle's record."""
    from collections import Counter

    battles, _log = cr072_runs(replay, mode)
    assert len(battles) == {"alcyone": 30, "spine": 16}[replay]
    for battle in battles:
        dead = _cr072_dead(battle)
        assert _cr072_killer_record(battle) == Counter(id(e.unit.killing_unit) for e in dead), battle.startSec
        assert sum(_cr072_killer_record(battle).values()) == battle.p1dc + battle.p2dc == len(dead)
    big = sorted(
        (e.second, e.unit.name, e.unit.killing_unit.name, b.startSec, id(e.unit.killing_unit) in _cr072_killer_record(b))
        for b in battles
        for e in _cr072_dead(b)
        if b.deathCost(e)[2] >= b.BIG_UNIT_SUPPLY_THRESHOLD
    )
    assert big == [(*death, True) for death in CR072_BIG_DEATHS[replay]]


CR072_BIG_UNITS_LOST = {  # battle start (s) -> {player name: big units lost}; every other battle and player 0
    "alcyone": {486: {"lilTiGGer": 1}, 503: {"lilTiGGer": 1}, 605: {"blacksquall": 2}, 665: {"blacksquall": 1}, 917: {"blacksquall": 1}},
    "spine": {381: {"serega": 2}},
}  # fmt: skip


@pytest.mark.parametrize("mode", list(CR072_MODES))
@pytest.mark.parametrize("replay", list(CR072_REPLAYS))
def test_cr072_ac2_every_battle_counts_its_big_units_lost_as_numbers(cr072_runs, replay, mode):
    """AC-2: every battle counts its big units lost (3 supply or more) as a number for each of its two players:
    the listed values, and 0 everywhere else."""
    battles, _log = cr072_runs(replay, mode)
    for battle in battles:
        players = (battle.player1, battle.player2)
        assert set(battle.bigUnitsLost) == set(players), battle.startSec
        assert all(type(n) is int for n in battle.bigUnitsLost.values()), (battle.startSec, battle.bigUnitsLost)
        want = CR072_BIG_UNITS_LOST[replay].get(battle.startSec, {})
        assert {p.name: battle.bigUnitsLost[p] for p in players} == {p.name: want.get(p.name, 0) for p in players}


@pytest.mark.parametrize("mode", list(CR072_MODES))
@pytest.mark.parametrize("replay", list(CR072_REPLAYS))
def test_cr072_ac3_the_run_log_reports_no_false_missing_killer(cr072_runs, replay, mode):
    """AC-3: no run-log line holds "ERR NO KILLING UNIT" (the catch-all's text; the other print in the same loop says
    only "NO KILLING UNIT"), and the log is 6 lines shorter on Alcyone (86 -> 80) and 2 on spine (4 -> 2)."""
    _battles, log = cr072_runs(replay, mode)
    lines = log.splitlines()
    assert [line for line in lines if "ERR NO KILLING UNIT" in line] == []
    assert len(lines) == {"alcyone": 80, "spine": 2}[replay]
