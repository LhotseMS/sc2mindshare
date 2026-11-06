"""CR-069: ``sc2mindshare upload-clocks REPLAY [REPLAY ...]`` on real replays, against the fake server.

The clocks a replay needs come from the real pipeline (analysis, graph, layout). The expected set is derived
independently from the Alcyone golden (QA check 4011): the distinct clocks of its image nodes, 70 since CR-023
P10b (the story's 68 predate it).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import shutil

import pytest

from sc2mindshare import cli
from sc2mindshare.media.clocks import RECORD_FILE, read_record

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
GOLDEN = CHECKOUT / "tests" / "golden"


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


def _alcyone_clocks() -> list[str]:
    """The distinct clocks of the golden's image nodes, in order: by file name (the new form) or, for the old
    form, through TimeImageTracking.csv (media id -> file name)."""
    doc = json.loads((GOLDEN / "alcyone" / "G-SNAP-current-compressed.json").read_text(encoding="utf-8"))
    by_media = {}
    tracking = MS_SC / "TimeImageTracking.csv"
    if tracking.exists():
        for line in tracking.read_text(encoding="utf-8").splitlines()[1:]:
            name, media = line.split(",")
            by_media[media] = name
    names: list[str] = []
    for n in doc["nodes"]:
        if n["type"] == "image":
            name = n["name"] if n["name"].endswith(".png") else by_media[n["name"][-24:]]
            if name not in names:
                names.append(name)
    return names


@pytest.fixture(scope="module")
def alcyone_clocks():
    need(ALCYONE)
    names = _alcyone_clocks()
    assert len(names) == 70
    return names


@pytest.fixture
def config_root(tmp_path):
    """A config root with the real support tables and clock pictures, and no record."""
    need(ALCYONE)
    root = tmp_path / "MS SC"
    root.mkdir()
    for name in ("unitsInfo.csv", "upgradesInfo.csv"):
        shutil.copyfile(MS_SC / name, root / name)
    (root / "ClockImages").symlink_to(MS_SC / "ClockImages")
    return root


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


def test_ac2_a_dry_run_lists_the_clocks_alcyone_needs(fake_media, config_root, alcyone_clocks):
    code, out, err = run("upload-clocks", ALCYONE, "--config-root", config_root, "--server", fake_media.url)
    assert (code, err) == (0, "")
    assert [(r.method, r.path) for r in fake_media.requests] == [("GET", "/media/health")]
    assert f"{len(alcyone_clocks)} to upload" in out
    listed = [line.strip() for line in out.splitlines() if line.strip().endswith(".png")]
    assert listed == alcyone_clocks
    assert not (config_root / RECORD_FILE).exists()


def test_ac3_ac4_a_confirmed_run_uploads_each_clock_once_then_nothing(fake_media, config_root, alcyone_clocks):
    live = ("--server", fake_media.url, "--live", "--pace", "0")  # no pacing against the fake
    code, out, err = run("upload-clocks", ALCYONE, "--config-root", config_root, *live)
    assert (code, err) == (0, "")
    assert [p.parts()[0][1] for p in fake_media.posts()] == alcyone_clocks
    assert [r.image_name for r in read_record(config_root / RECORD_FILE)] == alcyone_clocks
    assert f"uploaded {len(alcyone_clocks)}" in out
    fake_media.requests.clear()
    code, out, _ = run("upload-clocks", ALCYONE, "--config-root", config_root, *live)
    assert code == 0 and fake_media.posts() == [] and "nothing to upload" in out


def test_ac4_a_second_replay_uploads_only_what_it_adds(fake_media, config_root, alcyone_clocks):
    """Spine after Alcyone: needed(spine) minus needed(Alcyone), which may be empty (a valid no-op)."""
    need(SPINE)
    live = ("--server", fake_media.url, "--live", "--pace", "0")
    assert run("upload-clocks", ALCYONE, "--config-root", config_root, *live)[0] == 0
    fake_media.requests.clear()
    _, dry, _ = run("upload-clocks", SPINE, "--config-root", config_root, "--server", fake_media.url)
    spine_missing = [line.strip() for line in dry.splitlines() if line.strip().endswith(".png")]
    assert not set(spine_missing) & set(alcyone_clocks)
    fake_media.requests.clear()
    code, _, _ = run("upload-clocks", SPINE, "--config-root", config_root, *live)
    assert code == 0
    assert [p.parts()[0][1] for p in fake_media.posts()] == spine_missing


def test_two_replays_share_one_run(fake_media, config_root, alcyone_clocks):
    need(SPINE)
    code, out, _ = run("upload-clocks", ALCYONE, SPINE, "--config-root", config_root, "--server", fake_media.url)
    assert code == 0
    listed = [line.strip() for line in out.splitlines() if line.strip().endswith(".png")]
    assert listed[: len(alcyone_clocks)] == alcyone_clocks and len(listed) == len(set(listed))


@pytest.mark.parametrize("url", ["http://example.com:3042", "http://192.168.1.10:3042", "http://localhost@example.com:3042"])
def test_ac6_a_non_local_server_is_refused_before_anything(config_root, url):
    code, _, err = run("upload-clocks", ALCYONE, "--config-root", config_root, "--server", url)
    assert code == 2 and "local Mindshare only" in err


def test_the_exit_codes_and_flags_are_in_the_help():
    parser = cli._parser()
    sub = next(a for a in parser._subparsers._group_actions if a.dest == "command").choices["upload-clocks"]
    text = sub.format_help()
    for flag in ("--config-root", "--server", "--live", "--max", "--pace"):
        assert flag in text
    flat = " ".join(text.split())
    assert "dry run" in flat
    for code in ("0 done", "1 the analysis of a replay failed", "2 a usage error", "3 stopped cleanly", "4 refused"):
        assert code in flat, code  # Rex's N0: every exit code, 1 included


def test_a_missing_clock_picture_is_a_usage_error_before_any_request(fake_media, tmp_path, alcyone_clocks):
    root = tmp_path / "bare"
    root.mkdir()
    for name in ("unitsInfo.csv", "upgradesInfo.csv"):
        shutil.copyfile(MS_SC / name, root / name)
    (root / "ClockImages").mkdir()
    code, _, err = run("upload-clocks", ALCYONE, "--config-root", root, "--server", fake_media.url)
    assert code == 2 and alcyone_clocks[0] in err
    assert fake_media.requests == []
