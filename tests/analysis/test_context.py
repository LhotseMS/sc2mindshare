"""CR-011b: the detectors share an explicit AnalysisContext instead of module globals."""

import ast
import contextlib
import io
import os
import pathlib

import pytest

from sc2mindshare.analysis.context import AnalysisContext
from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.run import analyse, legacy_csv
from sc2mindshare.reader.loader import load_replay

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "sc2mindshare" / "analysis"


def _root():
    d = SRC
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"


def test_no_module_level_detector_globals_are_left():
    for name in ("basesDetector", "actionsDetector", "simpleDetector", "battleDetector", "singlesDetector"):
        assert not hasattr(detectors, name)
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(isinstance(n, ast.Global) for n in ast.walk(tree)), f"global statement in {path.name}"
        assert "detectors.detectors." not in path.read_text(encoding="utf-8").replace(
            "sc2mindshare.analysis.detectors.detectors import", ""
        )


def _quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


@pytest.mark.skipif(not (ALCYONE.exists() and SPINE.exists()), reason="replays not found")
def test_two_replays_in_one_process_give_their_own_results():
    # With module globals, the second analysis would overwrite the first's detectors.
    first = _quiet(analyse, load_replay(ALCYONE), MS_SC)
    first_csv = legacy_csv(first)
    _quiet(analyse, load_replay(SPINE), MS_SC)
    assert legacy_csv(first) == first_csv


def test_create_detectors_returns_the_context(monkeypatch):
    built = []

    class Fake:
        def __init__(self, replay, ctx):
            built.append((type(self).__name__, ctx))

    for name in ("BaseDetector", "ActionsDetector", "SimpleDetector", "BattleDetector", "SinglesDetector"):
        monkeypatch.setattr(detectors, name, type(name, (Fake,), {}))
    ctx = detectors.createDetectors("replay")
    assert isinstance(ctx, AnalysisContext)
    assert [n for n, _ in built] == ["BaseDetector", "ActionsDetector", "SimpleDetector", "BattleDetector", "SinglesDetector"]
    assert all(c is ctx for _, c in built)
