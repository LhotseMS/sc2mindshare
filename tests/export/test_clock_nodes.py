"""CR-069 AC-9 and AC-11: the clock nodes in the local Mindshare's format, read from the clock record.

AC-9: with a record holding Alcyone's clocks, every clock node shows its clock by the recorded picture ID
(``nodeImage``), is named by its file name and has a unique, server-independent ID (``clock-<m>-<ss>-<side>``);
position and size are the layout's; nothing refers to the old media host. AC-11: without a record, or with one
clock missing, the export still succeeds, leaves exactly those clock nodes out with one warning per clock, and
nothing else moves. The record here is the committed fixture (tests/golden/clock-record-fixture.csv).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import sys

import pytest

from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.export.mindshare_json import build_document, to_json
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutResult, layout
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("golden", CHECKOUT / "tests" / "golden" / "golden.py")
assert _spec and _spec.loader
golden = importlib.util.module_from_spec(_spec)
sys.modules["golden"] = golden
_spec.loader.exec_module(golden)


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
CLOCK_ID = re.compile(r"^clock-(\d+)-(\d{2})-([12])$")


def need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    return path


@pytest.fixture(scope="module")
def graph():
    with contextlib.redirect_stdout(io.StringIO()):
        return to_graph(analyse(load_replay(need(ALCYONE)), MS_SC))


@pytest.fixture(scope="module")
def record():
    return golden.fixture_clock_map()


def _doc(graph, clock_map, mode="compressed") -> tuple[dict, LayoutResult]:
    placed = layout(items(graph), Profile(timeline=mode), clock_map)
    return json.loads(to_json(build_document(graph, placed))), placed


# --- the node itself (no replay needed) ----------------------------------------------------------------------------


def test_a_clock_node_is_in_the_local_form():
    from sc2mindshare.layout.sweep import ClockNode

    placed = LayoutResult(extra_nodes=[ClockNode("0-10.png", "8d4e894d-f6b7-41a6-80df-b999b322349c", 2, 2.5, 5.76)])
    from sc2mindshare.domain.models import Graph

    doc = build_document(Graph(nodes=(), links=()), placed)
    assert doc["nodes"] == [
        {
            "type": "image",
            "name": "0-10.png",
            "ID": "clock-0-10-2",
            "nodeImage": "8d4e894d-f6b7-41a6-80df-b999b322349c",
            "size": [1.1, 0.75],
            "properties": {},
            "position": {"x": 2.5, "y": 5.76, "z": 0.01},
        }
    ]


def test_the_profile_has_no_media_host():
    assert not hasattr(Profile(), "clock_host")


# --- AC-9 ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_ac9_every_clock_node_points_at_its_recorded_picture(graph, record, mode):
    doc, placed = _doc(graph, record, mode)
    clocks = [n for n in doc["nodes"] if n["type"] == "image"]
    assert len(clocks) == 140 and len({n["name"] for n in clocks}) == 70
    for n in clocks:
        assert n["nodeImage"] == record[n["name"]]
        m = CLOCK_ID.match(n["ID"])
        assert m and f"{int(m.group(1))}-{m.group(2)}.png" == n["name"]
        assert n["size"] == [1.1, 0.75] and n["properties"] == {}
    ids = [n["ID"] for n in doc["nodes"]]
    assert len(ids) == len(set(ids))  # unique, also against every other node
    assert "touch4dev" not in to_json(build_document(graph, placed))
    # positions and sides as the layout placed them: side 1 below, side 2 above
    for n in clocks:
        side = int(n["ID"][-1])
        assert n["position"]["y"] == (-5.76 if side == 1 else 5.76)


def test_ac9_the_node_ids_do_not_depend_on_the_server(graph, record):
    other = {name: "other-" + picture for name, picture in record.items()}
    a, _ = _doc(graph, record)
    b, _ = _doc(graph, other)
    assert [n["ID"] for n in a["nodes"]] == [n["ID"] for n in b["nodes"]]
    assert [n.get("nodeImage") for n in a["nodes"]] != [n.get("nodeImage") for n in b["nodes"]]


# --- AC-11 -------------------------------------------------------------------------------------------------------------


def _without_clocks(doc):
    return {**doc, "nodes": [n for n in doc["nodes"] if n["type"] != "image"]}


def test_ac11_without_a_record_there_are_no_clocks_and_one_warning_per_clock(graph, record):
    full, _ = _doc(graph, record)
    bare, placed = _doc(graph, {})
    assert [n for n in bare["nodes"] if n["type"] == "image"] == []
    warnings = [w for w in placed.warnings if w.startswith("no clock image")]
    assert len(warnings) == 70 and all("sc2mindshare upload-clocks" in w for w in warnings)
    assert bare == _without_clocks(full)  # every other node, link and position is identical


def test_ac11_one_missing_clock_leaves_out_exactly_its_two_nodes(graph, record):
    full, _ = _doc(graph, record)
    partial, placed = _doc(graph, {k: v for k, v in record.items() if k != "0-10.png"})
    gone = [n for n in full["nodes"] if n not in partial["nodes"]]
    assert sorted(n["ID"] for n in gone) == ["clock-0-10-1", "clock-0-10-2"]
    assert [w for w in placed.warnings if w.startswith("no clock image")] == [
        "no clock image for 0-10.png: run sc2mindshare upload-clocks (G6)"
    ]
    assert partial == {**full, "nodes": [n for n in full["nodes"] if n not in gone]}
