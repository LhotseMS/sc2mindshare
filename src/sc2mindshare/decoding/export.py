"""Export a DecodedReplay as one JSON document (stream 3's own output, additive to stream 1's).

Times stay integer game loops; any value in seconds carries its unit in its name (TD-30).
Keys are sorted and the text ends with a newline, so the output is byte-stable for goldens.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any

from sc2mindshare.decoding.camera_hotkeys import camera_recalls, camera_saves
from sc2mindshare.decoding.command_flags import command_flag_summary, zoom_events
from sc2mindshare.decoding.command_manager import CommandActivity, command_activity
from sc2mindshare.decoding.control_groups import control_group_activity
from sc2mindshare.decoding.metadata import GameMetadata, PlayerMetadata, mmr_by_player, mmr_consistency
from sc2mindshare.decoding.target_flags import target_flag_summary

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
        "camera_hotkeys": _camera_hotkeys(replay),
        "command_activity": [_activity(pid, a) for pid, a in command_activity(replay).items()],
        "target_flags": _target_flags(replay),
        "command_flags": [
            {"player_id": pid, **dataclasses.asdict(summary)} for pid, summary in command_flag_summary(replay).items()
        ],
        "zoom_events": [{"player_id": pid, "count": n} for pid, n in sorted(zoom_events(replay).items())],
        "control_groups": [
            {"player_id": pid, "kind": kind.name.lower(), "source": source, "count": count}
            for pid, counts in control_group_activity(replay).items()
            for (kind, source), count in sorted(counts.items(), key=lambda kv: (kv[0][0].name, kv[0][1]))
        ],
        "warnings": list(decoded.warnings),
    }


def _target_flags(replay: Any) -> dict[str, Any]:
    summary = target_flag_summary(replay)
    return {
        "by_kind_and_relation": [
            {"kind": kind.value, "relation": relation, "count": count}
            for (kind, relation), count in sorted(
                summary.by_kind_and_relation.items(), key=lambda kv: (kv[0][0].value, kv[0][1])
            )
        ],
        "resolved_in_tracker": {
            kind.value: count for kind, count in sorted(summary.resolved.items(), key=lambda kv: kv[0].value)
        },
        "unknown_flags": {str(flags): count for flags, count in sorted(summary.unknown_flags.items())},
    }


def _activity(pid: int, activity: CommandActivity) -> dict[str, Any]:
    row: dict[str, Any] = {"player_id": pid}
    row.update(dataclasses.asdict(activity))
    row["actions_without_paired_states"] = activity.actions_without_paired_states
    return row


def _camera_hotkeys(replay: Any) -> dict[str, Any]:
    saves = sorted((e for e in camera_saves(replay) if e.player is not None), key=lambda e: e.frame)
    recalls: dict[tuple[int, int], int] = {}
    for recall in camera_recalls(replay):
        recalls[(recall.player_id, recall.slot)] = recalls.get((recall.player_id, recall.slot), 0) + 1
    return {
        "saves": [
            {"game_loop": e.frame, "player_id": e.player.pid, "slot": e.slot, "x": e.saved_x, "y": e.saved_y} for e in saves
        ],
        "recalls": [{"player_id": pid, "slot": slot, "count": count} for (pid, slot), count in sorted(recalls.items())],
    }


def to_json(decoded: DecodedReplay) -> str:
    return json.dumps(to_dict(decoded), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
