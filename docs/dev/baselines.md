# Baselines at the batch base (`16beefa`, 2026-10-18)

Recorded by CR-001/CR-002 (T01, T02) for the approach gates. Interpreter Homebrew Python 3.14.5.

## G2 from CR-009 on: three suites, each with its own baseline (TD-7, D6a)

| Suite | Where | How | Baseline at CR-009 |
|---|---|---|---|
| Our suite | `tests/` (not `pin_conformance/`), `scripts/tests/` | `scripts/gates` (or pytest `-m "not pin_conformance"`) | **110 passed** |
| Pin conformance | `tests/pin_conformance/` (upstream v1.9.0's own tests, byte-identical; the 7 `test_replays/5.0.15/` replays added) | `scripts/gates`, or pytest `-m pin_conformance` | **73: 70 passed, 3 xfailed** |
| The fork's suite | `legacy/tests/` (moved from `test_replays/test_replays.py` and `test_s2gs/test_all.py`) | `scripts/legacy-suite` | **72: 65 passed, 4 failed, 3 xfailed** (unchanged, see below); leaves with `legacy/` at CR-025 (logged G2 exception, D6a) |

No count may drop below its own baseline. Some pin-conformance tests load maps over the network (`load_map=True`), as upstream's do.

## G2 before CR-009: the fork's upstream test suite (`test_replays/`, `test_s2gs/`)

Run in the legacy environment (`scripts/legacy-env`, `requirements/legacy.lock`) from the repository root:

```sh
scripts/py-env <root>/.tools/venvs/legacy/bin/python -m pytest -p no:cacheprovider test_replays test_s2gs -q -rf
```

**72 tests: 65 passed, 4 failed, 3 xfailed** (53 s). The 4 failures are caused by the fork's own core edits, not by the environment:

| Test | Failure | Fork cause |
|---|---|---|
| `test_33_shift_click_calldown_mule` | 26 != 29 | The fork's `ContextLoader` drops the last target command on every selection change, so fewer `UpdateTargetUnitCommandEvent`s get their ability copied |
| `test_33_shift_click_spawn_larva` | 20 != 23 | Same cause |
| `test_creepTracker` | (600, 24.83) != (840, 24.83) | The fork's changed time base (`frame / 22.4` instead of `frame >> 4`) |
| `test_game_event_string` | `'00.01\tGlobal …'` != `'00.00'` | The fork's rewritten `GameEvent.__str__` / `.time` |

The G2 rule "the count never drops" is measured against 72 collected / 65 passing for the fork's suite. Its replacement by upstream v1.9.0's suite (pin conformance) and the logged exception when `legacy/` is deleted are D6a / TD-7.

## G3: ruff on the fork

Measured on a clean `git archive 16beefa` copy with ruff 0.16.10 and the repository's `ruff.toml` (corrected 2026-10-18 after Vera's G7 re-run):

```sh
git archive 16beefa | tar -x -C <copy>
scripts/py-env .venv/bin/ruff check --config <copy>/ruff.toml --statistics <copy>          # whole tree
scripts/py-env .venv/bin/ruff check --config <copy>/ruff.toml --statistics <copy>/sc2reader # sc2reader/ only
```

**1,026 findings on the whole tree (355 auto-fixable); 971 on `sc2reader/` (338).** These numbers are frozen until T24 deletes the fork. G3 for a task is **0 findings on the files the task adds** and **0 new findings on the legacy files it touches** (TD-40 as clarified, TD-46 proposal).

The earlier figure of 984 was wrong: it came from `ruff check --statistics <repo> --exclude scripts` without `--config`, and `--exclude scripts` also dropped `sc2reader/scripts/` (with the 33,000-line `get-pip.py`). With `--config` and the same exclusion the count is 978. Neither is the baseline.

## Known legacy defect counts (TD-6)

Counted in the legacy run log by `scripts/run_legacy.py` (`summary.json`, `creep_tracker_errors`), with `load_map=False`. These are the fork's broken `CreepTracker` plugin (`'CreepTracker' object has no attribute 'creepTracker'`), swallowed by the engine; creep data is not exported, so the CSV is unaffected. A change in these counts means the legacy run changed.

| Replay | CreepTracker errors | Other |
|---|---|---|
| Alcyone LE (92440) | 926 | 1 blocked map download (CreepTracker calls `load_map`) |
| 200k dmg spine crawler ZvP (83830) | 354 | |
| 1000 spores ZvP (81433) | n/a | crashes: `EnergyTracker.getEnergyAtTime` KeyError 118489090 (defect L1; the legacy code keeps it. In `sc2mindshare`, CR-076's layer fix E1 gets the default run past it; the bug-faithful run still stops there) |

Morgan's planning spike counted 24 CreepTracker messages on Alcyone, but with `load_map=False` and without running the Mindshare detectors, so that number is not comparable with these runs (corrected after his CR-004 review).
