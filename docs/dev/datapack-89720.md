# Data pack 89720 in the legacy tree (CR-008, T08)

2026-10-18. The fork had dropped upstream's registration of the `89720` unit and ability data (#181), so builds from 89634 on (our Alcyone replay is 92440) were decoded with the `80949` tables. CR-008 restores upstream's two registrations in `sc2reader/resources.py` exactly as in `a7778d0`: `80949` for `80949 <= build < 89634`, `89720` for `89634 <= build`.

**Expected delta, written before the run (TD-3):** about one Ability row (the `MorphToBaneling` command, nameless under 80949) and its links; no unit rows.

**Actual delta: none.** `G-CSV-1` (legacy + 89720) is byte-identical to `G-CSV-0` on Alcyone (and on `200k dmg spine crawler ZvP`, build 83830, which keeps 80949 by design), `Intervals.csv` included.

**Why one row fewer than expected:** the replay's only `MorphToBaneling` command is a `BasicCommandEvent` (checked with the datapack set to `Build 89720`), and the legacy layer makes Ability nodes only from `TargetUnitCommandEvent`s (`SimpleDetector.findSimpleNodes`). The renamed ability never reaches the CSV.

Consequence: the move to the pinned upstream (CR-009 onwards) is held to **zero** difference against `G-CSV-1`, which equals `G-CSV-0`.

Gates: the fork suite is unchanged (72 tests: 65 passed, 4 failed, 3 xfailed); ruff findings on `resources.py` are identical before and after (121, TD-46 rule).
