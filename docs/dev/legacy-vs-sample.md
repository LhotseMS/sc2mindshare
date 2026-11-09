# Legacy output vs Stefan's sample CSV (CR-004, T04)

2026-10-18. A = Stefan's sample `MS SC/Alcyone LE__lilTiGGer_vs_blacksquall/events_Alcyone LE__lilTiGGer_vs_blacksquall.csv` (2025-01-07, cp1250). B = the current code (`16beefa` plus CR-003's run-only edits) on the same replay, run by `scripts/run_legacy.py` (pass 1, offline, `load_map=False`). Compared with `scripts/compare_csv.py`, image URLs masked. Like the workbook's Power Query, the tool treats a row whose first field contains `-` as a link, so a node named with a hyphen (for example a game on "Post-Youth LE") would be read as a link; no such name occurs on Alcyone.

```sh
scripts/py-env .venv/bin/python scripts/compare_csv.py --a-encoding cp1250 "<sample csv>" "<root>/.tools/tmp/legacy-run/Alcyone LE__lilTiGGer_vs_blacksquall/events.csv"
```

## Result

**Every row of the sample is in the current output, in the same order.** The differences are two, both explained by code:

| # | Difference | Rows | Cause |
|---|---|---|---|
| 1 | The 8 Upgrade rows have one trailing `;` fewer in B | 8 | Padding: Upgrade's hand-kept `propertiesCount` (python bug 5). Values are identical |
| 2 | B has 14 `Harrasment` nodes that A does not have | 14 records, 20 physical lines | The harassment export (`battleDetector.harrasmentNodes` in `parseReplay`, commit `b35086d`, 2024-09-09) |

Counts per type (records):

| Type | A | B |
|---|---|---|
| Ability | 215 | 215 |
| Battle | 30 | 30 |
| Building | 110 | 110 |
| Chat | 1 | 1 |
| Energy Excess | 16 | 16 |
| Game | 1 | 1 |
| Harrasment | 0 | **14** |
| Initiated | 3 | 3 |
| Inject Delay | 21 | 21 |
| Player | 2 | 2 |
| Scouting | 11 | 11 |
| Stats | 30 | 30 |
| Supply Block | 11 | 11 |
| Units | 192 | 192 |
| Upgrade | 8 | 8 |
| Links (all) | 412 | 412 |

A: 1,063 physical lines = 1,063 records. B: 1,083 physical lines = 1,077 records; 6 harassment descriptions contain a raw newline (python bug 7), each splitting its row over 2 lines.

## Which code made the sample

No committed version reproduces it exactly, so it came from a local, uncommitted variant (consistent with its media host `media.api.app.mindshareapp.com`, which is in no commit):

- it has Scouting rows, exported since `b459f0a` (2024-09-24), and Inject Delay rows (since `5b6957c`, 2024-09-02);
- but it has no Harrasment rows, although `parseReplay` exports them since `b35086d` (2024-09-09), before Scouting;
- and its Upgrade padding matches none of the committed `propertiesCount` values since `e1bd03d` (2024-07-19).

`65a5d81` against `9172628` (the "latest commits are unstable" pair): that diff changes only `HarrasmentNode.propertiesCount` (6 to 4), the energy tracker's error logging, the media URL and the generated uploader. It cannot remove harassment rows or change Upgrade padding, so a bisect between the two would not reproduce the sample. (Running old commits would need an extra checkout, which is not approved; the history above answers the question without one.)

**Baseline (D7a, A4): the current code's output (`G-CSV-0`) with these two differences listed.**

## New defects seen in B (for the CR-023 defect ledger)

| Id | Defect | Evidence |
|---|---|---|
| H1 | Harrasment node IDs repeat: `Harrasment-0` ×7, `Harrasment-1` ×3 (cause not yet checked; likely a per-battle sequence) | B, 14 nodes, 6 distinct IDs |
| H2 | A harassment description says "Pull occured after -16.0s": a negative pull delay | B, `Harrasment-1` at 07:49 |
| L1 | `1000 spores ZvP` (5.0.2.81433) crashes in `EnergyTracker.getEnergyAtTime` (KeyError on a Lair never registered) | CR-003 run log. Fixed in `sc2mindshare` by CR-076's layer fix E1 (the default run gets past it); it remains in the bug-faithful run and the legacy code |

## Risks to the legacy output from the environment

- **pandas 3.0.6 and numpy 2.5.3** in the legacy environment (Stefan's old setup had pandas 2.2.2, numpy 2.0.0). The fork uses pandas only to read `ImageTracking.csv` into a name → id dict (`fileHandler.getImageTrackingFile`), and numpy not at all outside the screenshot tool. The comparison above shows no effect on any non-image field; the image IDs it feeds are masked. Risk: low, watched by this comparison.
- **`load_map=False`**: the map is used only for heatmaps (pass 2). With the map absent, the fork's CreepTracker logs 926 errors and one blocked map download (Morgan's spike count of 24 came from a different setup: `load_map=False`, no detectors); the creep data is not exported. No effect on the CSV in the comparison above.
- **Text encoding**: B is written as UTF-8 (macOS default), A as cp1250 (Windows). Both decode to the same text here.
