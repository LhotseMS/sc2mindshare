"""CR-016 (T15): ``sc2mindshare build`` reproduces the goldens in one command."""

import contextlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

from sc2mindshare import cli

CHECKOUT = pathlib.Path(__file__).resolve().parents[1]
GOLDEN = CHECKOUT / "tests" / "golden" / "alcyone"
VENV_BIN = pathlib.Path(sys.executable).parent


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"


def need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    return path


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_one_command_reproduces_the_goldens(tmp_path, mode):
    need(ALCYONE)
    out = tmp_path / "game" / "graph.json"
    code, stdout, stderr = run("build", ALCYONE, "--out", out, "--timeline", mode, "--config-root", MS_SC)
    assert (code, stderr) == (0, "")
    assert out.read_bytes() == (GOLDEN / f"G-SNAP-1-{mode}.json").read_bytes()
    assert (out.parent / "Intervals.csv").read_bytes() == (GOLDEN / "Intervals-1.csv").read_bytes()
    doc = json.loads((out.parent / "intervals.json").read_text(encoding="utf-8"))
    assert doc["graph"] == "graph.json" and len(doc["intervals"]) == 30 and doc["intervals"][0]["id"] == "Battle-1"
    # the layer's debug prints go to the log, never to the console or into the JSON
    assert stdout == f"wrote {out}, {out.parent / 'intervals.json'}, {out.parent / 'Intervals.csv'}\n"
    assert (out.parent / "graph.log").read_text(encoding="utf-8") != ""


def test_compressed_is_the_default_and_the_config_root_can_come_from_the_environment(tmp_path, monkeypatch):
    need(ALCYONE)
    monkeypatch.setenv("MS_SC_ROOT", str(MS_SC))
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out, "--log", tmp_path / "run.log")
    assert (code, stderr) == (0, "")
    assert out.read_bytes() == (GOLDEN / "G-SNAP-1-compressed.json").read_bytes()
    assert (tmp_path / "run.log").exists() and not (tmp_path / "graph.log").exists()


def test_another_replay_builds(tmp_path):
    """G5 smoke through the CLI: 200k dmg spine crawler ZvP (1000 spores ZvP fails in the legacy layer, L1)."""
    need(SPINE)
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", SPINE, "--out", out, "--config-root", MS_SC)
    assert (code, stderr) == (0, "")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links"]
    assert all("position" in n for n in doc["nodes"])


def test_usage_errors_exit_2_and_write_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("MS_SC_ROOT", raising=False)
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out)
    assert code == 2 and "--config-root" in stderr
    code, _, stderr = run("build", tmp_path / "missing.SC2Replay", "--out", out, "--config-root", MS_SC)
    assert code == 2 and "missing.SC2Replay" in stderr
    need(ALCYONE)  # the replay check comes first, so this case needs a real replay
    code, _, stderr = run("build", ALCYONE, "--out", out, "--config-root", tmp_path / "nowhere")
    assert code == 2 and "nowhere" in stderr
    assert list(tmp_path.iterdir()) == []


def test_a_failing_analysis_exits_1_with_the_traceback_in_the_log(tmp_path, monkeypatch):
    need(ALCYONE)

    def broken(replay, support_root, **_):
        print("layer output before the failure")
        raise KeyError(1)

    monkeypatch.setattr(cli, "analyse", broken)
    out = tmp_path / "graph.json"
    code, stdout, stderr = run("build", ALCYONE, "--out", out, "--config-root", MS_SC)
    assert code == 1 and stdout == ""
    assert stderr == f"sc2mindshare: the analysis failed: KeyError: 1 (traceback in {tmp_path / 'graph.log'})\n"
    log = (tmp_path / "graph.log").read_text(encoding="utf-8")
    assert "layer output before the failure" in log and "Traceback" in log
    assert sorted(p.name for p in tmp_path.iterdir()) == ["graph.log"]  # no partial outputs


def test_the_readme_documents_the_help_text():
    """'--help documented in the README' (T15): the README's usage block is the command's own help."""
    env = dict(os.environ, COLUMNS="100")
    help_text = subprocess.run(
        [str(VENV_BIN / "sc2mindshare"), "build", "--help"], check=True, capture_output=True, text=True, env=env
    ).stdout
    readme = (CHECKOUT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"<!-- build --help -->\n```text\n(.*?)```\n", readme, re.DOTALL)
    assert block is not None, "README.md has no '<!-- build --help -->' usage block"
    assert block.group(1) == help_text


def test_a_second_build_into_the_same_folder_is_refused(tmp_path):
    """screenshotGame.py reads <game folder>/Intervals.csv, a fixed name, so one folder holds one build's
    intervals: building another --out into it would overwrite them. Re-running the same build is fine."""
    need(ALCYONE)
    first = tmp_path / "graph.json"
    assert run("build", ALCYONE, "--out", first, "--config-root", MS_SC)[0] == 0
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    code, _, stderr = run("build", ALCYONE, "--out", tmp_path / "other.json", "--config-root", MS_SC)
    assert code == 2 and "graph.json" in stderr and "another --out folder" in stderr
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert run("build", ALCYONE, "--out", first, "--config-root", MS_SC)[0] == 0  # the same build again


def test_intervals_without_their_json_are_refused(tmp_path):
    need(ALCYONE)
    (tmp_path / "Intervals.csv").write_text("start,end,id\n", encoding="utf-8")
    code, _, stderr = run("build", ALCYONE, "--out", tmp_path / "graph.json", "--config-root", MS_SC)
    assert code == 2 and "Intervals.csv" in stderr


def test_the_outputs_appear_together_or_not_at_all(tmp_path, monkeypatch):
    """All three files are written to temporary names first and renamed only when all are written."""
    need(ALCYONE)
    real = cli._write_temp

    def failing(path, text):
        if path.name == "Intervals.csv":
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(cli, "_write_temp", failing)
    code, _, stderr = run("build", ALCYONE, "--out", tmp_path / "graph.json", "--config-root", MS_SC)
    assert code == 1 and "disk full" in stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["graph.log"]  # no output, no temporary file left


def test_with_analysis_adds_the_analysis_object_and_nothing_else(tmp_path):
    """CR-021: opt-in; without the flag the output is the golden (the other tests), with it the same
    document gains a top-level "analysis" object and nothing else changes."""
    need(ALCYONE)
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out, "--config-root", MS_SC, "--with-analysis")
    assert (code, stderr) == (0, "")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links", "analysis"]
    analysis = doc.pop("analysis")
    assert doc == json.loads((GOLDEN / "G-SNAP-1-compressed.json").read_text(encoding="utf-8"))
    assert analysis["game"]["base_build"] == 92440 and len(analysis["units"]) == 1232


def test_the_exposed_values_are_computed_only_when_asked_for(tmp_path, monkeypatch):
    """Morgan's G6 N1 on c312162: a failure in expose() (or in reading its tables) never breaks the
    default build; with --with-analysis it fails the build like any analysis failure."""
    need(ALCYONE)
    from sc2mindshare.analysis import run as analysis_run

    def broken(*_args, **_kwargs):
        raise RuntimeError("expose broke")

    monkeypatch.setattr(analysis_run, "expose", broken)
    plain = tmp_path / "plain" / "graph.json"
    plain.parent.mkdir()
    code, _, stderr = run("build", ALCYONE, "--out", plain, "--config-root", MS_SC)
    assert (code, stderr) == (0, "")
    assert plain.read_text(encoding="utf-8") == (GOLDEN / "G-SNAP-1-compressed.json").read_text(encoding="utf-8")
    asked = tmp_path / "asked" / "graph.json"
    asked.parent.mkdir()
    code, _, stderr = run("build", ALCYONE, "--out", asked, "--config-root", MS_SC, "--with-analysis")
    assert code == 1 and "RuntimeError: expose broke" in stderr
