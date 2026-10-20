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
