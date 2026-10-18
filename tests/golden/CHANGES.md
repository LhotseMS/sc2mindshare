# Golden ledger

Every intended change to a golden gets an entry here **before** the change (approach G1; QA design §5), appended (never edited) as a fenced `json` block:

```text
{"entry": "P1", "task": "CR-023", "defect": "...", "golden": ["<golden file>"], "base_sha256": "<sha of the golden before>",
 "changes": [{"select": {"type": "Battle"} or {"ID": "Harrasment-0#2"}, "fields": ["name", "position.x"], "count": 30}],
 "added": ["<ID#n>"], "removed": ["<ID#n>"]}
```

`scripts/check_golden_delta.py --entry <id> --old <before> --new <after>` checks the diff against the entry both ways (C3) and the base (C4); `--git <base>..<head>` checks that the entry was committed first (C1) and that this file only grew (C2). The frozen goldens below never change (`alcyone/FROZEN.sha256`); `scripts/regen_golden.py --check` re-checks that they still reproduce.

Goldens (Alcyone LE, `MS SC/Alcyone LE__lilTiGGer_vs_blacksquall/`):

| File | What | Made by |
|---|---|---|
| `alcyone/G-CSV-1.csv` | The legacy code's events CSV (fork `16beefa` + CR-003 run-only edits + CR-008 data pack 89720), pass 1, offline. 1,083 physical lines, 1,077 records | `scripts/run_legacy.py` |
| `alcyone/Intervals-1.csv` | The battle intervals written in the same run | same |
| `alcyone/G-VIEW-1.json` | The workbook's JSON before placement (`visuals`, `detail`, `dataTypes`, `nodes` without `position`, `links`) from the VBA view port on `G-CSV-1`, raw-newline rows rejoined. 665 nodes, 412 links | `tests/reference/vba_view/make_view.py` |

`G-CSV-0` (the legacy code before CR-008) is byte-identical to `G-CSV-1`, so it is not stored separately (entry D0).

## Baseline records (before the entry format)

| Id | Date | Task | Golden | Expected change (written first) | Actual | Reviewer |
|---|---|---|---|---|---|---|
| B0 | 2026-10-18 | CR-003, CR-004 | G-CSV-0 | Baseline: the current code's output, differences from Stefan's sample listed in `docs/dev/legacy-vs-sample.md` (8 Upgrade rows one `;` shorter; 14 Harrasment nodes the sample lacks) | as expected | morgan |
| D0 | 2026-10-18 | CR-008 | G-CSV-0 → G-CSV-1 | About one Ability row (`MorphToBaneling`, nameless under 80949) and its links; no unit rows (TD-3) | **None**: byte-identical. The one `MorphToBaneling` is a `BasicCommandEvent`; Ability nodes come only from `TargetUnitCommandEvent`s (`docs/dev/datapack-89720.md`) | morgan |
| V0 | 2026-10-18 | CR-006, CR-007 | G-VIEW-1 | First version (no previous golden) | 665 nodes, 412 links | morgan |

## Entries

(None yet. The first entries come with the defect fixes, CR-023.)

### H1: Harrasment node IDs are unique (CR-014, before the layout; TD rex-4, Leo leo-1)

The legacy layer numbers Harrasment nodes per battle (`Battle.harrasSeq`), so Alcyone has `Harrasment-0` x7 and `Harrasment-1` x3. Layout guard G1 treats a duplicate ID as an error. Fix: one game-wide sequence in the TD-20 node order, `Harrasment-1` ... `Harrasment-14`, applied to the domain graph (`analysis/fixes.py`); the legacy analysis output and its CSV oracle stay bug-faithful. No link references a Harrasment node on Alcyone, so no link changes. New current golden: `alcyone/G-VIEW-current.json` (G-VIEW-1 plus the entries below).

```json
{"entry": "H1", "task": "CR-014", "defect": "H1 repeated Harrasment IDs (per-battle sequence)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "0587e893610adc67b4539fcac139679cf57e41bcf3e66d693e5cd51c8fe23fb5", "changes": [{"select": {"type": "Harrasment"}, "fields": ["ID"], "count": 14}], "added": [], "removed": []}
```


### S0: the first layout snapshot, G-SNAP-1 (CR-014; awaiting Stefan's visual check, B2)

`alcyone/G-SNAP-1-compressed.json` and `alcyone/G-SNAP-1-linear.json`: G-VIEW-current laid out by `layout/sweep.py` (Leo's fixed spec), with positions, layout sizes and 136 clock nodes (68 pairs). Not frozen yet: Stefan imports both into Mindshare once and confirms they look like today's layout apart from Leo's listed differences (B8: the 11 supply blocks, as in round2-leo.md; B9: the main bases at the start and every in-game row one row later, with a 0-10 clock pair); then they join `FROZEN.sha256`. Until then a change to them needs an entry here like any other.
