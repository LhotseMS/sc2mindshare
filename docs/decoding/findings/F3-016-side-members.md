# F3-016 to F3-019: the small side members and the user options (CR-050, T3-10)

**Status:** framing supported on all three replays; meanings as labelled below. 2026-10-18, Morgan.
**Corpus (E1, CR-056, `E1-corpus.md`):** F3-016 holds on 42 of 45 corpus replays; the 3 others are vs-AI games, where the resume loop is the human's last dialog action, 45 to 95 loops before the leave. F3-017 holds on all 288 corpus replays with this framing. F3-018 holds on 95 of 101 (sc2reader misreads `base_build_num` on build 23925).
Decoder: `src/sc2mindshare/decoding/side_members.py`; tests: `tests/decoding/test_side_members.py`.
Probes (read only, in the orchestrator's `.scratch/stream3/`): `sidefiles_probe.py`, `sync_probe.py`, `resumable_probe.py`.
The oracle is the raw archive bytes (mpyq) and s2protocol 5.0.16.97563.0's decode of `SUserOptionsEvent`, both independent of sc2reader.

## Members

| Member | alcyone | spores | spine | Framing | Meaning | Confidence |
|---|---|---|---|---|---|---|
| `replay.resumable.events` | 12 B | 12 B | 12 B | u32 little-endian, then the constant `03 10 ff ff ff ff 00 00` | The u32 is one loop before the first `PlayerLeaveEvent` (22368 / 32473 / 14764 against 22369 / 32474 / 14765): the last loop the game could be resumed from (**F3-016**). The tail's meaning is unknown | supported (u32), unknown (tail) |
| `replay.sync.events` | 1745 B | 2535 B | 1155 B | 5-byte records: `01 40`, then a 24-bit little-endian field `(v << 1) \| 1`, `v` 16 bits | One record per 64 game loops: 349 / 507 / 231 records = game loops // 64 (22369, 32511, 14805). The 16 bits of `v` are each set about half the time, so the values look like periodic sync checksums (**F3-017**) | supported (framing, interval), suggested (checksum) |
| `replay.load.info` | 52 B | 52 B | 52 B | all zero | none on ladder replays | supported |
| `replay.sync.history` | 0 B | 0 B | 0 B | empty (listed in `(listfile)`, no bytes) | none | supported |
| `replay.server.battlelobby` | 32121 B | 32089 B | 31965 B | not decoded | Holds both players' names (found as byte strings in all three) and 14 `s2ma` cache-file references | **personal data (F3-019)**: only its size is read out; never exported |

The hypothesis in the plan ("`resumable` and `load.info` are trivial; `sync.events` is periodic checksums") holds for `load.info` and `sync.events`; `resumable.events` is not trivial: it carries the resume loop.

Any other framing raises `FramingError` in the parsers and becomes a warning in `side_members()`, never a guessed value.

## User options (F3-018)

The plan's hypothesis was that the `UserOptionsEvent` flags are guessed (`readers.py:702`). **Refuted for our builds:** that comment is in sc2reader's Wings of Liberty reader (`GameEventsReader_15405`). From `GameEventsReader_38215` on, which covers 81433, 83830 and 92440, the reader decodes all 14 fields in Blizzard's order, and the values of the fields `UserOptionsEvent` keeps equal s2protocol's on all six players. This agreement is weak evidence on its own (Rex's CR-050 review): every flag has the same value on all six players, so a swapped pair of flags would agree too. Only `base_build_num`, read after the ten flags, varies; it matches on 95 of 101 corpus replays (E1), which confirms the bit layout:

| Field (s2protocol) | sc2reader attribute | Value on all six players |
|---|---|---|
| `m_gameFullyDownloaded` | `game_fully_downloaded` | True |
| `m_developmentCheatsEnabled` | `development_cheats_enabled` | False |
| `m_multiplayerCheatsEnabled` | `multiplayer_cheats_enabled` | False |
| `m_syncChecksummingEnabled` | `sync_checksumming_enabled` | False |
| `m_isMapToMapTransition` | `is_map_to_map_transition` | False |
| `m_debugPauseEnabled` | `debug_pause_enabled` | False |
| `m_baseBuildNum` | `base_build_num` | the replay's base build |
| `m_testCheatsEnabled`, `m_useGalaxyAsserts`, `m_platformMac`, `m_cameraFollow` | decoded, dropped by the event class | False |
| `m_buildNum`, `m_versionFlags` | decoded, dropped | the base build; 0 |
| `m_hotkeyProfile` | decoded, dropped | `<custom>` |

`use_ai_beacons` and `starting_rally` are always None on these builds (the fields are not in the schema).

The dropped fields would need a game-events reader change (the reader seam of CR-044); not done, because the values are constant on our data. `m_hotkeyProfile` is a user-chosen name, so it would count as personal data if it were exposed.

## Exported

`side_members` (member sizes, resume loop, `load_info_all_zero`, the number of sync checksums, warnings) and `user_options` (one row per player) in the decoding JSON. The checksums themselves are not listed, and nothing of `battlelobby` but its size.
