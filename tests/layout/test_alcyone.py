"""CR-014 on Alcyone: Leo's predictions (layout-spec.md §5, §7; round2-leo.md), invariants (QA design
§4) and the live snapshot G-SNAP-current (both modes; G-SNAP-1 is frozen since Stefan checked it, B2)."""

import contextlib
import copy
import csv
import importlib.util
import io
import json
import math
import os
import pathlib
import sys

import pytest
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.export.mindshare_json import build_document, to_json
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import Profile
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
    with need(MS_SC / "TimeImageTracking.csv", "TimeImageTracking.csv").open(encoding="utf-8") as f:
        return {r["imageName"]: r["imageID"] for r in csv.DictReader(f)}


@pytest.fixture(scope="module")
def graph():
    with contextlib.redirect_stdout(io.StringIO()):
        return to_graph(analyse(load_replay(need(ALCYONE, "Alcyone replay")), MS_SC))


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


def test_predictions_compressed(graph, clock_map):
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


def test_predictions_linear(graph, clock_map):
    r = layout(items(graph), Profile(timeline="linear"), clock_map)
    assert r.rows[-1][2] == 247.5  # 100 windows, 17 of them empty
    assert len(r.rows) == 83


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
        if n.kind in ("Battle", "Game", "Player", "Energy Excess", "Inject Delay", "Scouting", "Harrasment"):
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
    by_media = golden.load_clock_map(MS_SC / "TimeImageTracking.csv")  # media id -> file name, for the M2 mask
    report = golden.diff_json(expected, doc, by_media)
    assert report.ok, str(report)
    assert report.budget_actual["M2"] == 136 and report.budget_actual["M2 unknown"] == 0
    assert all(n["position"]["z"] == 0.01 for n in doc["nodes"])


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_the_layout_changes_only_what_it_owns(graph, clock_map, mode):
    """The laid-out document against G-VIEW-current under the view masks, independent of G-SNAP-current."""
    doc = _document(graph, clock_map, mode)
    by_media = golden.load_clock_map(MS_SC / "TimeImageTracking.csv")
    current = json.loads((GOLDEN / "G-VIEW-current.json").read_text(encoding="utf-8"))
    view_report = golden.diff_json(current, copy.deepcopy(doc), by_media, view=True)
    assert view_report.ok, str(view_report)
    # diff_json leaves the M4 counts out of its budget comparison (a view golden has no positions or
    # clocks), so they are asserted here (Morgan's CR-014 P2): every one of the 665 graph nodes has a
    # position, and the 136 clock nodes (68 occupied windows without Stats, x 2 sides) are all present.
    assert (view_report.budget_expected["M4 clock"], view_report.budget_expected["M4 position"]) == (0, 0)
    assert (view_report.budget_actual["M4 clock"], view_report.budget_actual["M4 position"]) == (136, 665)
