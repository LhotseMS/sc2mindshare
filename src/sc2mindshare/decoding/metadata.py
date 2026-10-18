"""replay.gamemetadata.json: the client's own summary of a game (CR-043, T3-3).

sc2reader never opens this member. It holds per-player MMR, the client's APM and the result,
plus the exact data version a replay needs to be played back.

Units (TD-30): `duration_game_seconds` is the file's `Duration`, which is in game seconds
(game loops / 16, rounded to the nearest second; real seconds are loops / 22.4). `apm_client` keeps the file's `APM` under a
neutral name: what the client counts and over which minutes is not established yet.

MMR (TD-28, F3-008): this file is the primary source; initData's `scaled_rating` is the
fallback. Both agree for all six players of the three replays. sc2reader's `User.mmr`
turns a missing rating into 0, so it is not used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sc2mindshare.decoding.archive import MemberUnreadable, read_member

MEMBER = "replay.gamemetadata.json"

_TOP_KEYS = {"Title", "GameVersion", "DataBuild", "DataVersion", "BaseBuild", "Duration", "Players"}
_PLAYER_KEYS = {"PlayerID", "MMR", "APM", "Result", "SelectedRace", "AssignedRace"}


@dataclass(frozen=True)
class PlayerMetadata:
    player_id: int | None
    mmr: int | None
    apm_client: float | None
    result: str | None
    selected_race: str | None
    assigned_race: str | None
    extra: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class GameMetadata:
    title: str | None = None
    game_version: str | None = None
    data_build: int | None = None
    data_version: str | None = None
    base_build: int | None = None
    duration_game_seconds: int | None = None
    players: tuple[PlayerMetadata, ...] = ()
    extra: tuple[tuple[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_replay(cls, replay: Any) -> GameMetadata:
        try:
            raw = read_member(replay, MEMBER)
        except MemberUnreadable as exc:
            return cls(warnings=(f"{MEMBER} unreadable: {exc}",))
        if raw is None:
            return cls(warnings=(f"{MEMBER} not in archive",))
        return cls.from_json(raw)

    @classmethod
    def from_json(cls, raw: bytes) -> GameMetadata:
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            return cls(warnings=(f"{MEMBER} is not valid JSON: {exc}",))
        if not isinstance(data, dict):
            return cls(warnings=(f"{MEMBER} is not a JSON object",))
        warnings: list[str] = []
        duration = _int(data.get("Duration"))
        if duration is None and data.get("Duration") is not None:
            warnings.append(f"Duration {data.get('Duration')!r} is not a number; read as None")
        players = tuple(_player(p, warnings) for p in data.get("Players", []) if isinstance(p, dict))
        return cls(
            title=_str(data.get("Title")),
            game_version=_str(data.get("GameVersion")),
            data_build=_int(data.get("DataBuild")),
            data_version=_str(data.get("DataVersion")),
            base_build=_int(str(data.get("BaseBuild", "")).removeprefix("Base") or None),
            duration_game_seconds=duration,
            players=players,
            extra=_extra(data, _TOP_KEYS),
            warnings=tuple(warnings),
        )

    def player(self, player_id: int) -> PlayerMetadata | None:
        return next((p for p in self.players if p.player_id == player_id), None)


def _rating(value: Any) -> int | None:
    """A rating is a positive integer; 0 and negatives (e.g. -36400) mean unranked or missing, as upstream reads them."""
    mmr = _int(value)
    return mmr if mmr is not None and mmr > 0 else None


def _player(data: dict[str, Any], warnings: list[str]) -> PlayerMetadata:
    player_id = _int(data.get("PlayerID"))
    mmr = _rating(data.get("MMR"))
    if mmr is None and _int(data.get("MMR")) is not None:
        warnings.append(f"player {player_id}: MMR {data.get('MMR')} is not a rating (unranked or missing); read as None")
    return PlayerMetadata(
        player_id=player_id,
        mmr=mmr,
        apm_client=_float(data.get("APM")),
        result=_str(data.get("Result")),
        selected_race=_str(data.get("SelectedRace")),
        assigned_race=_str(data.get("AssignedRace")),
        extra=_extra(data, _PLAYER_KEYS),
    )


def _extra(data: dict[str, Any], known: set[str]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((k, v) for k, v in data.items() if k not in known))


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class MmrCheck:
    player_id: int
    gamemetadata: int | None
    init_data: int | None

    @property
    def agree(self) -> bool:
        return self.gamemetadata == self.init_data


def _init_data_mmr(player: Any) -> int | None:
    init = getattr(player, "init_data", None) or {}
    return _rating(init.get("scaled_rating"))


def mmr_consistency(replay: Any, meta: GameMetadata) -> tuple[MmrCheck, ...]:
    """Both MMR sources per player, matched by player id (TD-28)."""
    rows = []
    for player in sorted(replay.players, key=lambda p: p.pid):
        from_meta = meta.player(player.pid)
        rows.append(MmrCheck(player.pid, from_meta.mmr if from_meta else None, _init_data_mmr(player)))
    return tuple(rows)


def mmr_by_player(replay: Any, meta: GameMetadata) -> dict[int, int | None]:
    """The MMR to use per player id: gamemetadata.json first, initData's scaled_rating as the fallback."""
    result: dict[int, int | None] = {}
    for player in replay.players:
        from_meta = meta.player(player.pid)
        mmr = from_meta.mmr if from_meta and from_meta.mmr is not None else None
        result[player.pid] = mmr if mmr is not None else _init_data_mmr(player)
    return result
