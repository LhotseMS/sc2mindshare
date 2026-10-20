"""Golden tests and the harness's own tests (CR-007, T07), to Vera's design (`qa-golden-design.md`).

Goldens (frozen, `FROZEN.sha256`): G-CSV-1 (+ Intervals-1) from the legacy code, and G-VIEW-1
from the VBA view port on G-CSV-1. Inputs pinned in `INPUTS.sha256`. Missing inputs skip with a
reason, or fail under `SC2MS_REQUIRE_GOLDEN=1` (set by `scripts/gates`). H1-H22 are the harness
tests of the design's §2.
"""

import copy
import importlib.util
import itertools
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


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
REPLAY = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"
CONFIG = CHECKOUT / "src" / "sc2mindshare" / "config"


def need(path, what):
    """Skip with a reason when an input is absent; fail instead under SC2MS_REQUIRE_GOLDEN=1."""
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(f"{exc} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(str(exc))


@pytest.fixture(scope="module")
def csv_golden():
    return (ALCYONE / "G-CSV-1.csv").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def view_golden():
    return json.loads((ALCYONE / "G-VIEW-1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def clock_map():
    return golden.load_clock_map(need(MS_SC / "TimeImageTracking.csv", "TimeImageTracking.csv"))


def _config(name):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


def _inputs():
    return {
        "replay": need(REPLAY, "Alcyone replay"),
        "unitsInfo.csv": need(MS_SC / "unitsInfo.csv", "unitsInfo.csv"),
        "upgradesInfo.csv": need(MS_SC / "upgradesInfo.csv", "upgradesInfo.csv"),
        "TimeImageTracking.csv": need(MS_SC / "TimeImageTracking.csv", "TimeImageTracking.csv"),
        "config/visuals.json": CONFIG / "visuals.json",
        "config/details.json": CONFIG / "details.json",
        "config/data_types.json": CONFIG / "data_types.json",
    }


def _run_legacy(out, seed=None):
    env = dict(os.environ)
    if seed is not None:
        env["PYTHONHASHSEED"] = seed
    cmd = [str(LEGACY_PY), str(CHECKOUT / "scripts" / "run_legacy.py"), "--support", str(MS_SC), "--out", str(out), str(REPLAY)]
    subprocess.run(cmd, check=True, capture_output=True, env=env)
    return (out / REPLAY.stem / "events.csv").read_text(encoding="utf-8")


# --- the goldens ----------------------------------------------------------------------


def test_frozen_goldens_are_unchanged():
    pins = golden.read_pins(ALCYONE / "FROZEN.sha256")
    assert set(pins) == {"G-CSV-1.csv", "Intervals-1.csv", "G-VIEW-1.json"}
    for name, digest in pins.items():
        assert golden.sha256(ALCYONE / name) == digest, f"frozen golden changed: {name} (stop and report)"


def test_inputs_are_the_pinned_ones():
    golden.check_pins(ALCYONE / "INPUTS.sha256", _inputs())


def test_view_golden_is_the_vba_view_of_the_csv_golden(csv_golden, view_golden):
    view = vba_view.build_view(
        csv_golden, _config("visuals.json"), _config("details.json"), _config("data_types.json"), rejoin_raw_newlines=True
    )
    report = golden.diff_json(view_golden, view)
    assert report.ok, str(report)


def test_view_golden_holds_the_view_size_of_every_supply_block(view_golden):
    blocks = [n for n in view_golden["nodes"] if n["type"] == "Supply Block"]
    assert len(blocks) == 11
    assert all(n["size"] == [2.65, 1] for n in blocks)  # TD-21, Leo's condition 1


def test_csv_golden_is_what_the_legacy_code_writes_now(tmp_path, csv_golden):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    golden.check_pins(ALCYONE / "INPUTS.sha256", _inputs())
    report = golden.diff_csv(csv_golden, _run_legacy(tmp_path))
    assert report.ok, str(report)
    assert report.budget_actual == {"M1": 1}
    assert (tmp_path / REPLAY.stem / "Intervals.csv").read_text() == (ALCYONE / "Intervals-1.csv").read_text()


def test_h22_legacy_output_is_hash_seed_stable(tmp_path):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    need(REPLAY, "Alcyone replay")
    outputs = {seed: _run_legacy(tmp_path / f"seed-{seed}", seed) for seed in ("0", "1", "random")}
    assert len(set(outputs.values())) == 1


_LEGACY_DATAPACK = """
import sys
import sc2reader
replay = sc2reader.load_replay(sys.argv[1], load_level=2, load_map=False)
print(sc2reader.__file__)
print(replay.build, replay.expansion, replay.datapack.id)
"""


def test_legacy_alcyone_uses_data_pack_89720():
    """CR-008 (D0): G-CSV-1 is byte-identical under 80949 and 89720, so the golden cannot pin the
    registration; this does. Alcyone is build 92440, so 89720 applies (89634 <= build)."""
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    need(REPLAY, "Alcyone replay")
    out = subprocess.run(
        [str(LEGACY_PY), "-c", _LEGACY_DATAPACK, str(REPLAY)], check=True, capture_output=True, text=True
    ).stdout.splitlines()
    assert pathlib.Path(out[0]).is_relative_to(CHECKOUT / "legacy")  # the fork tree, not upstream 1.9.0
    assert out[1] == "92440 LotV 89720"


def test_golden_counts(csv_golden, view_golden):
    assert len(csv_golden.split("\n")) == 1084  # 1083 lines and the final newline
    assert (len(view_golden["nodes"]), len(view_golden["links"])) == (665, 412)


# --- H1-H21: the harness itself ---------------------------------------------------------


def _lines(text):
    return text.split("\n")


def _set_field(line, index, value):
    f = line.split(";")
    f[index] = value
    return ";".join(f)


def _index(lines, needle):
    return next(i for i, line in enumerate(lines) if needle in line)


def _csv_mutate(csv_golden, needle, index, value):
    lines = _lines(csv_golden)
    i = _index(lines, needle)
    lines[i] = _set_field(lines[i], index, value)
    return "\n".join(lines)


def test_h1_text_is_compared_and_named(csv_golden):
    lines = _lines(csv_golden)
    i = _index(lines, ";Building;Building-")
    nid = lines[i].split(";")[3]
    lines[i] = "X" + lines[i]
    report = golden.diff_csv(csv_golden, "\n".join(lines))
    assert not report.ok and f"{nid}#1" in str(report) and "fields 0" in str(report)


def test_h2_a_time_field(csv_golden):
    assert not golden.diff_csv(csv_golden, _csv_mutate(csv_golden, ";Battle;Battle-1;", 11, "0:02:03")).ok


def test_h3_m1_hides_the_url_value(csv_golden):
    other = "https://media.api.mindshareapp.com/media/resource/0123456789abcdef01234567"
    assert golden.diff_csv(csv_golden, _csv_mutate(csv_golden, ";Game;Game-1;", 4, other)).ok


def test_h4_m1_keeps_the_url_count(csv_golden):
    report = golden.diff_csv(csv_golden, _csv_mutate(csv_golden, ";Game;Game-1;", 4, ""))
    assert not report.ok and "mask budget" in str(report)


def test_h5_reordered_lines_are_reported_as_order(csv_golden):
    lines = _lines(csv_golden)
    abilities = [i for i, line in enumerate(lines) if ";Ability;Ability-" in line]
    i = next(a for a, b in itertools.pairwise(abilities) if b == a + 1 and lines[a].split(";")[5] == lines[b].split(";")[5])
    lines[i], lines[i + 1] = lines[i + 1], lines[i]
    report = golden.diff_csv(csv_golden, "\n".join(lines))
    assert not report.ok and "order differs" in str(report)


def _first(view, typ):
    return next(n for n in view["nodes"] if n["type"] == typ)


def _json_mutated(view_golden, mutate):
    doc = copy.deepcopy(view_golden)
    mutate(doc)
    return doc


def test_h6_four_decimal_boundary(view_golden):
    a = _json_mutated(view_golden, lambda d: _first(d, "Building").__setitem__("size", [2.6501, 1]))
    b = _json_mutated(view_golden, lambda d: _first(d, "Building").__setitem__("size", [2.65004, 1]))
    assert not golden.diff_json(view_golden, a).ok
    assert golden.diff_json(view_golden, b).ok


def test_h7_negative_zero_and_h8_int_against_float():
    assert golden.diff_json({"nodes": [{"ID": "a", "x": -0.0, "y": 2}]}, {"nodes": [{"ID": "a", "x": 0.0, "y": 2.0}]}).ok


def test_h9_bool_is_not_a_number():
    assert not golden.diff_json(
        {"nodes": [{"ID": "Ability-1", "combat": True}]}, {"nodes": [{"ID": "Ability-1", "combat": 1}]}
    ).ok


def test_h10_key_order_is_ignored(view_golden):
    shuffled = _json_mutated(view_golden, lambda d: d["nodes"].__setitem__(5, dict(reversed(list(d["nodes"][5].items())))))
    assert golden.diff_json(view_golden, shuffled).ok


def test_h11_extra_missing_and_null_are_differences(view_golden):
    for mutate in (
        lambda d: d["nodes"][5].__setitem__("foo", None),
        lambda d: d["nodes"][5].pop("properties"),
        lambda d: d["nodes"][5].__setitem__("description", None),
    ):
        assert not golden.diff_json(view_golden, _json_mutated(view_golden, mutate)).ok


def test_h12_m3_is_exactly_as_wide_as_agreed(view_golden):
    sb = _json_mutated(view_golden, lambda d: _first(d, "Supply Block").__setitem__("size", [7.5, 1]))
    building = _json_mutated(view_golden, lambda d: _first(d, "Building").__setitem__("size", [7.5, 1]))
    assert golden.diff_json(view_golden, sb, view=True).ok
    assert not golden.diff_json(view_golden, building, view=True).ok
    assert not golden.diff_json(view_golden, sb).ok  # layout comparison: no M3


def _with_clock(view, media_id, suffix, host="https://media.api.mindshare.touch4dev.net/media/resource/"):
    doc = copy.deepcopy(view)
    doc["nodes"].append(
        {"type": "image", "name": host + media_id, "ID": media_id + suffix, "size": [1.1, 0.75], "properties": {}}
    )
    return doc


def test_h13_m2_keeps_the_clock_meaning(view_golden, clock_map):
    by_name = {name: mid for mid, name in clock_map.items()}
    ref = _with_clock(view_golden, by_name["0-10.png"], "1")
    assert golden.diff_json(ref, _with_clock(view_golden, by_name["0-10.png"], "1", host="https://other/x/"), clock_map).ok
    assert not golden.diff_json(ref, _with_clock(view_golden, by_name["0-10.png"], "2"), clock_map).ok
    assert not golden.diff_json(ref, _with_clock(view_golden, by_name["0-20.png"], "1"), clock_map).ok
    assert not golden.diff_json(ref, _with_clock(view_golden, "ffffffffffffffffffffffff", "1"), clock_map).ok


def test_h13_clock_nodes_need_the_clock_map(view_golden):
    with pytest.raises(golden.InputMissing):
        golden.diff_json(_with_clock(view_golden, "abc", "1"), _with_clock(view_golden, "abc", "1"))


def test_h14_links(view_golden):
    assert not golden.diff_json(view_golden, _json_mutated(view_golden, lambda d: d["links"].pop(3))).ok
    assert not golden.diff_json(view_golden, _json_mutated(view_golden, lambda d: d["links"][3].__setitem__("direction", 2))).ok


def test_h15_repeated_ids_are_keyed_by_occurrence(view_golden):
    def mutate(d):
        second = [n for n in d["nodes"] if n["ID"] == "Harrasment-0"][1]
        second["description"] = "changed"

    report = golden.diff_json(view_golden, _json_mutated(view_golden, mutate))
    assert not report.ok and "Harrasment-0#2" in str(report)


def test_h16_mask_budget_catches_a_type_rename(view_golden):
    report = golden.diff_json(
        view_golden, _json_mutated(view_golden, lambda d: _first(d, "Building").__setitem__("type", "Supply Block")), view=True
    )
    assert not report.ok
    assert report.budget_expected["M3"] == 11 and report.budget_actual["M3"] == 12


def test_h17_a_changed_byte_fails_the_frozen_check(tmp_path):
    copy_ = tmp_path / "G-CSV-1.csv"
    data = bytearray((ALCYONE / "G-CSV-1.csv").read_bytes())
    data[100] ^= 1
    copy_.write_bytes(bytes(data))
    assert golden.sha256(copy_) != golden.read_pins(ALCYONE / "FROZEN.sha256")["G-CSV-1.csv"]


def test_h18_missing_inputs_skip_or_fail(monkeypatch, tmp_path):
    missing = tmp_path / "no-MS-SC"
    monkeypatch.delenv("SC2MS_REQUIRE_GOLDEN", raising=False)
    with pytest.raises(pytest.skip.Exception):
        need(missing, "MS SC")
    monkeypatch.setenv("SC2MS_REQUIRE_GOLDEN", "1")
    with pytest.raises(pytest.fail.Exception):
        need(missing, "MS SC")


def test_h19_no_unicode_folding():
    nfc, nfd = "Ondřej", "Ondřej"
    assert not golden.diff_json(
        {"nodes": [{"ID": "Player-1", "name": nfc}]}, {"nodes": [{"ID": "Player-1", "name": "Ondrej"}]}
    ).ok
    assert not golden.diff_json({"nodes": [{"ID": "Player-1", "name": nfc}]}, {"nodes": [{"ID": "Player-1", "name": nfd}]}).ok


def test_h20_non_finite_numbers_fail():
    doc = {"nodes": [{"ID": "a", "position": {"x": float("nan")}}]}
    with pytest.raises(golden.GoldenError, match="non-finite"):
        golden.diff_json(doc, copy.deepcopy(doc))


def test_h21_urls_outside_column_5_are_not_masked(csv_golden):
    lines = _lines(csv_golden)
    i = _index(lines, ";Battle;Battle-1;")
    f = lines[i].split(";")
    f[1] = f[1] + " https://example.com/x"
    lines[i] = ";".join(f)
    assert not golden.diff_csv(csv_golden, "\n".join(lines)).ok


def test_line_endings_and_final_newline_are_differences(csv_golden):
    assert not golden.diff_csv(csv_golden, csv_golden.replace("\n", "\r\n")).ok
    assert not golden.diff_csv(csv_golden, csv_golden.rstrip("\n")).ok


def test_non_url_text_in_the_image_column_is_still_compared(csv_golden):
    # The second half of a row split by a raw newline (P7) is a "node row" on its own line;
    # its column 5 holds a time, which must stay compared (Vera, G7 of CR-007).
    lines = _lines(csv_golden)
    i = next(n for n, line in enumerate(lines) if line.startswith("Pull occured after 18.0s"))
    assert lines[i].split(";")[4] == "10:04"
    report = golden.diff_csv(csv_golden, _csv_mutate(csv_golden, "Pull occured after 18.0s", 4, "10:05"))
    assert not report.ok
    assert report.budget_actual == report.budget_expected == {"M1": 1}


@pytest.mark.parametrize(
    "host",
    ["https://media.api.mindshareapp.com/media/resource/", "https://media.api.mindshareapp.com/media/resource"],
)
def test_m2_reads_the_trailing_media_id_whatever_the_host(view_golden, clock_map, host):
    by_name = {name: mid for mid, name in clock_map.items()}
    ref = _with_clock(view_golden, by_name["0-10.png"], "1", host=host)
    report = golden.diff_json(ref, _with_clock(view_golden, by_name["0-10.png"], "1"), clock_map)
    assert report.ok
    assert report.budget_expected["M2"] == 1 and report.budget_expected["M2 unknown"] == 0
    wrong = golden.diff_json(ref, _with_clock(view_golden, by_name["0-20.png"], "1", host=host), clock_map)
    assert not wrong.ok


def test_an_unknown_clock_is_counted(view_golden, clock_map):
    report = golden.diff_json(_with_clock(view_golden, "f" * 24, "1"), _with_clock(view_golden, "f" * 24, "1"), clock_map)
    assert report.budget_expected["M2 unknown"] == 1
