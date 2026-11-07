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


### M1: spine's legacy CSV frozen; the done-when counts (CR-019 follow-ups, Morgan's review of cd5dea5)

New frozen goldens, pinned in `PARITY.sha256`; no existing golden changes: `spine/G-CSV-1.csv` (456 lines) and `spine/Intervals-1.csv` (17 lines), the live legacy run's output for `200k dmg spine crawler ZvP`, written by `freeze_parity_fixtures.py legacy-csv` only after the frozen spine models rendered exactly them. The spine models are now tied to the legacy output without the legacy venv, as Alcyone's are to G-CSV-1.

The done-when (tests pass with the legacy venv absent) as measured, always with `SC2MS_REQUIRE_GOLDEN=1` (a missing input fails, never skips), on a `git archive` copy without `.venv-legacy`, `-m "not legacy"`: at `cd5dea5` 427 passed, 9 deselected, 3 xfailed; at `105b1d9` 449 passed, 9 deselected, 3 xfailed. Unfiltered, the only failures are the 9 legacy-marked items.


### P1: a battle is named after the base nearest to its first death (CR-023, T22)

`BaseDetector.getClosestBase` stored a boolean (`dist = base.minDistance(...) < minDistance`) instead of the distance, so it returned the second base it iterated, lilTiGGer's Natural, for every battle: all 30 Alcyone battles read "... near lilTiGGer Natural". Fix: compare the real distances; the nearest of the bases the layer found to the battle's first countable death wins (the first one on a tie). Applied inside the analysis layer, switched by its ledger id (`analysis.fixes.LAYER_FIXES`), so the bug-faithful run (`fixes=()`) and its CSV oracle are unchanged. Only the Battle names change, in the three current goldens; nothing feeds the layout, so no position moves. Predicted, before the change, by an independent nearest-base computation on the bug-faithful layer (`.scratch/rex/cr023/probe_p1.py`):

| Battle | Was near | Now near |
|---|---|---|
| `Battle-1` | lilTiGGer Natural | blacksquall Natural |
| `Battle-2` | lilTiGGer Natural | blacksquall Natural |
| `Battle-3` | lilTiGGer Natural | blacksquall Natural |
| `Battle-4` | lilTiGGer Natural | blacksquall Natural |
| `Battle-5` | lilTiGGer Natural | blacksquall Natural |
| `Battle-6` | lilTiGGer Natural | lilTiGGer 3rd base |
| `Battle-7` | lilTiGGer Natural | blacksquall Natural |
| `Battle-8` | lilTiGGer Natural | blacksquall 3rd base |
| `Battle-9` | lilTiGGer Natural | blacksquall 5th base |
| `Battle-10` | lilTiGGer Natural | blacksquall 5th base |
| `Battle-11` | lilTiGGer Natural | blacksquall 3rd base |
| `Battle-12` | lilTiGGer Natural | blacksquall Natural |
| `Battle-13` | lilTiGGer Natural | blacksquall 3rd base |
| `Battle-14` | lilTiGGer Natural | blacksquall Natural |
| `Battle-15` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-16` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-17` | lilTiGGer Natural | lilTiGGer 4th base |
| `Battle-18` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-19` | lilTiGGer Natural | lilTiGGer 8th base |
| `Battle-20` | lilTiGGer Natural | lilTiGGer 5th base |
| `Battle-21` | lilTiGGer Natural | lilTiGGer 5th base |
| `Battle-22` | lilTiGGer Natural | lilTiGGer Main base |
| `Battle-23` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-24` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-25` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-26` | lilTiGGer Natural | blacksquall 5th base |
| `Battle-27` | lilTiGGer Natural | blacksquall Natural |
| `Battle-28` | lilTiGGer Natural | blacksquall Main base |
| `Battle-29` | lilTiGGer Natural | blacksquall 6th base |
| `Battle-30` | lilTiGGer Natural | blacksquall 6th base |

The bases are every Hatchery, Nexus or Orbital the layer found near minerals over the whole game, so a battle can be named after a base built later (the ledger fix is the distance only; a base that is not up yet is a separate question for the wording, A10).

```json
{"entry": "P1-view", "task": "CR-023", "defect": "P1 getClosestBase stores a boolean: every battle near lilTiGGer Natural", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "a131bb9d0a54c5ccd8c1b730291f95374d2479c778c226ad029d30d5721d704b", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 30}], "added": [], "removed": []}
```

```json
{"entry": "P1-snap-compressed", "task": "CR-023", "defect": "P1 getClosestBase stores a boolean: every battle near lilTiGGer Natural", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "f6bfbd02c25f09da77b3968d088ea003ec99e975e09060f35d0c306f41138b5c", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 30}], "added": [], "removed": []}
```

```json
{"entry": "P1-snap-linear", "task": "CR-023", "defect": "P1 getClosestBase stores a boolean: every battle near lilTiGGer Natural", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "a070ea623dc58cab466382b0da536e60d478750be8afdd8a7c4b2ee97f8dc68d", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 30}], "added": [], "removed": []}
```


### P1b: a battle is named only after a base that existed when it started (CR-023, T22; D8a)

Stefan's D8a on P1: skip bases started after the battle. "Existed" here: the base's init or born event, in whole seconds (`int(frame / 22.4)`), is at or before the battle's start (`Battle.startSec`); a base under construction counts. Among those bases the nearest to the battle's first countable death wins, as in P1 (first on a tie). On Alcyone the battle start and the first death give the same answer for every battle (the closest case, Battle-8, starts and has its first death at 338 s; the base P1 named was started at 340 s). A base destroyed before the battle still counts (the layer does not track a base's destruction). Applied inside the layer as its own ledger id, `P1b` in `analysis.fixes.LAYER_FIXES`. Only Battle names change: 7 of the 30, in the three current goldens, against P1's names. Predicted before the change by an independent computation on the bug-faithful layer (`.scratch/rex/cr023/probe_p1b.py`):

| Battle | Starts | P1 named (base started) | Now near |
|---|---|---|---|
| `Battle-8` | 338 s | blacksquall 3rd base (started 340 s) | blacksquall Main base |
| `Battle-9` | 384 s | blacksquall 5th base (started 762 s) | blacksquall Natural |
| `Battle-10` | 392 s | blacksquall 5th base (started 762 s) | blacksquall Natural |
| `Battle-15` | 514 s | blacksquall 6th base (started 781 s) | blacksquall 3rd base |
| `Battle-16` | 596 s | blacksquall 6th base (started 781 s) | blacksquall 3rd base |
| `Battle-18` | 635 s | blacksquall 6th base (started 781 s) | lilTiGGer 5th base |
| `Battle-19` | 665 s | lilTiGGer 8th base (started 698 s) | lilTiGGer 5th base |

```json
{"entry": "P1b-view", "task": "CR-023", "defect": "P1b (D8a): a battle named after a base built later", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "494186638e7b7c11df674cd07df93d3d901208b631c35311fad3d85a552d398a", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 7}], "added": [], "removed": []}
```

```json
{"entry": "P1b-snap-compressed", "task": "CR-023", "defect": "P1b (D8a): a battle named after a base built later", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "53cc33aaf5a2a72dc8b41eb7433b6a04dace3c1c681e6479b36f12e8e05f59d1", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 7}], "added": [], "removed": []}
```

```json
{"entry": "P1b-snap-linear", "task": "CR-023", "defect": "P1b (D8a): a battle named after a base built later", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "a5286770fa93adf9aaaddaaaffb3f2eaa0b7fc6662f845b961ce3811843fe5fb", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 7}], "added": [], "removed": []}
```


### P1c: a base counts only while its town hall stands (CR-023, T22; D10a, amends P1b)

Stefan's D10a on P1b: a base counts from its town hall's start until the town hall is destroyed, and again after a rebuild. A base's town halls are the one that founded it and every later town hall started at the same location (the layer's own rebuild rule, `BaseDetector.processNewMainBase`). A base stands in second S when one of its town halls was started (init or born) at or before S and has not died before S, all in whole seconds (`int(frame / 22.4)`) against `Battle.startSec`. As P1b keeps a town hall started in the battle's own start second, P1c keeps one that **dies in that second**: it still stood when the battle began. On Alcyone that is Battle-13 (starts at 486 s, blacksquall's 3rd Nexus dies at 486 s), which keeps "near blacksquall 3rd base". Applied inside the layer as ledger id `P1c`. Only one Battle name changes, in the three current goldens: `Battle-15` (starts at 514 s), 'VoidRay killed Roach near blacksquall 3rd base' -> 'VoidRay killed Roach near blacksquall Natural'; blacksquall's 3rd base had its Nexus from 340 s to 486 s and again from 567 s. Predicted before the change by an independent computation on the bug-faithful layer (`.scratch/rex/cr023/probe_p1c.py`, town halls found from the tracker events at each base's location, deaths from the UnitDiedEvents). On `200k dmg spine crawler ZvP` no name changes (no town hall dies or is rebuilt there; it has only frozen bug-faithful goldens).

```json
{"entry": "P1c-view", "task": "CR-023", "defect": "P1c (D10a): a battle named after a base whose town hall was destroyed", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "f845281f2aa0c995dcefaa0c3e1b2be68317ff5c921d14dece2fcb79ecc4bc6c", "changes": [{"select": {"ID": "Battle-15"}, "fields": ["name"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P1c-snap-compressed", "task": "CR-023", "defect": "P1c (D10a): a battle named after a base whose town hall was destroyed", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "41955fbf5b35313be94b327285d3255bf7a77872f831154d36b8bf8a82f52e5a", "changes": [{"select": {"ID": "Battle-15"}, "fields": ["name"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P1c-snap-linear", "task": "CR-023", "defect": "P1c (D10a): a battle named after a base whose town hall was destroyed", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "47a9f4f231f37c7d40f441ee139cd39da31bb210d3fe112ffe5c8590e1c2a72b", "changes": [{"select": {"ID": "Battle-15"}, "fields": ["name"], "count": 1}], "added": [], "removed": []}
```


### S1: the layer's supply history, S1-S4 (CR-023, T22; D9a; TD-27 folded in; written against G-VIEW-current after P1c)

The layer's supply tracker over-counts: on Alcyone it reaches 215 and 205 supply with a limit of 360, where PlayerStats `food_used` peaks at 200 and 198. Root cause, measured against PlayerStats (`.scratch/rex/cr023/probe_supply.py`): **S1** the 12 starting workers are added on top of `INITIAL_SUPPLY` = 12 (24 at 0:00 against `food_used` 12; this is TD-27's 57 s supply block from 0:00); **S2** the providers alive at 0:00 are added on top of `INITIAL_LIMIT` = 15 (30 against `food_made` 15 for blacksquall); **S3** a Hatchery provides 15 in the layer's table, not 6, and Lair and Hive are missing; **S4** providers are matched by their final type (the main base born a Hatchery reads as a Hive; an Overseer's death does not lower the limit). No death subtracts supply that was never added. Fix (Stefan's D9a): S1-S4, keeping the meaning (finished units against the limit, at the exact event); and the team default Q-b2: every event of one loop is applied before a block is judged, so there are no zero-length blocks. The series then starts at 12/14 (lilTiGGer) and 12/15 (blacksquall), as PlayerStats. Applied inside the layer as ledger id `S1`. Predicted before the change by an independent recomputation of the series on the bug-faithful layer's own events and eligibility rules (`.scratch/rex/cr023/probe_supply_fixed.py`): the Supply Block set goes from 11 to 9.

Now (G-VIEW-current):

| Block | Player | Start | End | Duration |
|---|---|---|---|---|
| `Supply Block-0` | lilTiGGer | 00:00:00 | 00:00:57 | 57 s |
| `Supply Block-1` | lilTiGGer | 00:01:45 | 00:02:31 | 46 s |
| `Supply Block-2` | lilTiGGer | 00:06:30 | 00:06:58 | 28 s |
| `Supply Block-3` | lilTiGGer | 00:07:16 | 00:07:56 | 40 s |
| `Supply Block-4` | lilTiGGer | 00:07:58 | 00:08:09 | 11 s |
| `Supply Block-5` | lilTiGGer | 00:08:41 | 00:10:05 | 84 s |
| `Supply Block-6` | lilTiGGer | 00:12:31 | 00:12:50 | 19 s |
| `Supply Block-7` | lilTiGGer | 00:13:32 | 00:13:43 | 11 s |
| `Supply Block-8` | blacksquall | 00:14:01 | 00:14:08 | 7 s |
| `Supply Block-9` | blacksquall | 00:14:35 | 00:15:41 | 66 s |
| `Supply Block-10` | blacksquall | 00:15:50 | 00:16:12 | 22 s |

After:

| Block | Player | Start | End | Duration |
|---|---|---|---|---|
| `Supply Block-0` | lilTiGGer | 00:00:38 | 00:00:57 | 19 s |
| `Supply Block-1` | lilTiGGer | 00:02:08 | 00:02:13 | 5 s |
| `Supply Block-2` | lilTiGGer | 00:06:42 | 00:06:50 | 8 s |
| `Supply Block-3` | lilTiGGer | 00:12:40 | 00:12:48 | 8 s |
| `Supply Block-4` | lilTiGGer | 00:13:18 | 00:13:43 | 25 s |
| `Supply Block-5` | blacksquall | 00:00:32 | 00:00:38 | 6 s |
| `Supply Block-6` | blacksquall | 00:14:01 | 00:14:10 | 9 s |
| `Supply Block-7` | blacksquall | 00:14:35 | 00:15:42 | 67 s |
| `Supply Block-8` | blacksquall | 00:15:49 | 00:16:14 | 25 s |

The Supply Block IDs are one sequence over both players, so they renumber (`renumber`, QA design Addendum A, keyed on player and start time): the two blocks that keep their start, blacksquall's at 00:14:01 and 00:14:35, become `Supply Block-6` and `-7` and change their end time, duration, name and description; the other 9 old blocks are removed and 7 new ones added. Supply Blocks have no links. Per D7a the snapshot (G-SNAP-1) is not regenerated for this row until Stefan confirms B2; its entries follow then. Still open, and not part of this row: a unit is added with its final type's supply (a Roach that became a Ravager counts 3), the naming row's root cause, so lilTiGGer's finished-unit supply peaks at 203.

```json
{"entry": "S1-view", "task": "CR-023", "defect": "S1 the layer's supply history over-counts (S1-S4; TD-27's 57 s block from 0:00)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "5871a9d4d78e9b55ddcf25ab319382b83323535505188a429f3bc6ccdf75e780", "renumber": {"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 2, "links_dropped": 0}, "changes": [{"select": {"ID": "Supply Block-6"}, "fields": ["name", "description", "properties.duration", "properties.end time"], "count": 1}, {"select": {"ID": "Supply Block-7"}, "fields": ["name", "description", "properties.duration", "properties.end time"], "count": 1}], "added": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1", "Supply Block-3#1", "Supply Block-4#1", "Supply Block-5#1", "Supply Block-8#1"], "removed": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1", "Supply Block-3#1", "Supply Block-4#1", "Supply Block-5#1", "Supply Block-6#1", "Supply Block-7#1", "Supply Block-10#1"]}
```


### S1 in the snapshot (CR-023, T22; D9a; TD-58)

The same supply change in both G-SNAP-1 files, written before the change and regenerated on this row's branch only (Kevin's TD-58: nothing lands in the confirmed snapshot before Stefan's B2 confirmation, and the gates stay green). Predicted by laying out today's graph with its Supply Blocks replaced by the 9 the independent probe predicts (`.scratch/rex/cr023/predict_supply_docs.py`; the layout itself is unchanged): the Supply Block set goes from 11 to 9 as in G-VIEW-current; the two blocks that keep their start (`Supply Block-6`, `-7` in the new IDs) change their name, description, duration and end time and keep their size and position; no other node moves (the Supply Blocks have their own lane).

```json
{"entry": "S1-snap-compressed", "task": "CR-023", "defect": "S1 the layer's supply history over-counts (S1-S4; TD-27's 57 s block from 0:00)", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "1167ac308af6bd35b292380105cd4e2c2be79a86da029b3f0b4d7214acfd8f7e", "renumber": {"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 2, "links_dropped": 0}, "changes": [{"select": {"ID": "Supply Block-6"}, "fields": ["description", "name", "properties.duration", "properties.end time"], "count": 1}, {"select": {"ID": "Supply Block-7"}, "fields": ["description", "name", "properties.duration", "properties.end time"], "count": 1}], "added": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1", "Supply Block-3#1", "Supply Block-4#1", "Supply Block-5#1", "Supply Block-8#1"], "removed": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1", "Supply Block-3#1", "Supply Block-4#1", "Supply Block-5#1", "Supply Block-6#1", "Supply Block-7#1", "Supply Block-10#1"]}
```

```json
{"entry": "S1-snap-linear", "task": "CR-023", "defect": "S1 the layer's supply history over-counts (S1-S4; TD-27's 57 s block from 0:00)", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "551ee9f78bf73fffa129e80d95be9937fe3af3743a1cba018ca8fed4e28370c3", "renumber": {"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 2, "links_dropped": 0}, "changes": [{"select": {"ID": "Supply Block-6"}, "fields": ["description", "name", "properties.duration", "properties.end time"], "count": 1}, {"select": {"ID": "Supply Block-7"}, "fields": ["description", "name", "properties.duration", "properties.end time"], "count": 1}], "added": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1", "Supply Block-3#1", "Supply Block-4#1", "Supply Block-5#1", "Supply Block-8#1"], "removed": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1", "Supply Block-3#1", "Supply Block-4#1", "Supply Block-5#1", "Supply Block-6#1", "Supply Block-7#1", "Supply Block-10#1"]}
```


### S1b: supersedes the S1 entries' root-cause claim and prediction; adds S5 (CR-023, T22; D9a; Morgan's G6 on 5932f93)

**Correction.** The S1 entries above say that no death subtracts what was never added. That was measured for supply only, and it is wrong for the limit: the layer lowers the limit when a supply provider dies **before it finished**, although an unfinished provider never raised it. On Alcyone blacksquall's two Nexuses killed under construction (13:06 and 14:01) each take 15 off the limit, which gives blacksquall three blocks that PlayerStats does not show (`food_used` stays below `food_made` there; Morgan's model `.scratch/morgan/prop-audit/supply_check.py`). **S5** (Kevin's call, from D9a's "finished units against the limit"): a provider that dies before it finished does not lower the limit; the tracker lowers it only for a provider whose limit it added. Applied under the same ledger id `S1`.

**New prediction**, from the bug-faithful layer by the independent recomputation (`.scratch/rex/cr023/probe_supply_fixed.py`, now with S5), matching Morgan's model: over the whole row the Supply Block set goes from 11 to **7** (S1's entries predicted 9):

| Player | Start | End | Duration |
|---|---|---|---|
| lilTiGGer | 00:00:38 | 00:00:57 | 19 s |
| lilTiGGer | 00:02:08 | 00:02:13 | 5 s |
| lilTiGGer | 00:06:42 | 00:06:50 | 8 s |
| lilTiGGer | 00:12:40 | 00:12:48 | 8 s |
| lilTiGGer | 00:13:18 | 00:13:43 | 25 s |
| blacksquall | 00:00:32 | 00:00:38 | 6 s |
| blacksquall | 00:14:47 | 00:15:36 | 49 s |

Against the goldens as the S1 entries left them (on this branch): lilTiGGer's 5 blocks and blacksquall's at 00:00:32 stay as they are; blacksquall's at 00:14:01, 00:14:35 and 00:15:49 (`Supply Block-6`, `-7`, `-8`) are removed and one at 00:14:47 is added (as `Supply Block-6`); keyed on player and start time, no ID of a kept block changes. In both snapshots no other node moves. G-VIEW-current and G-SNAP-1 are regenerated on this branch only (TD-58). The final-type supply of a morphed unit (a Ravager counts 3) stays with the naming row.

```json
{"entry": "S1b-view", "task": "CR-023", "defect": "S1b: S5, a provider that dies unfinished lowers the limit (supersedes S1's claim and prediction)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "9b03ebd859ee6392ead8c1139d8b149cb1c0e24a4b09f6e44c8d4dd221ce2875", "renumber": {"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}, "changes": [], "added": ["Supply Block-6#1"], "removed": ["Supply Block-6#1", "Supply Block-7#1", "Supply Block-8#1"]}
```

```json
{"entry": "S1b-snap-compressed", "task": "CR-023", "defect": "S1b: S5, a provider that dies unfinished lowers the limit (supersedes S1's claim and prediction)", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "900f7d289d5b3bb46cdf3f1f62db384304b83794643266f67f082a2d480065f5", "renumber": {"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}, "changes": [], "added": ["Supply Block-6#1"], "removed": ["Supply Block-6#1", "Supply Block-7#1", "Supply Block-8#1"]}
```

```json
{"entry": "S1b-snap-linear", "task": "CR-023", "defect": "S1b: S5, a provider that dies unfinished lowers the limit (supersedes S1's claim and prediction)", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "eba951d6b18b59c36b78b40950e0d286ebe8275b33cf248472e9da2bdca9e106", "renumber": {"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}, "changes": [], "added": ["Supply Block-6#1"], "removed": ["Supply Block-6#1", "Supply Block-7#1", "Supply Block-8#1"]}
```


### P8: the last 10 s Units interval is written (CR-023, T22)

The simple detector writes a Units group when the next interval begins, so the units of the last interval were never written (Alcyone's last Units node was at 00:16:20). Fix: after the events, the pending interval is flushed by the same code as during the loop (count, supply, total at time, the previous/next link to the type's last group). Applied inside the layer as ledger id `P8`. Predicted before the change by an independent probe (`.scratch/rex/cr023/probe_p8.py`: the layer's eligibility and interval rules over the events, grouped per player and type; it matches the buffer the layer leaves unflushed): on Alcyone one node and one link are added, `Units-193` (blacksquall, Probe, 1, supply 1, total at time 47, at 00:16:40) and `Units-192 > Units-193` ("previous"/"next"); in both snapshots nothing else moves (`.scratch/rex/cr023/predict_p8_docs.py`). On `200k dmg spine crawler ZvP` the same happens (serega's Probe at 00:11:00, `Units-129`, linked from `Units-124`; spine has only frozen bug-faithful goldens). The 16:40 label is two seconds after the game ends: a Units group is labelled with the nearest ten seconds (the information-only row on the "last 10s" wording).

```json
{"entry": "P8-view", "task": "CR-023", "defect": "P8 the last 10 s Units interval is never written", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "ea675ba06fced2d4b8b027b575566814b8c2e7003db5b0c60972a4afa794af7f", "changes": [], "added": ["Units-193#1", "Units-192>Units-193#1"], "removed": []}
```

```json
{"entry": "P8-snap-compressed", "task": "CR-023", "defect": "P8 the last 10 s Units interval is never written", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "c7a32026a7e16fb461bd9f9b053c1b8cbf10d00d7ef878e151f3b8d6d77086ee", "changes": [], "added": ["Units-193#1", "Units-192>Units-193#1"], "removed": []}
```

```json
{"entry": "P8-snap-linear", "task": "CR-023", "defect": "P8 the last 10 s Units interval is never written", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "163d31293052224b42196ff21713f54310209e4f9a6e88bb7bb980bd8025fcc4", "changes": [], "added": ["Units-193#1", "Units-192>Units-193#1"], "removed": []}
```


### P2: race words are no longer stripped from inside names (CR-023, T22; wording ours, A10)

The layer's name cleaning (`reader.compat.clean_name`, the fork's `replaceStrings`) removes "Zerg" and "Terran" anywhere in a text, so "Zergling" reads "ling" and "zerglingmovementspeed" reads "ling Movement Speed" (python bug 2). Fix (team wording under A10, shown to Stefan with the row): the two bare removals are dropped; the explicit `" (Zerg)"` / `" (Terran)"` / `" (Protoss)"` removals stay. Race words then read as Protoss ones always did ("Protoss Ground Weapons Level 1"). Applied as layer fix `P2` (Morgan's ruling): `clean_name(text, split, fixes)` and `object_text(value, fixes)` take the fix set explicitly, and every site whose text reaches the output passes its `ctx.fixes`; the cleaned name is also a grouping key (`nameC`: the per-type unit counts and the Units node's type), and those sites pass it too. Predicted before the change by running today's pipeline with the two removals taken out of the cleaning table for the whole run (`.scratch/rex/cr023/predict_p2_docs.py`): in the three current goldens 13 Battle names and 12 Battle descriptions, 6 Units nodes (name, description, `type`: "ling" -> "Zergling") and 1 Upgrade (name and description) change; the per-type unit counts are unchanged, only the key "ling" becomes "Zergling"; no standalone "ling" is left.

```json
{"entry": "P2-view", "task": "CR-023", "defect": "P2 'Zerg'/'Terran' stripped anywhere ('ling')", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "946efdb683b6f71f86a544a5e6cafd9d4e07b424b11ea8e3aa1987dda8bec19e", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 13}, {"select": {"type": "Battle"}, "fields": ["description"], "count": 12}, {"select": {"type": "Units"}, "fields": ["name", "description", "properties.type"], "count": 6}, {"select": {"type": "Upgrade"}, "fields": ["name", "description"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P2-snap-compressed", "task": "CR-023", "defect": "P2 'Zerg'/'Terran' stripped anywhere ('ling')", "golden": ["alcyone/G-SNAP-1-compressed.json"], "base_sha256": "5a7b8848ed4ec31c7d354de49836bcaeaf45e8ab8ca6d94e8e28ac7df774801f", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 13}, {"select": {"type": "Battle"}, "fields": ["description"], "count": 12}, {"select": {"type": "Units"}, "fields": ["name", "description", "properties.type"], "count": 6}, {"select": {"type": "Upgrade"}, "fields": ["name", "description"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "P2-snap-linear", "task": "CR-023", "defect": "P2 'Zerg'/'Terran' stripped anywhere ('ling')", "golden": ["alcyone/G-SNAP-1-linear.json"], "base_sha256": "7e25ca29825a6823ed5d13443807094325b60a28efc9444ce77a5f1f5b9f615f", "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 13}, {"select": {"type": "Battle"}, "fields": ["description"], "count": 12}, {"select": {"type": "Units"}, "fields": ["name", "description", "properties.type"], "count": 6}, {"select": {"type": "Upgrade"}, "fields": ["name", "description"], "count": 1}], "added": [], "removed": []}
```


### freeze-snap: G-SNAP-1 frozen; the live snapshot goldens are G-SNAP-current (B2, D12a; QA design Addendum B)

Stefan imported G-SNAP-1 into Mindshare and confirmed it (B2, D12a). Both files are frozen as confirmed at 066aa37 and pinned in `alcyone/FROZEN.sha256`: `alcyone/G-SNAP-1-compressed.json` sha256 `f6bfbd02c25f09da77b3968d088ea003ec99e975e09060f35d0c306f41138b5c`, `alcyone/G-SNAP-1-linear.json` sha256 `a070ea623dc58cab466382b0da536e60d478750be8afdd8a7c4b2ee97f8dc68d`. The cut (the next commit, on `cr-022-time-as-a-number`) copies them byte for byte to `alcyone/G-SNAP-current-compressed.json` and `alcyone/G-SNAP-current-linear.json`, the live goldens from then on (as G-VIEW-1 and G-VIEW-current), and points the golden tests, `regen_golden.py` and the CLI comparisons at them. No golden's content changes. The snapshot entries written before the freeze move to the live copies with the lines below; their `base_sha256` still holds.

```json
{"entry": "freeze-snap", "task": "CR-023", "defect": "none: G-SNAP-1 frozen after Stefan's check (B2, D12a; QA design Addendum B)", "golden": ["alcyone/G-SNAP-1-compressed.json", "alcyone/G-SNAP-1-linear.json"], "frozen_sha256": {"alcyone/G-SNAP-1-compressed.json": "f6bfbd02c25f09da77b3968d088ea003ec99e975e09060f35d0c306f41138b5c", "alcyone/G-SNAP-1-linear.json": "a070ea623dc58cab466382b0da536e60d478750be8afdd8a7c4b2ee97f8dc68d"}, "copies": {"alcyone/G-SNAP-1-compressed.json": "alcyone/G-SNAP-current-compressed.json", "alcyone/G-SNAP-1-linear.json": "alcyone/G-SNAP-current-linear.json"}, "changes": [], "added": [], "removed": []}
```

- `P3d-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P3d-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)
- `A12-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `A12-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)
- `P3e-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P3e-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)

Snapshot entries of this row moved to the live copies (`cr-023-p1-closest-base`, merging the freeze forward):

- `P1-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P1-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)
- `P1b-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P1b-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)
- `P1c-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P1c-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)

Snapshot entries of this row moved to the live copies (`cr-023-supply-s1`, merging the freeze forward):

- `S1-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `S1-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)
- `S1b-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `S1b-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)

Snapshot entries of this row moved to the live copies (`cr-023-p8-last-units`, merging the freeze forward):

- `P8-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P8-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)

Snapshot entries of this row moved to the live copies (`cr-023-p2-race-words`, merging the freeze forward):

- `P2-snap-compressed`: golden now `alcyone/G-SNAP-current-compressed.json` (freeze, Addendum B)
- `P2-snap-linear`: golden now `alcyone/G-SNAP-current-linear.json` (freeze, Addendum B)


### P11: a base needs a mineral field near it on both axes (CR-023, T22; D11a)

`BaseDetector.isNearMinerals` takes a town hall as a base when any mineral field is within 5 cells on the x axis **or** on the y axis, so a town hall anywhere on the same row or column as a mineral field passes (python bug: `or` for `and`). On Alcyone that makes 14 bases, among them lilTiGGer's macro Hatcheries at (41, 34), (48, 31) and (38, 40), which mine nothing. Fix (D11a): a mineral field within 7 cells on both axes (`and`, `<= 7`). Applied inside the layer as ledger id `P11`. Predicted before the change by running today's pipeline with `isNearMinerals` replaced for the whole run by D11a's rule, written on its own (`.scratch/rex/cr023/predict_p11_docs_v2.py`; the documents are byte-identical to the first prediction, `p11-predicted/`, that QA measured for Addendum C): on Alcyone 11 bases, the three macro Hatcheries drop out. Names that named a base change: 5 Battle names, 5 Building names, 3 Harrasment descriptions. Three nodes go: `Harrasment-7` (lilTiGGer, 14:03, "1 died, no pull", at a dropped base) and `Scouting-0` and `Scouting-1` (blacksquall's Probe at 00:41 and 01:11, "scouted 4th base", a dropped base). The later IDs of both types shift down, so the entries are `renumber` lists (QA design Addendum C), keyed by `(player, time)` for both types; no link touches either type, so none is dropped. In the snapshots the lanes of the removed nodes close up: Energy Excess, Inject Delay, Harrasment and Scouting positions move. The entry bodies were derived with the checker's own `renumber_maps`, `diff_by_key` and `order_records` (`.scratch/rex/cr023/derive_p11_entries.py`) and check clean against the predicted documents. On `200k dmg spine crawler ZvP` nothing changes (its bases are the same under both rules).

```json
{"entry": "P11-view", "task": "CR-023", "defect": "P11 isNearMinerals: 'or' within 5 cells finds bases away from the minerals (D11a: 'and', 7 cells)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "eb3164ac2545f1b709679835a1f671f1e94cb6d69722dcbd47a694cc3e8770a3", "renumber": [{"type": "Harrasment", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 7, "links_dropped": 0}, {"type": "Scouting", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 9, "links_dropped": 0}], "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 5}, {"select": {"type": "Building"}, "fields": ["name"], "count": 5}, {"select": {"type": "Harrasment"}, "fields": ["description"], "count": 3}], "added": [], "removed": ["Harrasment-7#1", "Scouting-0#1", "Scouting-1#1"]}
```

```json
{"entry": "P11-snap-compressed", "task": "CR-023", "defect": "P11 isNearMinerals: 'or' within 5 cells finds bases away from the minerals (D11a: 'and', 7 cells)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "996a13fa970ddfa2794259027a293b48afd942942700789e84391a7b723caad4", "renumber": [{"type": "Harrasment", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 7, "links_dropped": 0}, {"type": "Scouting", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 9, "links_dropped": 0}], "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 5}, {"select": {"type": "Building"}, "fields": ["name"], "count": 5}, {"select": {"type": "Energy Excess"}, "fields": ["position.x", "position.y"], "count": 16}, {"select": {"type": "Harrasment"}, "fields": ["description", "position.x", "position.y"], "count": 9}, {"select": {"type": "Inject Delay"}, "fields": ["position.x", "position.y"], "count": 21}, {"select": {"type": "Scouting"}, "fields": ["position.x", "position.y"], "count": 9}], "added": [], "removed": ["Harrasment-7#1", "Scouting-0#1", "Scouting-1#1"]}
```

```json
{"entry": "P11-snap-linear", "task": "CR-023", "defect": "P11 isNearMinerals: 'or' within 5 cells finds bases away from the minerals (D11a: 'and', 7 cells)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "68f931af4986ce9a57be619c73267b15238ecda0dca00f9d9e94c8af15335537", "renumber": [{"type": "Harrasment", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 7, "links_dropped": 0}, {"type": "Scouting", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 9, "links_dropped": 0}], "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 5}, {"select": {"type": "Building"}, "fields": ["name"], "count": 5}, {"select": {"type": "Energy Excess"}, "fields": ["position.x", "position.y"], "count": 16}, {"select": {"type": "Harrasment"}, "fields": ["description", "position.x", "position.y"], "count": 9}, {"select": {"type": "Inject Delay"}, "fields": ["position.x", "position.y"], "count": 21}, {"select": {"type": "Scouting"}, "fields": ["position.x", "position.y"], "count": 9}], "added": [], "removed": ["Harrasment-7#1", "Scouting-0#1", "Scouting-1#1"]}
```


### N1: units and buildings are named by their type at the time (CR-023, T22; D6a: rename only; TD-13)

The layer names a unit or building by its final type, the type it had when the replay ended: a Gateway reads "Warp Gate" from the moment it was built, lilTiGGer's main base "Hive" from the start, and an Overlord that later became an Overseer is grouped with the Overseers when it hatched. Fix (D6a, rename only, no morph nodes): the type at the time of the event (`reader.compat.type_at`, upstream's type history) names and groups them. Applied inside the layer as ledger id `N1`:
- **Units:** a group is the units of one interval, one player and one type at their event; its name, description, `type` and `count` follow. Its `supply` still adds the units' final-type supply: that is the next row's (a unit that changes type, a Roach that became a Ravager counting 3; Stefan decides a vs b). Its `total at time` counts per player and type as today, and a unit that changes type moves from its old type's count to its new one at the change (when the old type is counted). The previous/next link joins a group to the last group of its own type at the time.
- **Buildings:** the name (and its per-player index over the same name), `type` and the build-time lookup use the type at the done (or born) event, so the start moves with the build time (a Gateway's, not a Warp Gate's).
- **Battles:** a killer is named by its type at the kill.
Not changed: what a unit's energy is registered under, and the supply (the next row).

Predicted before the change by an independent model over today's graph (`.scratch/rex/cr023/predict_naming_docs.py`): it regroups the layer's own unit events by (interval, player, type at the event) with its own counting, rebuilds the Units links, and renames the buildings and the KILLS lists, then the unchanged view, layout and export. QA's figures confirmed against the layer (`probe_naming.py`): 14 Units nodes are retyped, 11 merge into the group of their type at the time and 3 are only renamed, so 193 -> 182 Units nodes (Vera's 192 -> 181 plus P8's node). Merged: Units-68 -> 69, 73 -> 72, 76 -> 75, 85 -> 84, 89 -> 88, 104 -> 105, 133 -> 135, 150 -> 149, 155 -> 154, 160 -> 159, 152 -> 151; renamed: Units-24 and Units-122 (Overseer -> Overlord), Units-182 (Ravager -> Roach). The later Units IDs shift (115 change), and the Units links are rebuilt (164 -> 158; 3 dropped by the rewrite, 8 removed, 5 added). Buildings: 14 Warp Gates become Gateways, renumbered Gateway .. Gateway 13 and started 39 s earlier; lilTiGGer's main base is a Hatchery (start unchanged), the Greater Spire a Spire (so the next Spire reads "Spire 1"). Battles: two KILLS lists change (Battle-12 "Ravager killed Stalker", Battle-26 "Baneling killed Probe": they were a Roach and a Zergling then) and merge into the existing entries. Scouting and Initiated nodes do not change (Scouting-10's unit was already an Overseer at 09:59). In both snapshots the compressed timeline's 12:10 clock window goes and a 0:50 one comes (the first Gateway's start); in the compressed one most items after 0:50 move on x. The entries are `renumber` entries for Units keyed by (player, time, type), derived with the checker's own functions (`.scratch/rex/cr023/derive_naming_entries.py`) and checked clean against the predicted documents.

```json
{"entry": "N1-view", "task": "CR-023", "defect": "N1 names by the unit's final type, not its type at the time (Warp Gate, Hive, Overseer; D6a: rename only)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "6e5a27a6a4fcff7076b187c775154a6b2cf5c9d6c236a735ef42dadffe2e112f", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {"Units-24": "Overlord", "Units-68": "Overlord", "Units-73": "Overlord", "Units-76": "Roach", "Units-85": "Roach", "Units-89": "Overlord", "Units-104": "Overlord", "Units-122": "Overlord", "Units-133": "Overlord", "Units-150": "Zergling", "Units-155": "Zergling", "Units-160": "Zergling", "Units-182": "Roach", "Units-152": "Observer"}, "merged": {"Units-68": "Units-69", "Units-73": "Units-72", "Units-76": "Units-75", "Units-85": "Units-84", "Units-89": "Units-88", "Units-104": "Units-105", "Units-133": "Units-135", "Units-150": "Units-149", "Units-155": "Units-154", "Units-160": "Units-159", "Units-152": "Units-151"}, "ids_changed": 115, "links_dropped": 3}], "changes": [{"select": {"type": "Battle"}, "fields": ["description"], "count": 2}, {"select": {"type": "Building"}, "fields": ["name", "properties.time", "properties.type"], "count": 17}, {"select": {"type": "Units"}, "fields": ["description", "name", "properties.count", "properties.supply", "properties.total at time", "properties.type"], "count": 25}, {"select": {"type": "Units"}, "fields": ["<order>"], "count": 1}, {"select": {"type": "Units>Units"}, "fields": ["<order>"], "count": 1}], "added": ["Units-10>Units-24#1", "Units-116>Units-121#1", "Units-171>Units-172#1", "Units-24>Units-41#1", "Units-91>Units-171#1"], "removed": ["Units-10>Units-41#1", "Units-116>Units-127#1", "Units-24>Units-68#1", "Units-71>Units-84#1", "Units-81>Units-171#1", "Units-84>Units-99#1", "Units-91>Units-172#1", "Units-99>Units-121#1"]}
```

```json
{"entry": "N1-snap-compressed", "task": "CR-023", "defect": "N1 names by the unit's final type, not its type at the time (Warp Gate, Hive, Overseer; D6a: rename only)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "a3d5359988d25325b09c2c9b1744c417b712c12dc9a4a95193ae7ad263405f1b", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {"Units-24": "Overlord", "Units-68": "Overlord", "Units-73": "Overlord", "Units-76": "Roach", "Units-85": "Roach", "Units-89": "Overlord", "Units-104": "Overlord", "Units-122": "Overlord", "Units-133": "Overlord", "Units-150": "Zergling", "Units-155": "Zergling", "Units-160": "Zergling", "Units-182": "Roach", "Units-152": "Observer"}, "merged": {"Units-68": "Units-69", "Units-73": "Units-72", "Units-76": "Units-75", "Units-85": "Units-84", "Units-89": "Units-88", "Units-104": "Units-105", "Units-133": "Units-135", "Units-150": "Units-149", "Units-155": "Units-154", "Units-160": "Units-159", "Units-152": "Units-151"}, "ids_changed": 115, "links_dropped": 3}], "changes": [{"select": {"type": "Ability"}, "fields": ["position.x"], "count": 107}, {"select": {"type": "Battle"}, "fields": ["description", "position.x"], "count": 20}, {"select": {"type": "Building"}, "fields": ["name", "position.x", "position.y", "properties.time", "properties.type"], "count": 88}, {"select": {"type": "Stats"}, "fields": ["position.x"], "count": 22}, {"select": {"type": "Supply Block"}, "fields": ["position.x", "size"], "count": 3}, {"select": {"type": "Units"}, "fields": ["description", "name", "position.x", "position.y", "properties.count", "properties.supply", "properties.total at time", "properties.type"], "count": 144}, {"select": {"type": "Upgrade"}, "fields": ["position.x", "position.y"], "count": 7}, {"select": {"type": "image"}, "fields": ["position.x"], "count": 90}, {"select": {"type": "Units"}, "fields": ["<order>"], "count": 1}, {"select": {"type": "Units>Units"}, "fields": ["<order>"], "count": 1}], "added": ["<clock:0-50.png>#1#1", "<clock:0-50.png>#2#1", "Units-10>Units-24#1", "Units-116>Units-121#1", "Units-171>Units-172#1", "Units-24>Units-41#1", "Units-91>Units-171#1"], "removed": ["<clock:12-10.png>#1#1", "<clock:12-10.png>#2#1", "Units-10>Units-41#1", "Units-116>Units-127#1", "Units-24>Units-68#1", "Units-71>Units-84#1", "Units-81>Units-171#1", "Units-84>Units-99#1", "Units-91>Units-172#1", "Units-99>Units-121#1"]}
```

```json
{"entry": "N1-snap-linear", "task": "CR-023", "defect": "N1 names by the unit's final type, not its type at the time (Warp Gate, Hive, Overseer; D6a: rename only)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "fb949868b3f58f76601005f14bdb8e8fe8ff96b1696619eb7845bb45d6781ad6", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {"Units-24": "Overlord", "Units-68": "Overlord", "Units-73": "Overlord", "Units-76": "Roach", "Units-85": "Roach", "Units-89": "Overlord", "Units-104": "Overlord", "Units-122": "Overlord", "Units-133": "Overlord", "Units-150": "Zergling", "Units-155": "Zergling", "Units-160": "Zergling", "Units-182": "Roach", "Units-152": "Observer"}, "merged": {"Units-68": "Units-69", "Units-73": "Units-72", "Units-76": "Units-75", "Units-85": "Units-84", "Units-89": "Units-88", "Units-104": "Units-105", "Units-133": "Units-135", "Units-150": "Units-149", "Units-155": "Units-154", "Units-160": "Units-159", "Units-152": "Units-151"}, "ids_changed": 115, "links_dropped": 3}], "changes": [{"select": {"type": "Battle"}, "fields": ["description"], "count": 2}, {"select": {"type": "Building"}, "fields": ["name", "position.x", "position.y", "properties.time", "properties.type"], "count": 22}, {"select": {"type": "Units"}, "fields": ["description", "name", "position.x", "position.y", "properties.count", "properties.supply", "properties.total at time", "properties.type"], "count": 34}, {"select": {"type": "Upgrade"}, "fields": ["position.y"], "count": 2}, {"select": {"type": "Units"}, "fields": ["<order>"], "count": 1}, {"select": {"type": "Units>Units"}, "fields": ["<order>"], "count": 1}], "added": ["<clock:0-50.png>#1#1", "<clock:0-50.png>#2#1", "Units-10>Units-24#1", "Units-116>Units-121#1", "Units-171>Units-172#1", "Units-24>Units-41#1", "Units-91>Units-171#1"], "removed": ["<clock:12-10.png>#1#1", "<clock:12-10.png>#2#1", "Units-10>Units-41#1", "Units-116>Units-127#1", "Units-24>Units-68#1", "Units-71>Units-84#1", "Units-81>Units-171#1", "Units-84>Units-99#1", "Units-91>Units-172#1", "Units-99>Units-121#1"]}
```


### B3: an Ability's combat, queued and minimap are emitted (CR-023, T22)

The workbook's `readNodes` never set `combatSet`, so an Ability's `combat`, `queued` and `minimap` never reached the Mindshare document (VBA analysis §4.6, B3), although `dataTypes` declares all three as `bool` and the legacy CSV carries them. The view port kept that for G-VIEW-1. Fix: the current document emits them, as booleans, after `type` (the domain's field order; `target` stays last); the bug-faithful document still omits them (G-VIEW-1 unchanged). An export fix, switched on with the graph fixes (`export_fixes` on the domain graph, `B3`). Predicted before the change from the legacy CSV's own columns (`.scratch/rex/cr023/predict_b3_docs.py`: today's goldens with the three values of each Ability's G-CSV-1 row inserted): all 215 Ability nodes of each of the three current goldens gain the three properties (21 combat, 14 queued, none on the minimap); nothing else changes, positions included.

```json
{"entry": "B3-view", "task": "CR-023", "defect": "B3 an Ability's combat, queued and minimap are never emitted", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "5dd83b896fd712ed1d7ac37692f3c0b36eea4ba2064d844cf73d01a7b25595c8", "changes": [{"select": {"type": "Ability"}, "fields": ["properties.combat", "properties.queued", "properties.minimap"], "count": 215}], "added": [], "removed": []}
```

```json
{"entry": "B3-snap-compressed", "task": "CR-023", "defect": "B3 an Ability's combat, queued and minimap are never emitted", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "8a70aef0b628ffdd4e32577df77d352314e3390c08d89b09f2c41aef5eb03052", "changes": [{"select": {"type": "Ability"}, "fields": ["properties.combat", "properties.queued", "properties.minimap"], "count": 215}], "added": [], "removed": []}
```

```json
{"entry": "B3-snap-linear", "task": "CR-023", "defect": "B3 an Ability's combat, queued and minimap are never emitted", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "1dbf28123b1a2cd3fe179ac0f7e06699df32f37905979bc692ce9324f729fe52", "changes": [{"select": {"type": "Ability"}, "fields": ["properties.combat", "properties.queued", "properties.minimap"], "count": 215}], "added": [], "removed": []}
```


### P10: spell effects are not counted as units (CR-023, T22)

The layer counts every finished non-building as a unit unless its name starts with an `OMIT_UNITS` entry, and it checks the unit's final name. The Disruptor's Purification Nova (`DisruptorPhased`) and the Adept's shade (`AdeptPhaseShift`) are born as units of their own, so Alcyone has Units groups "Disruptor Phased" (3) and "Adept Phase Shift" (4) (python analysis §5 item 10; plan row P10). Fix: `DisruptorPhased`, `AdeptPhaseShift` and `RavagerCocoon` join the omitted names, and eligibility reads the unit's type at the event, not its final type (as N1 names it; a Roach that died as a Ravager Cocoon was a Roach when it hatched). Applied inside the layer as ledger id `P10`. Not changed (raised separately): `OMIT_UNITS`'s "Shield battery" and "Extractor Rich" never match the ids `ShieldBattery` and `ExtractorRich`, so 2 Shield Battery groups and 1 Extractor Rich group stay Units nodes. Predicted before the change from today's graph (`.scratch/rex/cr023/predict_p10_docs.py`: the seven groups and the five previous/next links between them removed, the other Units renumbered in order; per-type totals are unchanged, since counts are per type): Units-34, 42, 45, 65 (Adept Phase Shift) and Units-122, 124, 180 (Disruptor Phased) go, and the later Units IDs shift (142 change). In the snapshots 8 Units nodes move on y (the lanes close up). The entries are `renumber` entries for Units keyed by (player, time, type), derived with the checker's own functions (`.scratch/rex/cr023/derive_p10_entries.py`) and checked clean against the predicted documents.

```json
{"entry": "P10-view", "task": "CR-023", "defect": "P10 spell effects counted as units (Disruptor Phased, Adept Phase Shift); eligibility by the final type", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "43e8b8cc2e3078a412fc6ad0e775d905f35ffc5bf02774a74014f42bc659c94b", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {}, "merged": {}, "ids_changed": 142, "links_dropped": 0}], "changes": [], "added": [], "removed": ["Units-122#1", "Units-122>Units-124#1", "Units-124#1", "Units-124>Units-180#1", "Units-180#1", "Units-34#1", "Units-34>Units-42#1", "Units-42#1", "Units-42>Units-45#1", "Units-45#1", "Units-45>Units-65#1", "Units-65#1"]}
```

```json
{"entry": "P10-snap-compressed", "task": "CR-023", "defect": "P10 spell effects counted as units (Disruptor Phased, Adept Phase Shift); eligibility by the final type", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "68544e332a956f60e72b82660e668c4adbb3e76a4ad2769ff9b0456e5e8fb675", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {}, "merged": {}, "ids_changed": 142, "links_dropped": 0}], "changes": [{"select": {"type": "Units"}, "fields": ["position.y"], "count": 8}], "added": [], "removed": ["Units-122#1", "Units-122>Units-124#1", "Units-124#1", "Units-124>Units-180#1", "Units-180#1", "Units-34#1", "Units-34>Units-42#1", "Units-42#1", "Units-42>Units-45#1", "Units-45#1", "Units-45>Units-65#1", "Units-65#1"]}
```

```json
{"entry": "P10-snap-linear", "task": "CR-023", "defect": "P10 spell effects counted as units (Disruptor Phased, Adept Phase Shift); eligibility by the final type", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "dc392ec888db3d64536257cc3f73c7c962ff995f453a36360d1cfc3ae31db48f", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {}, "merged": {}, "ids_changed": 142, "links_dropped": 0}], "changes": [{"select": {"type": "Units"}, "fields": ["position.y"], "count": 8}], "added": [], "removed": ["Units-122#1", "Units-122>Units-124#1", "Units-124#1", "Units-124>Units-180#1", "Units-180#1", "Units-34#1", "Units-34>Units-42#1", "Units-42#1", "Units-42>Units-45#1", "Units-45#1", "Units-45>Units-65#1", "Units-65#1"]}
```


### P12: `UNITS_FROM_STATE_CHANGE` is a tuple (CR-023, T22; no golden changes)

`EnergyTracker.UNITS_FROM_STATE_CHANGE = ("OrbitalCommand")` is a string, not a tuple, so `name in UNITS_FROM_STATE_CHANGE` is a substring test. Fix: `("OrbitalCommand",)`. Of the names the tracker tests, only `OrbitalCommand` is a substring of "OrbitalCommand" (no unit id is "Orbital", "Command" or empty), so no output can change, the bug-faithful CSV included: a plain correction, not a switched layer fix. Predicted: none of the goldens changes (no entry block; a test pins the tuple and the membership).


### P13: one time format, hh:mm:ss of game time (CR-023, T22; B11)

The legacy layer writes times in three forms (`export/time_text.py`): a Battle's as Python's `timedelta` text (`0:07:57`), a Harrasment's and a Scouting's as sc2reader's `Length` text (`14:03`, and `01:00:05` from an hour on), every other one as the time of day. The workbook's rule then reformats a `time` it can read as a time of day, so a Battle's `time` reads `00:07:36` but its `end time` stays `0:07:57` (B11), and a Harrasment's or Scouting's `14:03` is read as 14 h 03 min, `14:03:00` (B9's display part; from 24 min on, `25:10` is not a time of day and is kept as it is). Fix: the current document writes every time property as `hh:mm:ss` of game time, hours not wrapping (a 70-minute game reads `01:10:00`); the bug-faithful document is unchanged. An export fix, switched on with the graph fixes (`P13` in `export_fixes`, with B3). Descriptions are prose from the layer and keep their text. Predicted before the change from today's goldens (`.scratch/rex/cr023/predict_p13_docs.py`): the 30 Battle `end time`s are zero-padded, and the 13 Harrasment and 9 Scouting `time`s read as the game time they are (`14:03:00` -> `00:14:03`); nothing else changes, positions included (the layout reads the game time, not the text).

```json
{"entry": "P13-view", "task": "CR-023", "defect": "P13/B11 mixed time formats (a Battle end time 0:07:57, a Harrasment or Scouting time mm:ss read as hh:mm)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "e464c36eae7fb223e6228e18bdae4dd5d9ae0b53ae3de6c18a711d524ba041bd", "changes": [{"select": {"type": "Battle"}, "fields": ["properties.end time"], "count": 30}, {"select": {"type": "Harrasment"}, "fields": ["properties.time"], "count": 13}, {"select": {"type": "Scouting"}, "fields": ["properties.time"], "count": 9}], "added": [], "removed": []}
```

```json
{"entry": "P13-snap-compressed", "task": "CR-023", "defect": "P13/B11 mixed time formats (a Battle end time 0:07:57, a Harrasment or Scouting time mm:ss read as hh:mm)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "1dbf22fdd5948c33adc96a4d4ce058a5d3cfaa63abc7ca709540e7d6aa47f810", "changes": [{"select": {"type": "Battle"}, "fields": ["properties.end time"], "count": 30}, {"select": {"type": "Harrasment"}, "fields": ["properties.time"], "count": 13}, {"select": {"type": "Scouting"}, "fields": ["properties.time"], "count": 9}], "added": [], "removed": []}
```

```json
{"entry": "P13-snap-linear", "task": "CR-023", "defect": "P13/B11 mixed time formats (a Battle end time 0:07:57, a Harrasment or Scouting time mm:ss read as hh:mm)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "11b8c4792d243c2eefbd136e913c8f2b2b13c54e27fde84727f5c32a6aae1296", "changes": [{"select": {"type": "Battle"}, "fields": ["properties.end time"], "count": 30}, {"select": {"type": "Harrasment"}, "fields": ["properties.time"], "count": 13}, {"select": {"type": "Scouting"}, "fields": ["properties.time"], "count": 9}], "added": [], "removed": []}
```


### S6: a unit's supply follows its type (CR-023, T22; D15a)

The layer adds and removes a unit's supply by its final type, its type when the replay ended, and a Units group adds its units' final-type supply: a Roach that later became a Ravager counts 3 from the moment it hatched, and an Observer that ended in siege mode counts 0 (`ObserverSiegeMode` is missing from sc2reader's datapack, so it has no supply). Fix (Stefan's D15a): a unit counts the supply of its type when it finishes, and the difference is added at each type change, as the game does (Roach 2, then Ravager 3). A cocoon counts what the datapack gives it, which is its target's supply (RavagerCocoon 3, BroodLordCocoon 4), so the game's charge at the start of a morph follows; a type missing from the datapack keeps the previous supply (Leo and Vera to confirm). At death the unit takes away what it counted. A Units group's `supply` is the sum of its units' supply at their event. Applied inside the layer as ledger id `S6`. Predicted before the change by an independent model (`.scratch/rex/cr023/predict_s6_docs.py`): today's supply series corrected unit by unit (a counted unit adds its supply at the time less its final supply, from its finish to its death, with a point at each type change that moves it), the block rule stated on its own (judged once per loop; checked first: with no correction it gives today's 7 blocks exactly), and the Units supply recomputed. On Alcyone: lilTiGGer's 6:42-6:50 block goes (his Roaches count 2 until they morph), blacksquall gets a 2 s block at 14:43 (an Observer that ended in siege mode counts 1 again), and 4 Units groups change `supply` (Units-69 9 -> 8, Units-77 7 -> 6, Units-165 3 -> 2, Units-137 1 -> 2). The Supply Block entries are `renumber` entries keyed by (player, time) (3 IDs shift), derived with the checker's own functions (`.scratch/rex/cr023/derive_s6_entries.py`) and checked clean against the predicted documents. On `200k dmg spine crawler ZvP` the 2 blocks and the Units supply are unchanged.

```json
{"entry": "S6-view", "task": "CR-023", "defect": "D15a units counted with their final type's supply (a Roach that became a Ravager counts 3 from its birth)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "885e3f0dc5cb376503cd11fa79bc76a31257de506d2e9a1189503f404d9bc2a5", "renumber": [{"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 3, "links_dropped": 0}], "changes": [{"select": {"type": "Units"}, "fields": ["properties.supply"], "count": 4}], "added": ["Supply Block-5#1"], "removed": ["Supply Block-2#1"]}
```

```json
{"entry": "S6-snap-compressed", "task": "CR-023", "defect": "D15a units counted with their final type's supply (a Roach that became a Ravager counts 3 from its birth)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "2b521aa317e1c03c9be4cc7a0b57d430129c852db1bd3de8efb52f9e7d71044f", "renumber": [{"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 3, "links_dropped": 0}], "changes": [{"select": {"type": "Units"}, "fields": ["properties.supply"], "count": 4}], "added": ["Supply Block-5#1"], "removed": ["Supply Block-2#1"]}
```

```json
{"entry": "S6-snap-linear", "task": "CR-023", "defect": "D15a units counted with their final type's supply (a Roach that became a Ravager counts 3 from its birth)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "9ed810bb8e5a73a4e27ff6d47045c5b5b4d7d060ba4ae6ff8f3ecbfea76b4339", "renumber": [{"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 3, "links_dropped": 0}], "changes": [{"select": {"type": "Units"}, "fields": ["properties.supply"], "count": 4}], "added": ["Supply Block-5#1"], "removed": ["Supply Block-2#1"]}
```


### B12: `detail` lists only properties that exist (CR-023, T22; D16a)

The workbook's Details sheet marks the properties Mindshare shows as a node's detail, and the export read its columns B-J only (VBA analysis §4.6, B12). The extracted config (`config/details.json`) therefore lists Stats' "eco Min", which no node carries (the layer emits no economy spending; "eco Gas", "tech Min" and "tech Gas", also marked, fell outside B-J), and Initiated's "subtype", which is the property "type". Fix (Stefan's D16a): the current document's `detail` drops "eco Min" and reads "type" for Initiated; producing eco and tech is its own Backlog story. The bug-faithful document keeps the workbook's list (G-VIEW-1 unchanged). An export fix, switched on with the graph fixes (`B12` in `export_fixes`). Predicted from today's goldens (`.scratch/rex/cr023/predict_b12_docs.py`): only the `detail` record changes in each of the three current goldens, and afterwards every listed property is one that some node of its type carries.

```json
{"entry": "B12-view", "task": "CR-023", "defect": "B12 detail lists eco Min, which is no property, and Initiated subtype, which is type (D16a)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "754508e7727ad94e9ca2c90dcbdf8df713d0430ebb52373c1ba212069fc97baf", "changes": [{"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "B12-snap-compressed", "task": "CR-023", "defect": "B12 detail lists eco Min, which is no property, and Initiated subtype, which is type (D16a)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "1b8668945c89b7285c50395215155ed8d0fa62c8f4d23c6ac842862194edcb4a", "changes": [{"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "B12-snap-linear", "task": "CR-023", "defect": "B12 detail lists eco Min, which is no property, and Initiated subtype, which is type (D16a)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "eb44e37feb5549b534a4ad5376ba001f4d8799b3226a297b20678be54163e859", "changes": [{"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```


### P9: the replay's time-zone offset is printed (CR-023, T22; D17a; no golden changes)

The Game node writes its time zone as `"UTC+".format(offset)` (no placeholder: "UTC+" with no number) for a positive offset and "UTC" otherwise, and the description "Played on <date> <time zone>" uses the same text. sc2reader's `replay.date` is the game's end in UTC, and `replay.time_zone` is the offset of the PC that recorded the replay (Alcyone -5, spine +1). Fix (Stefan's D17a): the description keeps the date in UTC with "UTC" ("Played on 2024-07-24 07:55:57 UTC for ..."), and the Game node's time-zone value is the recorder's offset, "UTC-5" / "UTC+1" ("UTC+5:30" for a half hour; "UTC" for none). Applied inside the layer as ledger id `P9`. Predicted: no golden changes. Alcyone's description already reads "UTC", and the Mindshare document emits no Game properties (the view writes the Game node's name, description and size only), so the new value shows in the domain node and the legacy-format outputs, not in the goldens; spine's description changes from "UTC+" to "UTC" (spine has no current goldens). No entry block; tests pin the texts.


### P10b: Shield Batteries and rich Extractors are Building nodes (CR-023, T22; D18a)

`OMIT_UNITS` lists "Shield battery" and "Extractor Rich", which never match the ids `ShieldBattery` and `ExtractorRich`; and sc2reader's datapack (`unit_info.json`) has neither, so they are marked neither buildings nor army. The layer therefore counts them as finished units: Alcyone has 2 "Shield Battery" Units groups and 1 "Extractor Rich", spine 1 "Shield Battery". Fix (Stefan's D18a): the two spellings are corrected, and both are structures like the others: a finished or born one is a Building node (its name, per-player index, type and start as for any building; an Extractor Rich builds as an Extractor, which is the row unitsInfo.csv has), an unfinished one an Initiated node, and none is counted as a unit. Applied inside the layer as ledger id `P10b`. Not changed: their deaths. A battery's death is not a countable death today (neither a building nor army in the datapack), so battles do not list it; making it count would change battle texts and is left for Stefan. Predicted before the change from today's graph (`.scratch/rex/cr023/predict_d18a_docs.py`): the layer numbers every building-eligible finished or born event in loop order, so the three structures take Building-12, Building-33 and Building-101 (blacksquall's Shield Batteries finished at 3:00 and 6:24, started 2:31 and 5:55; lilTiGGer's Extractor Rich finished at 14:15, started 13:54), and 99 later Building IDs shift by one to three. Units-30, Units-76 (Shield Battery) and Units-156 (Extractor Rich) go with the link between the two battery groups, and 143 later Units IDs shift. In the snapshots the batteries' starts open the 2:40 and 6:00 windows of the compressed timeline, so most items move on x, and the new clock pairs appear in both. On `200k dmg spine crawler ZvP`: serega's two Shield Batteries (finished at 10:53 and 10:54) become Building-53 and Building-54 and his Units-121 goes (spine has no current goldens). The entries are `renumber` lists for Units (key: player, time, type) and Building (key: player, name), derived with the checker's own functions (`.scratch/rex/cr023/derive_d18a_entries.py`) and checked clean against the predicted documents.

```json
{"entry": "P10b-view", "task": "CR-023", "defect": "D18a ShieldBattery and ExtractorRich counted as Units (OMIT_UNITS misspelt; the datapack marks them neither buildings nor army)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "484f021b1aec2a1f38e02ca74a8a087ce04bb2f906c53182b3d80860f8e1f091", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {}, "merged": {}, "ids_changed": 143, "links_dropped": 0}, {"type": "Building", "key": ["properties.player", "name"], "retype": {}, "merged": {}, "ids_changed": 99, "links_dropped": 0}], "changes": [], "added": ["Building-101#1", "Building-12#1", "Building-33#1"], "removed": ["Units-156#1", "Units-30#1", "Units-30>Units-76#1", "Units-76#1"]}
```

```json
{"entry": "P10b-snap-compressed", "task": "CR-023", "defect": "D18a ShieldBattery and ExtractorRich counted as Units (OMIT_UNITS misspelt; the datapack marks them neither buildings nor army)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "9ad85cf9157467f9827f0ee5f8e6b9c7c00a6d1fd13a0efb5bd7175d16448828", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {}, "merged": {}, "ids_changed": 143, "links_dropped": 0}, {"type": "Building", "key": ["properties.player", "name"], "retype": {}, "merged": {}, "ids_changed": 99, "links_dropped": 0}], "changes": [{"select": {"type": "Ability"}, "fields": ["position.x"], "count": 211}, {"select": {"type": "Battle"}, "fields": ["position.x"], "count": 28}, {"select": {"type": "Building"}, "fields": ["position.x"], "count": 99}, {"select": {"type": "Chat"}, "fields": ["position.x"], "count": 1}, {"select": {"type": "Initiated"}, "fields": ["position.x"], "count": 3}, {"select": {"type": "Stats"}, "fields": ["position.x"], "count": 26}, {"select": {"type": "Supply Block"}, "fields": ["position.x"], "count": 4}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 147}, {"select": {"type": "Upgrade"}, "fields": ["position.x"], "count": 8}, {"select": {"type": "image"}, "fields": ["position.x"], "count": 118}], "added": ["<clock:2-40.png>#1#1", "<clock:2-40.png>#2#1", "<clock:6-00.png>#1#1", "<clock:6-00.png>#2#1", "Building-101#1", "Building-12#1", "Building-33#1"], "removed": ["Units-156#1", "Units-30#1", "Units-30>Units-76#1", "Units-76#1"]}
```

```json
{"entry": "P10b-snap-linear", "task": "CR-023", "defect": "D18a ShieldBattery and ExtractorRich counted as Units (OMIT_UNITS misspelt; the datapack marks them neither buildings nor army)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "b4b94a4503d1a6056e2e4d3e6801be4fbd4c69d3b05bfe590db5b5116da6b471", "renumber": [{"type": "Units", "key": ["properties.player", "properties.time", "properties.type"], "retype": {}, "merged": {}, "ids_changed": 143, "links_dropped": 0}, {"type": "Building", "key": ["properties.player", "name"], "retype": {}, "merged": {}, "ids_changed": 99, "links_dropped": 0}], "changes": [{"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 10}], "added": ["<clock:2-40.png>#1#1", "<clock:2-40.png>#2#1", "<clock:6-00.png>#1#1", "<clock:6-00.png>#2#1", "Building-101#1", "Building-12#1", "Building-33#1"], "removed": ["Units-156#1", "Units-30#1", "Units-30>Units-76#1", "Units-76#1"]}
```


### S7: a Drone's supply leaves when its structure is placed, and the limit stops at 200 (CR-023, T22; Vera's finding on S6)

A Zerg structure is made from a Drone. The game frees the Drone's supply when the structure is placed, but the replay reports the Drone's death only when the structure finishes (on Alcyone all 30 of lilTiGGer's placements: the Drone dies, with no killer and at the structure's place, in the loop the structure is done). The layer takes the supply away at that death, so a Drone keeps counting for the whole build. And the layer adds every provider's supply to the limit with no cap, where the game stops at 200. Together they make lilTiGGer's 12:40-12:48 "block", while PlayerStats shows him at 200/202, maxed. Fix: a Zerg structure's placement (its UnitInit; not a creep tumor or a Nydus worm, which no Drone makes) takes away its Drone's supply (1), and the Drone's death at the structure's place then takes nothing more; a structure cancelled before it finishes gives the Drone's supply back (the game returns the Drone); and the limit is the providers' total capped at 200. Applied inside the layer as ledger id `S7`. Predicted before the change (`.scratch/rex/cr023/predict_s7_blocks.py`: today's series with lilTiGGer's 30 placements matched to their Drones' deaths and the supply taken from the placement on, the limit capped, and the block rule stated on its own), on Alcyone: the 12:40-12:48 block goes; so does the 2:08-2:13 one (Drones in a Spawning Pool and a Hatchery; PlayerStats has 21.5/22 at 2:08, not blocked); the first one starts at 0:41 instead of 0:38 (the Spawning Pool's Drone leaves at 0:18); the 13:18-13:43 block stays (PlayerStats 186.5/184 at 13:20). The cap alone would turn 12:40-12:48 into 12:31-12:50 and add a 0 s block at 15:22 (Vera's model); with the placements it changes nothing on Alcyone, since no in-game supply then exceeds 200, and a player at 200/200 is maxed, not blocked ("not at 200"). On `200k dmg spine crawler ZvP` the 2 blocks are unchanged. The Supply Block entries are `renumber` entries keyed by (player, time) (4 IDs shift), derived with the checker's own functions (`.scratch/rex/cr023/derive_s7_entries.py`) and checked clean against the predicted documents.

```json
{"entry": "S7-view", "task": "CR-023", "defect": "S7 a Drone that becomes a structure keeps its supply until the structure finishes; the limit is not capped at 200", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "a1f0654b973c0fec8c53507f732a3e4605f62da29c785fb38e510b104a20c190", "renumber": [{"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 4, "links_dropped": 0}], "changes": [], "added": ["Supply Block-0#1"], "removed": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1"]}
```

```json
{"entry": "S7-snap-compressed", "task": "CR-023", "defect": "S7 a Drone that becomes a structure keeps its supply until the structure finishes; the limit is not capped at 200", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "e1274c1f750af9ed68f9b5a490d44f5620bd1a7a2020827e5986b6543e827803", "renumber": [{"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 4, "links_dropped": 0}], "changes": [], "added": ["Supply Block-0#1"], "removed": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1"]}
```

```json
{"entry": "S7-snap-linear", "task": "CR-023", "defect": "S7 a Drone that becomes a structure keeps its supply until the structure finishes; the limit is not capped at 200", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "979594c912c74ec0d4e731e0eff07b71d812e7e9571a02e315ba61b3408863c4", "renumber": [{"type": "Supply Block", "key": ["properties.player", "properties.time"], "retype": {}, "merged": {}, "ids_changed": 4, "links_dropped": 0}], "changes": [], "added": ["Supply Block-0#1"], "removed": ["Supply Block-0#1", "Supply Block-1#1", "Supply Block-2#1"]}
```


### S8: the type changes the missing-type supply rule covers are named; any other is flagged (CR-023, T22; hardening, Vera)

S6's rule keeps a unit's supply when it changes into a type missing from sc2reader's datapack. Vera confirmed it for a mode switch (an Observer in siege mode keeps its supply in the game), but the rule applied to any missing type silently. Fix: the types it covers are named, each with the type it is a mode or cocoon of (ObserverSiegeMode, OverseerSiegeMode, OverlordTransport, OverlordCocoon, TransportOverlordCocoon, VikingFighter, HellionTank, LiberatorAG, ThorAP, RavagerBurrowed, DroneBurrowed); a counted unit that changes into any other missing type still keeps its supply, but the layer records it (`SimpleDetector.supplyFlags`, and a line in the run's log) instead of passing over it. Applied with ledger id `S8`. Predicted: no golden changes. On the three replays the only missing types a counted unit changes into are OverlordCocoon and ObserverSiegeMode (Alcyone; `.scratch/rex/cr023/probe_s8.py`), both named, so nothing is flagged. No entry block; tests pin the named list and the flag.


- S8 correction (Morgan's optional N0, and a check of the names): the named modes are sc2reader's type titles, which the type history holds, each missing from the datapack: ObserverSiegeMode, OverseerSiegeMode, OverlordTransport, TransportOverlordCocoon, LiberatorAG, ThorAP, RavagerBurrowed and, added, LurkerBurrowed. The record above also listed OverlordCocoon, VikingFighter and HellionTank (ids whose titles, OverseerCocoon, Viking and BattleHellion, are in the datapack) and DroneBurrowed (in the datapack); they are no longer listed, which changes no result. LurkerEgg (a morph to a dearer unit) stays flagged. Still no golden changes.

- S7 correction (Morgan's G6 on 169c1fb): the S7 entry says a structure cancelled before it finishes gives the Drone's supply back. It does not: the replay hands the Drone back as a new birth (on spine, Piliskner's Extractor cancelled at 1:24 and a Drone born at 1:25 with no earlier event), which the birth path already counts, so the give-back counted that Drone twice for the rest of his game. A placed structure that dies unfinished now leaves the Drone matching and gives nothing back. No golden changes: Alcyone has no such cancel, and spine's 2 Supply Blocks are unchanged.


### P10c: a destroyed Shield Battery or Rich Extractor counts in battles like another structure (CR-068; D21a, D26a, D32a)

Since P10b both are structures (Building nodes), but their deaths are still not countable deaths: sc2reader's datapack has neither, so `countableUnitDeath` and `buildingDeath` say no, and a battle leaves the death out of its dead, its owner's losses and the LOST list. Fix (Stefan's D21a, D26a): under the new fix id `P10c` both predicates are true for the two structures (the set P10b introduced, moved to `reader/compat.py`), at the battle call sites only: the battle's own death handling (`battle.py`) and the battle detector that forms the battles (`BattleDetector.sortDeaths`, Kevin's call on the Touchpoint question); the supply, heatmap, harassment and scouting callers keep the faithful rule (out of scope). Such a death's minerals and gas come from the unitsInfo.csv row the structure maps to (Shield Battery 100/0; a Rich Extractor as an Extractor, 25/0), its supply is 0. As for any structure, it goes in its owner's LOST list only; the KILLS lists stay units-only (D32a). Predicted before the change from plain tracker events and today's goldens (`.scratch/rex/cr068/predict_docs.py`): on Alcyone the two such deaths with a killing unit are blacksquall's Shield Batteries at 7:48 (a Roach) and 14:33 (a Zergling), inside Battle-12 (7:36-7:57) and Battle-27 (14:31-15:05) and after their starts, so no battle is created, merged, renamed or moved. Each of the two: dead +1, p2 dead +1, blacksquall's sentence "lost N units, S supply, M min G gas" gets N +1 and M +100 (supply unchanged), and "Shield Battery" joins his LOST list in death order (Battle-12 `Shield Battery, Pylon`; Battle-27 `Pylon(9), Assimilator(3), Shield Battery, Nexus`). Battle names: unchanged (a name reads the dead units' and killers' types, which a structure death does not change). Positions: none (the layout reads a battle's start, supply dead and order, all unchanged; Leo's case 1). On `200k dmg spine crawler ZvP` and `1000 spores ZvP` no battery or Rich Extractor dies (spine has no current goldens). The entries were derived with the checker's own functions (`.scratch/rex/cr068/derive_entries.py`) and checked clean against the predicted documents.

```json
{"entry": "P10c-view", "task": "CR-068", "defect": "P10c a destroyed Shield Battery or Rich Extractor is not a countable death, so battles leave it out (D21a, D26a, D32a)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "c5307174cc66f2d3e37cf6c17af9739e06028a13043f6e32053e02ea42fac6f7", "changes": [{"select": {"type": "Battle"}, "fields": ["description", "properties.dead", "properties.p2 dead"], "count": 2}], "added": [], "removed": []}
```

```json
{"entry": "P10c-snap-compressed", "task": "CR-068", "defect": "P10c a destroyed Shield Battery or Rich Extractor is not a countable death, so battles leave it out (D21a, D26a, D32a)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "07e79ad24cfc5abc3ac8b8d5f9e0040525831190227ccbf9790b92ea96e47ed6", "changes": [{"select": {"type": "Battle"}, "fields": ["description", "properties.dead", "properties.p2 dead"], "count": 2}], "added": [], "removed": []}
```

```json
{"entry": "P10c-snap-linear", "task": "CR-068", "defect": "P10c a destroyed Shield Battery or Rich Extractor is not a countable death, so battles leave it out (D21a, D26a, D32a)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "0aae07586c81b3b9c1f0bc2c9190ab3bab39ccfc9d4b6ba2ea4ccfc4e85a6cfd", "changes": [{"select": {"type": "Battle"}, "fields": ["description", "properties.dead", "properties.p2 dead"], "count": 2}], "added": [], "removed": []}
```

- P10c correction (Stefan's D34a): a destroyed Rich Extractor is valued exactly as a normal Extractor of the same race, as sc2reader's datapack values it (a Zerg Extractor: 75 minerals, 25 plus the Drone's 50), not at unitsInfo.csv's 25 as the entry above says. The Shield Battery stays at its table row, 100. No golden changes: no Rich Extractor dies on the three replays (and no Extractor; checked again on the regenerated goldens).

- P10c correction to the note above: normal Extractors do die on the replays (Alcyone: two of lilTiGGer's at 16:07 and 16:08; spine: one at 1:24; spores: two with no killer), but their valuation path is the one D34a reuses and does not change; it is Rich Extractors that never die there. Still no golden changes (the regen checks below).


### G1: the Game node's game type and length are its own (CR-067; no golden changes)

The layer's Game node (`analysis/exports/gameNode.py`) sets `self.type = replay.type` and then `self.type = "Game"` (the node's own type), so the value it writes for the game type is always "Game"; and it writes the length with `datetime.strptime(str(replay.length), "%M.%S")`, which fails for a game of an hour or more (`%M` stops at 59) and has no hours. Fix (CR-067, D27a): the game type is the replay's (`replay.type`, "1v1"), kept apart from the node's type; the length is hh:mm:ss of the replay's length, hours included ("01:05:09"); and the date played is written with an explicit `YYYY-MM-DD HH:MM:SS` format of the replay's UTC date, never `str()` (CR-064's time-zone-aware dates would add "+00:00"). Applied inside the layer as ledger id `G1`. Predicted: no golden changes. The workbook view emits no Game values, and Alcyone's description already reads "for 00:16:38" with the same date text; without G1 (the bug-faithful run) the CSV oracle keeps "Game" and the legacy length text. G2 below shows the values.


### G2: the Game node's seven properties are in the Mindshare file (CR-067; D20a, D24a, D27a)

The workbook view writes no Game properties, so the Mindshare file carries none of the values the layer computes for the game (CR-023 P9's record: "the document emits no Game properties"). Fix (Stefan's D20a, D24a; story CR-067): with the export fix `G2` the Game node carries seven properties, in this order: `date played (UTC)` (the replay's UTC date, "2024-07-24 07:55:57"), `time zone` (the recorder's offset, P9's "UTC-5"), `length` ("00:16:38", G1), `game type` ("1v1", G1), `ladder` (true, a boolean), `category` ("Ladder") and `speed` ("Faster"); `dataTypes` gains one entry for each (string, typelist, time[h:m:s], typelist, bool, typelist, typelist), after the workbook's, none of which changes; and `detail` gains a Game entry with `date played (UTC)` and `length`, after the others. An export fix, switched on with the graph fixes, so the bug-faithful document (G-VIEW-1, G-SNAP-1) is unchanged. The schema (`schema/mindshare-graph.schema.json`) types the seven Game properties and requires them (TD-16: further properties stay allowed). No size, position, link or other node changes (the Game node's size is fixed). Predicted from the property table in CR-067 and Alcyone's replay (date, time zone -5, length, "1v1", ladder, "Ladder", "Faster"). On `200k dmg spine crawler ZvP`: date played (UTC) 2021-02-12 13:44:00, time zone UTC+1, length 00:11:00 (spine has no current goldens).

```json
{"entry": "G2-view", "task": "CR-067", "defect": "G2 the Game node's properties are not in the Mindshare file (D20a, D24a)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "c5307174cc66f2d3e37cf6c17af9739e06028a13043f6e32053e02ea42fac6f7", "changes": [{"select": {"type": "Game"}, "fields": ["properties.date played (UTC)", "properties.time zone", "properties.length", "properties.game type", "properties.ladder", "properties.category", "properties.speed"], "count": 1}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "G2-snap-compressed", "task": "CR-067", "defect": "G2 the Game node's properties are not in the Mindshare file (D20a, D24a)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "07e79ad24cfc5abc3ac8b8d5f9e0040525831190227ccbf9790b92ea96e47ed6", "changes": [{"select": {"type": "Game"}, "fields": ["properties.date played (UTC)", "properties.time zone", "properties.length", "properties.game type", "properties.ladder", "properties.category", "properties.speed"], "count": 1}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "G2-snap-linear", "task": "CR-067", "defect": "G2 the Game node's properties are not in the Mindshare file (D20a, D24a)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "0aae07586c81b3b9c1f0bc2c9190ab3bab39ccfc9d4b6ba2ea4ccfc4e85a6cfd", "changes": [{"select": {"type": "Game"}, "fields": ["properties.date played (UTC)", "properties.time zone", "properties.length", "properties.game type", "properties.ladder", "properties.category", "properties.speed"], "count": 1}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```


### G2r: G2 again, on CR-068's goldens (CR-067 landing)

CR-068 lands before CR-067, so the merge of cr-068 into cr-067 kept CR-068's goldens, which lack G2; the three G2 entries above have the pre-CR-068 bases and can no longer apply. G2r restates them unchanged on CR-068's goldens: the same seven Game properties, `dataTypes` and `detail` changes, and nothing else (P10c touches only Battle nodes, G2 only the Game node and the two config records, so the two do not meet). The regeneration follows in its own commit.

```json
{"entry": "G2r-view", "task": "CR-067", "defect": "G2 the Game node's properties are not in the Mindshare file (D20a, D24a); restated on CR-068's goldens", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "3a5e2762a7d6a697d3063cc8198b2e0f247cad0504d240785759021d14e0e302", "changes": [{"select": {"type": "Game"}, "fields": ["properties.date played (UTC)", "properties.time zone", "properties.length", "properties.game type", "properties.ladder", "properties.category", "properties.speed"], "count": 1}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "G2r-snap-compressed", "task": "CR-067", "defect": "G2 the Game node's properties are not in the Mindshare file (D20a, D24a); restated on CR-068's goldens", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "3d617740bff9eca46bb2c82d4b4a6ee47f790583221bd896a810003b1512f8e5", "changes": [{"select": {"type": "Game"}, "fields": ["properties.date played (UTC)", "properties.time zone", "properties.length", "properties.game type", "properties.ladder", "properties.category", "properties.speed"], "count": 1}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "G2r-snap-linear", "task": "CR-067", "defect": "G2 the Game node's properties are not in the Mindshare file (D20a, D24a); restated on CR-068's goldens", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "74c1513a590c5223352e4c1e98c4e2839c65c00dee9745b45544bdb4cbd3b0a2", "changes": [{"select": {"type": "Game"}, "fields": ["properties.date played (UTC)", "properties.time zone", "properties.length", "properties.game type", "properties.ladder", "properties.category", "properties.speed"], "count": 1}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"ID": "detail"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```


### CK1: the clock nodes point at the local Mindshare's pictures (CR-069; D41a, D42a, D45a, D51a)

The layout's clock nodes name a picture on the 2024 dev media host (`name` = `https://media.api.mindshare.touch4dev.net/media/resource/<24-hex id>`, `ID` = the id plus the side), a server that no longer exists, so Mindshare shows grey placeholders. Fix (story CR-069): a clock node is written in the local Mindshare's format: `name` is the clock's file name (`0-10.png`), `ID` is `clock-<m>-<ss>-<side>` (`clock-0-10-1`, server-independent and unique, one clock per window), and the new `nodeImage` holds the picture ID the clock got on the chosen server, read from the clock record (`MS SC/ClockImageRecord.csv`; for the goldens the committed fixture `tests/golden/clock-record-fixture.csv`, 480 clocks with uuid5 IDs on `localhost:3042`). Type, size, properties, position and order are unchanged, and so is which windows get a clock. The export no longer reads `TimeImageTracking.csv`.

How C3 sees it: mask M2 already compares a clock node by its clock, not by its media id (`<clock:0-10.png>` and `<clock:0-10.png>#1`, through `TimeImageTracking.csv` for the old form). The new form gives the same tokens from the file name and the `clock-...` ID, without a clock map (golden.py; `check_golden_delta` keys new-form clocks without a map, the checker change of this story). So `name` and `ID` compare equal under M2, their raw form is pinned by the CR-069 export tests (AC-9), and the one listed change is the added `nodeImage` on every clock node. Predicted from today's goldens: 140 clock nodes (70 clocks x 2 sides) in each snapshot (CR-069's 136/68 predate CR-023 P10b, whose two battery starts open two more windows). G-VIEW-current has no clock nodes: no change. The frozen G-SNAP-1 keeps today's form.

```json
{"entry": "CK1-snap-compressed", "task": "CR-069", "defect": "CK1 the clock nodes point at the dead 2024 media host (D41a, D42a)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "33fb8d536a7cb9c692a46ac857f1ee144451bc389749283b2b9623780db25ab5", "changes": [{"select": {"type": "image"}, "fields": ["nodeImage"], "count": 140}], "added": [], "removed": []}
```

```json
{"entry": "CK1-snap-linear", "task": "CR-069", "defect": "CK1 the clock nodes point at the dead 2024 media host (D41a, D42a)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "50736726618cda8c6372b208239e9ea52dbfc221f18da18a17173af89c9cc659", "changes": [{"select": {"type": "image"}, "fields": ["nodeImage"], "count": 140}], "added": [], "removed": []}
```


### F1: a lifted town hall and an Overlord in its cocoon still provide supply, and their death lowers the limit (CR-023, T22; Morgan's G6 F1 on S1; no golden changes)

S1 lowers the limit when a provider dies, by its type at the death (`trackers.PROVIDERS_AT_EVENT`). The table has no lifted town hall (CommandCenterFlying, OrbitalCommandFlying; a PlanetaryFortress cannot lift and the datapack has no flying type for it) and no Overlord in a cocoon (OverseerCocoon, the type history's name for an Overlord morphing into an Overseer; TransportOverlordCocoon, one growing ventral sacs). In the game each still provides its supply (15, 8), so when one dies the limit must go down, but `providerOf` returned None and the limit never went down. And a death the fork does not count (`countableUnitDeath`: the datapack marks neither TransportOverlordCocoon nor OverlordTransport army or building) never reached `providerOf` at all, so OverlordTransport, already in the table, never lowered the limit either. Fix: the four types provide what their unit provided (`trackers.PROVIDERS_IN_A_MODE`), and every death of a finished provider lowers the limit, counted or not; only the supply changes (a death the fork does not count still counts nowhere else: not in battles, not in the unit counts). Applied inside the layer as ledger id `F1`. Predicted: no golden changes. On the three replays no unit dies as one of the four types or as an OverlordTransport, and every provider that dies is a counted death (`.scratch/rex/cr-023-f1-f2-v1/probe_f1.py`: Alcyone 8 Overlords, 10 Overseers, 16 Pylons, 4 Nexuses, 1 Hatchery; spine 3 Overlords, 1 Pylon; spores 8 Overlords, 7 Overseers, 12 Pylons, 4 Nexuses, 1 Hatchery). No entry block; tests pin the four types, their values and the uncounted death.


### F1b: an uncounted provider death changes only the supply (CR-023, T22; Morgan's finding 4 on F1; test only, no golden changes)

F1 lets a death the fork does not count still lower the supply limit (`SimpleDetector.providerDied`). Morgan's finding 4 on F1 asked for proof that such a death changes nothing else: it must not reach the battles, the Units nodes' counts and totals, or any other node or link. No product code changes: the F1 fixture (`uncounted_overlord_deaths`, Alcyone with its Overlord deaths made uncounted) also keeps each patched run's graph without its Supply Block nodes, and a new test pins that those nodes and every link are the same with and without F1. Predicted: no golden changes (only a test changes). No entry block.


### F2: a type change waits until the unit's interval is written (CR-023, T22; Morgan's G6 F2 on N1; Kevin's J7)

N1 moves a unit from its old type's count to its new type's at the type change (`SimpleDetector.moveUnitTypeCount`), but a unit enters its type's count only when its 10 s interval is written (`flushUnitInterval`). A unit that changes type while it still waits in that interval was moved too early: when its old type had no count yet (the first Widow Mine burrowing, the first Siege Tank sieging) the move was skipped and the unit stayed on its old type; when its old type had a count, the Units node written afterwards left the unit out of its `total at time`. Fix (Kevin's J7, option a, under Stefan's standing instruction): the move of a unit still waiting in the unwritten interval is applied once that interval is written, in the order the changes came; a unit already written moves at once, as before. Applied inside the layer as ledger id `F2`. Predicted before the change (`.scratch/rex/cr-023-f1-f2-v1/probe_f2.py`, and an uncommitted trial of the fix): on Alcyone one unit changes type while waiting, lilTiGGer's Roach of 14:50 (`Units-162`, one Roach), which becomes a Ravager Cocoon before its interval is written; its `total at time` goes from 0 to 1, in the three current goldens, and nothing else changes. On `200k dmg spine crawler ZvP` no unit changes type while waiting; `1000 spores ZvP` stops at L1 before the detector. The related death rule (the first unit of a type that dies while waiting in its interval is never subtracted) is not part of F2.

```json
{"entry": "F2-view", "task": "CR-023", "defect": "F2 a type change applied before the unit's interval is written (Units-162: one Roach, total at time 0)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "923ea1221356c892f3b660cc67944f9099ded0b5ca6d5247eacc10c88c493e10", "changes": [{"select": {"ID": "Units-162"}, "fields": ["properties.total at time"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "F2-snap-compressed", "task": "CR-023", "defect": "F2 a type change applied before the unit's interval is written (Units-162: one Roach, total at time 0)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "fbb9a508e1b65e8afddbef42c9607bac57c8bcb44a1ec884a90c624f27b563dd", "changes": [{"select": {"ID": "Units-162"}, "fields": ["properties.total at time"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "F2-snap-linear", "task": "CR-023", "defect": "F2 a type change applied before the unit's interval is written (Units-162: one Roach, total at time 0)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "6b21c279242b9a555afa3771458c46422796aa6fec90de38e14261466dcb9799", "changes": [{"select": {"ID": "Units-162"}, "fields": ["properties.total at time"], "count": 1}], "added": [], "removed": []}
```


### F2b: F2 also defers a waiting unit's death (CR-023, T22; Morgan's G0 P1 on F2; Stefan's D1a; closes F5 for waiting units)

Addendum to F2: the rule now also defers a waiting unit's death (D1a, closing F5 for waiting units). A countable death of a unit still waiting in the unwritten 10 s interval (`SimpleDetector.releaseUnitCount`, the loop's own death-count code moved into a method) goes into the same queue as its type changes, in event order, and leaves the count of its type at death once the interval is written; before, it was applied at once, so a unit that changed type and died before the flush stayed counted alive, and a unit born and killed inside its interval was taken off before it was ever counted (or not at all, as the first of its type). A death of a unit already written applies at once, as before. Predicted before the change by the parked trial (`.scratch/rex/cr-023-f1-f2-v1/f2-round2-p1-death-queue.patch`, run against the goldens at 203c0c6): on Alcyone two Units nodes change `total at time`, in the three current goldens, and nothing else: `Units-169` (lilTiGGer's 2 Roaches at 16:20) 0 -> 2 and `Units-92` (blacksquall's 2 Stalkers at 07:50) 1 -> 3. Spine and spores as in F2.

```json
{"entry": "F2b-view", "task": "CR-023", "defect": "F2b a waiting unit's death applied before its interval is written (Units-169: two Roaches, total at time 0)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "407244a0db5c31fe79abd70814f4c4af1c310e617612c9881a129df8b7b82a5f", "changes": [{"select": {"ID": "Units-169"}, "fields": ["properties.total at time"], "count": 1}, {"select": {"ID": "Units-92"}, "fields": ["properties.total at time"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "F2b-snap-compressed", "task": "CR-023", "defect": "F2b a waiting unit's death applied before its interval is written (Units-169: two Roaches, total at time 0)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "e438b43b0bfad6a940fd64fbfb4421113278cec3181c01dccbc12d0d21dac913", "changes": [{"select": {"ID": "Units-169"}, "fields": ["properties.total at time"], "count": 1}, {"select": {"ID": "Units-92"}, "fields": ["properties.total at time"], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "F2b-snap-linear", "task": "CR-023", "defect": "F2b a waiting unit's death applied before its interval is written (Units-169: two Roaches, total at time 0)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "b34eb02ae1de2de6fa1c1641e75cb6395b7d70c3ef4ccbb686ba0fee0f7dad3a", "changes": [{"select": {"ID": "Units-169"}, "fields": ["properties.total at time"], "count": 1}, {"select": {"ID": "Units-92"}, "fields": ["properties.total at time"], "count": 1}], "added": [], "removed": []}
```


### P10c-stop: a battle death whose cost cannot be found stops the run (CR-070; Stefan's D1a; Morgan's P3 on CR-068; no golden changes)

P10c values a destroyed Shield Battery from its unitsInfo.csv row and a Rich Extractor as the replay datapack's Extractor (D34a), but the lookup ran inside the battle's catch-all error handler, after the death was already added to the battle's dead: a lookup that failed (no row, a cost cell that is not a whole number, no Extractor in the datapack) left the death counted without its minerals, gas, supply and killer, with one red line in the run log. Fix (story CR-070, Stefan's D1a): the cost is looked up before the death is counted, outside the catch-all, and a failed lookup stops the run with a ValueError naming the replay's file name, the death's own time, the structure (type name, unit id, owner) and what was missing. An empty cost cell still reads 0. Not a new ledger id: it is P10c's own valuation, and without P10c nothing is looked up, so the bug-faithful run cannot stop for it. Predicted: no golden changes. Every lookup succeeds on the three replays with the shipped unitsInfo.csv (Alcyone's two Shield Battery deaths at 7:48 and 14:33 find the row; no Rich Extractor dies on any of them), and a found cost is the same number as before, only taken one line earlier. No entry block.


### A battle records the killer of every big unit it loses (CR-072; Stefan's D2a; no golden changes)

The battle sets its count of big units lost to numbers and, a few lines later, resets it to lists (`analysis/battle.py`, the fork's code), so adding one big-unit loss raised for every death of 3 supply or more. The catch-all error handler hid the failure after the death and its cost were counted but before its killer was recorded, and printed a false "ERR NO KILLING UNIT" line to the run log: 6 times on Alcyone (RavagerCocoon 8:09, Ravager 8:23, Disruptor 10:15, Immortal 10:18, Oracle 11:05, Void Ray 15:24) and twice on spine (Immortals at 6:50 and 7:12), in both modes. Fix (story CR-072, D2a): the reset is removed, so the count stays a number and the killer is recorded. In place, in both modes, with no ledger id: nothing reads the count or the killer record, so no output changes; only the run log loses those 8 lines. The frozen fork under `legacy/` keeps the bug. Predicted: no golden changes (checked on archived copies of ea178d1 and 02d1019: every output and the three current goldens byte-identical with the fix, in both modes). No entry block.


### BO1: each player's build order, as numbered steps on the nodes (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a, D58a, D59a, D60a, D62b)

The graph shows units by the 10 s window they finished in, and no build order a player could compare with a guide. Fix (story CR-034): every worker, building, unit, upgrade and morph a player started up to 6:00 is a numbered step (P0-2's rules on the analysis's exposed values, CR-021; Leo's 8-loop anchored grouping, one step per line; Leo's supply reading; Rex's chrono rule). Each step goes on the node holding its first unit or its upgrade (D58a); every Building, Upgrade and Units node carries `step #`, `at supply`, `started at` and `steps` (its first step's values, the list only when it holds two or more; 0, 0, 00:00:00 and "" when it holds none, D62b), and `dataTypes` gains their four types (int, int, time[h:m:s], string), after the others, none of which changes. Each Player node's description gets, after one blank line, "Build order to 6:00 (supply, time, item):" and one line per step. Every building morph of the game becomes a Building node of its result at its start (change - morph time; D53b): on Alcyone lilTiGGer's Lair (5:06, also step 39), Hive and Greater Spire, and blacksquall's 14 Warp Gates, as Building-114 to Building-130 in start order, after the last Building node. The workbook-faithful goldens do not change (the steps come with the graph fixes and the export fix `BO1`, both off there).

Predicted before the change from today's goldens and Leo's layout note (`.scratch/plan/streams/leo-cr034.md` §2; derived with `.scratch/morgan/cr-034/predict_entries.py`): the morph nodes open two empty windows of the compressed timeline, w43 (7:10-7:20, two Warp Gates) and w75 (12:30-12:40, one), so every item in a later window moves +2.5 on x (+5.0 after w75), with its clock, and two clock pairs are added; blacksquall's unit in w63 moves outwards on y (the BaU pad of the three Warp Gates there). Leo wrote his row counts on the goldens before CR-023 P10b, which had already added two rows: on today's goldens the compressed timeline goes from 85 to 87 rows and its last x from 210 to 215. Linear: no x change; the w63 pad and two clock pairs. Battles: no shift change (Leo, checked). Supply blocks: none of today's spans w43 or w75, so none widens.

```json
{"entry": "BO1-view", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "923ea1221356c892f3b660cc67944f9099ded0b5ca6d5247eacc10c88c493e10", "changes": [{"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": ["Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```

```json
{"entry": "BO1-snap-compressed", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "fbb9a508e1b65e8afddbef42c9607bac57c8bcb44a1ec884a90c624f27b563dd", "changes": [{"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"type": "Ability"}, "fields": ["position.x"], "count": 191}, {"select": {"type": "Battle"}, "fields": ["position.x"], "count": 19}, {"select": {"type": "Building"}, "fields": ["position.x"], "count": 66}, {"select": {"type": "Chat"}, "fields": ["position.x"], "count": 1}, {"select": {"type": "Initiated"}, "fields": ["position.x"], "count": 3}, {"select": {"type": "Stats"}, "fields": ["position.x"], "count": 16}, {"select": {"type": "Supply Block"}, "fields": ["position.x"], "count": 3}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 83}, {"select": {"type": "Upgrade"}, "fields": ["position.x"], "count": 6}, {"select": {"type": "image"}, "fields": ["position.x"], "count": 80}], "added": ["<clock:12-40.png>#1#1", "<clock:12-40.png>#2#1", "<clock:7-20.png>#1#1", "<clock:7-20.png>#2#1", "Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```

```json
{"entry": "BO1-snap-linear", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "6b21c279242b9a555afa3771458c46422796aa6fec90de38e14261466dcb9799", "changes": [{"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 1}], "added": ["<clock:12-40.png>#1#1", "<clock:12-40.png>#2#1", "<clock:7-20.png>#1#1", "<clock:7-20.png>#2#1", "Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```


### BO1b: BO1's two snapshot entries, restated on what the change made (CR-034; supersedes `BO1-snap-compressed` and `BO1-snap-linear`)

The regenerated snapshots differ from BO1's prediction in three ways; `BO1-view` holds as written. The behaviour is the layout's own (no layout code changed); the prediction was wrong:

- **One new row, not two.** The last of the 12:18-12:30 Warp Gates changes type at loop 16958, so it starts at 750.05 s (change - 7 s). The layout floors a start to its second (G11), so it is at 12:30, the end of window 74 (740-750 s], an occupied row, not w75. Only w43 (7:10-7:20, two Warp Gates at 7:14) is a new row: compressed rows 70 -> 71 clock rows, last x 210 -> 212.5, one clock pair added (7-20); every item after w43 moves +2.5 on x and none +5.0.
- **The w43 row takes the units buffered there.** Leo's table says so for the compressed timeline; it happens in the linear one too. lilTiGGer's 9 Drones (Units-88) and blacksquall's 3 Probes (Units-89), which sat stacked in the 7:20-7:30 row, move to their own stacks (compressed: +2.5 on x; both: back to the first stack places on y); in the linear timeline Units-85 to Units-87 (7:20) move from the 7:30 slot to the 7:20 row, -2.5 on x.
- **The w63 item that moves outwards is blacksquall's Charge upgrade (Upgrade-8), not a unit:** the two Warp Gates of w63 that start before it (10:33, 10:34) stack under it, so it moves +2.1 on y in both timelines. That is the +2.1 Leo predicted for the w63 pad.

Nothing else differs: no size changes (no supply block spans w43), no battle moves on y, the 17 morph nodes and 293 step-property changes as listed. The records are paired by ID (a `renumber` spec on Building with the key `ID` and no ID changed): the plain sequence alignment pairs the wrong records once 17 nodes are inserted and 478 move. Derived from the regenerated documents with the checker's own functions (`.scratch/morgan/cr-034/actual_entries.py`); reported to Leo to confirm.

```json
{"entry": "BO1b-snap-compressed", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b); restated on the regenerated snapshots", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "fbb9a508e1b65e8afddbef42c9607bac57c8bcb44a1ec884a90c624f27b563dd", "renumber": [{"type": "Building", "key": ["ID"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}], "changes": [{"select": {"type": "Ability"}, "fields": ["position.x"], "count": 193}, {"select": {"type": "Battle"}, "fields": ["position.x"], "count": 19}, {"select": {"type": "Building"}, "fields": ["position.x"], "count": 69}, {"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"type": "Chat"}, "fields": ["position.x"], "count": 1}, {"select": {"type": "Initiated"}, "fields": ["position.x"], "count": 3}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"type": "Stats"}, "fields": ["position.x"], "count": 18}, {"select": {"type": "Supply Block"}, "fields": ["position.x"], "count": 3}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 85}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["position.x", "position.y"], "count": 7}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}, {"select": {"type": "image"}, "fields": ["position.x"], "count": 80}], "added": ["<clock:7-20.png>#1#1", "<clock:7-20.png>#2#1", "Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```

```json
{"entry": "BO1b-snap-linear", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b); restated on the regenerated snapshots", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "6b21c279242b9a555afa3771458c46422796aa6fec90de38e14261466dcb9799", "renumber": [{"type": "Building", "key": ["ID"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}], "changes": [{"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 5}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["position.y"], "count": 1}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}], "added": ["<clock:7-20.png>#1#1", "<clock:7-20.png>#2#1", "Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```

- BO1b correction (Leo's check of e9af05a, `.scratch/plan/streams/leo-cr034-delta-check.md`; Rex's review): the sentence "That is the +2.1 Leo predicted for the w63 pad" above is withdrawn. Upgrade-8 (Charge, 10:35, blacksquall) moves +2.1 on y because the two Warp Gates of w63 that start before it (10:33, 10:34) take the stack places under it (k1 -> k3, 2 x 1.05); the w63 pad Leo predicted does not happen (the B stack holds 5, the free limit). It equals that pad only by coincidence. Leo confirmed all three BO1b points. Units: BO1 counted row slots (85), BO1b clock rows (70 -> 71); both are the same timeline (85 -> 86 slots).


### BO1c: the steps' research times by upgrade id; a step no node holds is logged (CR-034 review round 2; D63a; no golden changes)

The steps looked an upgrade's research time up by its exact id in upgradesInfo.csv, whose rows are partly ids (`WarpGateResearch`) and partly display names (`Glial Reconstitution`, `Melee Attacks Level 1`), with `ProtossGroundArmorLevelN` where the replay writes `ProtossGroundArmorsLevelN`, and `overlordspeed` named only as `Pneumatized Carapace`. A missed id had its start estimated at its finish (D60a), so on spine `overlordspeed` became a step at its finish (5:21) under its raw id. Fix (Stefan's D63a): the time is looked up by id, then by the id squashed to letters and digits against the squashed row names, without a leading `Evolve`, with `Armors` read as `Armor`, and through a small alias table (data, like `UNIT_ALIASES`: the Zerg attack and carapace levels, `overlordspeed`); a step named by a display-name row takes that name. An id still not found keeps D60a (logged, start at its finish). A step that no node holds (a unit morph, a cancelled building, an upgrade the layer made no Upgrade node for) is logged in the run log. Predicted: no golden changes. Every Alcyone upgrade the new lookup finds (Glial Reconstitution, Muscular Augments, Grooved Spines, the Zerg levels, Pneumatized Carapace, Anabolic Synthesis, the Protoss armour levels) finishes after 7:26 and starts after 6:00, and the legacy layer's Upgrade nodes are unchanged; spine has no current goldens (its step list changes: `overlordspeed` 5:21 becomes Pneumatized Carapace at its start, and Glial Reconstitution becomes a step).


### BO1d: BO1 restated on the goldens after CR-023 F2/F2b (CR-034 landing)

CR-023's F2 and F2b land on cr-batch-2026-10 before CR-034, so the merge of cr-batch-2026-10 (33b8df9) into cr-034-my-build-as-steps keeps the batch's goldens, which lack BO1; `BO1-view`, `BO1b-snap-compressed` and `BO1b-snap-linear` have the pre-F2 bases and can no longer apply. BO1d restates them unchanged on the batch's goldens: the same step properties, Player descriptions, `dataTypes`, the 17 morph nodes and, in the snapshots, the same moves and clock pair, paired by ID as in BO1b. F2 and F2b change only `total at time` on Units-162, Units-169 and Units-92, a field BO1 does not touch, so the two do not meet. The regeneration follows in its own commit.

```json
{"entry": "BO1d-view", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b); restated on the goldens after CR-023 F2/F2b", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "02d86ed1da956510d729c2c82bff8e6218a465cafd6791d36c4bb630d5b8dcc5", "changes": [{"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": ["Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```

```json
{"entry": "BO1d-snap-compressed", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b); restated on the goldens after CR-023 F2/F2b", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "03631dc7a3bd881e35feb82b1badf29cfe18f0827a8991e1ebfebe7a1b97b35e", "renumber": [{"type": "Building", "key": ["ID"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}], "changes": [{"select": {"type": "Ability"}, "fields": ["position.x"], "count": 193}, {"select": {"type": "Battle"}, "fields": ["position.x"], "count": 19}, {"select": {"type": "Building"}, "fields": ["position.x"], "count": 69}, {"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"type": "Chat"}, "fields": ["position.x"], "count": 1}, {"select": {"type": "Initiated"}, "fields": ["position.x"], "count": 3}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"type": "Stats"}, "fields": ["position.x"], "count": 18}, {"select": {"type": "Supply Block"}, "fields": ["position.x"], "count": 3}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 85}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["position.x", "position.y"], "count": 7}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}, {"select": {"type": "image"}, "fields": ["position.x"], "count": 80}], "added": ["<clock:7-20.png>#1#1", "<clock:7-20.png>#2#1", "Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```

```json
{"entry": "BO1d-snap-linear", "task": "CR-034", "defect": "BO1 the build order is not in the graph (CR-034, S2-1; D47a, D48a, D49b, D52a, D53b, D57a-D62b); restated on the goldens after CR-023 F2/F2b", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "8d1d15f9eabe32f75752cc3e36e56a802c322a939251b9ae04ec67be246aef47", "renumber": [{"type": "Building", "key": ["ID"], "retype": {}, "merged": {}, "ids_changed": 0, "links_dropped": 0}], "changes": [{"select": {"type": "Building"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 113}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"type": "Units"}, "fields": ["position.x", "position.y"], "count": 5}, {"select": {"type": "Units"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["position.y"], "count": 1}, {"select": {"type": "Upgrade"}, "fields": ["properties.step #", "properties.at supply", "properties.started at", "properties.steps"], "count": 8}], "added": ["<clock:7-20.png>#1#1", "<clock:7-20.png>#2#1", "Building-114#1", "Building-115#1", "Building-116#1", "Building-117#1", "Building-118#1", "Building-119#1", "Building-120#1", "Building-121#1", "Building-122#1", "Building-123#1", "Building-124#1", "Building-125#1", "Building-126#1", "Building-127#1", "Building-128#1", "Building-129#1", "Building-130#1"], "removed": []}
```


### Every node of a type carries the same properties: a blank player or target is written as "", and a mixed type stops the export (CR-063; D5a, D3a, D4a; no golden changes)

Mindshare refuses a whole import when two nodes of one type carry different properties ("node 'Building-4' has different parameters than node 'Building-1' but the same type: 'Building'"). The view (`export/view.py`, `node_view`, after the workbook's `ScReplayNode.GetView`) left a node's `player` out when it was blank, and an Ability's `target` likewise, so a replay with a blank player name or a targetless Ability would come out mixed. Fix (story CR-063): `time` and `player` (every type but Game and Player) and an Ability's `target` are always written, a blank one as `""`, in the same place as before (`time`, `player` first; `target` last on an Ability). The fill applies to the workbook-faithful document too, not as an export fix (D4a): a deliberate departure from the old workbook, whose frozen VBA port (`tests/reference/vba_view/`) is unchanged. And `build_document` now checks, per node type, that every node carries the same property names in the same order, and raises a ValueError naming the type, two of its nodes and the property that differs, before anything is written (properties only, not `images`, D5a).

The import check (AC-3; Vera, 2026-11-06, Stefan's local Mindshare) accepted a blank target and a blank player, and a Battle with and without a picture, with no "different parameters" error. One side effect, cosmetic: a blank player adds an empty option to that type's player list in Mindshare's node editor; only a replay with a blank player name has it. A `time` is never blank (the Node model refuses a node without one), so writing it always changes nothing.

Predicted: no golden changes. No node of any golden has a blank or missing time, player or target, and no type is mixed in any of them (checked at 144e561 on the six Alcyone JSON goldens and the Alcyone and spine model goldens, and on the four documents the code builds from Alcyone and spine), so every node is written with the same keys and values as before. No entry block.


### The harassment, scouting, inject-delay and spare-energy nodes sit in lanes along the timeline, not on the side grid (CR-073; D6a, D7a, D8a, D9a, D1a, D2b)

The 59 nodes of these four types sat on the block beside the timeline (spec §5.11) with no link to when they happened. CR-073 gives each type a lane on its player's side, beyond the units and beyond the band reserved for the Scouting Gap rail (D8a: "outside, new lines on top and bottom"): an events lane with the scouting and harassment cards at their start column, then an inject-delay lane and a spare-energy lane with bars over their period (D7a), 1.0 high (D1a). A harassment card sits on the attacker's side (D2b): the opponent of the player who lost the workers; the node's `player` property is unchanged. The lanes never occupy a window, so no column is added and nothing else moves. Cards and bars of one lane and side that would cover each other are stacked, levels chosen on the compressed columns and used in both timelines (Leo's Algorithm notes, CR-073).

Predicted independently by Leo before the change (`.scratch/leo/cr-073/prediction-h1_0-attacker.json`, bar height 1.0, harassment on the attacker's side), copied here unchanged: `position` of the 59 nodes (13 Harrasment, 9 Scouting, 16 Energy Excess, 21 Inject Delay) and `size` of the 37 bars, in both current snapshots; nothing else. Each entry's `expected` holds the predicted value per node (rounded to 6 decimals; the export writes 4). G-VIEW-current, the frozen goldens and the spine goldens do not change.

```json
{"entry": "TL1-snap-compressed", "task": "CR-073", "defect": "TL1 the harassment, scouting, inject-delay and spare-energy nodes sit on the side grid, not at their moment (CR-073; D6a, D7a, D8a, D9a, D1a, D2b)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "27a38bdd62840ff57d2cf0cc95c645c59d0ac7d961ca0099501d7fe4d9933bcb", "changes": [{"select": {"type": "Harrasment"}, "fields": ["position"], "count": 13}, {"select": {"type": "Scouting"}, "fields": ["position"], "count": 9}, {"select": {"type": "Energy Excess"}, "fields": ["position", "size"], "count": 16}, {"select": {"type": "Inject Delay"}, "fields": ["position", "size"], "count": 21}], "added": [], "removed": [], "expected": {"Harrasment-1": {"position": [77.5, 22.4]}, "Harrasment-2": {"position": [97.5, 22.4]}, "Harrasment-3": {"position": [97.5, -20.5]}, "Harrasment-4": {"position": [130.0, 22.4]}, "Harrasment-5": {"position": [130.0, 23.45]}, "Harrasment-6": {"position": [162.5, 22.4]}, "Harrasment-7": {"position": [185.0, 22.4]}, "Harrasment-8": {"position": [180.0, -20.5]}, "Harrasment-9": {"position": [182.5, -20.5]}, "Harrasment-10": {"position": [182.5, -21.55]}, "Harrasment-11": {"position": [185.0, -20.5]}, "Harrasment-12": {"position": [190.0, -20.5]}, "Harrasment-13": {"position": [197.5, -20.5]}, "Energy Excess-2": {"position": [23.75, -26.25], "size": [5.0, 1.0]}, "Energy Excess-6": {"position": [105.0, -26.25], "size": [7.5, 1.0]}, "Energy Excess-7": {"position": [107.5, -27.3], "size": [12.5, 1.0]}, "Energy Excess-8": {"position": [120.0, -28.35], "size": [32.5, 1.0]}, "Energy Excess-9": {"position": [122.5, -26.25], "size": [27.5, 1.0]}, "Energy Excess-12": {"position": [155.0, -26.25], "size": [27.5, 1.0]}, "Energy Excess-13": {"position": [158.75, -27.3], "size": [20.0, 1.0]}, "Energy Excess-14": {"position": [175.0, -28.35], "size": [22.5, 1.0]}, "Energy Excess-0": {"position": [2.5, 27.1], "size": [7.5, 1.0]}, "Energy Excess-1": {"position": [15.0, 27.1], "size": [7.5, 1.0]}, "Energy Excess-3": {"position": [45.0, 28.15], "size": [22.5, 1.0]}, "Energy Excess-4": {"position": [61.25, 28.15], "size": [5.0, 1.0]}, "Energy Excess-5": {"position": [61.25, 27.1], "size": [65.0, 1.0]}, "Energy Excess-10": {"position": [138.75, 27.1], "size": [5.0, 1.0]}, "Energy Excess-11": {"position": [105.0, 29.2], "size": [102.5, 1.0]}, "Energy Excess-15": {"position": [181.25, 27.1], "size": [10.0, 1.0]}, "Inject Delay-0": {"position": [46.25, -23.9], "size": [10.0, 1.0]}, "Inject Delay-1": {"position": [50.0, -22.85], "size": [17.5, 1.0]}, "Inject Delay-2": {"position": [58.75, -23.9], "size": [10.0, 1.0]}, "Inject Delay-3": {"position": [76.25, -23.9], "size": [10.0, 1.0]}, "Inject Delay-4": {"position": [77.5, -22.85], "size": [22.5, 1.0]}, "Inject Delay-5": {"position": [101.25, -22.85], "size": [15.0, 1.0]}, "Inject Delay-6": {"position": [93.75, -24.95], "size": [30.0, 1.0]}, "Inject Delay-7": {"position": [108.75, -23.9], "size": [20.0, 1.0]}, "Inject Delay-8": {"position": [120.0, -22.85], "size": [7.5, 1.0]}, "Inject Delay-9": {"position": [132.5, -24.95], "size": [7.5, 1.0]}, "Inject Delay-10": {"position": [127.5, -23.9], "size": [17.5, 1.0]}, "Inject Delay-11": {"position": [130.0, -22.85], "size": [12.5, 1.0]}, "Inject Delay-12": {"position": [146.25, -22.85], "size": [10.0, 1.0]}, "Inject Delay-13": {"position": [158.75, -23.9], "size": [20.0, 1.0]}, "Inject Delay-14": {"position": [162.5, -24.95], "size": [12.5, 1.0]}, "Inject Delay-15": {"position": [162.5, -22.85], "size": [22.5, 1.0]}, "Inject Delay-16": {"position": [177.5, -23.9], "size": [7.5, 1.0]}, "Inject Delay-17": {"position": [187.5, -23.9], "size": [7.5, 1.0]}, "Inject Delay-18": {"position": [186.25, -22.85], "size": [25.0, 1.0]}, "Inject Delay-19": {"position": [197.5, -23.9], "size": [12.5, 1.0]}, "Inject Delay-20": {"position": [208.75, -22.85], "size": [5.0, 1.0]}, "Scouting-0": {"position": [20.0, -20.5]}, "Scouting-1": {"position": [20.0, -21.55]}, "Scouting-2": {"position": [32.5, -20.5]}, "Scouting-3": {"position": [52.5, -20.5]}, "Scouting-4": {"position": [52.5, -21.55]}, "Scouting-8": {"position": [127.5, -20.5]}, "Scouting-5": {"position": [42.5, 22.4]}, "Scouting-6": {"position": [42.5, 23.45]}, "Scouting-7": {"position": [42.5, 24.5]}}}
```

```json
{"entry": "TL1-snap-linear", "task": "CR-073", "defect": "TL1 the harassment, scouting, inject-delay and spare-energy nodes sit on the side grid, not at their moment (CR-073; D6a, D7a, D8a, D9a, D1a, D2b)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "3c320b95032642a035f7c1cc5da06d5ca44944b336222983e654f96d76e528b6", "changes": [{"select": {"type": "Harrasment"}, "fields": ["position"], "count": 13}, {"select": {"type": "Scouting"}, "fields": ["position"], "count": 9}, {"select": {"type": "Energy Excess"}, "fields": ["position", "size"], "count": 16}, {"select": {"type": "Inject Delay"}, "fields": ["position", "size"], "count": 21}], "added": [], "removed": [], "expected": {"Harrasment-1": {"position": [95.0, 22.4]}, "Harrasment-2": {"position": [115.0, 22.4]}, "Harrasment-3": {"position": [115.0, -20.5]}, "Harrasment-4": {"position": [150.0, 22.4]}, "Harrasment-5": {"position": [150.0, 23.45]}, "Harrasment-6": {"position": [190.0, 22.4]}, "Harrasment-7": {"position": [212.5, 22.4]}, "Harrasment-8": {"position": [207.5, -20.5]}, "Harrasment-9": {"position": [210.0, -20.5]}, "Harrasment-10": {"position": [210.0, -21.55]}, "Harrasment-11": {"position": [212.5, -20.5]}, "Harrasment-12": {"position": [220.0, -20.5]}, "Harrasment-13": {"position": [227.5, -20.5]}, "Energy Excess-2": {"position": [32.5, -26.25], "size": [7.5, 1.0]}, "Energy Excess-6": {"position": [123.75, -26.25], "size": [10.0, 1.0]}, "Energy Excess-7": {"position": [126.25, -27.3], "size": [15.0, 1.0]}, "Energy Excess-8": {"position": [138.75, -28.35], "size": [35.0, 1.0]}, "Energy Excess-9": {"position": [142.5, -26.25], "size": [27.5, 1.0]}, "Energy Excess-12": {"position": [178.75, -26.25], "size": [35.0, 1.0]}, "Energy Excess-13": {"position": [182.5, -27.3], "size": [27.5, 1.0]}, "Energy Excess-14": {"position": [203.75, -28.35], "size": [25.0, 1.0]}, "Energy Excess-0": {"position": [2.5, 27.1], "size": [7.5, 1.0]}, "Energy Excess-1": {"position": [18.75, 27.1], "size": [10.0, 1.0]}, "Energy Excess-3": {"position": [58.75, 28.15], "size": [30.0, 1.0]}, "Energy Excess-4": {"position": [78.75, 28.15], "size": [5.0, 1.0]}, "Energy Excess-5": {"position": [75.0, 27.1], "size": [72.5, 1.0]}, "Energy Excess-10": {"position": [158.75, 27.1], "size": [5.0, 1.0]}, "Energy Excess-11": {"position": [123.75, 29.2], "size": [105.0, 1.0]}, "Energy Excess-15": {"position": [210.0, 27.1], "size": [12.5, 1.0]}, "Inject Delay-0": {"position": [61.25, -23.9], "size": [15.0, 1.0]}, "Inject Delay-1": {"position": [63.75, -22.85], "size": [25.0, 1.0]}, "Inject Delay-2": {"position": [76.25, -23.9], "size": [10.0, 1.0]}, "Inject Delay-3": {"position": [93.75, -23.9], "size": [10.0, 1.0]}, "Inject Delay-4": {"position": [95.0, -22.85], "size": [22.5, 1.0]}, "Inject Delay-5": {"position": [120.0, -22.85], "size": [17.5, 1.0]}, "Inject Delay-6": {"position": [112.5, -24.95], "size": [32.5, 1.0]}, "Inject Delay-7": {"position": [127.5, -23.9], "size": [22.5, 1.0]}, "Inject Delay-8": {"position": [140.0, -22.85], "size": [7.5, 1.0]}, "Inject Delay-9": {"position": [152.5, -24.95], "size": [7.5, 1.0]}, "Inject Delay-10": {"position": [147.5, -23.9], "size": [17.5, 1.0]}, "Inject Delay-11": {"position": [150.0, -22.85], "size": [12.5, 1.0]}, "Inject Delay-12": {"position": [166.25, -22.85], "size": [10.0, 1.0]}, "Inject Delay-13": {"position": [182.5, -23.9], "size": [27.5, 1.0]}, "Inject Delay-14": {"position": [186.25, -24.95], "size": [20.0, 1.0]}, "Inject Delay-15": {"position": [186.25, -22.85], "size": [30.0, 1.0]}, "Inject Delay-16": {"position": [205.0, -23.9], "size": [7.5, 1.0]}, "Inject Delay-17": {"position": [216.25, -23.9], "size": [10.0, 1.0]}, "Inject Delay-18": {"position": [215.0, -22.85], "size": [27.5, 1.0]}, "Inject Delay-19": {"position": [227.5, -23.9], "size": [12.5, 1.0]}, "Inject Delay-20": {"position": [240.0, -22.85], "size": [7.5, 1.0]}, "Scouting-0": {"position": [25.0, -20.5]}, "Scouting-1": {"position": [25.0, -21.55]}, "Scouting-2": {"position": [42.5, -20.5]}, "Scouting-3": {"position": [70.0, -20.5]}, "Scouting-4": {"position": [70.0, -21.55]}, "Scouting-8": {"position": [147.5, -20.5]}, "Scouting-5": {"position": [55.0, 22.4]}, "Scouting-6": {"position": [55.0, 23.45]}, "Scouting-7": {"position": [57.5, 24.5]}}}
```


### BC0: spine's current goldens, made at the base (CR-035, Kevin's call 14; no change to any golden)

CR-035's AC12 checks the current output of Alcyone and spine (D7a), but spine had only workbook-faithful goldens (`spine/G-CSV-1.csv`, `spine/Intervals-1.csv`, `spine/models-faithful.json`), so there was no committed "before" for its current output. BC0 adds `spine/G-VIEW-current.json`, `spine/G-SNAP-current-compressed.json` and `spine/G-SNAP-current-linear.json`, made by `scripts/regen_golden.py --replay spine` from the code at af37022 (no product change; the snapshots with the committed fixture clock record, as Alcyone's). Each entry follows the H1 pattern for a new file: its base is the new file's own sha256 and it lists no change, so `check_golden_delta.py --old <file> --new <file>` passes it and every later spine entry has a base. Nothing else changes.

```json
{"entry": "BC0-spine-view", "task": "CR-035", "defect": "BC0 spine has no current golden (CR-035 call 14, AC12, D7a)", "golden": ["spine/G-VIEW-current.json"], "base_sha256": "dc138bb0acaab98cc5721a06eb7b2b7c1ce59eae5147b2f0af4e3f2e01be845d", "changes": [], "added": [], "removed": []}
```

```json
{"entry": "BC0-spine-snap-compressed", "task": "CR-035", "defect": "BC0 spine has no current golden (CR-035 call 14, AC12, D7a)", "golden": ["spine/G-SNAP-current-compressed.json"], "base_sha256": "6906bcd7b18a8823c89b5d723565b515759b23d6056f8bd72fa2f9f73ffa606a", "changes": [], "added": [], "removed": []}
```

```json
{"entry": "BC0-spine-snap-linear", "task": "CR-035", "defect": "BC0 spine has no current golden (CR-035 call 14, AC12, D7a)", "golden": ["spine/G-SNAP-current-linear.json"], "base_sha256": "985f40674972b3dfcc56609f696507a0bf88080c190e49feca09bf18fb0aed77", "changes": [], "added": [], "removed": []}
```


### BO2: each step's supply is the supply at its start, with its range where the replay cannot pin it (CR-035, D2a, D6a; Kevin's call 13)

CR-034 read a step's supply as `floor(food_used)` of the last PlayerStats sample at or before its start; samples come every 160 loops (about 7 s), so the reading trails the real supply by up to 5 by 3:30 and 10 by 6:00 (Leo). Every build order guide we have is graded by supply, so the reading is the verdict. Fix (D2a; Leo's algorithm notes §1, `analysis/build_steps.supply_reading`): R(L) = the last sample at or before the start (12 before the first) plus every visible supply change strictly between that sample and the start (a unit's supply at its start; -1 for a Zerg structure's Drone; morph differences; deaths), rounded down. Where the changes between two samples do not add up to the next sample, the step carries the range its supply lies in (D6a): a new text property `supply range` ("17–19"), "" on every other node (call 13); `at supply` stays an int holding R. The unit supplies come from unitsInfo.csv's Supply column, added to the analysis tables (`TimeTables.supplies`, in the `--with-analysis` object and its schema).

Predicted, listed before the change (both replays, the view and both snapshots, as QA's re-based oracle §1.1-1.3): text only, nothing moves.
- `at supply` changes where a node's first step's supply changes, and `steps` where a listed step's supply changes; the changed steps are Alcyone lilTiGGer 14 of 50 and blacksquall 20 of 68, spine Zerg 22 of 60 and Protoss 23 of 74 (Leo §1). On nodes: Alcyone 12 Building, 17 Units, 1 Upgrade (`at supply`) and 6 Units (`steps`); spine 20 Building, 11 Units, 1 Upgrade and 13 Units.
- `supply range` on every Building, Units and Upgrade node (Alcyone 130, 172, 8; spine 63, 121, 2), filled only on the first step of a ≈ step's node (≈ steps: Alcyone 5 and 18, spine 1 and 21).
- Each Player's description (its build order list) and `dataTypes` (`supply range`: string).
- No position, size, row, clock or ID changes; no node added or removed. The workbook-faithful goldens do not change (no steps there).

```json
{"entry": "BO2-alcyone-view", "task": "CR-035", "defect": "BO2 a step's supply is the last 7-second sample, not the supply at its start (CR-035 D2a, D6a; Kevin's call 13)", "golden": ["alcyone/G-VIEW-current.json"], "base_sha256": "1c78f2071d2c90814f0bff1b28618a007c0ffa344961732439ec3bcb4bc4dd77", "changes": [{"select": {"type": "Building"}, "fields": ["properties.at supply"], "count": 12}, {"select": {"type": "Units"}, "fields": ["properties.at supply"], "count": 17}, {"select": {"type": "Upgrade"}, "fields": ["properties.at supply"], "count": 1}, {"select": {"type": "Units"}, "fields": ["properties.steps"], "count": 6}, {"select": {"type": "Building"}, "fields": ["properties.supply range"], "count": 130}, {"select": {"type": "Units"}, "fields": ["properties.supply range"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.supply range"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "BO2-alcyone-snap-compressed", "task": "CR-035", "defect": "BO2 a step's supply is the last 7-second sample, not the supply at its start (CR-035 D2a, D6a; Kevin's call 13)", "golden": ["alcyone/G-SNAP-current-compressed.json"], "base_sha256": "27a38bdd62840ff57d2cf0cc95c645c59d0ac7d961ca0099501d7fe4d9933bcb", "changes": [{"select": {"type": "Building"}, "fields": ["properties.at supply"], "count": 12}, {"select": {"type": "Units"}, "fields": ["properties.at supply"], "count": 17}, {"select": {"type": "Upgrade"}, "fields": ["properties.at supply"], "count": 1}, {"select": {"type": "Units"}, "fields": ["properties.steps"], "count": 6}, {"select": {"type": "Building"}, "fields": ["properties.supply range"], "count": 130}, {"select": {"type": "Units"}, "fields": ["properties.supply range"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.supply range"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "BO2-alcyone-snap-linear", "task": "CR-035", "defect": "BO2 a step's supply is the last 7-second sample, not the supply at its start (CR-035 D2a, D6a; Kevin's call 13)", "golden": ["alcyone/G-SNAP-current-linear.json"], "base_sha256": "3c320b95032642a035f7c1cc5da06d5ca44944b336222983e654f96d76e528b6", "changes": [{"select": {"type": "Building"}, "fields": ["properties.at supply"], "count": 12}, {"select": {"type": "Units"}, "fields": ["properties.at supply"], "count": 17}, {"select": {"type": "Upgrade"}, "fields": ["properties.at supply"], "count": 1}, {"select": {"type": "Units"}, "fields": ["properties.steps"], "count": 6}, {"select": {"type": "Building"}, "fields": ["properties.supply range"], "count": 130}, {"select": {"type": "Units"}, "fields": ["properties.supply range"], "count": 172}, {"select": {"type": "Upgrade"}, "fields": ["properties.supply range"], "count": 8}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "BO2-spine-view", "task": "CR-035", "defect": "BO2 a step's supply is the last 7-second sample, not the supply at its start (CR-035 D2a, D6a; Kevin's call 13)", "golden": ["spine/G-VIEW-current.json"], "base_sha256": "dc138bb0acaab98cc5721a06eb7b2b7c1ce59eae5147b2f0af4e3f2e01be845d", "changes": [{"select": {"type": "Building"}, "fields": ["properties.at supply"], "count": 20}, {"select": {"type": "Units"}, "fields": ["properties.at supply"], "count": 11}, {"select": {"type": "Upgrade"}, "fields": ["properties.at supply"], "count": 1}, {"select": {"type": "Units"}, "fields": ["properties.steps"], "count": 13}, {"select": {"type": "Building"}, "fields": ["properties.supply range"], "count": 63}, {"select": {"type": "Units"}, "fields": ["properties.supply range"], "count": 121}, {"select": {"type": "Upgrade"}, "fields": ["properties.supply range"], "count": 2}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "BO2-spine-snap-compressed", "task": "CR-035", "defect": "BO2 a step's supply is the last 7-second sample, not the supply at its start (CR-035 D2a, D6a; Kevin's call 13)", "golden": ["spine/G-SNAP-current-compressed.json"], "base_sha256": "6906bcd7b18a8823c89b5d723565b515759b23d6056f8bd72fa2f9f73ffa606a", "changes": [{"select": {"type": "Building"}, "fields": ["properties.at supply"], "count": 20}, {"select": {"type": "Units"}, "fields": ["properties.at supply"], "count": 11}, {"select": {"type": "Upgrade"}, "fields": ["properties.at supply"], "count": 1}, {"select": {"type": "Units"}, "fields": ["properties.steps"], "count": 13}, {"select": {"type": "Building"}, "fields": ["properties.supply range"], "count": 63}, {"select": {"type": "Units"}, "fields": ["properties.supply range"], "count": 121}, {"select": {"type": "Upgrade"}, "fields": ["properties.supply range"], "count": 2}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```

```json
{"entry": "BO2-spine-snap-linear", "task": "CR-035", "defect": "BO2 a step's supply is the last 7-second sample, not the supply at its start (CR-035 D2a, D6a; Kevin's call 13)", "golden": ["spine/G-SNAP-current-linear.json"], "base_sha256": "985f40674972b3dfcc56609f696507a0bf88080c190e49feca09bf18fb0aed77", "changes": [{"select": {"type": "Building"}, "fields": ["properties.at supply"], "count": 20}, {"select": {"type": "Units"}, "fields": ["properties.at supply"], "count": 11}, {"select": {"type": "Upgrade"}, "fields": ["properties.at supply"], "count": 1}, {"select": {"type": "Units"}, "fields": ["properties.steps"], "count": 13}, {"select": {"type": "Building"}, "fields": ["properties.supply range"], "count": 63}, {"select": {"type": "Units"}, "fields": ["properties.supply range"], "count": 121}, {"select": {"type": "Upgrade"}, "fields": ["properties.supply range"], "count": 2}, {"select": {"type": "Player"}, "fields": ["description"], "count": 2}, {"select": {"ID": "dataTypes"}, "fields": [""], "count": 1}], "added": [], "removed": []}
```


### BC2: the build check's verdict rows, a new golden per replay (CR-035, AC2-AC7, AC10; no change to any other golden)

CR-035 compares each player's steps with a build order guide (`analysis/build_check.py`). Its result per player and replay is kept as a golden of its own (approach §2, form d): `alcyone/build-check.json` and `spine/build-check.json`, made by `scripts/regen_golden.py --golden build-check.json [--replay spine]` with no guide named, so each player gets the closest guide for his matchup (D1a). Each player's entry lists the guide, picked or suggested, the score (an exact fraction), how the steps were graded, every guide occurrence with its verdict, the paired step, the Δ, ≈, the trigger's moment and the done-later start, then the extras and the units counted, not graded; or the reason there is no build check (AC10). The values are checked as literals against QA's oracle in `tests/analysis/test_build_check.py`. Each entry follows the H1 pattern for a new file (BC0): its base is the new file's sha256 and it lists no change. The Mindshare documents do not change: nothing is exported yet.

```json
{"entry": "BC2-alcyone-checks", "task": "CR-035", "defect": "BC2 the build check has no golden (CR-035, approach §2 form d)", "golden": ["alcyone/build-check.json"], "base_sha256": "e57b7b25b653cdbaebc8d6a14490bcf368d278f584db5869cc7261cb2ebe006a", "changes": [], "added": [], "removed": []}
```

```json
{"entry": "BC2-spine-checks", "task": "CR-035", "defect": "BC2 the build check has no golden (CR-035, approach §2 form d)", "golden": ["spine/build-check.json"], "base_sha256": "1b622d3df854ff578a31d9023d88b52b7f66e991d2da5765593323de93713df3", "changes": [], "added": [], "removed": []}
```
