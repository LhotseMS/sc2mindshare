"""CR-018 (T17): schema/mindshare-graph.schema.json, and the documents sc2mindshare writes validate against it.

TD-16: existing properties are required and typed; further properties on existing node types, and new
node types, are allowed. The 1000 spores replay cannot be checked: its analysis fails in the legacy
layer (L1, the known G5 failure awaiting Stefan); Alcyone (both modes) and the spine replay are.
"""

import contextlib
import copy
import csv
import importlib.util
import io
import json
import os
import pathlib

import pytest

from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.export.mindshare_json import build_document, to_json
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import layout
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = json.loads((CHECKOUT / "schema" / "mindshare-graph.schema.json").read_text(encoding="utf-8"))
GOLDEN = CHECKOUT / "tests" / "golden" / "alcyone"

_spec = importlib.util.spec_from_file_location("schema_subset", pathlib.Path(__file__).with_name("schema_subset.py"))
assert _spec and _spec.loader
subset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(subset)
CHECK = subset.Checker(SCHEMA)


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"


# --- the documents ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_alcyone_validates(mode):
    doc = json.loads((GOLDEN / f"G-SNAP-1-{mode}.json").read_text(encoding="utf-8"))
    assert CHECK.errors(doc) == []


@pytest.fixture(scope="module")
def spine_document():
    for needed in (SPINE, MS_SC / "TimeImageTracking.csv"):
        if not needed.exists():
            if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
                pytest.fail(f"missing input {needed} (SC2MS_REQUIRE_GOLDEN=1)")
            pytest.skip(f"missing input {needed}")
    with (MS_SC / "TimeImageTracking.csv").open(encoding="utf-8") as f:
        clock_map = {r["imageName"]: r["imageID"] for r in csv.DictReader(f)}
    with contextlib.redirect_stdout(io.StringIO()):
        graph = to_graph(analyse(load_replay(SPINE), MS_SC))
    # validated as written: the JSON text, read back (whole numbers are integers in the text, A12)
    return json.loads(to_json(build_document(graph, layout(items(graph), Profile(), clock_map))))


def test_the_spine_replay_validates(spine_document):
    assert CHECK.errors(spine_document) == []


# --- TD-16: additive properties and new types are allowed; existing ones stay required and typed ------------


@pytest.fixture
def doc():
    return json.loads((GOLDEN / "G-SNAP-1-compressed.json").read_text(encoding="utf-8"))


def _node(doc, node_id):
    return next(n for n in doc["nodes"] if n["ID"] == node_id)


def test_additive_properties_on_existing_types_are_allowed(doc):
    _node(doc, "Building-3")["properties"] |= {"verdict": "late", "off by s": 142, "guide time": "00:01:00"}
    _node(doc, "Units-10")["properties"]["verdict"] = "on time"
    doc["dataTypes"] |= {"verdict": "typelist", "off by s": "int", "guide time": "time[h:m:s]"}
    assert CHECK.errors(doc) == []


def test_new_node_types_are_allowed(doc):
    doc["nodes"].append(
        {
            "name": "Evolution Chamber · missing",
            "description": "Missing: ...",
            "type": "Missing Step",
            "ID": "Missing Step-1",
            "size": [2.65, 1],
            "properties": {"time": "00:04:30", "player": "lilTiGGer", "done later at": "00:10:31"},
            "position": {"x": 25, "y": -12.2, "z": 0.01},
        }
    )
    assert CHECK.errors(doc) == []


@pytest.mark.parametrize(
    ("node_id", "change", "message"),
    [
        ("Units-10", lambda n: n["properties"].pop("count"), "missing required property 'count'"),
        ("Units-10", lambda n: n["properties"].update(count="1"), "is not of type integer"),
        ("Units-10", lambda n: n.update(size=[1, 1]), "is not of type number"),
        ("Battle-2", lambda n: n["properties"].update({"supply dead": "4.5"}), "is not of type number"),
        ("Stats-11", lambda n: n["properties"].pop("workers"), "missing required property 'workers'"),
        ("Building-1", lambda n: n["properties"].update(type=3), "is not of type string"),
        ("Building-3", lambda n: n.pop("position"), "missing required property 'position'"),
        ("Building-3", lambda n: n["position"].pop("z"), "missing required property 'z'"),
        ("Building-3", lambda n: n.pop("description"), "missing required property 'description'"),
        ("Supply Block-0", lambda n: n.update(size=2.5), "is not of type array"),
    ],
)
def test_existing_properties_stay_required_and_typed(doc, node_id, change, message):
    change(_node(doc, node_id))
    errors = CHECK.errors(doc)
    assert errors and any(message in e for e in errors), errors


def test_the_top_level_links_clocks_and_data_types_are_checked(doc):
    bad = copy.deepcopy(doc)
    bad["extra"] = 1
    assert any("'extra' is not allowed" in e for e in CHECK.errors(bad))
    bad = copy.deepcopy(doc)
    bad["links"][0]["direction"] = 3
    assert any("is not one of" in e for e in CHECK.errors(bad))
    bad = copy.deepcopy(doc)
    bad["dataTypes"]["verdict"] = "colour"
    assert any("$.dataTypes.verdict" in e for e in CHECK.errors(bad))
    bad = copy.deepcopy(doc)
    next(n for n in bad["nodes"] if n["type"] == "image")["properties"]["x"] = 1
    assert any("more than 0 properties" in e for e in CHECK.errors(bad))
    clock = next(n for n in doc["nodes"] if n["type"] == "image")
    assert "description" not in clock  # clock images have none, and the schema allows that


# --- the checker itself --------------------------------------------------------------------------------------


def test_the_checker_refuses_keywords_it_does_not_implement():
    with pytest.raises(subset.UnsupportedKeyword):
        subset.Checker({"type": "string", "pattern": "^#"}).errors("#fff")
    with pytest.raises(subset.UnsupportedKeyword):
        subset.Checker({"$ref": "other.json#/x"}).errors(1)


@pytest.mark.parametrize(
    ("schema", "value", "ok"),
    [
        ({"type": "integer"}, 2, True),
        ({"type": "integer"}, 2.0, True),  # 2020-12: no fractional part
        ({"type": "integer"}, 2.5, False),
        ({"type": "integer"}, True, False),  # JSON true is not a number
        ({"type": "number"}, False, False),
        ({"enum": [1]}, True, False),
        ({"const": 0}, False, False),
        ({"anyOf": [{"type": "number"}, {"type": "array"}]}, "x", False),
        ({"if": {"const": 1}, "then": {"type": "integer"}, "else": {"type": "string"}}, 2, False),
        ({"if": {"const": 1}, "then": {"type": "integer"}, "else": {"type": "string"}}, 1, True),
        ({"properties": {"a": {"type": "string"}}, "additionalProperties": False}, {"a": "x", "b": 1}, False),
    ],
)
def test_checker_semantics(schema, value, ok):
    assert (subset.Checker(schema).errors(value) == []) is ok
