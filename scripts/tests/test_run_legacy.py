"""Tests for scripts/run_legacy.py (staging and the offline guard; the legacy run itself is T03's smoke)."""

import importlib.util
import pathlib
import socket
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


def test_block_network_refuses_connections(monkeypatch):
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", socket.getaddrinfo)
    run_legacy.block_network()
    with pytest.raises(run_legacy.NetworkBlockedError):
        socket.create_connection(("example.com", 443))
    with pytest.raises(run_legacy.NetworkBlockedError):
        socket.getaddrinfo("example.com", 443)
    s = socket.socket()
    try:
        with pytest.raises(run_legacy.NetworkBlockedError):
            s.connect(("127.0.0.1", 9))
    finally:
        s.close()


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
