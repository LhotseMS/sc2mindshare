"""CR-069 AC-1: ``scripts/one_clock_check.py``, the one-picture check, against the fake server (never the network).

A dry run asks for the upload status once and uploads nothing; ``--live`` uploads the one clock, reads it back,
compares the decoded pictures (size and pixels, D51a: the server re-encodes what it stores) and writes a one-node
import file whose node points at the picture by its ID; ``--picture-id`` does the same for a picture already
uploaded, with no upload.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "one_clock_check.py"


def _png(pixels: bytes = bytes(range(128)), size=(8, 4), **save) -> bytes:
    """A small RGBA PNG; the same pixels saved with other options give other bytes."""
    out = io.BytesIO()
    Image.frombytes("RGBA", size, pixels).save(out, "PNG", **save)
    return out.getvalue()


PNG = _png()
#: what the local Mindshare serves back: the same picture re-encoded (it adds pHYs and recompresses, D51a)
REENCODED = _png(dpi=(72, 72), compress_level=1)


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
        "uploaded": True,
        "sha256_file": hashlib.sha256(PNG).hexdigest(),
        "sha256_served": hashlib.sha256(PNG).hexdigest(),
        "picture": "identical: 8x4 RGBA, same pixels",
        "out": str(out_file),
        "sha256_out": hashlib.sha256(out_file.read_bytes()).hexdigest(),
    }


def test_a_re_encoded_picture_with_the_same_pixels_passes(fake_media, config_root, tmp_path, capsys):
    """D51a: the server re-encodes the PNG it stores, so the read-back compares size and pixels, not bytes."""
    assert REENCODED != PNG
    fake_media.served_bytes = REENCODED
    out_file = tmp_path / "one-clock.json"
    code, out, _ = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", out_file, "--live")
    assert code == 0
    assert fake_media.posts()[0].parts()[0] == ("file", "0-10.png", PNG)  # the file's own bytes are what is sent
    report = json.loads(out.strip().splitlines()[-1])
    assert report["sha256_file"] == hashlib.sha256(PNG).hexdigest()
    assert report["sha256_served"] == hashlib.sha256(REENCODED).hexdigest()  # audit only
    assert report["picture"] == "identical: 8x4 RGBA, same pixels"
    assert out_file.exists()


@pytest.mark.parametrize(
    ("served", "why"),
    [
        (_png(bytes([255]) + bytes(range(1, 128))), "pixels differ"),  # the first pixel's red only
        (_png(bytes(range(128)) * 2, size=(8, 8)), "size differs"),
        (b"<html>not a picture</html>", "not a picture"),
    ],
    ids=["one-pixel", "size", "not-a-picture"],
)
def test_live_stops_when_the_picture_read_back_differs(fake_media, config_root, tmp_path, capsys, served, why):
    fake_media.served_bytes = served
    out_file = tmp_path / "one-clock.json"
    code, _, err = _run(capsys, "--config-root", config_root, "--server", fake_media.url, "--out", out_file, "--live")
    assert code == 4
    assert why in err
    assert not out_file.exists()


def test_a_picture_already_uploaded_is_read_back_without_an_upload(fake_media, config_root, tmp_path, capsys):
    """D51a: the one-node file for the picture uploaded on 2026-10-21, with no second upload."""
    fake_media.stored["8d4e894d-f6b7-41a6-80df-b999b322349c"] = REENCODED
    out_file = tmp_path / "qa" / "one-clock.json"
    code, out, _ = _run(
        capsys, "--config-root", config_root, "--server", fake_media.url, "--out", out_file,
        "--picture-id", "8d4e894d-f6b7-41a6-80df-b999b322349c",
    )  # fmt: skip
    assert code == 0
    assert fake_media.posts() == []
    assert [(r.method, r.path) for r in fake_media.requests] == [
        ("GET", "/media/health"),
        ("GET", "/media/resource/8d4e894d-f6b7-41a6-80df-b999b322349c"),
    ]
    [node] = json.loads(out_file.read_text(encoding="utf-8"))["nodes"]
    assert node["nodeImage"] == "8d4e894d-f6b7-41a6-80df-b999b322349c"
    report = json.loads(out.strip().splitlines()[-1])
    assert (report["uploaded"], report["status"]) == (False, None)
    assert report["sha256_served"] == hashlib.sha256(REENCODED).hexdigest()


def test_a_picture_id_and_live_together_are_a_usage_error(fake_media, config_root, tmp_path, capsys):
    code, _, err = _run(
        capsys, "--config-root", config_root, "--server", fake_media.url, "--out", tmp_path / "x.json",
        "--live", "--picture-id", "8d4e894d-f6b7-41a6-80df-b999b322349c",
    )  # fmt: skip
    assert code == 2
    assert "--picture-id" in err and "--live" in err
    assert fake_media.requests == []


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
