"""Tests for scripts/compare_csv.py (legacy events CSV comparison, image URLs masked)."""

import importlib.util
import pathlib
import sys

_PATH = pathlib.Path(__file__).resolve().parent.parent / "compare_csv.py"
_spec = importlib.util.spec_from_file_location("compare_csv", _PATH)
assert _spec and _spec.loader
compare_csv = importlib.util.module_from_spec(_spec)
sys.modules["compare_csv"] = compare_csv
_spec.loader.exec_module(compare_csv)

PAD = ";" * 15


def node(name, typ, nid, images="", props="00:01:00;p1"):
    return f"{name};desc;{typ};{nid};{images};{props}{PAD}"


def link(a, b):
    return f"{a};{b};previous;next;Two consecutive battles;1{PAD}"


def test_records_rejoin_a_row_whose_description_holds_a_raw_newline():
    split_row = "5 died, before pull;5 workers died.\nPull occured after 3s.;Harrasment;Harrasment-1;;00:01:00;p1" + PAD
    text = node("A", "Units", "Units-1") + "\n" + split_row + "\n" + node("B", "Units", "Units-2")
    recs = compare_csv.records(text)
    assert [r.physical_lines for r in recs] == [1, 2, 1]
    assert recs[1].text.split(";")[1] == "5 workers died.\\nPull occured after 3s."
    assert compare_csv.kind(recs[1].text) == ("node", "Harrasment")


def test_kind_follows_the_power_query_rule():
    assert compare_csv.kind(node("Zealot", "Battle", "Battle-1")) == ("node", "Battle")
    assert compare_csv.kind(link("Battle-1", "Battle-2")) == ("link", "Battle>Battle")


def test_mask_replaces_the_image_field_of_nodes_only():
    masked = compare_csv.mask(node("G", "Game", "Game-1", images="https://x/1|https://x/2"))
    assert masked.split(";")[4] == "<images>"
    assert compare_csv.mask(link("Battle-1", "Battle-2")) == link("Battle-1", "Battle-2")


def test_compare_identical_except_images():
    a = "\n".join([node("G", "Game", "Game-1", images="https://a"), link("Game-1", "Player-1")])
    b = "\n".join([node("G", "Game", "Game-1", images="https://b"), link("Game-1", "Player-1")])
    result = compare_csv.compare(a, b)
    assert result.identical
    assert result.same_order


def test_compare_reports_extra_rows_by_kind_and_padding_only_differences():
    up_a = node("Burrow", "Upgrade", "Upgrade-1") + ";"
    up_b = node("Burrow", "Upgrade", "Upgrade-1")
    harass = node("1 died", "Harrasment", "Harrasment-0")
    result = compare_csv.compare(up_a, f"{up_b}\n{harass}")
    assert not result.identical
    assert result.counts_a[("node", "Upgrade")] == 1
    assert result.only_b_by_kind == {("node", "Harrasment"): 1}
    assert result.only_a_by_kind == {}
    assert result.padding_only == 1


def test_duplicate_ids_are_reported():
    text = "\n".join([node("x", "Harrasment", "Harrasment-0"), node("y", "Harrasment", "Harrasment-0")])
    assert compare_csv.duplicate_ids(compare_csv.records(text)) == {"Harrasment-0": 2}


def test_a_changed_non_image_field_is_a_difference():
    a = node("G", "Game", "Game-1", props="00:16:38;p1")
    b = node("G", "Game", "Game-1", props="00:16:39;p1")
    result = compare_csv.compare(a, b)
    assert not result.identical
    assert result.only_a_by_kind == {("node", "Game"): 1}
    assert result.only_b_by_kind == {("node", "Game"): 1}
