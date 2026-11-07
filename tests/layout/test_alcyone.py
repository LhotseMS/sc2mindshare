"""CR-014 on Alcyone: Leo's predictions (layout-spec.md §5, §7; round2-leo.md), invariants (QA design
§4) and the live snapshot G-SNAP-current (both modes; G-SNAP-1 is frozen since Stefan checked it, B2)."""

import contextlib
import copy
import importlib.util
import io
import json
import math
import os
import pathlib
import re
import sys

import pytest

from sc2mindshare.analysis.fixes import LAYER_FIXES
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.export.mindshare_json import build_document, to_json
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import TIMELINE_LANES, Profile
from sc2mindshare.layout.sweep import LayoutItem, layout
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
GOLDEN = CHECKOUT / "tests" / "golden" / "alcyone"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


golden = _load("golden", CHECKOUT / "tests" / "golden" / "golden.py")


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"


def need(path, what):
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(str(exc))
        pytest.skip(str(exc))


@pytest.fixture(scope="module")
def clock_map():
    """CR-069: the clocks' picture IDs from the committed fixture record (localhost:3042), as the goldens are built."""
    return golden.fixture_clock_map()


@pytest.fixture(scope="module")
def graph():
    with contextlib.redirect_stdout(io.StringIO()):
        return to_graph(analyse(load_replay(need(ALCYONE, "Alcyone replay")), MS_SC))


def _graph_without(*left_out):
    fixes = tuple(f for f in LAYER_FIXES if f not in left_out)
    with contextlib.redirect_stdout(io.StringIO()):
        return to_graph(analyse(load_replay(need(ALCYONE, "Alcyone replay")), MS_SC, fixes=fixes), mixed=True)


@pytest.fixture(scope="module")
def graph_before_s1():
    """The graph Leo's round-2 predictions were made for: every fix but CR-023's S1 (the supply series),
    which replaces the Supply Blocks, and N1, which came later (an explicit mix). The layout code is the
    same for all."""
    return _graph_without("S1", "N1", "S6", "P10b", "S7")


@pytest.fixture(scope="module")
def graph_before_n1():
    """The graph Leo's S1 predictions were made for: every fix but CR-023's N1 (names by the type at the
    time), S6 (supply by the type at the time), P10b (batteries as Buildings) and S7 (Drones leave at
    placement; the limit stops at 200), which came later. N1 starts the first Gateway 39 s earlier, which opens a 0:50 window in the
    compressed timeline and moves what follows it by one window; the N1 entries and the goldens hold that."""
    return _graph_without("N1", "S6", "P10b", "S7")


@pytest.fixture(scope="module", params=["compressed", "linear"])
def placed(request, graph, clock_map):
    return request.param, layout(items(graph), Profile(timeline=request.param), clock_map)


# --- Leo's predictions -----------------------------------------------------------------------------

SUPPLY_BLOCKS = {  # round2-leo.md, compressed, B9 applied: (centre x, width)
    "Supply Block-0": (3.75, 10.0),
    "Supply Block-1": (21.25, 10.0),
    "Supply Block-2": (73.75, 10.0),
    "Supply Block-3": (86.25, 10.0),
    "Supply Block-4": (91.25, 5.0),
    "Supply Block-5": (110.0, 22.5),
    "Supply Block-6": (155.0, 2.5),
    "Supply Block-7": (168.75, 5.0),
    "Supply Block-8": (175.0, 2.5),
    "Supply Block-9": (188.75, 20.0),
    "Supply Block-10": (200.0, 7.5),
}


def test_predictions_compressed(graph_before_s1, clock_map):
    """Leo's predictions (round2-leo.md), on the input they were made for (``graph_before_s1``)."""
    graph = graph_before_s1
    r = layout(items(graph), Profile(), clock_map)
    assert len(r.rows) == 83 and r.rows[0][2] == 0 and r.rows[-1][2] == 205
    mains = [n.id for n in graph.nodes if n.kind == "Building" and n.start.seconds == -71]
    assert [r.positions[m] for m in mains] == [(0.0, -8.0), (0.0, 8.0)]  # row 0, lilTiGGer on -y (B9, B13)
    names = [c.file_name for c in r.extra_nodes]
    assert "0-10.png" in names and "58-50.png" not in names
    for sb, (centre, width) in SUPPLY_BLOCKS.items():
        assert r.positions[sb][0] == pytest.approx(centre) and r.sizes[sb][0] == pytest.approx(width), sb
        assert abs(r.positions[sb][1]) == 12.16
    assert r.positions["Battle-16"][1] == pytest.approx(2.659, abs=5e-4)
    assert r.positions["Battle-25"][1] == pytest.approx(3.735, abs=5e-4)
    assert r.positions["Battle-28"][1] == pytest.approx(3.355, abs=5e-4)
    assert r.warnings == []


#: Leo's predictions for the 7 Supply Blocks after CR-023's S1 with S5, from spec r3 alone, written before
#: he opened the regenerated snapshot (.scratch/plan/streams/leo-supply-s1-predictions.md): block ->
#: (compressed centre x, compressed width, linear centre x, linear width, side).
SUPPLY_BLOCKS_S1 = {
    "Supply Block-0": (7.5, 2.5, 10.0, 7.5, -1),
    "Supply Block-1": (21.25, 5.0, 31.25, 5.0, -1),
    "Supply Block-2": (75.0, 2.5, 100.0, 2.5, -1),
    "Supply Block-3": (155.0, 2.5, 188.75, 5.0, -1),
    "Supply Block-4": (166.25, 10.0, 201.25, 10.0, -1),
    "Supply Block-5": (7.5, 2.5, 7.5, 2.5, 1),
    "Supply Block-6": (188.75, 15.0, 226.25, 15.0, 1),
}


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_the_supply_blocks_after_s1_are_where_leo_predicted(graph_before_n1, clock_map, mode):
    """Leo's predictions for the 7 blocks, both modes, on the input they were made for (``graph_before_n1``);
    the round-2 predictions above stay on theirs (``graph_before_s1``)."""
    graph = graph_before_n1
    r = layout(items(graph), Profile(timeline=mode), clock_map)
    blocks = [n.id for n in graph.nodes if n.kind == "Supply Block"]
    assert blocks == list(SUPPLY_BLOCKS_S1)
    for block, (cx, cw, lx, lw, side) in SUPPLY_BLOCKS_S1.items():
        x, width = (cx, cw) if mode == "compressed" else (lx, lw)
        assert r.positions[block] == (pytest.approx(x), pytest.approx(side * 12.16)), block
        assert r.sizes[block] == [pytest.approx(width), 1], block


def test_predictions_linear(graph, clock_map):
    r = layout(items(graph), Profile(timeline="linear"), clock_map)
    # 100 windows, 14 of them empty (17 before P10b's two battery starts, 15 before CR-034's Warp Gates at 7:14)
    assert r.rows[-1][2] == 247.5
    assert len(r.rows) == 86


# --- invariants (QA design §4) -------------------------------------------------------------------------


def test_i1_every_item_has_one_finite_position_and_a_size(graph, placed):
    _, r = placed
    for n in graph.nodes:
        x, y = r.positions[n.id]
        assert math.isfinite(x) and math.isfinite(y) and n.id in r.sizes


def test_i2_x_never_decreases_with_time_inside_a_bucket(graph, placed):
    _, r = placed
    for kind in ("Battle", "Building", "Stats", "Chat", "Ability", "Units", "Supply Block"):
        nodes = sorted((n for n in graph.nodes if n.kind == kind), key=lambda n: (n.start, graph.nodes.index(n)))
        xs = [r.positions[n.id][0] for n in nodes]
        if kind != "Supply Block":
            assert xs == sorted(xs), kind


def test_i3_swapping_the_players_mirrors_y_except_battles(graph, clock_map, placed):
    mode, r = placed
    swapped = []
    for i in items(graph):
        player = i.player
        if i.type == "Player":
            continue
        swapped.append(i)
    players = [i for i in items(graph) if i.type == "Player"]
    mirrored = [LayoutItem(p.id, p.type, p.t, p.order, players[1 - k].player) for k, p in enumerate(players)] + swapped
    m = layout(mirrored, Profile(timeline=mode), clock_map)
    for n in graph.nodes:
        if n.kind in ("Battle", "Game", "Player"):  # CR-073: the four lane types mirror by side too
            continue
        assert m.positions[n.id][0] == pytest.approx(r.positions[n.id][0])
        assert m.positions[n.id][1] == pytest.approx(-r.positions[n.id][1]), n.id


def test_i13_determinism_and_shuffled_input(graph, clock_map, placed):
    mode, r = placed
    shuffled = list(reversed(items(graph)))  # each item keeps its own order value
    again = layout(shuffled, Profile(timeline=mode), clock_map)
    assert again.positions == r.positions and [c for c in again.extra_nodes] == list(r.extra_nodes)


# --- the live snapshot G-SNAP-current -------------------------------------------------------------------


def _document(graph, clock_map, mode):
    return build_document(graph, layout(items(graph), Profile(timeline=mode), clock_map))


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_snapshot(graph, clock_map, mode):
    doc = _document(graph, clock_map, mode)
    text = to_json(doc)
    assert text == to_json(_document(graph, clock_map, mode))  # byte-identical runs
    expected = json.loads((GOLDEN / f"G-SNAP-current-{mode}.json").read_text(encoding="utf-8"))
    report = golden.diff_json(expected, doc)  # CR-069: clock nodes in the local form need no clock map for M2
    assert report.ok, str(report)
    # 136 before P10b, 140 before CR-034 (BO1: the two Warp Gates at 7:14 open the 7:10-7:20 window)
    assert report.budget_actual["M2"] == 142 and report.budget_actual["M2 unknown"] == 0
    assert text == (GOLDEN / f"G-SNAP-current-{mode}.json").read_text(encoding="utf-8")  # and byte for byte
    assert all(n["position"]["z"] == 0.01 for n in doc["nodes"])


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_the_layout_changes_only_what_it_owns(graph, clock_map, mode):
    """The laid-out document against G-VIEW-current under the view masks, independent of G-SNAP-current."""
    doc = _document(graph, clock_map, mode)
    current = json.loads((GOLDEN / "G-VIEW-current.json").read_text(encoding="utf-8"))
    view_report = golden.diff_json(current, copy.deepcopy(doc), view=True)
    # CR-073: an inject-delay or spare-energy bar's size is the layout's now, as a supply block's is (M3, which
    # stays as agreed); the snapshot and the TL1 entries pin the 37 sizes. Nothing else may differ from the view.
    bars = sorted(f"{n['ID']}#1" for n in doc["nodes"] if n["type"] in ("Energy Excess", "Inject Delay"))
    assert len(bars) == 37
    assert sorted(view_report.changed) == [(k, "size") for k in bars], str(view_report)
    assert [line for line in view_report.lines if not line.startswith(("node Energy Excess-", "node Inject Delay-"))] == [
        "summary: Energy Excess size x16",
        "summary: Inject Delay size x21",
    ], str(view_report)
    # diff_json leaves the M4 counts out of its budget comparison (a view golden has no positions or
    # clocks), so they are asserted here (Morgan's CR-014 P2): every one of the 665 graph nodes has a
    # position, and the 142 clock nodes (71 occupied windows without Stats, x 2 sides; P10b's two battery
    # starts open 2 more, CR-034's Warp Gates at 7:14 one) are all present.
    assert (view_report.budget_expected["M4 clock"], view_report.budget_expected["M4 position"]) == (0, 0)
    # 639 = 665 less the 4 Supply Blocks CR-023's S1 (with S5) removes (11 -> 7), plus P8's last Units node,
    # less the 3 nodes P11 drops (Harrasment-7, Scouting-0, Scouting-1), less the 11 Units nodes N1 merges,
    # less the 7 spell-effect Units nodes P10 drops; P10b turns 3 Units groups into 3 Buildings (no change);
    # S6 and S7 leave 2 Supply Blocks fewer (7 -> 5); CR-034 (BO1) adds the 17 building-morph nodes
    assert (view_report.budget_actual["M4 clock"], view_report.budget_actual["M4 position"]) == (142, 656)


# --- CR-073: the timeline lanes ---------------------------------------------------------------------------------

#: Leo's independent prediction (prediction-h1_0-attacker.json), a few nodes: (compressed position, size),
#: (linear position, size). The full 59 are the ledger entries TL1-snap-compressed and TL1-snap-linear.
LANE_LITERALS = {
    "Scouting-0": (((20.0, -20.5), [2.65, 1]), ((25.0, -20.5), [2.65, 1])),
    "Scouting-7": (((42.5, 24.5), [2.65, 1]), ((57.5, 24.5), [2.65, 1])),  # level 2 in both modes
    "Harrasment-1": (((77.5, 22.4), [2.65, 1]), ((95.0, 22.4), [2.65, 1])),  # lilTiGGer lost the workers
    "Harrasment-3": (((97.5, -20.5), [2.65, 1]), ((115.0, -20.5), [2.65, 1])),
    "Harrasment-5": (((130.0, 23.45), [2.65, 1]), ((150.0, 23.45), [2.65, 1])),
    "Inject Delay-1": (((50.0, -22.85), [17.5, 1.0]), ((63.75, -22.85), [25.0, 1.0])),
    "Energy Excess-0": (((2.5, 27.1), [7.5, 1.0]), ((2.5, 27.1), [7.5, 1.0])),
    "Energy Excess-11": (((105.0, 29.2), [102.5, 1.0]), ((123.75, 29.2), [105.0, 1.0])),
}


def _ledger_expected(mode):
    changes = (CHECKOUT / "tests" / "golden" / "CHANGES.md").read_text(encoding="utf-8")
    entry = next(
        e for e in map(json.loads, re.findall(r"```json\n(.*?)\n```", changes, re.DOTALL)) if e["entry"] == f"TL1-snap-{mode}"
    )
    return entry["expected"]


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_cr073_the_four_types_are_where_leo_predicted(graph, clock_map, mode):
    doc = _document(graph, clock_map, mode)
    lane_nodes = {n["ID"]: n for n in doc["nodes"] if n["type"] in TIMELINE_LANES}
    expected = _ledger_expected(mode)
    assert len(lane_nodes) == len(expected) == 59 and set(lane_nodes) == set(expected)
    for node_id, want in expected.items():
        n = lane_nodes[node_id]
        assert [n["position"]["x"], n["position"]["y"]] == [round(v, 4) for v in want["position"]], node_id
        assert n["size"] == [round(v, 4) for v in want.get("size", [2.65, 1])], node_id
    for node_id, by_mode in LANE_LITERALS.items():
        position, size = by_mode[0 if mode == "compressed" else 1]
        n = lane_nodes[node_id]
        assert (n["position"]["x"], n["position"]["y"]) == position and n["size"] == size, node_id


def test_cr073_a_harassment_card_sits_on_the_attackers_side_and_keeps_its_player(graph, placed):
    _, r = placed
    side_a, side_b = (n.value("name") for n in graph.nodes if n.kind == "Player")
    lost = {side_a: 0, side_b: 0}
    for n in (n for n in graph.nodes if n.kind == "Harrasment"):
        loser = n.value("player")  # the domain node, which the export writes: unchanged
        lost[loser] += 1
        assert (r.positions[n.id][1] > 0) == (loser == side_a), n.id  # on the opponent's side
    assert lost == {"lilTiGGer": 6, "blacksquall": 7}


def test_cr073_without_the_four_types_nothing_else_moves(graph, clock_map, placed):
    mode, r = placed
    others = [i for i in items(graph) if i.type not in TIMELINE_LANES]
    without = layout(others, Profile(timeline=mode), clock_map)
    assert {k: v for k, v in r.positions.items() if k in without.positions} == without.positions
    assert {k: v for k, v in r.sizes.items() if k in without.sizes} == without.sizes
    assert r.rows == without.rows and r.extra_nodes == without.extra_nodes and r.warnings == without.warnings == []


def test_cr073_lane_ys_and_sizes_are_rounded_and_xs_on_the_half_pitch(graph, placed):
    _, r = placed
    for n in (n for n in graph.nodes if n.kind in TIMELINE_LANES):
        x, y = r.positions[n.id]
        assert y == round(y, 6) and abs(y) >= 20.0 and x % 1.25 == 0, n.id
        assert all(v == round(v, 6) for v in r.sizes[n.id]), n.id
