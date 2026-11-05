"""Order records of scripts/check_golden_delta.py (QA design Addendum A §A.4): order is reported per node type,
per link type pair, and for interleaving, in plain C3 and under a renumber entry alike."""

import copy
import importlib.util
import json
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_golden_delta", _HERE.parent / "check_golden_delta.py")
assert _spec and _spec.loader
cgd = importlib.util.module_from_spec(_spec)
sys.modules["check_golden_delta"] = cgd
_spec.loader.exec_module(cgd)
_spec = importlib.util.spec_from_file_location("renumber_tests", _HERE / "test_check_golden_delta_renumber.py")
assert _spec and _spec.loader
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)


def _node(i, typ):
    return {"ID": i, "type": typ, "name": i, "description": "d", "properties": {}}


def _link(a, b):
    return {"name1": "previous", "name2": "next", "direction": 1, "node1": a, "node2": b}


PLAIN = {
    "nodes": [
        _node("Battle-1", "Battle"),
        _node("Battle-2", "Battle"),
        _node("Ability-1", "Ability"),
        _node("Ability-2", "Ability"),
        _node("Units-1", "Units"),
        _node("Units-2", "Units"),
    ],
    "links": [_link("Units-1", "Units-2"), _link("Ability-1", "Ability-2"), _link("Ability-2", "Units-1")],
}


def _write(path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _swap(seq, i, j):
    seq[i], seq[j] = seq[j], seq[i]


def _plain_entry(old, changes=()):
    return {
        "entry": "O1",
        "task": "CR-023",
        "golden": ["x"],
        "base_sha256": cgd.golden.sha256(old),
        "changes": list(changes),
        "added": [],
        "removed": [],
    }


def _order(select):
    return {"select": select, "fields": ["<order>"], "count": 1}


@pytest.fixture
def plain(tmp_path):
    return _write(tmp_path / "old.json", PLAIN), tmp_path


def _check(entry, old, tmp, new_doc):
    return cgd.check_delta(entry, old, _write(tmp / "new.json", new_doc))


def test_plain_a_swap_within_a_type_is_that_types_order_record_only(plain):
    old, tmp = plain
    new = copy.deepcopy(PLAIN)
    _swap(new["nodes"], 2, 3)  # Ability-1 <-> Ability-2
    assert _check(_plain_entry(old), old, tmp, new) == ["unlisted change: nodes[Ability] <order>"]
    assert _check(_plain_entry(old, [_order({"type": "Ability"})]), old, tmp, new) == []


def test_plain_an_interleaving_is_nodes_order_only(plain):
    old, tmp = plain
    new = copy.deepcopy(PLAIN)
    _swap(new["nodes"], 3, 4)  # Ability-2 <-> Units-1: each type keeps its own order
    assert _check(_plain_entry(old), old, tmp, new) == ["unlisted change: nodes <order>"]
    assert _check(_plain_entry(old, [_order({"ID": "nodes"})]), old, tmp, new) == []


def test_plain_a_move_that_does_both_reports_both(plain):
    old, tmp = plain
    new = copy.deepcopy(PLAIN)
    new["nodes"] = [new["nodes"][i] for i in (0, 1, 5, 2, 3, 4)]  # Units-2 to before the Abilities: both
    assert sorted(_check(_plain_entry(old), old, tmp, new)) == [
        "unlisted change: nodes <order>",
        "unlisted change: nodes[Units] <order>",
    ]


def test_a_listed_type_order_with_no_reorder_fails(plain):
    old, tmp = plain
    assert _check(_plain_entry(old, [_order({"type": "Battle"})]), old, tmp, copy.deepcopy(PLAIN)) == [
        "listed but not changed: {'type': 'Battle'} ['<order>']"
    ]


def test_a_document_wide_nodes_order_does_not_cover_a_within_type_reorder(plain):
    old, tmp = plain
    new = copy.deepcopy(PLAIN)
    _swap(new["nodes"], 0, 1)
    assert sorted(_check(_plain_entry(old, [_order({"ID": "nodes"})]), old, tmp, new)) == [
        "listed but not changed: {'ID': 'nodes'} ['<order>']",
        "unlisted change: nodes[Battle] <order>",
    ]


def test_a_types_field_select_never_covers_its_order(plain):
    old, tmp = plain
    new = copy.deepcopy(PLAIN)
    _swap(new["nodes"], 0, 1)
    new["nodes"][0]["name"] = "renamed"  # a listed field change on the same type
    entry = _plain_entry(old, [{"select": {"type": "Battle"}, "fields": ["name"], "count": 1}])
    assert _check(entry, old, tmp, new) == ["unlisted change: nodes[Battle] <order>"]


def test_links_within_a_type_pair_and_interleaving(plain):
    old, tmp = plain
    new = copy.deepcopy(PLAIN)
    new["links"] = [new["links"][i] for i in (0, 2, 1)]  # Ability>Ability <-> Ability>Units: interleaving only
    assert _check(_plain_entry(old), old, tmp, new) == ["unlisted change: links <order>"]
    two = copy.deepcopy(PLAIN)
    two["links"].append(_link("Units-2", "Units-1"))
    old2 = _write(tmp / "old2.json", two)
    swapped = copy.deepcopy(two)
    _swap(swapped["links"], 0, 3)  # the two Units>Units links
    assert _check(_plain_entry(old2), old2, tmp, swapped) == ["unlisted change: links[Units>Units] <order>"]
    assert sorted(_check(_plain_entry(old2, [_order({"ID": "links"})]), old2, tmp, swapped)) == [
        "listed but not changed: {'ID': 'links'} ['<order>']",
        "unlisted change: links[Units>Units] <order>",
    ]


def test_morgans_probe_a_listed_units_order_does_not_waive_battles(tmp_path):
    """Units order listed, Battle reordered and not listed: fails on Battle's order record (§A.4 break)."""
    o, n = copy.deepcopy(rt.OLD), copy.deepcopy(rt.NEW)
    b2 = {"ID": "Battle-2", "type": "Battle", "name": "b2", "description": "d", "properties": {}}
    o["nodes"].append(b2)
    n["nodes"].append(copy.deepcopy(b2))
    nodes = n["nodes"]
    i1, i2 = (next(k for k, x in enumerate(nodes) if x["ID"] == y) for y in ("Units-1", "Units-2"))
    nodes[i1], nodes[i2] = nodes[i2], nodes[i1]
    b1, b2i = (next(k for k, x in enumerate(nodes) if x["ID"] == y) for y in ("Battle-1", "Battle-2"))
    nodes[b1], nodes[b2i] = nodes[b2i], nodes[b1]
    old, new = _write(tmp_path / "o.json", o), _write(tmp_path / "n.json", n)
    entry = rt._entry(old)
    entry["changes"].append(_order({"type": "Units"}))
    assert cgd.check_delta(entry, old, new) == ["unlisted change: nodes[Battle] <order>"]


def test_order_keys_cannot_collide_with_record_keys():
    assert all("#" not in k for k in ("nodes", "links", "nodes[Units]", "links[Units>Units]"))
    assert cgd.order_key("nodes", "Units") == "nodes[Units]" and cgd.order_key("links", "Units>Units") == "links[Units>Units]"
