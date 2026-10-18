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

The mixed forms are ledger entry P13 (one format in export), fixed in CR-023 (T22) with its own
golden entry.
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


def legacy_text(kind: str, time: GameTime | None) -> str:
    """The legacy text of a time field of a node of ``kind``."""
    if time is None:
        return "None"
    if kind in _TIMEDELTA_KINDS:
        return str(datetime.timedelta(seconds=time.seconds))
    if kind in _LENGTH_KINDS:
        return _length(time.seconds)
    return _time_of_day(time.seconds)


def text_values(node: Node) -> tuple[tuple[str, str], ...]:
    """Every field of ``node`` as the legacy text, in the declared order."""
    return tuple((name, value if isinstance(value, str) else legacy_text(node.kind, value)) for name, value in node.values)
