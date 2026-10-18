"""Tests for scripts/run_legacy.py (staging and the offline guard; the legacy run itself is T03's smoke)."""

import importlib.util
import pathlib
import subprocess
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "run_legacy.py"
_spec = importlib.util.spec_from_file_location("run_legacy", _PATH)
assert _spec and _spec.loader
run_legacy = importlib.util.module_from_spec(_spec)
sys.modules["run_legacy"] = run_legacy
_spec.loader.exec_module(run_legacy)


@pytest.fixture
def support(tmp_path):
    folder = tmp_path / "support"
    folder.mkdir()
    for name in run_legacy.SUPPORT_FILES:
        (folder / name).write_text(f"{name}\n")
    game = folder / "Some Map__a_vs_b"
    game.mkdir()
    (game / "Intervals.csv").write_text("start,end,id\n")  # must never be staged
    return folder


def test_stage_copies_support_files_and_the_replay_but_no_game_folder(tmp_path, support):
    replay = tmp_path / "game.SC2Replay"
    replay.write_bytes(b"MPQ")
    root = run_legacy.stage(replay, support, tmp_path / "work")
    assert root == tmp_path / "work" / "MS SC"
    assert sorted(p.name for p in root.iterdir()) == sorted([*run_legacy.SUPPORT_FILES, "Replays"])
    assert (root / "Replays" / "game.SC2Replay").read_bytes() == b"MPQ"
    assert not list(root.rglob("Intervals.csv"))


def test_stage_starts_from_an_empty_root_each_time(tmp_path, support):
    replay = tmp_path / "game.SC2Replay"
    replay.write_bytes(b"MPQ")
    root = run_legacy.stage(replay, support, tmp_path / "work")
    (root / "Some Map__a_vs_b").mkdir()
    (root / "Some Map__a_vs_b" / "Intervals.csv").write_text("left over from a previous run\n")
    root = run_legacy.stage(replay, support, tmp_path / "work")
    assert not list(root.rglob("Intervals.csv"))


def test_stage_fails_on_a_missing_support_file(tmp_path, support):
    (support / "unitsInfo.csv").unlink()
    replay = tmp_path / "game.SC2Replay"
    replay.write_bytes(b"MPQ")
    with pytest.raises(FileNotFoundError, match="unitsInfo.csv"):
        run_legacy.stage(replay, support, tmp_path / "work")


GUARD_PROBE = """
import importlib.util, socket, sys
spec = importlib.util.spec_from_file_location("run_legacy", sys.argv[1])
mod = importlib.util.module_from_spec(spec); sys.modules["run_legacy"] = mod; spec.loader.exec_module(mod)
mod.block_network()
results = []
def attempt(name, fn):
    try:
        fn(); results.append(name + "=open")
    except mod.NetworkBlockedError:
        results.append(name + "=blocked")
attempt("create_connection", lambda: socket.create_connection(("127.0.0.1", 9), timeout=1))
attempt("getaddrinfo", lambda: socket.getaddrinfo("example.com", 443))
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
attempt("sendto", lambda: s.sendto(b"x", ("127.0.0.1", 9)))
attempt("sendmsg", lambda: s.sendmsg([b"x"], [], 0, ("127.0.0.1", 9)))
attempt("connect_ex", lambda: socket.socket().connect_ex(("127.0.0.1", 9)))
print(" ".join(results))
"""


def test_block_network_refuses_connections_datagrams_and_lookups():
    # The audit hook cannot be removed, so the probe runs in its own interpreter.
    out = subprocess.run(
        [sys.executable, "-c", GUARD_PROBE, str(_PATH)], capture_output=True, text=True, check=True
    ).stdout.split()
    assert out == [
        "create_connection=blocked",
        "getaddrinfo=blocked",
        "sendto=blocked",
        "sendmsg=blocked",
        "connect_ex=blocked",
    ]


def test_child_writes_the_traceback_to_the_log_and_returns_1(tmp_path, monkeypatch):
    fake = tmp_path / "execs"
    fake.mkdir()
    (fake / "mindShareReplay.py").write_text("def parseReplay(name, load_map=True):\n    raise KeyError(118489090)\n")
    probe = (
        "import importlib.util, sys; sys.path.insert(0, sys.argv[2]);"
        "spec = importlib.util.spec_from_file_location('run_legacy', sys.argv[1]);"
        "mod = importlib.util.module_from_spec(spec); sys.modules['run_legacy'] = mod; spec.loader.exec_module(mod);"
        "sys.exit(mod.child('x.SC2Replay', __import__('pathlib').Path(sys.argv[3])))"
    )
    log = tmp_path / "run.log"
    code = subprocess.run([sys.executable, "-c", probe, str(_PATH), str(tmp_path), str(log)], check=False).returncode
    assert code == 1
    text = log.read_text()
    assert "Traceback (most recent call last)" in text
    assert "KeyError: 118489090" in text


def test_find_outputs_returns_the_single_events_csv_and_intervals(tmp_path):
    game = tmp_path / "Map__a_vs_b"
    game.mkdir()
    (game / "events_Map__a_vs_b.csv").write_text("x\n")
    (game / "Intervals.csv").write_text("start,end,id\n")
    assert run_legacy.find_outputs(tmp_path) == (game / "events_Map__a_vs_b.csv", game / "Intervals.csv")


def test_find_outputs_fails_when_the_csv_is_missing(tmp_path):
    with pytest.raises(RuntimeError, match="expected one events CSV"):
        run_legacy.find_outputs(tmp_path)


def test_count_creep_errors():
    line = "Whoa! 'CreepTracker' object has no attribute 'creepTracker'\n"
    assert run_legacy.count_creep_errors("noise\n" + line * 3) == 3
