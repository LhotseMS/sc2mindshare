"""CR-023 (T22): the layer fixes, each switched by its ledger id (analysis.fixes.LAYER_FIXES)."""

import contextlib
import io
import os
import pathlib
from types import SimpleNamespace

import pytest

from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.detectors.detectors import BaseDetector
from sc2mindshare.analysis.fixes import FIXES, LAYER_FIXES
from sc2mindshare.analysis.run import AnalysisResult, analyse, legacy_csv
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"


def test_the_layer_fixes_in_ledger_order():
    assert LAYER_FIXES == ("P1", "P1b", "P1c", "S1", "P8", "P2", "P11", "N1", "P10", "S6", "P9", "P10b")


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
    faithful = AnalysisResult((), (), None)
    full = AnalysisResult((), (), None, fixes=frozenset(LAYER_FIXES))
    partial = AnalysisResult((), (), None, fixes=frozenset({"P1", "P1b"}))  # any proper subset
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
    before_s6 = tuple(f for f in LAYER_FIXES if f != "S6")  # the S1/S1b entries' input; S6 came later
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
    # P10 drops 7 spell-effect groups; P10b turns Units groups into Buildings (Alcyone 3 for 3, spine 1 for 2)
    assert len(graphs["fixed"].nodes) == len(graphs["faithful"].nodes) + 1 - 7 - (4 + 3 + 11 if "Alcyone" in replay else 0) + (
        2 + 1 if "spine" in replay else 0
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
    assert (before["Building-6"].name, after["Building-6"].name) == ("Warp Gate", "Gateway")
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
        ("Shield Battery", "blacksquall", 151),
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
    if not ALCYONE.exists():
        pytest.skip(f"missing input {ALCYONE}")
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
