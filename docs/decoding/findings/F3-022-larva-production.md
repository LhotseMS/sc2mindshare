# F3-022: the Zerg production chain, unit to egg to larva to town hall (CR-057, E2)

**Status:** supported: every larva-made unit is attributed to exactly one town hall on the three replays and on the five corpus replays from build 55505 with Zerg production. 2026-10-18, Morgan.
Decoder: `creators.larva_production(replay)` and `creators.larva_use(replay)`; tests: `tests/decoding/test_larva_production.py`.
Oracle: s2protocol's tracker events alone (orchestrator `.scratch/stream3/e2_oracle.py`).

## Rule

A unit born with `LarvaTrain` names its egg as the creator, and the egg has the larva's tag (F3-020). That larva's own birth names the Hatchery, Lair or Hive that spawned it. So: unit → larva tag → the larva's creator. The town hall's type is taken at the unit's birth loop (a Hatchery that later becomes a Lair is a Hatchery for its earlier units).

## Measured

| | alcyone | spores | spine | corpus (5 replays from 55505) |
|---|---|---|---|---|
| Larva-made units | 382 | 397 | 171 | 912 |
| Attributed to one town hall | 382 | 397 | 171 | 912 |
| Town halls that spawned larvae | 8 | 7 | 3 | |
| Larvae spawned / became an egg | 387 / 322 | 485 / 372 | 169 / 157 | |

Two Zerglings come from one egg, so the units can outnumber the larvae used. On Alcyone the main hatchery made 43 units as a Hatchery, 62 as a Lair and 11 as a Hive; the eighth town hall spawned 12 larvae and none was used.

## Exported

`larva_use`: one row per town hall (player, town hall id, larvae, larvae used, units) in the decoding JSON. The per-unit rows (`larva_production`) are offered to Cam for the larva-use feature. Expired larvae and inject timing are not derived here.
