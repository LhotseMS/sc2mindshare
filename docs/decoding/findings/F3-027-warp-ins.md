# F3-027: warp-ins cannot be tied to one WarpGate (CR-062)

**Status:** hypothesis **refuted** on the three replays: the replay does not record which WarpGate warped a unit in. 2026-10-18, Morgan.
Probes (read only, orchestrator `.scratch/stream3/`): `e7_warp_probe.py` (commands against unit inits), `e7_warp_selection.py` (sc2reader's ContextLoader and SelectionTracker).

## Hypothesis

A warped-in unit (a `UnitInitEvent` then a `UnitDoneEvent`, with no birth and so no creator, F3-024) can be tied to the WarpGate that warped it in, through the warp command.

## Measured

| | alcyone | spores | spine |
|---|---|---|---|
| Warp-ins (unit inits of Zealot, Stalker, Adept, Sentry, High Templar, Dark Templar) | 58 | 28 | 38 |
| New `WarpIn<Unit>` commands (Adepts use `TrainAdept`, not counted here) | 14 | 8 | 11 |
| Latest point command before a warp-in is a retarget | 46 | 20 | 22 |
| WarpGates in the active selection at that command: exactly 1 | 0 | 0 | 1 |
| ... 2 | 8 | 4 | 1 |
| ... 3 or more | 50 | 24 | 36 |

- The warp command is a target-point command that names the unit type and the point, but not a gate: it is issued to the whole selection, and the game picks the gate. Further warp-ins from the same hotkey press are retargets (sc2reader names their ability `RightClick`, because a retarget carries none).
- The command's "other unit" field is never set (F3-004), and no tracker event reports a WarpGate's cooldown or state.
- The selection at the command (sc2reader's SelectionTracker) holds 2 or more WarpGates for 123 of the 124 warp-ins. Only one spine warp-in has a single gate selected.
- Where the latest earlier command is a `WarpIn<Unit>` command, the unit's init point lies within about 3 map units of its target point: that ties a warp-in to its command, not to a gate.

## What can be said instead

- Per player: warp-in counts, unit types and loops (the unit inits), and the command that placed each one (loop, point, type).
- Per warp-in: the candidate WarpGates (the gates in the selection at the command), almost always more than one.

Per-gate counts would need either the engine (CR-051/CR-052, parked) or the selection order rule the client uses to pick a gate, which is not in the replay and is not measured here. No decoder is added: an attribution that is right for 1 of 124 warp-ins would only be a guess elsewhere.
