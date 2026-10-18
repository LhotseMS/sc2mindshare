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


### P3d: pre-game items show `00:00:00`, the real time in a property (CR-014b; D7a A9; ledger P3, display part)

The two main bases start at -71 s (signed `start_seconds`, B9); their legacy `time` text wraps to `23:58:49`. A9: pre-game items sit at the start of the timeline (done in CR-014) and show `00:00:00`, with the real value kept in a property. Fix `pre_game_display` (`analysis/fixes.py`, after H1): every node with a negative start shows `time` `00:00:00` and gets the property `pre-game time` = the signed start as `-hh:mm:ss` (`-00:01:11`). `time` is typed `time[h:m:s]` in `dataTypes`, which cannot hold a negative time, so the new property is declared `"pre-game time": "string"`, appended to `dataTypes` only in documents that use it (the bug-faithful document, G-VIEW-1, is unchanged). Positions do not change: the layout reads `start_seconds`, never the text. The analysis part of P3 (the legacy layer's own times) stays in T22. On Alcyone: `Building-1` and `Building-2`, plus `dataTypes`, in each of the three non-frozen goldens.

```json
{"entry": "P3d-view", "task": "CR-014b", "defect": "P3 display: pre-game time wraps to 23:58:49 (A9)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "b3b67358b3fc11ff6643d2c33acd742a82d4e1bfafc12d0dcc5a5f5409a17bb6", "changes": [{"select": {"type": "Building"}, "fields": ["properties.time", "properties.pre-game time"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P3d-snap-compressed", "task": "CR-014b", "defect": "P3 display: pre-game time wraps to 23:58:49 (A9)", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "d1df0132e5cc36dfd7ece87d7fccc94dfc8c3c413d13098fd27502ea3c0ee8df", "changes": [{"select": {"type": "Building"}, "fields": ["properties.time", "properties.pre-game time"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P3d-snap-linear", "task": "CR-014b", "defect": "P3 display: pre-game time wraps to 23:58:49 (A9)", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "0a5fe62d26539b95386102e03a2af98398e47252991f3fe5eeac33a5e4a492ee", "changes": [{"select": {"type": "Building"}, "fields": ["properties.time", "properties.pre-game time"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```


### A12: numbers written as VBA-JSON writes them (CR-014b; D7a A12)

A12: the Mindshare import follows VBA-JSON's number format. VBA-JSON writes a Double as VBA's string conversion does, so a whole number has no decimal part (`2`, not `2.0`); Python's `json` writes every float with one. `export.mindshare_json.to_json` now writes whole-number floats as integers, after the 4-decimal rounding of layout-spec.md §2 (unchanged: round to 4 dp first, then write). Text only: every value stays the same number, so `diff_json` (which compares numbers as numbers) reports no change, and `changes` is empty. The text delta, counted with a `parse_float` hook (strings such as an Inject Delay's `"50.0"` are text and stay): whole-number float literals 208 → 0 in G-VIEW-current, 1,044 → 0 in G-SNAP-1-compressed, 1,081 → 0 in G-SNAP-1-linear; no other byte changes. `scripts/tests/test_regen_golden.py` holds the goldens byte-identical to the code's output. The frozen G-VIEW-1 (written by the Python VBA view port) keeps its `.0` literals.

```json
{"entry": "A12-view", "task": "CR-014b", "defect": "A12 number format: whole numbers written as 2.0, VBA-JSON writes 2", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "15d829ecb06b7e0c92671fab2b5ed10c296564d063e9bfbd7f9360bf61124405", "changes": [], "added": [], "removed": []}
```

```json
{"entry": "A12-snap-compressed", "task": "CR-014b", "defect": "A12 number format: whole numbers written as 2.0, VBA-JSON writes 2", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "9563d11f89ed1d2fe3d4b2d0298b5728f78965974dbbd76a214b979a4b9827f9", "changes": [], "added": [], "removed": []}
```

```json
{"entry": "A12-snap-linear", "task": "CR-014b", "defect": "A12 number format: whole numbers written as 2.0, VBA-JSON writes 2", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "021880a2587a15e020165bb8b3a6f6e11371fba6a9922dbee758247ed6f9566b", "changes": [], "added": [], "removed": []}
```


### P3e: the pre-game time moves from a property to the description (CR-014c; P3d follow-up, Stefan's D3c)

Stefan's import of G-SNAP-1-compressed into Mindshare failed: "node 'Building-4' has different parameters than node 'Building-1' but the same type: 'Building'". Mindshare requires every node of a type to carry the same property keys, and P3d gave only the two main bases a `pre-game time` property. D3c: drop that property entirely; the two main bases keep `time` `00:00:00` (P3d's display fix stays, no `23:58:49`), and their real start goes into their description instead, `Started 71 s before the game (real start -00:01:11).` (their description was empty). The `pre-game time` dataTypes entry goes with the property. A new test holds every golden to one property key list per node type. The VBA's conditional keys (Ability `target`, `time`, `player`) are not touched (a separate story); on Alcyone every node of those types has them. G-VIEW-1 stays frozen and unchanged. On Alcyone: `Building-1` and `Building-2` (`properties.pre-game time` removed, `description` set) and `dataTypes`, in each of the three non-frozen goldens.

```json
{"entry": "P3e-view", "task": "CR-014c", "defect": "P3d follow-up: pre-game time property breaks the Mindshare import (D3c)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "e27ac227ffbb0dd442e5c8895e7a0eaffc52271ce71f7d236336e18e0001f78c", "changes": [{"select": {"type": "Building"}, "fields": ["properties.pre-game time", "description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P3e-snap-compressed", "task": "CR-014c", "defect": "P3d follow-up: pre-game time property breaks the Mindshare import (D3c)", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "eac3ff4d1ba771c9904c5a339b519c11efd48522eae12aa845b9f7393dbd8de5", "changes": [{"select": {"type": "Building"}, "fields": ["properties.pre-game time", "description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P3e-snap-linear", "task": "CR-014c", "defect": "P3d follow-up: pre-game time property breaks the Mindshare import (D3c)", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "d461347a78190e8b10a28221f87bf795fe4d0164dc4c7fa96212486b885a404e", "changes": [{"select": {"type": "Building"}, "fields": ["properties.pre-game time", "description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```


### M0: the parity fixtures, first version (CR-019, T18)

New frozen goldens, so the parity holds without the legacy venv (T24 deletes it). No existing golden changes. Each was written once by `scripts/freeze_parity_fixtures.py`, only after a live legacy run agreed, and is pinned in `PARITY.sha256` (never regenerated):

| File | What | Proven by |
|---|---|---|
| `alcyone/models-faithful.json` | The bug-faithful domain graph (`fixes=()`): 665 nodes, 412 links, the intervals | It renders the live legacy CSV and intervals (and G-CSV-1, Intervals-1) |
| `spine/models-faithful.json` | The same for `200k dmg spine crawler ZvP`: 302 nodes, 150 links | It renders the live legacy CSV and intervals |
| `spine/reader-state-legacy.summary.json`, `spores/reader-state-legacy.summary.json` | The legacy reader-state dump's summary and sha256, as Alcyone's since CR-010 | The new reader's dump equals the legacy one |

The 1000 spores replay has no model fixture: its analysis fails in the legacy layer (L1, CR-023). The tests that run the old fork carry the `legacy` marker; without the legacy venv, `-m "not legacy"` runs the rest.
