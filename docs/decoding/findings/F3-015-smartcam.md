# F3-015: `replay.smartcam.events` (CR-049, time-boxed)

**Status:** framing partly found, meaning **unknown**; the "battle hints" hypothesis is **refuted**. 2026-10-18, Morgan.

## What was tried (read-only probes in the orchestrator's `.scratch/stream3/`: `smartcam_probe.py`, `smartcam_loops.py`)

| # | Hypothesis | Test | Result |
|---|---|---|---|
| 1 | Bit-packed like the game and message streams (loop delta, user id, event id, payload) | Decode the first event header with s2protocol's `BitPackedDecoder` and the replay's protocol | **Refuted**: the first user id reads as 4 (only 0, 1 and 16 exist) |
| 2 | The stream carries game loops | Longest non-decreasing chain of little-endian u32 fields `≤` the game's loop count with a zero high half | **Supported**: Alcyone 786 loop fields from 420 to 22238 (the game has 22369 loops); spine 269 fields from 285 to 14738 |
| 3 | Fixed record bodies between loops | Body lengths between consecutive loop fields | Alcyone: 5 bytes ×193, 8 ×190, 9 ×183, 20 ×194, 12 ×24, 11 ×1; spine similar. Bodies are small groups of a count (u16, mostly 1–7), a u16 value (mostly 0x0340–0x046c), and a small byte |
| 4 | The u16 values are unit or ability ids | Look them up in the 92440 datapack | **Refuted**: they resolve to bridges, weapons and doodads (`AiurLightBridgeNW10`, `PhysicsKnot`, ...) or to nothing |
| 5 | The loops mark "interesting moments" (battles) for the observer camera | Share of loop fields inside the 30 battle windows of Intervals-1 | **Refuted**: 30.3 % inside windows that cover 30.5 % of the game (uniform); for comparison 51.4 % of unit deaths fall inside them |

## What is left open

The meaning of the bodies (a coordinate encoding, a camera hint list per player, or client UI state) needs either engine replay ground truth (CR-052) or a controlled replay (Stefan, stream 3 Q2). The member holds no player names; nothing from it is exported.
