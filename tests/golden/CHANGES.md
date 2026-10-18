# Golden ledger

Every intended change to a golden gets an entry here **before** the change (approach G1): the defect or task, the nodes and fields expected to change, and the count. The reviewer checks that `git diff tests/golden/` matches the entry and nothing else moved. Regenerate with `scripts/regen_golden.py`; never to make a failing test pass.

Goldens (Alcyone LE, `MS SC/Alcyone LE__lilTiGGer_vs_blacksquall/`):

| File | What | Made by |
|---|---|---|
| `alcyone/G-CSV-1.csv` | The legacy code's events CSV (fork `16beefa` + CR-003 run-only edits + CR-008 data pack 89720), pass 1, offline. 1,083 physical lines, 1,077 records | `scripts/run_legacy.py` |
| `alcyone/Intervals-1.csv` | The battle intervals written in the same run | same |
| `alcyone/G-VIEW-1.json` | The workbook's JSON before placement (`visuals`, `detail`, `dataTypes`, `nodes` without `position`, `links`) from the VBA view port on `G-CSV-1`, raw-newline rows rejoined. 665 nodes, 412 links | `tests/reference/vba_view/make_view.py` |

`G-CSV-0` (the legacy code before CR-008) is byte-identical to `G-CSV-1`, so it is not stored separately (entry D0).

## Entries

| Id | Date | Task | Golden | Expected change (written first) | Actual | Reviewer |
|---|---|---|---|---|---|---|
| B0 | 2026-10-18 | CR-003, CR-004 | G-CSV-0 | Baseline: the current code's output, differences from Stefan's sample listed in `docs/dev/legacy-vs-sample.md` (8 Upgrade rows one `;` shorter; 14 Harrasment nodes the sample lacks) | as expected | morgan (CR-003), pending (CR-004) |
| D0 | 2026-10-18 | CR-008 | G-CSV-0 → G-CSV-1 | About one Ability row (`MorphToBaneling`, nameless under 80949) and its links; no unit rows (TD-3) | **None**: byte-identical. The one `MorphToBaneling` is a `BasicCommandEvent`; Ability nodes come only from `TargetUnitCommandEvent`s (`docs/dev/datapack-89720.md`) | pending |
| V0 | 2026-10-18 | CR-006, CR-007 | G-VIEW-1 | First version (no previous golden) | 665 nodes, 412 links | pending |
