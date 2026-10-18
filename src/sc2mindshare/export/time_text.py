"""Times as the legacy layer wrote them (CR-022, T21): the one place a time field becomes text (the one
other time text, the pre-game note in a description, is ``analysis.fixes.signed_hhmmss``; see
``domain.time``).

Bug-faithful, per node kind (tests/analysis/test_time.py characterises every form):

- a Battle's times are Python's ``timedelta`` text, ``0:02:02``;
- a Harrasment's and a Scouting's are sc2reader's ``Length`` text, ``02:02`` (``01:00:05`` from one
  hour on);
- every other time is ``HH:MM:SS`` of the time of day, so a negative time wraps at midnight
  (``-71 s`` is ``23:58:49``: B9, ledger P3);
- an open end (an Energy Excess still running when the game ends) is ``None``.

The mixed forms are ledger entry P13 (one format in export), fixed in CR-023 (T22): with the export
fix ``P13`` every time is ``hh:mm:ss`` of game time, the hours not wrapping (``game_hms``).
"""

from __future__ import annotations

import datetime

from sc2mindshare.domain.models import Node
from sc2mindshare.domain.time import GameTime

_TIMEDELTA_KINDS = frozenset({"Battle"})
_LENGTH_KINDS = frozenset({"Harrasment", "Scouting"})


def _time_of_day(seconds: int) -> str:
    s = seconds % 86400
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}"


def _length(seconds: int) -> str:
    if seconds < 0:
        raise ValueError(f"a Length cannot be negative: {seconds} s")
    h, m, s = seconds // 3600, seconds // 60 % 60, seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def game_hms(seconds: int) -> str:
    """CR-023 P13: ``hh:mm:ss`` of game time, the hours not wrapping (a 70-minute game reads ``01:10:00``)."""
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def legacy_text(kind: str, time: GameTime | None) -> str:
    """The legacy text of a time field of a node of ``kind``."""
    if time is None:
        return "None"
    if kind in _TIMEDELTA_KINDS:
        return str(datetime.timedelta(seconds=time.seconds))
    if kind in _LENGTH_KINDS:
        return _length(time.seconds)
    return _time_of_day(time.seconds)


def time_text(kind: str, time: GameTime | None, export_fixes: frozenset[str] = frozenset()) -> str:
    """A time field's text: the legacy form, or with ``P13`` ``hh:mm:ss`` of game time (a negative time, which
    only a pre-game start has and P3d shows as 00:00:00, keeps the legacy form)."""
    if "P13" in export_fixes and time is not None and time.seconds >= 0:
        return game_hms(time.seconds)
    return legacy_text(kind, time)


def text_values(node: Node, export_fixes: frozenset[str] = frozenset()) -> tuple[tuple[str, str], ...]:
    """Every field of ``node`` as text, in the declared order: the legacy text, with P13 one time format."""
    return tuple(
        (name, value if isinstance(value, str) else time_text(node.kind, value, export_fixes)) for name, value in node.values
    )
