"""CR-069 AC-1: ``scripts/one_clock_check.py``, the one-picture check, against the fake server (never the network).

A dry run asks for the upload status once and uploads nothing; ``--live`` uploads the one clock, reads it back,
compares the bytes and writes a one-node import file whose node points at the picture by its ID.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "one_clock_check.py"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 2


def _script():
    spec = importlib.util.spec_from_file_location("one_clock_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["one_clock_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def config_root(tmp_path):
    root = tmp_path / "MS SC"
    (root / "ClockImages").mkdir(parents=True)
    (root / "ClockImages" / "0-10.png").write_bytes(PNG)
    return root


def _run(capsys, *args):
    code = _script().main([str(a) for a in args])
    out, err = capsys.readouterr()
    return code, out, err


def test_the_dry_run_asks_for_the_status_once_and_uploads_nothing(fake_media, config_root, tmp_path, capsys):
    out_file = tmp_path / "qa" / "one-clock.json"
    code, out, _ = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", out_file)
    assert code == 0
    assert [(r.method, r.path) for r in fake_media.requests] == [("GET", "/media/health")]
    assert "uploads: open" in out
    assert "dry run" in out and "0-10.png" in out and hashlib.sha256(PNG).hexdigest() in out
    assert "--live" in out
    assert not out_file.exists() and not out_file.parent.exists()


def test_the_dry_run_shows_a_paused_server(fake_media, config_root, tmp_path, capsys):
    fake_media.health_body = b'{"uploads": "paused"}'
    code, out, _ = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", tmp_path / "x.json")
    assert code == 0
    assert "uploads: paused" in out
    assert fake_media.posts() == []


def test_live_uploads_one_clock_reads_it_back_and_writes_the_one_node_file(fake_media, config_root, tmp_path, capsys):
    out_file = tmp_path / "qa" / "one-clock.json"
    code, out, _ = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", out_file, "--live")
    assert code == 0
    [post] = fake_media.posts()
    assert post.parts()[0] == ("file", "0-10.png", PNG)
    [picture_id] = fake_media.stored
    doc = json.loads(out_file.read_text(encoding="utf-8"))
    assert list(doc) == ["visuals", "detail", "dataTypes", "nodes", "links"]
    assert doc["links"] == []
    assert doc["nodes"] == [
        {
            "type": "image",
            "name": "0-10.png",
            "ID": "clock-0-10-1",
            "nodeImage": picture_id,
            "size": [1.1, 0.75],
            "properties": {},
            "position": {"x": 0, "y": 0, "z": 0.01},
        }
    ]
    report = json.loads(out.strip().splitlines()[-1])
    assert report == {
        "server": "localhost:" + fake_media.url.rsplit(":", 1)[1],
        "clock": "0-10.png",
        "pictureID": picture_id,
        "status": 201,
        "sha256_file": hashlib.sha256(PNG).hexdigest(),
        "sha256_served": hashlib.sha256(PNG).hexdigest(),
        "out": str(out_file),
        "sha256_out": hashlib.sha256(out_file.read_bytes()).hexdigest(),
    }


def test_live_stops_when_the_bytes_read_back_differ(fake_media, config_root, tmp_path, capsys):
    fake_media.served_bytes = PNG + b"x"
    out_file = tmp_path / "one-clock.json"
    code, _, err = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", out_file, "--live")
    assert code == 4
    assert "differ" in err
    assert not out_file.exists()


def test_live_uploads_nothing_when_uploads_are_paused(fake_media, config_root, tmp_path, capsys):
    fake_media.health_body = b'{"uploads": "paused"}'
    code, _, err = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", tmp_path / "x.json", "--live")
    assert code == 4
    assert "paused" in err
    assert fake_media.posts() == []


def test_a_refused_upload_stops_with_one_message(fake_media, config_root, tmp_path, capsys):
    fake_media.upload_status, fake_media.upload_headers = 429, {"Retry-After": "60"}
    code, _, err = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", tmp_path / "x.json", "--live")
    assert code == 4
    assert len(err.strip().splitlines()) == 1
    assert "429" in err and "60" in err
    assert "Traceback" not in err


def test_a_non_local_server_is_refused_before_any_connection(config_root, tmp_path, capsys):
    code, _, err = _run(
        capsys, "--config-root", config_root, "--server", "http://example.com:3042", "--out", tmp_path / "x.json"
    )
    assert code == 2
    assert "local Mindshare only" in err


def test_a_missing_clock_file_is_a_usage_error(fake_media, config_root, tmp_path, capsys):
    code, _, err = _run(
        capsys, "--config-root", config_root, "--server", fake_media.url, "--out", tmp_path / "x.json", "--clock", "0-20.png"
    )
    assert code == 2
    assert "0-20.png" in err
    assert fake_media.requests == []
