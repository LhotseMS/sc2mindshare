"""CR-013 (T13): the view and the Mindshare JSON from the domain models equal G-VIEW-1."""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys

import pytest

from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.models import EXTRA_FIELDS, Link, Node
from sc2mindshare.export import view
from sc2mindshare.export.mindshare_json import EXTRA_DATA_TYPES, build_document, load_config, to_json
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


@pytest.fixture(scope="module")
def document():
    try:
        golden.require(ALCYONE, "Alcyone replay")
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(str(exc))
        pytest.skip(str(exc))
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(load_replay(ALCYONE), MS_SC)
    return {
        "faithful": build_document(to_graph(result, fixes=())),
        "current": build_document(to_graph(result)),
    }


def test_the_bug_faithful_document_equals_g_view_1_with_the_view_masks(document):
    expected = json.loads((GOLDEN / "G-VIEW-1.json").read_text(encoding="utf-8"))
    report = golden.diff_json(expected, document["faithful"], view=True)
    assert report.ok, str(report)
    assert report.budget_actual == {"M1": 1, "M3": 11}
    assert golden.diff_json(expected, document["faithful"]).ok  # even unmasked, before the layout


def test_the_current_document_equals_g_view_current(document):
    expected = json.loads((GOLDEN / "G-VIEW-current.json").read_text(encoding="utf-8"))
    report = golden.diff_json(expected, document["current"])
    assert report.ok, str(report)


#: The ledger entries G-VIEW-current applies to G-VIEW-1, in order.
VIEW_LEDGER = ("H1", "P3d-view")


def test_g_view_current_is_g_view_1_plus_the_ledger():
    cgd = _load("check_golden_delta", CHECKOUT / "scripts" / "check_golden_delta.py")
    entries = cgd.entries((CHECKOUT / "tests" / "golden" / "CHANGES.md").read_text(encoding="utf-8"))
    chain = [entries[e] for e in VIEW_LEDGER]
    merged = {
        "entry": "+".join(VIEW_LEDGER),
        "base_sha256": chain[0]["base_sha256"],  # G-VIEW-1
        "changes": [c for e in chain for c in e["changes"]],
        "added": [a for e in chain for a in e["added"]],
        "removed": [r for e in chain for r in e["removed"]],
    }
    assert cgd.check_delta(merged, GOLDEN / "G-VIEW-1.json", GOLDEN / "G-VIEW-current.json") == []


def test_document_key_order_and_config_parts(document):
    doc = document["current"]
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links"]
    assert doc["visuals"] == load_config()["visuals"]
    assert json.loads(to_json(doc)) == doc


def test_p3d_the_main_bases_show_00_00_00_and_keep_their_real_time(document):
    """A9: the bug-faithful document keeps the legacy wrap; the current one shows 00:00:00 and adds
    "pre-game time", declared in dataTypes (only where it is used)."""
    faithful = {n["ID"]: n for n in document["faithful"]["nodes"]}
    current = {n["ID"]: n for n in document["current"]["nodes"]}
    for node_id, player, kind in (("Building-1", "lilTiGGer", "Hive"), ("Building-2", "blacksquall", "Nexus")):
        assert faithful[node_id]["properties"] == {"time": "23:58:49", "player": player, "type": kind}
        assert current[node_id]["properties"] == {
            "time": "00:00:00",
            "player": player,
            "type": kind,
            "pre-game time": "-00:01:11",
        }
    assert sum("pre-game time" in n["properties"] for n in document["current"]["nodes"]) == 2
    assert document["faithful"]["dataTypes"] == load_config()["dataTypes"]
    assert document["current"]["dataTypes"] == load_config()["dataTypes"] | {"pre-game time": "string"}
    assert list(document["current"]["dataTypes"])[-1] == "pre-game time"


def test_to_json_writes_numbers_as_vba_json_does():
    """D7a A12: a whole number has no decimal part (VBA's string conversion of a Double); other
    numbers, strings that look like numbers, booleans and the key order are unchanged."""
    doc = {
        "size": [2.65, 1.0],
        "x": -12.0,
        "zero": 0.0,
        "minus zero": -0.0,
        "z": 0.01,
        "small": 0.0001,  # the smallest non-zero value after the 4-dp rounding: no exponent form
        "negative small": -0.0001,
        "n": 3,
        "text": "50.0",
        "flag": True,
    }
    assert to_json(doc) == (
        '{\n "size": [\n  2.65,\n  1\n ],\n "x": -12,\n "zero": 0,\n "minus zero": 0,\n "z": 0.01,\n'
        ' "small": 0.0001,\n "negative small": -0.0001,\n "n": 3,\n "text": "50.0",\n "flag": true\n}\n'
    )
    assert json.loads(to_json(doc)) == doc  # the same numbers


def test_every_extra_field_has_a_mindshare_data_type():
    assert set(EXTRA_DATA_TYPES) == set(EXTRA_FIELDS)
    assert not set(EXTRA_DATA_TYPES) & set(load_config()["dataTypes"])  # never redefines a workbook type


def test_extra_properties_follow_the_kinds_own():
    node = Node(
        "Building",
        "Building-1",
        "b",
        "",
        (),
        (("time", "00:00:00"), ("player", "p"), ("type", "Hive")),
        -71,
        (("pre-game time", "-00:01:11"),),
    )
    assert list(view.node_view(node)["properties"]) == ["time", "player", "type", "pre-game time"]


def _node(kind, values, start=60, images=()):
    return Node(kind, f"{kind}-1", "n", "a X_LD b", tuple(images), tuple(values), start)


def test_battle_and_units_sizes_and_properties():
    battle = view.node_view(
        _node(
            "Battle",
            [
                ("time", "00:02:02"),
                ("player", "Common"),
                ("dead", "1"),
                ("p1 dead", "1"),
                ("p2 dead", "0"),
                ("supply dead", "0.5"),
                ("end time", "0:02:02"),
            ],
            images=["u1", "u2"],
        )
    )
    assert battle["size"] == 0.7 and battle["images"] == ["u1", "u2"] and battle["description"] == "a \n b"
    assert battle["properties"]["end time"] == "0:02:02"  # B11: raw text
    units = view.node_view(
        _node(
            "Units",
            [
                ("time", "00:00:00"),
                ("player", "p"),
                ("type", "Drone"),
                ("count", "12"),
                ("supply", "12"),
                ("total at time", "12"),
            ],
        )
    )
    assert units["size"] == 1.4
    assert list(units["properties"]) == ["time", "player", "type", "count", "total at time", "supply"]


@pytest.mark.parametrize(("supply", "size"), [(1, 0.7), (3, 0.95), (10, 1.2), (30, 1.6), (50, 2.5)])
def test_battle_size_thresholds(supply, size):
    assert view.battle_size(supply) == size


@pytest.mark.parametrize(("supply", "size"), [(3, 0.75), (3.5, 1), (10, 1), (20, 1.4), (21, 1.7)])
def test_units_size_thresholds(supply, size):
    assert view.units_size(supply) == size


def test_ability_flags_are_never_emitted_b3_and_scouting_time_b9():
    ability = view.node_view(
        _node(
            "Ability",
            [
                ("time", "00:03:00"),
                ("player", "p"),
                ("type", "SpawnLarva"),
                ("combat", "True"),
                ("queued", "False"),
                ("minimap", "False"),
                ("target", "Hatchery"),
            ],
        )
    )
    assert ability["properties"] == {"time": "00:03:00", "player": "p", "type": "SpawnLarva", "target": "Hatchery"}
    scout = view.node_view(_node("Scouting", [("time", "01:42"), ("player", "p"), ("unit", "Drone"), ("base", "Natural")]))
    assert scout["properties"]["time"] == "01:42:00"


def test_one_word_links_read_like_the_workbook():
    assert view.link_view(Link("Stats-1", "Stats-2", "", "", "", 2, name="vs")) == {
        "name1": "vs",
        "name2": "",
        "direction": 2,
        "node1": "Stats-1",
        "node2": "Stats-2",
    }
