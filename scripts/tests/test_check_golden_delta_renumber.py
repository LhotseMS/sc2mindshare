"""Tests for the ``renumber`` entries of scripts/check_golden_delta.py (QA design Addendum A, R1-R6).

The scenario is the CR-023 naming row in miniature: an Overseer group that was an Overlord at its event
merges into the Overlord group of the same window (Units-3 -> Units-2), another is only renamed
(Units-4 -> Overlord), the later IDs shift down by one, and a link between the merged pair becomes a
self-link. Each deliberate break of Addendum A §A.3 has a test.
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


def _link(a, b, n1="previous", n2="next"):
    return {"name1": n1, "name2": n2, "direction": 1, "node1": a, "node2": b}


OLD = {
    "nodes": [
        _units("Units-1", "00:00:10", "Drone"),
        _units("Units-2", "00:00:20", "Overlord"),
        _units("Units-3", "00:00:20", "Overseer"),  # an Overlord at its event: merges into Units-2
        _units("Units-4", "00:00:30", "Overseer"),  # an Overlord at its event: renamed only
        _units("Units-5", "00:00:40", "Drone"),
        {"ID": "Battle-1", "type": "Battle", "name": "b", "description": "d", "properties": {}},
    ],
    "links": [
        _link("Units-1", "Units-5"),  # the Drone chain
        _link("Units-3", "Units-4"),  # the Overseer chain: Units-2 -> Units-3 in the new IDs
        _link("Units-2", "Units-3", "same window", "same window"),  # becomes a self-link: dropped
    ],
}
NEW = {
    "nodes": [
        _units("Units-1", "00:00:10", "Drone"),
        _units("Units-2", "00:00:20", "Overlord", count=2, name="2 Overlords"),
        _units("Units-3", "00:00:30", "Overlord"),
        _units("Units-4", "00:00:40", "Drone"),
        {"ID": "Battle-1", "type": "Battle", "name": "b", "description": "d", "properties": {}},
    ],
    "links": [_link("Units-1", "Units-4"), _link("Units-2", "Units-3")],
}


def _entry(old_path, **renumber):
    spec = {
        "type": "Units",
        "key": ["properties.player", "properties.time", "properties.type"],
        "retype": {"Units-3": "Overlord", "Units-4": "Overlord"},
        "merged": {"Units-3": "Units-2"},
        "ids_changed": 2,
        "links_dropped": 1,
    }
    spec.update(renumber)
    return {
        "entry": "N1",
        "task": "CR-023",
        "golden": ["x"],
        "base_sha256": cgd.golden.sha256(old_path),
        "renumber": spec,
        "changes": [
            {"select": {"ID": "Units-2"}, "fields": ["name", "properties.count"], "count": 1},
            {"select": {"ID": "Units-3"}, "fields": ["name", "properties.type"], "count": 1},
        ],
        "added": [],
        "removed": [],
    }


def _write(path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def paths(tmp_path):
    return _write(tmp_path / "old.json", OLD), _write(tmp_path / "new.json", NEW), tmp_path


def _problems(entry, old, new):
    return cgd.check_delta(entry, old, new)


def test_a_renumber_that_matches_its_entry_passes_and_prints_the_map(paths, capsys):
    old, new, _ = paths
    assert _problems(_entry(old), old, new) == []
    out = capsys.readouterr().out
    assert "Units-3 -> Units-2 (merged)" in out and "Units-4 -> Units-3" in out and "Units-5 -> Units-4" in out


def test_the_map_itself():
    spec = _entry(pathlib.Path(__file__))["renumber"]
    id_map, problems, _ = cgd.renumber_map(spec, OLD, NEW, removed=set())
    assert problems == []
    assert id_map == {
        "Units-1": "Units-1",
        "Units-2": "Units-2",
        "Units-3": "Units-2",
        "Units-4": "Units-3",
        "Units-5": "Units-4",
    }


def test_r3_a_merge_left_out_of_merged_fails(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, merged={}), old, new)
    assert any(p.startswith("R3") for p in problems), problems


def test_r2_a_rename_left_out_of_retype_fails_with_one_removal_and_one_addition(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, retype={"Units-3": "Overlord"}), old, new)
    r2 = [p for p in problems if p.startswith("R2")]
    assert (
        len(r2) == 2
        and any("Units-4" in p and "removal" in p for p in r2)
        and any("Units-3" in p and "addition" in p for p in r2)
    ), problems


def test_r5_an_unlisted_change_to_a_surviving_node_fails(paths):
    old, _, tmp = paths
    new = copy.deepcopy(NEW)
    new["nodes"][0]["properties"]["count"] = 7
    problems = _problems(_entry(old), old, _write(tmp / "new2.json", new))
    assert any("unlisted change: Units-1#1 properties.count" in p for p in problems), problems


def test_r6_another_types_id_change_fails_before_any_c3_output(paths):
    old, _, tmp = paths
    new = copy.deepcopy(NEW)
    new["nodes"][4]["ID"] = "Battle-9"
    problems = _problems(_entry(old), old, _write(tmp / "new2.json", new))
    assert problems and all(p.startswith("R6") for p in problems), problems


def test_r6_ids_changed_must_equal_the_derived_count(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, ids_changed=3), old, new)
    assert any(p.startswith("R6") and "ids_changed" in p for p in problems), problems


def test_r4_links_dropped_one_too_low_fails(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, links_dropped=0), old, new)
    assert any(p.startswith("R4") for p in problems), problems


def test_r4_a_dropped_link_listed_in_removed_by_its_old_ids_counts(paths):
    old, new, _ = paths
    entry = _entry(old, links_dropped=0)
    entry["removed"] = ["Units-2>Units-3#1"]
    assert _problems(entry, old, new) == []


def test_r1_a_merged_target_listed_as_a_source_fails(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, merged={"Units-3": "Units-2", "Units-2": "Units-1"}), old, new)
    assert problems and all(p.startswith("R1") for p in problems), problems


def test_r1_a_retype_that_differs_from_the_targets_old_type_fails(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, retype={"Units-3": "Drone", "Units-4": "Overlord"}), old, new)
    assert problems and all(p.startswith("R1") for p in problems), problems


def test_r1_a_merged_source_without_a_retype_fails(paths):
    old, new, _ = paths
    problems = _problems(_entry(old, retype={"Units-4": "Overlord"}), old, new)
    assert problems and all(p.startswith("R1") for p in problems), problems


def test_r1_a_duplicate_key_on_the_new_side_is_ambiguous(paths):
    old, _, tmp = paths
    new = copy.deepcopy(NEW)
    new["nodes"][3]["properties"]["time"] = "00:00:10"
    new["nodes"][3]["properties"]["type"] = "Drone"
    new["nodes"][0]["properties"]["time"] = "00:00:10"
    problems = _problems(_entry(old), old, _write(tmp / "new2.json", new))
    assert any("ambiguous alignment" in p for p in problems), problems


def test_an_entry_without_renumber_is_unchanged(paths):
    """The plain C3 path still runs as before for entries that renumber nothing."""
    old, new, _ = paths
    entry = _entry(old)
    del entry["renumber"]
    assert any(p.startswith("unlisted change") for p in _problems(entry, old, new))


def test_r5_pairs_nodes_by_id_not_by_position(tmp_path):
    """An added node right before a changed, renumbered one: R5 compares the changed node with its own new
    record (by ID), not with the added neighbour (sequence alignment would pair them)."""
    old = {"nodes": [_units("Units-1", "00:00:10", "Drone")], "links": []}
    new = {"nodes": [_units("Units-1", "00:00:05", "Drone"), _units("Units-2", "00:00:10", "Drone", count=2)], "links": []}
    old_path, new_path = _write(tmp_path / "o.json", old), _write(tmp_path / "n.json", new)
    entry = {
        "entry": "N2",
        "task": "CR-023",
        "golden": ["x"],
        "base_sha256": cgd.golden.sha256(old_path),
        "renumber": {
            "type": "Units",
            "key": ["properties.player", "properties.time"],
            "retype": {},
            "merged": {},
            "ids_changed": 1,
            "links_dropped": 0,
        },
        "changes": [{"select": {"ID": "Units-2"}, "fields": ["properties.count"], "count": 1}],
        "added": ["Units-1#1"],
        "removed": [],
    }
    assert cgd.check_delta(entry, old_path, new_path) == []


def test_r6_another_types_order_swap_is_not_an_id_change(paths, tmp_path):
    """Vera's G7 (1) on e780214: R6 compares the other types' IDs as a multiset; their order is C3's."""
    old = copy.deepcopy(OLD)
    old["nodes"].append({"ID": "Battle-2", "type": "Battle", "name": "b2", "description": "d", "properties": {}})
    new = copy.deepcopy(NEW)
    new["nodes"].insert(4, {"ID": "Battle-2", "type": "Battle", "name": "b2", "description": "d", "properties": {}})
    old_path, new_path = _write(tmp_path / "o2.json", old), _write(tmp_path / "n2.json", new)
    problems = _problems(_entry(old_path), old_path, new_path)
    assert not any(p.startswith("R6") for p in problems), problems


@pytest.mark.parametrize("field", ["ids_changed", "links_dropped"])
def test_ids_changed_and_links_dropped_are_required(paths, field):
    """Vera's G7 (2) on e780214: a missing count is not read as 0."""
    old, new, _ = paths
    entry = _entry(old)
    del entry["renumber"][field]
    problems = _problems(entry, old, new)
    assert any(field in p and "required" in p for p in problems), problems


@pytest.mark.parametrize("retired", [{"type": "Units", "from_position": 3, "shift": -1}, {"type": "Units", "shift": 1}])
def test_the_retired_single_shift_form_is_refused(paths, retired):
    """Morgan's G6 N1 on e780214: the single-shift form of QA design §5.1 is refused, not half-read."""
    old, new, _ = paths
    entry = _entry(old)
    entry["renumber"] = retired
    problems = _problems(entry, old, new)
    assert problems == ["renumber: the single-shift form is retired (QA design Addendum A); state key, retype and merged"], (
        problems
    )
