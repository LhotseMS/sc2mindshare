"""Raw access to the members of a replay's MPQ archive (CR-042).

sc2reader keeps the opened mpyq archive on the Replay (`Replay.archive`), so any member
can be read without opening the file again and without patching sc2reader.
"""

from __future__ import annotations

from typing import Any


class MemberUnreadable(Exception):
    """The archive cannot say whether a member exists or what it holds (for example an encrypted
    (listfile) in early Wings of Liberty replays, which mpyq cannot decrypt)."""


def member_names(replay: Any) -> tuple[str, ...]:
    """The names in the archive's (listfile); sc2reader opens the archive with listfile=False."""
    try:
        listfile = replay.archive.read_file("(listfile)") or b""
    except NotImplementedError as exc:  # mpyq: "Encryption is not supported yet."
        raise MemberUnreadable("(listfile) is encrypted") from exc
    return tuple(sorted(bytes(listfile).decode("utf-8", "replace").split()))


def read_member(replay: Any, name: str) -> bytes | None:
    """The member's bytes, `b""` for an empty member, or None when the archive has no such member.

    mpyq returns None for an empty member and for an absent one alike; the listfile tells them apart.
    Raises MemberUnreadable when the member or the listfile cannot be read.
    """
    try:
        data = replay.archive.read_file(name)
    except NotImplementedError as exc:
        raise MemberUnreadable(f"{name} is encrypted") from exc
    if data is not None:
        return bytes(data)
    return b"" if name in member_names(replay) else None
