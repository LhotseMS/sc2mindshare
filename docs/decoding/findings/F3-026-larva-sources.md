# F3-026: natural versus injected larvae per town hall (CR-061)

**Status:** supported on the three replays (rule measured, not taken from game data). 2026-10-18, Morgan.
Decoder: `creators.larva_sources(replay)`; tests: `tests/decoding/test_larva_sources.py`. Oracle: s2protocol's tracker events alone (orchestrator `.scratch/stream3/e6_oracle.py`; probes `e6_larva_probe.py`, `e6_larva_gaps.py`, `e6_runs.py`).

## What was measured

- The first hypothesis, that an inject's larvae are born on one loop, is **refuted**: after loop 0 no two larvae of one hall share a loop.
- The loop gaps between consecutive larva births at one hall have two peaks: **4 loops** (136 on Alcyone, 231 on spores, 42 on spine) and **about 240 loops** (the natural spawn).
- Runs of births at most 4 loops apart have length 1 (179 / 128 / 103), **3** (67 / 110 / 21), and rarely 2 (0 / 8 / 0) or 4 (1 / 2 / 0).
- Every run of 3 or more follows an earlier `SpawnLarva` command (a `TargetUnitCommandEvent` or its retarget) on the same hall.

## Rule

After loop 0, a run of 3 or more births at one hall, at most 4 loops apart, is an **inject pop**: 3 injected larvae, and any further birth in the run is natural. A single birth is natural. A run of exactly 2 is **unclassified** (spores: 8 larvae in 4 runs), never guessed. The 3 larvae at loop 0 are start larvae. **Limit (Rex's review):** a natural larva born up to 4 loops before an inject's larvae joins their run, so that pop is dated up to 4 loops early; the counts stay right.

## Per hall (Alcyone)

The main hatchery had 3 start, 43 natural and 66 injected larvae, with 22 pops (the first at loop 4016) and at most 1970 loops between two pops. Three halls had no inject at all (22, 18 and 18 natural larvae). The full tables for the three replays are pinned in the test.

## For T2-3 (inject uptime)

The pops and the longest interval between pops are free of durations. Uptime itself (the time a hall is under an inject) needs the inject's duration, which is game data (CR-053). The command-to-pop gaps cluster at 625–650 loops but include the queen's walk and repeated clicks, so they are not used as a duration.

## Exported

`larva_sources` in the decoding JSON: one row per hall, with its pop loops.
