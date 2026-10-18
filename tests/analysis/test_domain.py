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
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.models import FIELDS, Link, Node
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
        return to_graph(analyse(load_replay(path), MS_SC), fixes=())  # bug-faithful: renders the legacy CSV


@pytest.fixture(scope="module")
def alcyone():
    return graph_of(need(ALCYONE, "Alcyone replay"))


def test_the_models_render_g_csv_1_byte_for_byte(alcyone):
    assert legacy_rows.render(alcyone) == (GOLDEN / "G-CSV-1.csv").read_text(encoding="utf-8")
    assert alcyone.intervals == (GOLDEN / "Intervals-1.csv").read_text(encoding="utf-8")


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
    main = [n for n in alcyone.nodes if n.kind == "Building" and n.value("time") == "23:58:49"]
    assert len(main) == 2  # one per player: the legacy text wraps past midnight ...
    assert all(n.start_seconds == -71 for n in main)  # ... the model keeps the real pre-game start


def test_scouting_minutes_are_read_as_minutes(alcyone):
    scout = next(n for n in alcyone.nodes if n.kind == "Scouting")
    m, s = scout.value("time").split(":")
    assert scout.start_seconds == int(m) * 60 + int(s)


def test_models_are_frozen_and_validated():
    ok = Node("Chat", "Chat-1", "hi", "", (), (("time", "00:01:00"), ("player", "a")), 60)
    with pytest.raises(AttributeError):
        ok.name = "x"  # type: ignore[misc]
    with pytest.raises(ValueError, match="declared"):
        Node("Chat", "Chat-1", "hi", "", (), (("player", "a"), ("time", "00:01:00")), 60)
    with pytest.raises(ValueError, match="unknown node kind"):
        Node("Comet", "Comet-1", "", "", (), (), 1)
    with pytest.raises(ValueError, match="start_seconds"):
        Node("Chat", "Chat-1", "hi", "", (), (("time", "00:01:00"), ("player", "a")), None)
    assert Link("Battle-1", "Battle-2", "previous", "next", "Two consecutive battles", 1).name is None


def test_no_properties_count_in_the_domain_or_the_adapter():
    for path in (
        CHECKOUT / "src" / "sc2mindshare" / "domain" / "models.py",
        CHECKOUT / "src" / "sc2mindshare" / "analysis" / "to_domain.py",
    ):
        assert "propertiesCount" not in path.read_text(encoding="utf-8")


def test_named_values_are_pinned(alcyone):
    # Swapping two names in FIELDS (e.g. "count" and "supply") must fail here.
    units = next(n for n in alcyone.nodes if n.kind == "Units" and n.name == "12 Drones")
    assert (units.value("type"), units.value("count"), units.value("supply"), units.value("total at time")) == (
        "Drone",
        "12",
        "12",
        "12",
    )
    battle = next(n for n in alcyone.nodes if n.id == "Battle-1")
    assert (battle.value("dead"), battle.value("p1 dead"), battle.value("p2 dead"), battle.value("supply dead")) == (
        "1",
        "1",
        "0",
        "0.5",
    )
    stats = next(n for n in alcyone.nodes if n.id == "Stats-1")
    assert (stats.value("cur. Min"), stats.value("col. rate Min"), stats.value("workers"), stats.value("used Min")) == (
        "330",
        "839",
        "14",
        "1250",
    )
