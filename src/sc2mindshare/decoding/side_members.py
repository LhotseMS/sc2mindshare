"""The small side members of a replay archive, and the user options (CR-050, T3-10).

sc2reader never opens these members. Measured on the three replays (builds 81433, 83830, 92440):

- ``replay.resumable.events`` (12 bytes): a little-endian u32, then the constant ``03 10 ff ff ff ff
  00 00`` (meaning unknown). The u32 is one game loop before the first PlayerLeaveEvent: the last
  loop the game could be resumed from (finding F3-016).
- ``replay.sync.events``: one 5-byte record per 64 game loops (``game loops // 64`` records), each
  ``01 40`` then a 24-bit little-endian field holding ``(value << 1) | 1`` with a 16-bit value. The
  values look uniformly random, which suggests periodic sync checksums (F3-017; the framing is
  supported, the meaning only suggested).
- ``replay.load.info`` (52 bytes): all zero. ``replay.sync.history``: empty.
- ``replay.server.battlelobby`` (about 32 KB): holds the players' names and cache-file references. It is
  personal data: only its size is ever read out of this module, never its content (F3-019).

Any framing other than the measured one raises :class:`FramingError` inside the parsers and becomes
a warning in :func:`side_members`, never a guess.

User options (F3-018): for every build since 38215, sc2reader's reader decodes all of
SUserOptionsEvent's fields as Blizzard's schema has them (the "guessing" comment at its line 702 is
in the Wings of Liberty reader only), and its ``UserOptionsEvent`` keeps seven of them. On the three
replays those seven equal s2protocol's values. The fields it drops (test cheats, galaxy asserts,
platform, camera follow, build number, version flags, hotkey profile) need a reader change and are
not exposed here; the hotkey profile is a user-chosen name and would count as personal data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from sc2reader.events.game import UserOptionsEvent  # type: ignore[import-untyped]

# isort: split
from sc2mindshare.decoding.archive import MemberUnreadable, read_member

_T = TypeVar("_T")

#: Members that hold personal data: never exported, only their size is read out.
PERSONAL_DATA_MEMBERS = ("replay.server.battlelobby",)

#: The side members this module reports, by their name after ``replay.``.
SIDE_MEMBERS = ("resumable.events", "load.info", "sync.events", "sync.history", "server.battlelobby")

#: Game loops between two sync records (F3-017).
SYNC_INTERVAL_LOOPS = 64

_SYNC_PREFIX = b"\x01\x40"
_SYNC_RECORD_BYTES = 5
_RESUMABLE_TAIL = bytes.fromhex("0310ffffffff0000")


class FramingError(ValueError):
    """A member's bytes do not have the framing measured on the three replays."""


def parse_sync_events(data: bytes) -> tuple[int, ...]:
    """The 16-bit value of every record in ``replay.sync.events``, in order."""
    if len(data) % _SYNC_RECORD_BYTES:
        raise FramingError(f"sync.events: {len(data)} bytes is not a multiple of {_SYNC_RECORD_BYTES}")
    values = []
    for offset in range(0, len(data), _SYNC_RECORD_BYTES):
        record = data[offset : offset + _SYNC_RECORD_BYTES]
        field = int.from_bytes(record[2:], "little")
        if record[:2] != _SYNC_PREFIX or not field & 1 or field >> 17:
            raise FramingError(f"sync.events: unknown record {record.hex()} at byte {offset}")
        values.append(field >> 1)
    return tuple(values)


def parse_resumable_events(data: bytes) -> int:
    """The resume loop in ``replay.resumable.events``."""
    if len(data) != 4 + len(_RESUMABLE_TAIL) or data[4:] != _RESUMABLE_TAIL:
        raise FramingError(f"resumable.events: unknown framing {data.hex()}")
    return int.from_bytes(data[:4], "little")


@dataclass(frozen=True)
class SideMembers:
    """What the side members hold; None where a member is missing, unreadable or not as measured."""

    #: (member name after ``replay.``, size in bytes or None when absent), in SIDE_MEMBERS order.
    member_bytes: tuple[tuple[str, int | None], ...]
    resume_loop: int | None
    load_info_all_zero: bool | None
    sync_checksums: tuple[int, ...] | None
    warnings: tuple[str, ...] = ()


def side_members(replay: Any) -> SideMembers:
    warnings: list[str] = []
    raw: dict[str, bytes | None] = {}
    for name in SIDE_MEMBERS:
        try:
            raw[name] = read_member(replay, "replay." + name)
        except MemberUnreadable as exc:
            raw[name] = None
            warnings.append(f"replay.{name} unreadable: {exc}")
    sizes = tuple((name, None if raw[name] is None else len(raw[name] or b"")) for name in SIDE_MEMBERS)
    raw.pop("server.battlelobby")  # personal data: only its size leaves this function

    def parsed(name: str, parse: Callable[[bytes], _T]) -> _T | None:
        data = raw[name]
        if data is None:
            return None
        try:
            return parse(data)
        except FramingError as exc:
            warnings.append(str(exc))
            return None

    load_info = raw["load.info"]
    return SideMembers(
        member_bytes=sizes,
        resume_loop=parsed("resumable.events", parse_resumable_events),
        load_info_all_zero=None if load_info is None else not any(load_info),
        sync_checksums=parsed("sync.events", parse_sync_events),
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class UserOptions:
    """The SUserOptionsEvent fields sc2reader keeps, for one player (F3-018)."""

    player_id: int
    game_fully_downloaded: bool | None
    development_cheats_enabled: bool | None
    multiplayer_cheats_enabled: bool | None
    sync_checksumming_enabled: bool | None
    is_map_to_map_transition: bool | None
    debug_pause_enabled: bool | None
    base_build_num: int | None


def _flag(value: Any) -> bool | None:
    return None if value is None else bool(value)


def user_options(replay: Any) -> tuple[UserOptions, ...]:
    """One row per UserOptionsEvent with a resolved player, in stream order."""
    rows = []
    for event in replay.game_events:
        if not isinstance(event, UserOptionsEvent) or event.player is None:
            continue
        build = event.base_build_num
        rows.append(
            UserOptions(
                player_id=int(event.player.pid),
                game_fully_downloaded=_flag(event.game_fully_downloaded),
                development_cheats_enabled=_flag(event.development_cheats_enabled),
                multiplayer_cheats_enabled=_flag(event.multiplayer_cheats_enabled),
                sync_checksumming_enabled=_flag(event.sync_checksumming_enabled),
                is_map_to_map_transition=_flag(event.is_map_to_map_transition),
                debug_pause_enabled=_flag(event.debug_pause_enabled),
                base_build_num=None if build is None else int(build),
            )
        )
    return tuple(rows)
