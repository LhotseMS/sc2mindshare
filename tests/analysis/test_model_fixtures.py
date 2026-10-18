"""CR-019 (T18): the analysis parity as frozen model-level fixtures, so it holds without the legacy venv.

``tests/golden/<game>/models-faithful.json`` is the bug-faithful domain graph (``fixes=()``) of Alcyone
and of the 200k dmg spine crawler replay, frozen by ``scripts/freeze_parity_fixtures.py`` only after it
rendered exactly the CSV a live legacy run wrote. These tests compare the pipeline with the fixtures,
so a refactor of the analysis keeps its parity check after the legacy venv is gone (T24). The
fixtures' own link to the legacy code is re-checked live when the venv is present (``legacy`` marker).
The 1000 spores replay has no model fixture: its analysis fails in the legacy layer (L1, CR-023).
"""

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE.parents[1]
GOLDEN = CHECKOUT / "tests" / "golden"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


golden = _load("golden", GOLDEN / "golden.py")
legacy_rows = _load("legacy_rows", HERE / "legacy_rows.py")
freeze = _load("freeze_parity_fixtures", CHECKOUT / "scripts" / "freeze_parity_fixtures.py")


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
GAMES = {
    "alcyone": MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
    "spine": MS_SC / "200k dmg spine crawler ZvP.SC2Replay",
}


def need(path, what):
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(f"{exc} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(str(exc))


def fixture_text(game):
    return (GOLDEN / game / "models-faithful.json").read_text(encoding="utf-8")


def _first_difference(expected, actual):
    for part in ("nodes", "links"):
        for i, (e, a) in enumerate(zip(expected[part], actual[part], strict=False)):
            if e != a:
                return f"{part}[{i}]: frozen {e} != now {a}"
        if len(expected[part]) != len(actual[part]):
            return f"{part}: {len(expected[part])} frozen, {len(actual[part])} now"
    return "intervals differ" if expected["intervals"] != actual["intervals"] else "no difference"


@pytest.mark.parametrize("game", sorted(GAMES))
def test_the_pipeline_still_gives_the_frozen_models(game):
    graph = freeze.faithful_graph(need(GAMES[game], f"{game} replay"), MS_SC)
    now = freeze.graph_doc(graph)
    frozen = json.loads(fixture_text(game))
    assert now == frozen, _first_difference(frozen, now)
    assert freeze.to_text(now) == fixture_text(game)  # byte for byte


@pytest.mark.parametrize("game", sorted(GAMES))
def test_the_fixture_renders_the_frozen_legacy_csv(game):
    """Without the legacy venv: the frozen models render the frozen legacy CSV and intervals (Alcyone's
    G-CSV-1 and Intervals-1; spine's, frozen from a live legacy run by ``freeze_parity_fixtures legacy-csv``)."""
    graph = freeze.graph_from_doc(json.loads(fixture_text(game)))
    assert legacy_rows.render(graph) == (GOLDEN / game / "G-CSV-1.csv").read_text(encoding="utf-8")
    assert graph.intervals == (GOLDEN / game / "Intervals-1.csv").read_text(encoding="utf-8")


@pytest.mark.parametrize("game", sorted(GAMES))
def test_a_fixture_reads_back_as_the_same_models(game):
    doc = json.loads(fixture_text(game))
    assert freeze.graph_doc(freeze.graph_from_doc(doc)) == doc  # the models validate their fields on construction
    assert len(doc["nodes"]) == {"alcyone": 665, "spine": 302}[game]
    assert len(doc["links"]) == {"alcyone": 412, "spine": 150}[game]


@pytest.mark.legacy  # runs the old fork in .venv-legacy (CR-019)
def test_the_spine_fixture_renders_a_live_legacy_run(tmp_path):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    replay = need(GAMES["spine"], "200k dmg replay")
    cmd = [str(LEGACY_PY), str(CHECKOUT / "scripts" / "run_legacy.py"), "--support", str(MS_SC), "--out", str(tmp_path)]
    subprocess.run([*cmd, str(replay)], check=True, capture_output=True)
    live_csv = (tmp_path / replay.stem / "events.csv").read_text(encoding="utf-8")
    live_intervals = (tmp_path / replay.stem / "Intervals.csv").read_text(encoding="utf-8")
    assert live_csv == (GOLDEN / "spine" / "G-CSV-1.csv").read_text(encoding="utf-8")  # the frozen copy is current
    assert live_intervals == (GOLDEN / "spine" / "Intervals-1.csv").read_text(encoding="utf-8")
    graph = freeze.graph_from_doc(json.loads(fixture_text("spine")))
    assert legacy_rows.render(graph) == live_csv and graph.intervals == live_intervals


def test_the_parity_fixtures_are_unchanged():
    """Frozen once (PARITY.sha256): a change to one is a golden change with its CHANGES.md entry."""
    pins = golden.read_pins(GOLDEN / "PARITY.sha256")
    assert set(pins) == {
        "alcyone/models-faithful.json",
        "alcyone/reader-state-legacy.summary.json",
        "spine/G-CSV-1.csv",
        "spine/Intervals-1.csv",
        "spine/models-faithful.json",
        "spine/reader-state-legacy.summary.json",
        "spores/reader-state-legacy.summary.json",
    }
    for name, digest in pins.items():
        assert golden.sha256(GOLDEN / name) == digest, f"frozen parity fixture changed: {name}"


def test_the_freeze_never_overwrites():
    with pytest.raises(SystemExit, match="frozen once"):
        freeze._target("alcyone", "models-faithful.json")
