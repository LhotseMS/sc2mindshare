# F3-021: unit data sources on this Mac, for `gamedata/` (CR-053, T3-13)

**Status:** analysis done; **the source choice is open (Stefan, A6)**. No loader is built yet. 2026-10-18, Morgan.
Probe (read only, orchestrator `.scratch/stream3/gamedata_probe.py`).

## Sources available without a download

| Source | Licence | Costs, supply | Build times | Per base build |
|---|---|---|---|---|
| `MS SC/unitsInfo.csv` (Stefan's sheet, 128 rows) | not stated; the notation (`30 (20)`, `varies`, `-`) looks like Liquipedia's, which is CC BY-SA 3.0 | yes, **incremental** (a morph's own cost: Lair 150/100) | yes, seconds, some with two values (`30 (20)`: gateway and warp gate) | no (one patch, not named) |
| sc2reader 1.9.0 `data/unit_info.json` (part of the pinned dependency) | MIT | yes, **cumulative** (a morph includes what it came from: Lair 500 = 300 + 50 drone + 150) | no | no |
| The installed StarCraft II client's game data (`/Applications/StarCraft II/SC2Data`) | Blizzard's EULA | in CASC archives | in CASC archives | yes |

The client's data would be the only per-build source, but reading CASC needs a third-party library (not standard library) and its licence terms are Blizzard's; both are outside what this task may decide. A public per-build dataset (for example the SC2 Techtree JSON) needs a download and a licence check, which only Stefan can approve.

## Diff of the two local sources for the units in the three replays

104 unit types appear in the three replays (players' births, inits and type changes). 65 are in both sources, 9 only in sc2reader (cocoons, burrowed and uprooted forms), 3 only in the sheet (`Changeling`, `Larva`, `ShieldBattery`), 27 in neither (beacons, eggs, effects such as `AdeptPhaseShift` and `DisruptorPhased`, and `ExtractorRich`).

After the cumulative/incremental difference (every Zerg building differs by the drone's 50 minerals; Lair, Hive, Greater Spire, Overseer, Ravager, Baneling and Brood Lord by their predecessor's cost; Warp Gate by the Gateway's), these values still disagree, which points to different patches:

| Unit | sc2reader | sheet |
|---|---|---|
| Immortal minerals | 250 | 275 |
| Disruptor supply | 3 | 4 |
| Tempest minerals / gas / supply | 300 / 200 / 4 | 250 / 175 / 5 |
| Ultralisk minerals | 300 | 275 |
| Warp Prism minerals | 200 | 250 |
| Interceptor minerals | 10 | 15 |
| Robotics Facility minerals | 200 | 150 |
| Robotics Bay minerals / gas | 200 / 200 | 150 / 150 |
| Nydus Network minerals / gas | 200 / 200 | 150 / 150 |

So neither local source can be called correct for builds 81433, 83830 and 92440 without a per-build reference.

## What the loader needs before it can be built

1. **A source decision (Stefan):** (a) the sheet's values as the first data version, with its licence confirmed and the patch it reflects named; (b) a public per-build dataset, downloaded with his OK after a licence check; or (c) the client's own data, with a CASC reader package and his OK on the licence.
2. Then: data files per first base build they apply to (the newest file at or below a replay's base build, as s2protocol does), a standard-library loader, and the diff above as its test, with the incremental or cumulative convention stated.
