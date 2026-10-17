"""Export a DecodedReplay as one JSON document (stream 3's own output, additive to stream 1's).

Times stay integer game loops; any value in seconds carries its unit in its name (TD-30).
Keys are sorted and the text ends with a newline, so the output is byte-stable for goldens.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any

from sc2mindshare.decoding.metadata import GameMetadata, PlayerMetadata, mmr_by_player, mmr_consistency

if TYPE_CHECKING:
    from sc2mindshare.decoding import DecodedReplay

FORMAT = "sc2mindshare.decoding/1"


def _player(p: PlayerMetadata) -> dict[str, Any]:
    d = dataclasses.asdict(p)
    d["extra"] = dict(p.extra)
    return d


def _metadata(m: GameMetadata) -> dict[str, Any]:
    d = dataclasses.asdict(m)
    d["players"] = [_player(p) for p in m.players]
    d["extra"] = dict(m.extra)
    d["warnings"] = list(m.warnings)
    return d


def to_dict(decoded: DecodedReplay) -> dict[str, Any]:
    replay = decoded.replay
    chosen = mmr_by_player(replay, decoded.metadata)
    return {
        "format": FORMAT,
        "replay": {"base_build": int(replay.base_build), "game_loops": int(replay.frames)},
        "gamemetadata": _metadata(decoded.metadata),
        "mmr": [
            {
                "player_id": row.player_id,
                "mmr": chosen[row.player_id],
                "gamemetadata": row.gamemetadata,
                "init_data": row.init_data,
                "agree": row.agree,
            }
            for row in mmr_consistency(replay, decoded.metadata)
        ],
        "warnings": list(decoded.warnings),
    }


def to_json(decoded: DecodedReplay) -> str:
    return json.dumps(to_dict(decoded), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
