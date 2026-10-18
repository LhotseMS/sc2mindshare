# E1: stream 3's findings over the upstream corpus (CR-056)

**Status:** done 2026-10-18, Morgan. Tool: `tools/decoding/corpus_findings.py` (read only); test: `tests/decoding/test_corpus_findings.py` (the counting, pinned on four corpus replays).
Corpus: the 345 replays in `test_replays/` (upstream sc2reader's, builds 15405 to 80949, including co-op and custom games). Never a golden (D5a).

## Summary

| Finding | Checked | Holds | Contradicts | Not applicable | Confidence now |
|---|---|---|---|---|---|
| Parity: `decoding.load` changes nothing sc2reader exposes (game and tracker events equal event by event: class and every plain attribute value, no exemption; re-run after Rex's CR-056 review) | 343 | 343 | 0 | 0 | **confirmed** for builds 15405–80949 |
| F3-009 every exact camera recall matches one slot | 40 | 37 | 3 | 303 | **refined**: a player can save the same point in two slots |
| F3-016 resume loop = first leave − 1 | 45 | 42 | 3 | 298 | supported; in 3 vs-AI games it is the last dialog action instead |
| F3-017 one sync record per 64 loops | 288 | 288 | 0 | 55 | **confirmed** where the framing is the measured one |
| F3-018 `base_build_num` = the replay's base build | 101 | 95 | 6 | 242 | supported from 24247 on; sc2reader misreads 23925 |
| F3-020 creators alive; after loop 0 only Broodlings lack one | 9 | 8 | 1 | 334 | **supported for ladder replays** from build 55505; not for co-op |

Two replays could not be loaded by plain sc2reader either (`bad_unit_ids_1`, `bad_unit_ids_2`: resumed games, `CorruptTrackerFileError`); they are counted apart.

## Contradictions and what they show

- **F3-009** (3 replays): `gameheart/gh_sameteam` (24944) 2 of 187 exact matches are ambiguous, `event_order` (26490) 42 of 291, `5.0.0.80949/... Ocrucius VS Rairden` 35 of 151. The player had the same camera point saved in two slots, so the update cannot tell which slot was pressed. `camera_recalls` reports the lowest such slot; the recall itself is still certain, only the slot is not.
- **F3-016** (3 replays): `3.0.0.38215/third` (−79 loops), `3.1.0/dusktowers` (−95), `3.3.0/ggissue48` (−45). All three are games of one human against the AI, and in each the resume loop is the loop of the human's last `DialogControlEvent` (probably the leave or surrender dialog), not the loop before the leave. The 42 other replays with the member and a leave hold. Not applicable: the member is absent before 23925, and its framing differs on 55 replays (45 of builds 23925–26490 and 10 later ones).
- **F3-017**: no contradiction. The framing differs (so not applicable) on 54 replays of builds 24247–32283; every other build, back to 15405, has `game loops // 64` records.
- **F3-018** (6 replays, all build 23925): sc2reader reads `base_build_num` 67120825 (2²⁶ + 11961) where the build is 23925, which looks like a one-bit misalignment in its reader for that build. s2protocol has no module for 23925 (its 23260 module fails on these replays), so this is not confirmed by the oracle. Our builds (≥ 81433) are unaffected.
- **F3-020** (1 replay): `coop/CoA` (56787), a co-op mission: 34 creators are not alive at the birth loop and many units have no creator after loop 0 (drop pods, Kerrigan's economy drops, Roaches, Hydralisks...). Co-op missions spawn units by trigger. On the 8 other replays with creators: after loop 0 only Broodlings lack one (9 and 9), and the creator's owner differs only for Changeling forms (`ChangelingMarineShield` ×3, `ChangelingZealot` ×1) and one `Assimilator → VespeneGeyser` (probably the geyser returning when the assimilator dies). The creator fields exist in Blizzard's schema from build 55505 on; before that no birth has a creator.

## Rerun

    scripts/py-env .venv/bin/python tools/decoding/corpus_findings.py --json <out.json>

(from the project root with absolute paths, as for the other stream 3 gates).
