# F3-024 and F3-025: production per structure and research, without durations (CR-058, CR-060 part 1)

**Status:** part 1 done 2026-10-18, Morgan. Idle time (E3) and research start times (E5) wait for CR-053's per-build durations; nothing duration-dependent is estimated.
Decoders: `creators.structure_production(replay)`, `research.research_completions(replay)`, `research.research_commands(replay)`. Tests: `tests/decoding/test_structure_production.py`, `tests/decoding/test_research.py`. Oracle for production: s2protocol's tracker events alone (orchestrator `.scratch/stream3/e3_oracle.py`).

## F3-024: production per structure (E3)

A production structure is the creator of a birth whose ability is its own train ability: a name ending in `Train` or starting with `Train` (`NexusTrain`, `GatewayTrain`, `StargateTrain`, `RoboticsFacilityTrain`, `TrainQueen`), never the egg's `LarvaTrain` (larva production is F3-022). Per structure: owner, type when started, started / finished / died loops (sc2reader's unit lifetime, equal to the tracker's init, done and died loops), units trained, first and last unit loop.

| | alcyone | spores | spine |
|---|---|---|---|
| Production structures | 15 | 16 | 8 |
| Units trained by them | 119 | 140 | 75 |

**Gap: warp-ins.** A unit warped in from a WarpGate is not born: it has a `UnitInitEvent` (the warp-in start) and a `UnitDoneEvent`, and no creator. On Alcyone 25 Stalkers, 18 Zealots and 15 High Templar arrive this way, so a Gateway's count stops when it becomes a WarpGate. Attributing warp-ins to a WarpGate would need the warp command in the game events and the selected gate; not done.

**What idle time needs:** each unit's train time for that build (CR-053). With it, a structure's busy intervals are [birth − train time, birth], merged; queued units and chrono boost make this an estimate, which E3 part 2 must state.

## F3-025: research (E5)

- `UpgradeCompleteEvent` is not only research. Each player's unlocked cosmetics (`RewardDance*`, `Spray*`, 11 names) are reported at loop 0, and a `Spray*` entry each time a spray is used in game (27 on Alcyone). `research_completions` leaves them out: 22 / 32 / 4 research completions remain on the three replays.
- A research is queued by a command named `Research*`, `Evolve*` or `Upgrade*`, but `UpgradeTo*` is a morph (`UpgradeToLair`, `UpgradeToHive`): 25 / 35 / 9 commands. Commands outnumber completions: a research can be cancelled, repeated after a cancel, or still running at the end (spine: `ResearchZergMissileWeaponsLevel1` twice, no completion).
- The ability names come from sc2reader's datapack (s2protocol has only ability links).

**What pairing needs:** a map from ability to upgrade, since the names differ (`EvolveMetabolicBoost` completes `zerglingmovementspeed`, `ResearchWarpGate` completes `WarpGateResearch`, `UpgradeGroundWeapons1` completes `ProtossGroundWeaponsLevel1`), and each research's duration. Both are game data, so they wait for CR-053's source decision.

## Exported

`structure_production` (one row per structure) and `research` (`completions` and `commands`, with loop, player and name) in the decoding JSON.
