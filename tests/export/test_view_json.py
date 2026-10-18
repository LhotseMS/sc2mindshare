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
from sc2mindshare.analysis.to_domain import to_graph, typed_values
from sc2mindshare.domain.models import Link, Node
from sc2mindshare.export import view
from sc2mindshare.export.mindshare_json import build_document, load_config, to_json
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
        faithful = analyse(load_replay(ALCYONE), MS_SC, fixes=())  # no layer fix (CR-023) ...
        current = analyse(load_replay(ALCYONE), MS_SC)  # ... and every one: two loads, a replay is consumed
    return {
        "faithful": build_document(to_graph(faithful, fixes=())),
        "current": build_document(to_graph(current)),
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
VIEW_LEDGER = ("H1", "P3d-view", "A12-view", "P3e-view", "P1-view", "P1b-view", "P1c-view", "S1-view", "S1b-view", "P8-view")
#: Their net effect on G-VIEW-1: H1 renumbers the 14 Harrasment nodes; P3d sets the main bases' time and
#: P3e moves their real start into the description; P1 renames the 30 battles, P1b 7 of them again and P1c one (CR-023). P3d's "pre-game time" property and dataTypes entry
#: are removed again by P3e, and A12 changes only the number text, so neither shows in the net delta.
#: S1 and S1b renumber the Supply Blocks, which no other entry touches: the net check sets them aside, and
#: their net effect is checked on the Supply Blocks alone: none of the 11 survives (keyed on player and
#: start time), 7 new ones (test below).
SUPPLY_NET = {"removed": [f"Supply Block-{i}#1" for i in range(11)], "added": [f"Supply Block-{i}#1" for i in range(7)]}
#: A future entry on G-VIEW-current needs a hand edit here (VIEW_LEDGER and its net effect).
VIEW_NET_DELTA = [
    {"select": {"type": "Harrasment"}, "fields": ["ID"], "count": 14},
    {"select": {"type": "Building"}, "fields": ["properties.time", "description"], "count": 2},
    {"select": {"type": "Battle"}, "fields": ["name"], "count": 30},
]


def _part(path, tmp_path, name, supply_blocks):
    """The document with only its Supply Blocks (or without them), written for check_delta."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["nodes"] = [n for n in doc["nodes"] if (n["type"] == "Supply Block") == supply_blocks]
    if supply_blocks:
        doc = {"nodes": doc["nodes"], "links": []}  # Supply Blocks have no links
    out = tmp_path / name
    out.write_text(json.dumps(doc), encoding="utf-8")
    return out


def test_g_view_current_is_g_view_1_plus_the_ledger(tmp_path):
    cgd = _load("check_golden_delta", CHECKOUT / "scripts" / "check_golden_delta.py")
    entries = cgd.entries((CHECKOUT / "tests" / "golden" / "CHANGES.md").read_text(encoding="utf-8"))
    assert all(e in entries for e in VIEW_LEDGER)
    assert [entries[e]["golden"] for e in VIEW_LEDGER] == [["alcyone/G-VIEW-current.json"]] * len(VIEW_LEDGER)
    assert [e for e in VIEW_LEDGER if entries[e].get("renumber")] == ["S1-view", "S1b-view"]
    assert all(c["select"].get("type") != "Supply Block" for c in VIEW_NET_DELTA)
    old_rest = _part(GOLDEN / "G-VIEW-1.json", tmp_path, "old-rest.json", supply_blocks=False)
    new_rest = _part(GOLDEN / "G-VIEW-current.json", tmp_path, "new-rest.json", supply_blocks=False)
    net = {
        "entry": "+".join(VIEW_LEDGER),
        "base_sha256": cgd.golden.sha256(old_rest),
        "changes": VIEW_NET_DELTA,
        "added": ["Units-193#1", "Units-192>Units-193#1"],  # P8
        "removed": [],
    }
    assert cgd.check_delta(net, old_rest, new_rest) == []
    old_sb = _part(GOLDEN / "G-VIEW-1.json", tmp_path, "old-sb.json", supply_blocks=True)
    new_sb = _part(GOLDEN / "G-VIEW-current.json", tmp_path, "new-sb.json", supply_blocks=True)
    net_sb = dict(
        entries["S1b-view"],
        entry="S1-view+S1b-view",
        base_sha256=cgd.golden.sha256(old_sb),
        renumber=dict(entries["S1b-view"]["renumber"], ids_changed=0),
        changes=[],
        **SUPPLY_NET,
    )
    assert cgd.check_delta(net_sb, old_sb, new_sb) == []


def test_document_key_order_and_config_parts(document):
    doc = document["current"]
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links"]
    assert doc["visuals"] == load_config()["visuals"]
    assert json.loads(to_json(doc)) == doc


def test_p3d_the_main_bases_show_00_00_00_and_their_real_start_in_the_description(document):
    """A9 (P3d) as amended by D3c (P3e): the bug-faithful document keeps the legacy wrap; the current one
    shows 00:00:00 with the same property keys as every other Building, and the real start in the
    description. dataTypes is the workbook's, unchanged."""
    faithful = {n["ID"]: n for n in document["faithful"]["nodes"]}
    current = {n["ID"]: n for n in document["current"]["nodes"]}
    for node_id, player, kind in (("Building-1", "lilTiGGer", "Hive"), ("Building-2", "blacksquall", "Nexus")):
        assert faithful[node_id]["properties"] == {"time": "23:58:49", "player": player, "type": kind}
        assert current[node_id]["properties"] == {"time": "00:00:00", "player": player, "type": kind}
        assert current[node_id]["description"] == "Started 71 s before the game (real start -00:01:11)."
    assert document["faithful"]["dataTypes"] == document["current"]["dataTypes"] == load_config()["dataTypes"]


def _key_lists_per_type(doc):
    """Node type -> the distinct property key lists (in order) its nodes have."""
    lists = {}
    for n in doc["nodes"]:
        lists.setdefault(n["type"], set()).add(tuple(n.get("properties", {})))
    return lists


@pytest.mark.parametrize(
    "name",
    [
        "G-VIEW-1.json",
        "G-VIEW-current.json",
        "G-SNAP-1-compressed.json",
        "G-SNAP-1-linear.json",
        "G-SNAP-current-compressed.json",
        "G-SNAP-current-linear.json",
    ],
)
def test_every_node_of_a_type_has_the_same_property_keys(name):
    """Mindshare refuses an import where two nodes of one type have different parameters ("node
    'Building-4' has different parameters than node 'Building-1' but the same type", Stefan's import of
    G-SNAP-1, 2026-10-18). So in every golden all nodes of a type carry the same property keys, in order."""
    doc = json.loads((GOLDEN / name).read_text(encoding="utf-8"))
    mixed = {t: sorted(keys) for t, keys in _key_lists_per_type(doc).items() if len(keys) > 1}
    assert mixed == {}


def test_the_documents_the_code_makes_have_the_same_property_keys_per_type(document):
    for doc in (document["faithful"], document["current"]):
        assert {t: keys for t, keys in _key_lists_per_type(doc).items() if len(keys) > 1} == {}


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


def _node(kind, values, images=()):
    """A node built from the legacy text, through the adapter (CR-022): its start is its time."""
    parts = [int(p) for p in dict(values)["time"].split(":")]
    start = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
    typed, begins = typed_values(f"{kind}-1", kind, values, start)
    return Node(kind, f"{kind}-1", "n", "a X_LD b", tuple(images), typed, begins)


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
