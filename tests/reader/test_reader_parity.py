"""CR-010 (T10) done-when: the new reader boundary gives the Mindshare layer exactly what the old
fork gave it, on every replay we have.

Compared per game event (the fork's class names, including its control-group classes), per
Update*CommandEvent (the copied ability fields, the flags, the target command) and per unit id
(the init, done and death back-links). The Alcyone dump of the legacy reader is pinned by its
sha256 in ``tests/golden/alcyone/reader-state-legacy.summary.json``; with this checkout's
``.venv-legacy`` present, the legacy reader is also re-dumped live and compared field by field,
on all three replays.
"""

import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE.parents[1]
SUMMARY = CHECKOUT / "tests" / "golden" / "alcyone" / "reader-state-legacy.summary.json"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dump_reader_state = _load("dump_reader_state", CHECKOUT / "scripts" / "dump_reader_state.py")
golden = _load("golden", CHECKOUT / "tests" / "golden" / "golden.py")


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
REPLAYS = {
    "alcyone": MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
    "spores": MS_SC / "1000 spores ZvP.SC2Replay",
    "spine": MS_SC / "200k dmg spine crawler ZvP.SC2Replay",
}


def need(path, what):
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(f"{exc} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(str(exc))


def _canonical(state):
    return (json.dumps(state, indent=None, sort_keys=True) + "\n").encode("utf-8")


def _first_difference(expected, actual):
    for key in sorted(set(expected) | set(actual)):
        e, a = expected.get(key), actual.get(key)
        if e == a:
            continue
        if isinstance(e, list) and isinstance(a, list):
            for i, (x, y) in enumerate(zip(e, a, strict=False)):
                if x != y:
                    return f"{key}[{i}]: legacy {x!r} != new {y!r}"
            return f"{key}: lengths {len(e)} != {len(a)}"
        if isinstance(e, dict) and isinstance(a, dict):
            k = next(k for k in sorted(set(e) | set(a)) if e.get(k) != a.get(k))
            return f"{key}[{k}]: legacy {e.get(k)!r} != new {a.get(k)!r}"
        return f"{key}: legacy {e!r} != new {a!r}"
    return "no difference"


@pytest.fixture(scope="module")
def new_alcyone():
    return dump_reader_state.dump(str(need(REPLAYS["alcyone"], "Alcyone replay")))


def test_alcyone_matches_the_pinned_legacy_dump(new_alcyone):
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert new_alcyone["game_events"] == summary["game_events"]
    assert new_alcyone["class_counts"] == summary["class_counts"]
    assert len(new_alcyone["updates"]) == summary["updates"]
    assert len(new_alcyone["units"]) == summary["units"]
    assert hashlib.sha256(_canonical(new_alcyone)).hexdigest() == summary["sha256"]


def test_the_comparison_has_content(new_alcyone):
    assert sum(1 for u in new_alcyone["updates"] if u["target"] is not None) == 1808
    assert new_alcyone["class_counts"]["StealControlGroupEvent"] == 18  # the fork's names, not upstream's
    assert all(set(links) == {"init", "done", "death"} for links in new_alcyone["units"].values())


@pytest.mark.legacy  # runs the old fork in .venv-legacy (CR-019)
@pytest.mark.parametrize("name", sorted(REPLAYS))
def test_live_legacy_dump_equals_the_new_dump(name, tmp_path):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    replay = need(REPLAYS[name], f"{name} replay")
    out = tmp_path / "legacy.json"
    subprocess.run(
        [str(LEGACY_PY), str(CHECKOUT / "scripts" / "dump_reader_state.py"), str(replay), str(out)],
        check=True,
        capture_output=True,
        cwd=tmp_path,  # the fork's CreepTracker may write debug images to the working directory
    )
    legacy = json.loads(out.read_text(encoding="utf-8"))
    new = dump_reader_state.dump(str(replay))
    assert legacy == new, _first_difference(legacy, new)


@pytest.mark.parametrize("name", ["spine", "spores"])
def test_the_new_dump_matches_the_pinned_legacy_dump(name):
    """CR-019: the spine and spores legacy dumps are pinned like Alcyone's (frozen after a live run
    agreed), so the reader parity holds on all three replays without the legacy venv."""
    summary = json.loads((CHECKOUT / "tests" / "golden" / name / "reader-state-legacy.summary.json").read_text(encoding="utf-8"))
    new = dump_reader_state.dump(str(need(REPLAYS[name], f"{name} replay")))
    assert new["game_events"] == summary["game_events"]
    assert new["class_counts"] == summary["class_counts"]
    assert len(new["updates"]) == summary["updates"]
    assert len(new["units"]) == summary["units"]
    assert len(new["command_updates"]) == summary["command_updates"]
    assert sum(1 for u in new["updates"] if u["target"] is not None) == summary["updates_with_target"]
    assert hashlib.sha256(_canonical(new)).hexdigest() == summary["sha256"]
