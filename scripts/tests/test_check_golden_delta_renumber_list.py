"""Tests for ``renumber`` as a list of specs in scripts/check_golden_delta.py (QA design Addendum C, for P11).

Two node types are renumbered in one entry: a Units group that was an Overlord at its event merges into the
Overlord group of its window (Units-3 -> Units-2; the later Units ID shifts down), and the first Scouting node
is removed (the later Scouting IDs shift down). A link from each merged Units node to the same Scouting node
becomes a duplicate after the rewrite: it is dropped and counts for the Units spec (its node1's old type).
Each deliberate break of Addendum C item 5 has a test.
"""

import copy
import importlib.util
import json
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "check_golden_delta.py"
_spec = importlib.util.spec_from_file_location("check_golden_delta", _PATH)
assert _spec and _spec.loader
cgd = importlib.util.module_from_spec(_spec)
sys.modules["check_golden_delta"] = cgd
_spec.loader.exec_module(cgd)


def _units(uid, time, typ, count=1, name=None):
    props = {"time": time, "player": "p1", "type": typ, "count": count}
    return {"ID": uid, "type": "Units", "name": name or typ, "description": "d", "properties": props}


def _scout(uid, time):
    return {"ID": uid, "type": "Scouting", "name": "s", "description": "d", "properties": {"time": time, "player": "p2"}}


def _link(a, b):
    return {"name1": "n1", "name2": "n2", "direction": 1, "node1": a, "node2": b}


OLD = {
    "nodes": [
        _units("Units-1", "00:00:10", "Drone"),
        _units("Units-2", "00:00:20", "Overlord"),
        _units("Units-3", "00:00:20", "Overseer"),  # an Overlord at its event: merges into Units-2
        _units("Units-4", "00:00:30", "Drone"),
        _scout("Scouting-0", "00:00:05"),  # removed
        _scout("Scouting-1", "00:00:15"),
        _scout("Scouting-2", "00:00:25"),
        {"ID": "Battle-1", "type": "Battle", "name": "b", "description": "d", "properties": {}},
    ],
    "links": [
        _link("Units-1", "Units-4"),
        _link("Units-2", "Scouting-1"),
        _link("Units-3", "Scouting-1"),  # a duplicate of the link above after the rewrite: dropped
        _link("Scouting-1", "Scouting-2"),
    ],
}
NEW = {
    "nodes": [
        _units("Units-1", "00:00:10", "Drone"),
        _units("Units-2", "00:00:20", "Overlord", count=2, name="2 Overlords"),
        _units("Units-3", "00:00:30", "Drone"),
        _scout("Scouting-0", "00:00:15"),
        _scout("Scouting-1", "00:00:25"),
        {"ID": "Battle-1", "type": "Battle", "name": "b", "description": "d", "properties": {}},
    ],
    "links": [_link("Units-1", "Units-3"), _link("Units-2", "Scouting-0"), _link("Scouting-0", "Scouting-1")],
}
UNITS = {
    "type": "Units",
    "key": ["properties.player", "properties.time", "properties.type"],
    "retype": {"Units-3": "Overlord"},
    "merged": {"Units-3": "Units-2"},
    "ids_changed": 1,
    "links_dropped": 1,
}
SCOUTING = {"type": "Scouting", "key": ["properties.player", "properties.time"], "ids_changed": 2, "links_dropped": 0}


def _entry(old_path, specs, removed=("Scouting-0#1",)):
    return {
        "entry": "P11x",
        "task": "CR-023",
        "golden": ["x"],
        "base_sha256": cgd.golden.sha256(old_path),
        "renumber": specs,
        "changes": [{"select": {"ID": "Units-2"}, "fields": ["name", "properties.count"], "count": 1}],
        "added": [],
        "removed": list(removed),
    }


def _write(path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def paths(tmp_path):
    return _write(tmp_path / "old.json", OLD), _write(tmp_path / "new.json", NEW)


def test_a_list_of_two_specs_that_matches_its_entry_passes(paths, capsys):
    old, new = paths
    assert cgd.check_delta(_entry(old, [UNITS, SCOUTING]), old, new) == []
    out = capsys.readouterr().out
    assert "Units-3 -> Units-2 (merged)" in out and "Units-4 -> Units-3" in out
    assert "Scouting-1 -> Scouting-0" in out and "Scouting-2 -> Scouting-1" in out


def test_r4_runs_once_on_the_union_of_the_maps():
    id_map, problems, result = cgd.renumber_maps([UNITS, SCOUTING], OLD, NEW, removed={"Scouting-0#1"})
    assert problems == []
    assert id_map["Units-4"] == "Units-3" and id_map["Scouting-2"] == "Scouting-1"
    assert result is not None
    links = [(lk["node1"], lk["node2"]) for lk in result["old_doc"]["links"]]
    assert links == [("Units-1", "Units-3"), ("Units-2", "Scouting-0"), ("Scouting-0", "Scouting-1")]


def test_r1_two_specs_naming_one_type_stop(paths):
    old, new = paths
    problems = cgd.check_delta(_entry(old, [UNITS, dict(UNITS, ids_changed=0)]), old, new)
    assert problems and problems[0].startswith("R1") and "Units" in problems[0]


def test_r6_a_scouting_id_changed_under_a_units_only_list(paths):
    old, new = paths
    problems = cgd.check_delta(_entry(old, [UNITS], removed=()), old, new)
    assert any(p.startswith("R6: IDs of other node types change") for p in problems), problems


def test_r4_a_dropped_link_stated_on_the_wrong_spec(paths):
    old, new = paths
    specs = [dict(UNITS, links_dropped=0), dict(SCOUTING, links_dropped=1)]
    problems = cgd.check_delta(_entry(old, specs), old, new)
    assert any(p.startswith("R4") and "Units" in p for p in problems), problems
    assert any(p.startswith("R4") and "Scouting" in p for p in problems), problems


def test_r2_a_removal_left_out_of_removed(paths):
    old, new = paths
    problems = cgd.check_delta(_entry(old, [UNITS, SCOUTING], removed=()), old, new)
    assert any(p.startswith("R2: unlisted removal: Scouting-0") for p in problems), problems


def test_a_single_dict_is_a_list_of_one():
    one = copy.deepcopy(OLD)
    one["nodes"] = [n for n in one["nodes"] if n["type"] != "Scouting"]
    one["links"] = [lk for lk in one["links"] if not lk["node2"].startswith("Scouting")]
    one_new = copy.deepcopy(NEW)
    one_new["nodes"] = [n for n in one_new["nodes"] if n["type"] != "Scouting"]
    one_new["links"] = [lk for lk in one_new["links"] if not lk["node2"].startswith("Scouting")]
    as_dict = cgd.renumber_maps(dict(UNITS, links_dropped=0), one, one_new, removed=set())
    as_list = cgd.renumber_maps([dict(UNITS, links_dropped=0)], one, one_new, removed=set())
    assert as_dict[:2] == as_list[:2] and as_dict[1] == []


# --- clock nodes under a renumber (the naming row's snapshots): R6 and the selectors see them as C3 does (M2) ---

_A, _B, _C = "a" * 24, "b" * 24, "c" * 24  # media ids: 0-50, 12-10 and 1-00 clocks
CLOCKS = {_A: "0-50.png", _B: "12-10.png", _C: "1-00.png"}


def _clock(media, side, x):
    return {"ID": f"{media}{side}", "type": "image", "name": f"https://host/media/resource/{media}", "position": {"x": x}}


def _with_clocks(doc, clocks):
    out = copy.deepcopy(doc)
    out["nodes"] = out["nodes"] + clocks
    return out


def test_a_clock_window_that_moves_is_a_removal_and_an_addition_by_its_clock(tmp_path):
    """The 12:10 clock pair goes and a 0:50 pair comes (another media id), and the 1:00 pair moves on x: R6
    compares other types' IDs as C3 keys them (M2: by clock), and {"type": "image"} selects the clock records."""
    old = _write(tmp_path / "old.json", _with_clocks(OLD, [_clock(_B, 1, 180), _clock(_B, 2, 180), _clock(_C, 1, 20)]))
    new = _write(tmp_path / "new.json", _with_clocks(NEW, [_clock(_A, 1, 10), _clock(_A, 2, 10), _clock(_C, 1, 30)]))
    entry = _entry(old, [UNITS, SCOUTING], removed=("Scouting-0#1", "<clock:12-10.png>#1#1", "<clock:12-10.png>#2#1"))
    entry["added"] = ["<clock:0-50.png>#1#1", "<clock:0-50.png>#2#1"]
    entry["changes"].append({"select": {"type": "image"}, "fields": ["position.x"], "count": 1})
    assert cgd.check_delta(entry, old, new, CLOCKS) == []
    entry["added"] = []  # the 0:50 pair left out: R6 names it by its clock, as C3 would
    assert cgd.check_delta(entry, old, new, CLOCKS) == [
        "R6: IDs of other node types change: [] -> ['<clock:0-50.png>#1', '<clock:0-50.png>#2']"
    ]
