"""CR-012 (T12): the analysis as frozen domain models, still rendering G-CSV-1 exactly."""

import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys

import pytest
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph, typed_values
from sc2mindshare.domain.models import FIELDS, Link, Node
from sc2mindshare.domain.time import GameTime
from sc2mindshare.export.time_text import text_values
from sc2mindshare.reader.loader import load_replay

HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE.parents[1]
GOLDEN = CHECKOUT / "tests" / "golden" / "alcyone"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


golden = _load("golden", CHECKOUT / "tests" / "golden" / "golden.py")
legacy_rows = _load("legacy_rows", HERE / "legacy_rows.py")


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"


def need(path, what):
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(f"{exc} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(str(exc))


def graph_of(path):
    with contextlib.redirect_stdout(io.StringIO()):
        return to_graph(analyse(load_replay(path), MS_SC, fixes=()), fixes=())  # bug-faithful: renders the legacy CSV


@pytest.fixture(scope="module")
def alcyone():
    return graph_of(need(ALCYONE, "Alcyone replay"))


def test_the_models_render_g_csv_1_byte_for_byte(alcyone):
    assert legacy_rows.render(alcyone) == (GOLDEN / "G-CSV-1.csv").read_text(encoding="utf-8")
    assert alcyone.intervals == (GOLDEN / "Intervals-1.csv").read_text(encoding="utf-8")


@pytest.mark.legacy  # runs the old fork in .venv-legacy (CR-019)
def test_spine_models_render_the_live_legacy_csv(tmp_path):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    replay = need(SPINE, "200k dmg replay")
    cmd = [
        str(LEGACY_PY),
        str(CHECKOUT / "scripts" / "run_legacy.py"),
        "--support",
        str(MS_SC),
        "--out",
        str(tmp_path),
        str(replay),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    assert legacy_rows.render(graph_of(replay)) == (tmp_path / replay.stem / "events.csv").read_text(encoding="utf-8")


def test_every_node_has_its_kinds_declared_fields(alcyone):
    kinds = {n.kind for n in alcyone.nodes}
    assert kinds == set(FIELDS)  # Alcyone has every kind
    assert all(tuple(k for k, _ in n.values) == FIELDS[n.kind] for n in alcyone.nodes)


def test_start_times_are_signed_for_the_main_bases_b9(alcyone):
    main = [n for n in alcyone.nodes if n.kind == "Building" and dict(text_values(n))["time"] == "23:58:49"]
    assert len(main) == 2  # one per player: the legacy text wraps past midnight ...
    assert all(n.start.seconds == -71 and n.time("time") == n.start for n in main)  # ... the model keeps the real start


def test_scouting_minutes_are_read_as_minutes(alcyone):
    scout = next(n for n in alcyone.nodes if n.kind == "Scouting")
    m, s = dict(text_values(scout))["time"].split(":")
    assert scout.start.seconds == int(m) * 60 + int(s)
    values, start = typed_values(
        "Scouting-1", "Scouting", [("time", "01:42"), ("player", "p"), ("unit", "u"), ("base", "b")], 102
    )
    assert start == GameTime.from_seconds(102) and dict(values)["time"] == start  # 01:42 is 1 min 42 s


def test_the_adapter_refuses_a_time_that_is_not_its_start():
    """CR-022: no time changes silently; the printed time must be the signed start (wrapped at midnight)."""
    with pytest.raises(ValueError, match="is not its start"):
        typed_values("Chat-1", "Chat", [("time", "00:01:00"), ("player", "p")], 61)
    values, _ = typed_values("Building-1", "Building", [("time", "23:58:49"), ("player", "p"), ("type", "Hatchery")], -71)
    assert dict(values)["time"] == GameTime.from_seconds(-71)
    values, _ = typed_values("Energy Excess-1", "Energy Excess", [("time", "00:05:00"), ("end time", "None")], 300)
    assert dict(values)["end time"] is None  # an open end


def test_models_are_frozen_and_validated():
    t = GameTime.from_seconds(60)
    ok = Node("Chat", "Chat-1", "hi", "", (), (("time", t), ("player", "a")), t)
    with pytest.raises(AttributeError):
        ok.name = "x"  # type: ignore[misc]
    with pytest.raises(ValueError, match="declared"):
        Node("Chat", "Chat-1", "hi", "", (), (("player", "a"), ("time", t)), t)
    with pytest.raises(ValueError, match="unknown node kind"):
        Node("Comet", "Comet-1", "", "", (), (), t)
    with pytest.raises(ValueError, match="start is required"):
        Node("Chat", "Chat-1", "hi", "", (), (("time", t), ("player", "a")), None)
    with pytest.raises(ValueError, match="must be a GameTime"):  # CR-022: a time is never text in the model
        Node("Chat", "Chat-1", "hi", "", (), (("time", "00:01:00"), ("player", "a")), t)
    with pytest.raises(ValueError, match="must be a GameTime"):  # only an open Energy Excess may have no end
        Node("Chat", "Chat-1", "hi", "", (), (("time", None), ("player", "a")), t)
    with pytest.raises(ValueError, match="is text"):
        Node("Chat", "Chat-1", "hi", "", (), (("time", t), ("player", t)), t)
    with pytest.raises(TypeError, match="read it with time"):
        ok.value("time")
    with pytest.raises(TypeError, match="whole number of loops"):
        GameTime(1.5)  # type: ignore[arg-type]
    assert Link("Battle-1", "Battle-2", "previous", "next", "Two consecutive battles", 1).name is None


def test_no_properties_count_in_the_domain_or_the_adapter():
    for path in (
        CHECKOUT / "src" / "sc2mindshare" / "domain" / "models.py",
        CHECKOUT / "src" / "sc2mindshare" / "analysis" / "to_domain.py",
    ):
        assert "propertiesCount" not in path.read_text(encoding="utf-8")


def test_named_values_are_pinned(alcyone):
    # Swapping two names in FIELDS (e.g. "count" and "supply") must fail here, so each pinned node has
    # every field pinned and pairwise different values. The literals are G-CSV-1 rows, in the legacy
    # getProperties order: Units-10 line 179 (type, count, supply, currentUnits; an Overlord costs no
    # supply), Battle-2 line 5 (its description says 3 + 2 units and 1.5 + 3 supply lost), Stats-11
    # line 372 (minerals and gas current, collection rates, workers, army, used).
    expected = {
        "Units-10": {
            "time": "00:01:00",
            "player": "lilTiGGer",
            "type": "Overlord",
            "count": "1",
            "supply": "0",
            "total at time": "2",
        },
        "Battle-2": {
            "time": "0:02:10",
            "player": "Common",
            "dead": "5",
            "p1 dead": "3",
            "p2 dead": "2",
            "supply dead": "4.5",
            "end time": "0:02:18",
        },
        "Stats-11": {
            "time": "00:06:25",
            "player": "lilTiGGer",
            "cur. Min": "115",
            "cur. Gas": "122",
            "col. rate Min": "1875",
            "col. rate Gas": "492",
            "workers": "41",
            "army Min": "2000",
            "army Gas": "350",
            "used Min": "7175",
            "used Gas": "450",
        },
    }
    nodes = {n.id: n for n in alcyone.nodes}
    for node_id, values in expected.items():
        assert len(set(values.values())) == len(values), node_id  # a swap of any two names would show
        assert dict(text_values(nodes[node_id])) == values, node_id
