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
        return build_document(to_graph(analyse(load_replay(ALCYONE), MS_SC)))


def test_document_equals_g_view_1_with_the_view_masks(document):
    expected = json.loads((GOLDEN / "G-VIEW-1.json").read_text(encoding="utf-8"))
    report = golden.diff_json(expected, document, view=True)
    assert report.ok, str(report)
    assert report.budget_actual == {"M1": 1, "M3": 11}


def test_document_equals_g_view_1_even_unmasked(document):
    # Before the layout (CR-014) the Supply Block size is still the view's [2.65, 1].
    expected = json.loads((GOLDEN / "G-VIEW-1.json").read_text(encoding="utf-8"))
    assert golden.diff_json(expected, document).ok


def test_document_key_order_and_config_parts(document):
    assert list(document) == ["visuals", "detail", "dataTypes", "nodes", "links"]
    assert document["visuals"] == load_config()["visuals"]
    assert json.loads(to_json(document)) == document


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
