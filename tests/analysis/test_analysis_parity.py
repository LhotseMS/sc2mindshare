"""CR-011 (T11) analysis parity: the ported layer on the new reader writes the legacy CSV exactly.

The test-only renderer is the layer's own CSVExporter (the product never writes the CSV). On
Alcyone the result must equal G-CSV-1 byte for byte (and the intervals Intervals-1); on
``200k dmg spine crawler ZvP`` it must equal a live run of the legacy code. ``1000 spores ZvP`` stopped in the
energy check (defect L1, ``KeyError: 118489090``) until CR-076's layer fix E1; with the default fixes it now gets
past it (Stefan's D3a: that test replaced the pin of the old failure, and spores has no golden).
"""

import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys

import pytest

from sc2mindshare.analysis.run import analyse, legacy_csv
from sc2mindshare.reader.loader import load_replay

HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE.parents[1]
GOLDEN = CHECKOUT / "tests" / "golden" / "alcyone"
LEGACY_PY = CHECKOUT / ".venv-legacy" / "bin" / "python"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


golden = _load("golden", CHECKOUT / "tests" / "golden" / "golden.py")


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
SPINE = MS_SC / "200k dmg spine crawler ZvP.SC2Replay"
SPORES = MS_SC / "1000 spores ZvP.SC2Replay"


def need(path, what):
    try:
        return golden.require(path, what)
    except golden.InputMissing as exc:
        if golden.strict():
            pytest.fail(f"{exc} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(str(exc))


def render(replay_path):
    replay = load_replay(replay_path)
    with contextlib.redirect_stdout(io.StringIO()):
        result = analyse(replay, MS_SC, fixes=())  # bug-faithful: no layer fix (CR-023)
    return legacy_csv(result), result


def test_alcyone_csv_is_g_csv_1_byte_for_byte():
    text, result = render(need(ALCYONE, "Alcyone replay"))
    expected = (GOLDEN / "G-CSV-1.csv").read_text(encoding="utf-8")
    report = golden.diff_csv(expected, text)
    assert report.ok, str(report)
    assert text == expected
    assert result.intervals == (GOLDEN / "Intervals-1.csv").read_text(encoding="utf-8")


@pytest.mark.legacy  # runs the old fork in .venv-legacy (CR-019)
def test_spine_csv_equals_a_live_legacy_run(tmp_path):
    need(LEGACY_PY, "this checkout's .venv-legacy (scripts/legacy-env)")
    replay = need(SPINE, "200k dmg replay")
    subprocess.run(
        [
            str(LEGACY_PY),
            str(CHECKOUT / "scripts" / "run_legacy.py"),
            "--support",
            str(MS_SC),
            "--out",
            str(tmp_path),
            str(replay),
        ],
        check=True,
        capture_output=True,
    )
    legacy = (tmp_path / replay.stem / "events.csv").read_text(encoding="utf-8")
    text, _ = render(replay)
    report = golden.diff_csv(legacy, text)
    assert report.ok, str(report)


#: Spores' 11 casts where the energy check took a lone Lair as the caster: E1 finds 8 of the player's Queens with the
#: energy each time, so it charges none and logs the cast (Stefan's D2a). From Rex's independent probe at dafcf59
#: (``.scratch/rex/cr-076/v2-refs-076.json``), not from the code under test.
SPORES_LINES = [
    *["energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)"] * 5,
    *["energy check: 20.01 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)"] * 2,
    *["energy check: 20.02 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)"] * 4,
]

#: With CR-080's CG1: the full list, from Rex's independent probe (CG1 patched in memory, not the code under
#: test; ``.scratch/cr-080-review/energy/01-patched.json``). The pre-CG1 lines above are all among them, in order.
SPORES_LINES_CG1 = [
    "energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 15.22 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 15.26 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 15.28 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 15.33 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 16.02 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 16.25 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 16.42 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.42 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.43 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.43 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.52 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.52 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.52 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.53 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 16.53 ParasiticBomb: selected Larva [4900004]: data doesn't match (7 own Viper with 125 energy)",
    "energy check: 17.32 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 17.33 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 17.42 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 18.19 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (3 own Nexus with 50 energy)",
    "energy check: 19.40 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 20.01 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 20.01 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 20.02 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 20.02 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 20.02 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 20.02 SpawnLarva: selected Lair [7100002]: data doesn't match (8 own Queen with 25 energy)",
    "energy check: 20.44 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 21.20 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 21.58 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
    "energy check: 22.15 ChronoBoostEnergyCost: selected Nexus [C30000A]: data doesn't match (4 own Nexus with 50 energy)",
]


def test_spores_gets_past_the_energy_step():
    """CR-076 (AC6, Stefan's D3a): replaces ``test_spores_fails_like_the_legacy_code_l1``, which pinned L1
    (``KeyError: 118489090`` in ``getEnergyAtTime``) in the bug-faithful run. With the default fixes (E1 on) the
    analysis finishes, and the run log holds the 11 lines (among 35 since CR-080). The bug-faithful run still stops at L1, unpinned (D3a)."""
    replay = need(SPORES, "1000 spores replay")
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        result = analyse(load_replay(replay), MS_SC)  # the default fixes: E1 on

    assert "E1" in result.fixes
    lines = log.getvalue().splitlines()
    found = [line for line in lines if "data doesn't match" in line]
    # CR-080 (CG1): a recalled group holds only what the player put in it, so a lone recalled unit the check has no
    # record for (an unfinished Nexus, a unit the reader names Larva) takes E1's search more often: 11 -> 35 lines
    assert found == SPORES_LINES_CG1
    remaining = iter(found)
    assert all(any(line == other for other in remaining) for line in SPORES_LINES)
    assert not [line for line in lines if line.startswith("ERROR unit:")]


def test_the_analysis_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    render(need(ALCYONE, "Alcyone replay"))
    assert list(tmp_path.iterdir()) == []
