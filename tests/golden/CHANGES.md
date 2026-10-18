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
