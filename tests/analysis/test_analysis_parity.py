"""CR-011 (T11) analysis parity: the ported layer on the new reader writes the legacy CSV exactly.

The test-only renderer is the layer's own CSVExporter (the product never writes the CSV). On
Alcyone the result must equal G-CSV-1 byte for byte (and the intervals Intervals-1); on
``200k dmg spine crawler ZvP`` it must equal a live run of the legacy code; on ``1000 spores ZvP``
it must fail exactly as the legacy code does (defect L1, kept on purpose until its fix).
"""

import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys

import pytest
from sc2mindshare.analysis.run import analyse, legacy_csv
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


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"
SPORES = MS_SC / "1000 spores ZvP.SC2Replay"


def need(path, what):
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(f"{exc} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(str(exc))


def render(replay_path):
    replay = load_replay(replay_path)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(replay, MS_SC)
    return legacy_csv(result), result


def test_alcyone_csv_is_g_csv_1_byte_for_byte():
    text, result = render(need(ALCYONE, "Alcyone replay"))
    expected = (GOLDEN / "G-CSV-1.csv").read_text(encoding="utf-8")
    report = golden.diff_csv(expected, text)
    assert report.ok, str(report)
    assert text == expected
    assert result.intervals == (GOLDEN / "Intervals-1.csv").read_text(encoding="utf-8")


@pytest.mark.legacy  # runs the old fork in .venv-legacy (CR-019)
def test_spine_csv_equals_a_live_legacy_run(tmp_path):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    replay = need(SPINE, "200k dmg replay")
    subprocess.run(
        [
            str(LEGACY_PY),
            str(CHECKOUT / "scripts" / "run_legacy.py"),
            "--support",
            str(MS_SC),
            "--out",
            str(tmp_path),
            str(replay),
        ],
        check=True,
        capture_output=True,
    )
    legacy = (tmp_path / replay.stem / "events.csv").read_text(encoding="utf-8")
    text, _ = render(replay)
    report = golden.diff_csv(legacy, text)
    assert report.ok, str(report)


def test_spores_fails_like_the_legacy_code_l1():
    replay = need(SPORES, "1000 spores replay")
    with pytest.raises(KeyError, match="118489090"):
        render(replay)


def test_the_analysis_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    render(need(ALCYONE, "Alcyone replay"))
    assert list(tmp_path.iterdir()) == []
