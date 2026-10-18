# Baselines at the batch base (`16beefa`, 2026-10-18)

Recorded by CR-001/CR-002 (T01, T02) for the approach gates. Interpreter Homebrew Python 3.14.5.

## G2: the fork's upstream test suite (`test_replays/`, `test_s2gs/`)

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

`ruff check` (ruff 0.16.10, the repository's `ruff.toml`) over the fork tree: **984 findings** (338 auto-fixable), plus a deprecation warning for the old top-level `ignore` setting. This number is frozen until T24 deletes the fork. G3 for a task is **0 findings on the files the task adds or changes** (Kevin, 2026-10-18).

## Known legacy defect counts (TD-6)

Counted in the legacy run log by `scripts/run_legacy.py` (`summary.json`, `creep_tracker_errors`), with `load_map=False`. These are the fork's broken `CreepTracker` plugin (`'CreepTracker' object has no attribute 'creepTracker'`), swallowed by the engine; creep data is not exported, so the CSV is unaffected. A change in these counts means the legacy run changed.

| Replay | CreepTracker errors | Other |
|---|---|---|
| Alcyone LE (92440) | 926 | 1 blocked map download (CreepTracker calls `load_map`) |
| 200k dmg spine crawler ZvP (83830) | 354 | |
| 1000 spores ZvP (81433) | n/a | crashes: `EnergyTracker.getEnergyAtTime` KeyError 118489090 (G5 failure, awaiting Stefan) |

With the map loaded (Stefan's old setup, Morgan's spike) Alcyone logs 24 CreepTracker errors instead of 926.
