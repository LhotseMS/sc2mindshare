# F3-023: the client's APM is not reproduced by counting game events (CR-059, E4)

**Status:** hypothesis **refuted** for every rule family tried (time-boxed). `apm_client` keeps its neutral name (TD-30). 2026-10-18, Morgan.
Probes (read only, orchestrator `.scratch/stream3/`): `e4_apm_probe.py`, `e4_apm_search2.py`, `e4_apm_search3.py`.

## Target

`gamemetadata.json`'s `APM` for the six players: Alcyone 286 / 142, spores 144 / 195, spine 148 / 142. Rule wanted: within ±1 for all six.

## Rules tried, and the best worst-case error of each family

Per player, the events in `player.events` (sc2reader 1.9.0 classes) plus the player's camera saves (CR-044); the window ends at the player's `PlayerLeaveEvent` (or the game's end).

| # | Family | Search | Best worst error (APM) |
|---|---|---|---|
| 1 | Count of a subset of event kinds / minutes | every subset of 16 kinds (camera updates and CommandManagerState included) × real minutes (22.4 loops/s) to the leave, real minutes to the end, game minutes (16 loops/s) | **11.6**, and only by overfitting a subset of 7 kinds |
| 2 | Family 1 without camera updates and CommandManagerState, from a start offset | every subset of 12 kinds × offsets 0–180 s in 10 s steps × real or game minutes × leave or end | **52.5**: every such rule undercounts all six players |
| 3 | Distinct loops with at least one event of the subset | every subset of 14 kinds × real or game minutes | **69.4** |
| 4 | A constant factor on a fixed set | APM / (events per real minute) | the factor varies 0.76–0.90 (all kinds but camera updates) and 1.14–1.33 (without camera updates and CommandManagerState): no constant |

So the client counts more than the user-originated events in the stream (family 2 undercounts), but fewer than all of them including the CommandManagerState events the client generates (family 4's first factor is below 1), and not in a fixed proportion.

## Likely explanations (not tested)

The client may count inputs that leave no game event, or weight events, or count per "action" in its input layer rather than per network event. Settling it needs ground truth: a controlled replay with a known number of actions (stream 3 Q2, Stefan) or the engine (CR-051/CR-052, parked).

## Consequence

The decoding export keeps the file's value as `apm_client`; no APM is computed by stream 3.
