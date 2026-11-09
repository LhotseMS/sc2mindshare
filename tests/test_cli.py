"""CR-016 (T15): ``sc2mindshare build`` reproduces the goldens in one command."""

import contextlib
import io
import json
import os
import pathlib
import re
import shutil
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


FIXTURE_RECORD = CHECKOUT / "tests" / "golden" / "clock-record-fixture.csv"


@pytest.fixture
def config(tmp_path):
    """CR-069: a config root with the real support tables and the committed fixture as its clock record, so a
    build reproduces the goldens without Stefan's own record (the goldens are built from the fixture)."""
    root = tmp_path / "config"
    root.mkdir()
    for name in ("unitsInfo.csv", "upgradesInfo.csv", "ImageTracking.csv"):  # ImageTracking: the Game's images
        shutil.copyfile(need(MS_SC / name), root / name)
    shutil.copyfile(FIXTURE_RECORD, root / "ClockImageRecord.csv")
    return root


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


@pytest.mark.parametrize("mode", ["compressed", "linear"])
def test_one_command_reproduces_the_goldens(tmp_path, config, mode):
    need(ALCYONE)
    out = tmp_path / "game" / "graph.json"
    code, stdout, stderr = run("build", ALCYONE, "--out", out, "--timeline", mode, "--config-root", config)
    assert (code, stderr) == (0, "")
    assert out.read_bytes() == (GOLDEN / f"G-SNAP-current-{mode}.json").read_bytes()
    assert (out.parent / "Intervals.csv").read_bytes() == (GOLDEN / "Intervals-1.csv").read_bytes()
    doc = json.loads((out.parent / "intervals.json").read_text(encoding="utf-8"))
    assert doc["graph"] == "graph.json" and len(doc["intervals"]) == 30 and doc["intervals"][0]["id"] == "Battle-1"
    # the layer's debug prints go to the log, never to the console or into the JSON
    assert stdout == f"wrote {out}, {out.parent / 'intervals.json'}, {out.parent / 'Intervals.csv'}\n"
    assert (out.parent / "graph.log").read_text(encoding="utf-8") != ""


def test_compressed_is_the_default_and_the_config_root_can_come_from_the_environment(tmp_path, config, monkeypatch):
    need(ALCYONE)
    monkeypatch.setenv("MS_SC_ROOT", str(config))
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out, "--log", tmp_path / "run.log")
    assert (code, stderr) == (0, "")
    assert out.read_bytes() == (GOLDEN / "G-SNAP-current-compressed.json").read_bytes()
    assert (tmp_path / "run.log").exists() and not (tmp_path / "graph.log").exists()


def test_another_replay_builds(tmp_path, config):
    """G5 smoke through the CLI: 200k dmg spine crawler ZvP. (1000 spores ZvP stopped in the legacy layer's energy
    check, L1, until CR-076's layer fix E1; it now stops there only in the bug-faithful run.)"""
    need(SPINE)
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", SPINE, "--out", out, "--config-root", config)
    # CR-023 P8 writes spine's last Units node (serega's Probe at 11:00), alone in its window: the layout
    # places it by its lag-flush rule (layout-spec §5.8) and says so
    assert (code, stderr) == (0, "sc2mindshare: layout warning: units left in the buffer at the end: flushed in window 65\n")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links"]
    assert all("position" in n for n in doc["nodes"])


SPORES = MS_SC / "1000 spores ZvP.SC2Replay"


def test_spores_builds_and_its_energy_mismatches_stay_in_the_log(tmp_path, config):
    """CR-076 (AC3, AC5, AC6): 1000 spores ZvP builds through the CLI. Its 11 casts the energy check cannot charge
    (Stefan's D2a) are lines in graph.log only: the graph carries no warning. No Energy Excess node is made for the
    five spellcaster types without a threshold (D2a)."""
    need(SPORES)
    out = tmp_path / "graph.json"
    code, _, _ = run("build", SPORES, "--out", out, "--config-root", config)
    assert code == 0
    log = (tmp_path / "graph.log").read_text(encoding="utf-8")
    assert log.count("data doesn't match") == 11
    text = out.read_text(encoding="utf-8")
    assert "data doesn't match" not in text and "energy check" not in text
    excess = [n["name"] for n in json.loads(text)["nodes"] if n.get("type") == "Energy Excess"]
    assert excess, "spores has Energy Excess nodes (Queens, Nexuses)"
    assert not [n for n in excess if n.split(" ")[0] in ("Sentry", "Oracle", "Infestor", "HighTemplar", "Overseer")]


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


def test_a_mixed_node_type_stops_the_build_with_no_mindshare_file(tmp_path, config, monkeypatch):
    """CR-063 AC-5 (S7): the export's guard stops a document Mindshare would refuse; the console wording
    "the analysis failed: ValueError: ..." is kept (D5a at Step 5)."""
    need(ALCYONE)
    from sc2mindshare.export import mindshare_json, view

    def dropping(node, export_fixes=frozenset()):
        out = view.node_view(node, export_fixes)
        if node.id == "Ability-12":
            del out["properties"]["target"]
        return out

    monkeypatch.setattr(mindshare_json, "node_view", dropping)
    folder = tmp_path / "out"
    folder.mkdir()
    out = folder / "graph.json"
    code, stdout, stderr = run("build", ALCYONE, "--out", out, "--config-root", config)
    assert code == 1 and stdout == ""
    assert stderr == (
        "sc2mindshare: the analysis failed: ValueError: node type 'Ability': node 'Ability-12' has different "
        "properties than node 'Ability-4' ('Ability-12' lacks property 'target'); Mindshare refuses such a file "
        f"(traceback in {folder / 'graph.log'})\n"
    )
    assert sorted(p.name for p in folder.iterdir()) == ["graph.log"]  # no graph.json, intervals.json, Intervals.csv


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


def test_with_analysis_adds_the_analysis_object_and_nothing_else(tmp_path, config):
    """CR-021: opt-in; without the flag the output is the golden (the other tests), with it the same
    document gains a top-level "analysis" object and nothing else changes."""
    need(ALCYONE)
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out, "--config-root", config, "--with-analysis")
    assert (code, stderr) == (0, "")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links", "analysis"]
    analysis = doc.pop("analysis")
    assert doc == json.loads((GOLDEN / "G-SNAP-current-compressed.json").read_text(encoding="utf-8"))
    assert analysis["game"]["base_build"] == 92440 and len(analysis["units"]) == 1232


def test_the_exposed_values_feed_every_build_and_a_failure_in_them_fails_it(tmp_path, config, monkeypatch):
    """CR-034 (D47a): the build steps are on by default and are made from the exposed values, so every build
    computes them (before CR-034 only --with-analysis did: Morgan's G6 N1 on c312162). A failure in expose() (or
    in reading its tables) fails the build like any analysis failure, with or without --with-analysis, and
    leaves no output."""
    need(ALCYONE)
    from sc2mindshare.analysis import run as analysis_run

    def broken(*_args, **_kwargs):
        raise RuntimeError("expose broke")

    monkeypatch.setattr(analysis_run, "expose", broken)
    for label, extra in (("plain", ()), ("asked", ("--with-analysis",))):
        out = tmp_path / label / "graph.json"
        out.parent.mkdir()
        code, _, stderr = run("build", ALCYONE, "--out", out, "--config-root", config, *extra)
        assert code == 1 and "RuntimeError: expose broke" in stderr
        assert not out.exists()


# --- CR-069: the clock record and --clock-server ------------------------------------------------------------------------


def _clock_warnings(stderr):
    return [line for line in stderr.splitlines() if "no clock image" in line]


def test_the_build_needs_no_time_image_tracking_csv(tmp_path, config):
    """D45a (Q2): the export no longer reads TimeImageTracking.csv, so the config root need not hold it."""
    need(ALCYONE)
    assert not (config / "TimeImageTracking.csv").exists()
    code, _, stderr = run("build", ALCYONE, "--out", tmp_path / "graph.json", "--config-root", config)
    assert (code, stderr) == (0, "")


def test_ac11_without_a_record_the_build_succeeds_without_clocks_and_says_so(tmp_path, config):
    need(ALCYONE)
    (config / "ClockImageRecord.csv").unlink()
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out, "--config-root", config)
    assert code == 0
    warnings = _clock_warnings(stderr)
    assert len(warnings) == 71 and all("sc2mindshare upload-clocks" in w for w in warnings)  # 70 before CR-034
    assert "no clock record" in stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert [n for n in doc["nodes"] if n["type"] == "image"] == []


def test_ac8_an_unreadable_record_leaves_the_build_without_clocks_and_the_file_as_it_is(tmp_path, config):
    need(ALCYONE)
    record = config / "ClockImageRecord.csv"
    record.write_text("not,a,record\n", encoding="utf-8")
    code, _, stderr = run("build", ALCYONE, "--out", tmp_path / "graph.json", "--config-root", config)
    assert code == 0 and "cannot read the clock record" in stderr and len(_clock_warnings(stderr)) == 71  # 70 before CR-034
    assert record.read_text(encoding="utf-8") == "not,a,record\n"


def test_ac5_the_clock_server_picks_its_own_rows(tmp_path, config):
    need(ALCYONE)
    out = tmp_path / "graph.json"
    code, _, stderr = run("build", ALCYONE, "--out", out, "--config-root", config, "--clock-server", "http://127.0.0.1:3042")
    assert (code, stderr) == (0, "")  # 127.0.0.1 and localhost on one port are one server
    other = tmp_path / "other" / "graph.json"
    other.parent.mkdir()
    code, _, stderr = run("build", ALCYONE, "--out", other, "--config-root", config, "--clock-server", "http://localhost:3043")
    assert code == 0 and len(_clock_warnings(stderr)) == 71  # 70 before CR-034


def test_the_clock_server_must_be_local(tmp_path, config):
    code, _, stderr = run(
        "build",
        need(ALCYONE),
        "--out",
        tmp_path / "graph.json",
        "--config-root",
        config,
        "--clock-server",
        "http://example.com:3042",
    )
    assert code == 2 and "local Mindshare only" in stderr


def test_cr070_ac5_a_cost_that_cannot_be_found_exits_1_and_writes_nothing(tmp_path, config):
    """CR-070 AC-5 (Stefan's D1a): with no Shield Battery row in the config root's unitsInfo.csv, the build stops at
    the 7:48 battery death in Battle-12: exit 1, the error on stderr with the traceback in the log, and no Mindshare
    file, intervals.json or Intervals.csv, neither in a fresh folder nor over an earlier build's (left as they were)."""
    need(ALCYONE)
    fresh, earlier = tmp_path / "fresh" / "graph.json", tmp_path / "earlier" / "graph.json"
    assert run("build", ALCYONE, "--out", earlier, "--config-root", config)[0] == 0
    outputs = [earlier.parent / name for name in ("graph.json", "intervals.json", "Intervals.csv")]
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in outputs]
    table = config / "unitsInfo.csv"
    lines = table.read_text(encoding="utf-8").splitlines(keepends=True)
    table.write_text("".join(line for line in lines if not line.startswith("Shield Battery,")), encoding="utf-8")
    message = (
        "cannot find the cost of ShieldBattery 72613891 (blacksquall) that died at 07:48 in "
        'Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay: unitsInfo.csv has no "Shield Battery" row'
    )
    for out in (fresh, earlier):
        code, stdout, stderr = run("build", ALCYONE, "--out", out, "--config-root", config)
        assert (code, stdout) == (1, "")
        log = out.parent / "graph.log"
        assert stderr == f"sc2mindshare: the analysis failed: ValueError: {message} (traceback in {log})\n"
        text = log.read_text(encoding="utf-8")
        assert "Traceback" in text and f"ValueError: {message}" in text
    assert sorted(p.name for p in fresh.parent.iterdir()) == ["graph.log"]
    assert [(p.read_bytes(), p.stat().st_mtime_ns) for p in outputs] == before


# --- CR-035: --guide (AC7, AC10; S22, S25, S26) ------------------------------------------------------------------------


def test_cr035_a_named_guide_is_picked_logged_and_exported(tmp_path, config):
    """S13, S22 through the CLI: the named guide is picked for lilTiGGer (graded by time and supply), blacksquall's is
    still suggested; both are in the log and in the exported graph."""
    need(ALCYONE)
    out = tmp_path / "game" / "graph.json"
    guide = "lilTiGGer=zvp-3-hatch-before-pool-liquipedia"
    code, _stdout, stderr = run("build", ALCYONE, "--out", out, "--config-root", config, "--guide", guide)
    assert (code, stderr) == (0, "")
    log = (out.parent / "graph.log").read_text(encoding="utf-8")
    assert "build check: player 1: 3 Hatch Before Pool (vs. Gate expand) (picked, score 79/105)" in log
    assert "build check: player 2: Gate, Nexus, Core into Stargate (PvZ) (suggested, score 10/33)" in log
    doc = json.loads(out.read_text(encoding="utf-8"))
    cards = [n for n in doc["nodes"] if n["type"] == "Build Comparison"]
    assert [(c["name"], c["properties"]["player"], c["properties"]["picked"], c["properties"]["graded by"]) for c in cards] == [
        ("Build check · 3 Hatch Before Pool (vs. Gate expand)", "lilTiGGer", "picked", "time and supply"),
        ("Build check · Gate, Nexus, Core into Stargate (PvZ)", "blacksquall", "suggested", "supply"),
    ]
    step = {
        n["properties"]["step #"]: n
        for n in doc["nodes"]
        if n["type"] == "Building" and n["properties"]["player"] == "lilTiGGer"
    }
    # S13: "17 - Hatchery at 0:52" with step 7 (1:20), +28; "19 - Hatchery at 1:25" with step 26 (3:24), +119
    assert [
        (step[k]["name"].rpartition(" · ")[2], step[k]["properties"]["guide time"], step[k]["properties"]["off by s"])
        for k in (7, 26)
    ] == [
        ("28 s late", "0:52", "+28"),
        ("1:59 late", "1:25", "+119"),
    ]


def test_cr035_a_reason_goes_to_stderr_and_the_log_and_the_build_succeeds(tmp_path, config):
    need(ALCYONE)
    out = tmp_path / "game" / "graph.json"
    code, _stdout, stderr = run(
        "build", ALCYONE, "--out", out, "--config-root", config, "--guide", "1=pvz-stargate-opener-project"
    )
    line = (
        'No build check: the build order guide "Gate, Nexus, Core into Stargate (PvZ)" is for Protoss vs Zerg, '
        "and lilTiGGer played Zerg vs Protoss."
    )
    assert (code, stderr) == (0, f"sc2mindshare: build check: {line}\n")
    assert f"build check: player 1: {line}" in (out.parent / "graph.log").read_text(encoding="utf-8")


@pytest.mark.parametrize("guide", ["Nobody=zvp-12-pool-economic-liquipedia", "3=zvp-12-pool-economic-liquipedia"])
def test_s26_an_unknown_player_is_a_usage_error(tmp_path, config, guide):
    need(ALCYONE)
    out = tmp_path / "game" / "graph.json"
    code, _stdout, stderr = run("build", ALCYONE, "--out", out, "--config-root", config, "--guide", guide)
    assert code == 2 and "no player" in stderr and not out.parent.exists()  # nothing written, graph.log included (finding 9)


@pytest.mark.parametrize("guide", ["lilTiGGer", "=zvp-12-pool-economic-liquipedia", "lilTiGGer="])
def test_a_malformed_guide_option_is_a_usage_error(tmp_path, config, guide):
    need(ALCYONE)
    code, _stdout, stderr = run("build", ALCYONE, "--out", tmp_path / "g.json", "--config-root", config, "--guide", guide)
    assert code == 2 and "PLAYER=GUIDE" in stderr


def test_s26_a_fault_in_the_comparison_fails_the_build_with_exit_1(tmp_path, config, monkeypatch):
    need(ALCYONE)
    import sc2mindshare.analysis.build_check as bc

    def broken(*args, **kwargs):
        raise RuntimeError("injected comparison fault")

    monkeypatch.setattr(bc, "compare", broken)
    out = tmp_path / "game" / "graph.json"
    code, _stdout, stderr = run("build", ALCYONE, "--out", out, "--config-root", config)
    assert code == 1 and "injected comparison fault" in stderr and "unreadable" not in stderr and not out.exists()
