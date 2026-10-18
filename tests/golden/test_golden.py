"""Golden tests (CR-007, T07) and the harness's own mutation checks.

- G-CSV-1: the legacy code (with data pack 89720, CR-008) on Alcyone; reproduced
  by a fresh legacy run when this checkout's .venv-legacy and MS SC/ exist.
- G-VIEW-1: the VBA view port (CR-006) on G-CSV-1, raw-newline rows rejoined.
Changing a golden on purpose: scripts/regen_golden.py, then an entry in CHANGES.md.
"""

import copy
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE.parents[1]
ALCYONE = HERE / "alcyone"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


golden = _load("golden", HERE / "golden.py")
vba_view = _load("vba_view", CHECKOUT / "tests" / "reference" / "vba_view" / "vba_view.py")


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("MS_SC_ROOT_SOURCE", _root() / "MS SC"))
REPLAY = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"


@pytest.fixture(scope="module")
def csv_golden():
    return (ALCYONE / "G-CSV-1.csv").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def view_golden():
    return json.loads((ALCYONE / "G-VIEW-1.json").read_text(encoding="utf-8"))


def _config(name):
    return json.loads((CHECKOUT / "src" / "sc2mindshare" / "config" / name).read_text(encoding="utf-8"))


# --- the goldens -------------------------------------------------------------------


def test_view_golden_is_the_vba_view_of_the_csv_golden(csv_golden, view_golden):
    view = vba_view.build_view(
        csv_golden,
        _config("visuals.json"),
        _config("details.json"),
        _config("data_types.json"),
        rejoin_raw_newlines=True,
    )
    assert golden.diff_json(view_golden, view) == []


@pytest.mark.skipif(not LEGACY_PY.exists(), reason="no .venv-legacy in this checkout (scripts/legacy-env)")
@pytest.mark.skipif(not REPLAY.exists(), reason=f"replay not found: {REPLAY}")
def test_csv_golden_is_what_the_legacy_code_writes_now(tmp_path, csv_golden):
    subprocess.run(
        [
            str(LEGACY_PY),
            str(CHECKOUT / "scripts" / "run_legacy.py"),
            "--support",
            str(MS_SC),
            "--out",
            str(tmp_path),
            str(REPLAY),
        ],
        check=True,
        capture_output=True,
    )
    fresh = (tmp_path / REPLAY.stem / "events.csv").read_text(encoding="utf-8")
    assert golden.diff_csv(csv_golden, fresh) == []
    assert (tmp_path / REPLAY.stem / "Intervals.csv").read_text() == (ALCYONE / "Intervals-1.csv").read_text()


def test_golden_counts(csv_golden, view_golden):
    assert len(golden.csv_records(csv_golden)) == 1077  # 1083 physical lines, 6 split by raw newlines
    assert (len(view_golden["nodes"]), len(view_golden["links"])) == (665, 412)


# --- mutation checks: the comparison catches what matters and ignores what it should ---------


def _replace_field(row, index, value):
    fields = row.split(";")
    fields[index] = value
    return ";".join(fields)


def test_csv_compare_fails_on_any_non_image_field(csv_golden):
    rows = csv_golden.splitlines()
    battle = next(i for i, r in enumerate(rows) if ";Battle;Battle-1;" in r)
    for index in (0, 1, 5, 7, 11):
        mutated = rows.copy()
        mutated[battle] = _replace_field(rows[battle], index, "MUTATED")
        assert golden.diff_csv(csv_golden, "\n".join(mutated)), index


def test_csv_compare_fails_on_reordered_rows(csv_golden):
    rows = csv_golden.splitlines()
    rows[3], rows[4] = rows[4], rows[3]
    assert golden.diff_csv(csv_golden, "\n".join(rows))


def test_csv_compare_ignores_image_urls(csv_golden):
    rows = csv_golden.splitlines()
    game = next(i for i, r in enumerate(rows) if ";Game;Game-1;" in r)
    rows[game] = _replace_field(rows[game], 4, "https://other.host/media/resource/123")
    assert golden.diff_csv(csv_golden, "\n".join(rows)) == []


def test_json_compare_fails_on_a_property_size_order_or_link(view_golden):
    for mutate in (
        lambda d: d["nodes"][5]["properties"].__setitem__("player", "someone"),
        lambda d: d["nodes"][5].__setitem__("size", 9.9),
        lambda d: d["nodes"].insert(0, d["nodes"].pop(1)),
        lambda d: d["links"][0].__setitem__("direction", 2),
        lambda d: d["detail"].pop(),
    ):
        doc = copy.deepcopy(view_golden)
        mutate(doc)
        assert golden.diff_json(view_golden, doc)


def test_json_compare_ignores_images_image_node_urls_rounding_and_negative_zero(view_golden):
    doc = copy.deepcopy(view_golden)
    doc["nodes"][0]["images"] = ["https://other.host/x"]
    doc["nodes"].append({"type": "image", "name": "https://a/1", "ID": "11", "size": [1.1, 0.75], "position": {"x": -0.0}})
    ref = copy.deepcopy(view_golden)
    ref["nodes"].append({"type": "image", "name": "https://b/2", "ID": "22", "size": [1.1, 0.75], "position": {"x": 0.0}})
    battle = next(n for n in doc["nodes"] if n["type"] == "Battle")
    battle["size"] = battle["size"] + 0.00001
    assert golden.diff_json(ref, doc) == []


def test_supply_block_size_is_masked_only_on_request(view_golden):
    doc = copy.deepcopy(view_golden)
    sb = next(n for n in doc["nodes"] if n["type"] == "Supply Block")
    sb["size"] = [7.5, 1]
    assert golden.diff_json(view_golden, doc)
    assert golden.diff_json(view_golden, doc, mask_supply_block_size=True) == []
