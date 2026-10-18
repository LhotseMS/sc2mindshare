# F3-020: unit creator attribution from SUnitBornEvent (CR-055, T3-14)

**Status:** supported on all three replays; the hypothesis holds with two refinements. 2026-10-18, Morgan.
**Corpus (E1, CR-056, `E1-corpus.md`):** the creator fields exist from build 55505; 8 of the 9 corpus replays with creators agree (other owners only for Changeling forms and one Assimilator → VespeneGeyser); the co-op mission `coop/CoA` does not (trigger-spawned units). Supported for ladder replays.
Decoder: `src/sc2mindshare/decoding/creators.py` (`creations(replay)`); tests: `tests/decoding/test_creators.py`.
Probe (read only, orchestrator `.scratch/stream3/creator_probe.py`): s2protocol 5.0.16.97563.0 decode of the tracker events, independent of sc2reader.

## What the event carries

`SUnitBornEvent` has `m_creatorUnitTagIndex`, `m_creatorUnitTagRecycle` (both optional) and `m_creatorAbilityName` (optional). sc2reader 1.9.0's tracker reader decodes them as struct fields 7, 8 and 9; its `UnitBornEvent` drops them. The decoder keeps them through the reader seam (a tracker-events reader that lets sc2reader build every event), in a separate store: `replay.tracker_events` is unchanged (tested against a plain sc2reader load).

## Measured

| | alcyone | spores | spine |
|---|---|---|---|
| Births | 1153 | 1579 | 664 |
| With a creator | 896 | 1307 | 448 |
| No creator, loop 0, player 0 (map units) | 179 | 199 | 153 |
| No creator, loop 0, players 1 / 2 (start units) | 29 / 28 | 28 / 29 | 29 / 28 |
| No creator, later | Broodling ×21 | Broodling ×15, ParasiticBombRelayDummy ×1 | Broodling ×6 |
| Creator not alive at that loop | 0 | 0 | 0 |
| Creator owned by another player | 0 | 1 (ChangelingZealot from a Changeling) | 8 (ForceField, neutral, from a Sentry) |

**Refinements of the hypothesis** ("every trained unit names the building or larva and the ability; the only units without a creator are start and map units"):
1. Broodlings (and one Parasitic Bomb dummy) are born without a creator, after loop 0.
2. For Zerg the creator is the **egg**, not the hatchery: a larva is born from a Hatchery, Lair or Hive with an **empty** ability name (`""`), the larva becomes an egg under the same tag (a type change), and the unit is born from that tag with `LarvaTrain`. Attributing a Zerg unit to a structure takes two steps: unit → egg/larva → the larva's own creator.

Other creators on the three replays: `NexusTrain`, `GatewayTrain`, `RoboticsFacilityTrain`, `StargateTrain`, `TrainQueen`, `CarrierHangar` (Interceptors), `BroodLordHangar`, `MorphZerglingToBaneling` (from the BanelingCocoon), `AdeptPhaseShift`, `PurificationNovaTargeted`, `ForceField`, `SpawnChangeling`, `ParasiticBomb`, `ViperParasiticBombRelay`.

## Exported

`creators` in the decoding JSON: counts per (player, creator ability), and births without a creator per (player, at game start). The per-unit rows stay in the API (`creations`), for stream 2's production features (Cam): idle time and queue use per structure, larva use per hatchery.
