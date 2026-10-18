"""Frozen models of the Mindshare graph (CR-012, T12).

Each node kind declares its fields in ``FIELDS``; a ``Node`` with other field names cannot be
built, so a value can no longer shift into another column (the legacy hand-kept column counts,
python bugs 4 and 5, cannot happen here).

Times are numbers (CR-022, T21): the ``time`` and ``end time`` fields hold a ``GameTime`` (an open
Energy Excess has no end, None), and ``export/`` alone writes them as text. Every other field is
still the legacy layer's text, bugs included. ``start`` is what the layout places a node by: its
**signed** start (a main base built before 0:00 starts at -71 s, where the legacy text wraps to
``23:58:49``; Leo's B9 condition), or None for the Game and Player nodes. It is a field of its own
because a fix may show another time than the node's start (``analysis.fixes.pre_game_display``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from sc2mindshare.domain.time import GameTime

#: The declared fields of every node kind, in the legacy CSV's column order.
FIELDS: Mapping[str, tuple[str, ...]] = {
    "Game": ("speed", "ladder", "type", "category", "duration", "date", "timezone"),
    "Player": ("name", "race", "region", "subregion"),
    "Battle": ("time", "player", "dead", "p1 dead", "p2 dead", "supply dead", "end time"),
    "Units": ("time", "player", "type", "count", "supply", "total at time"),
    "Building": ("time", "player", "type"),
    "Initiated": ("time", "player", "type", "type (repeated)"),  # InitNode appends its subtype twice
    "Upgrade": ("time", "player"),  # the subtype is dropped by a format bug (python bug 4)
    "Ability": ("time", "player", "type", "combat", "queued", "minimap", "target"),
    "Stats": (
        "time",
        "player",
        "cur. Min",
        "cur. Gas",
        "col. rate Min",
        "col. rate Gas",
        "workers",
        "army Min",
        "army Gas",
        "used Min",
        "used Gas",
    ),
    "Supply Block": ("time", "player", "end time", "duration"),
    "Energy Excess": ("time", "player", "end time", "duration"),
    "Inject Delay": ("time", "player", "end time", "duration"),
    "Harrasment": ("time", "player", "end time", "deaths"),
    "Scouting": ("time", "player", "unit", "base"),
    "Chat": ("time", "player"),
}

#: The fields that hold a ``GameTime``.
TIME_FIELDS = frozenset({"time", "end time"})
#: The time fields that may be empty (None): an Energy Excess still open when the game ends.
OPEN_ENDED = frozenset({("Energy Excess", "end time")})

#: A field's value: a time, or the legacy text.
Value = GameTime | str | None


@dataclass(frozen=True)
class Node:
    kind: str
    id: str
    name: str
    description: str
    images: tuple[str, ...]
    values: tuple[tuple[str, Value], ...]
    start: GameTime | None

    def __post_init__(self) -> None:
        if self.kind not in FIELDS:
            raise ValueError(f"unknown node kind {self.kind!r} ({self.id})")
        names = tuple(name for name, _ in self.values)
        if names != FIELDS[self.kind]:
            raise ValueError(f"{self.id}: fields {names} are not the declared {FIELDS[self.kind]}")
        for name, value in self.values:
            if name in TIME_FIELDS:
                if not isinstance(value, GameTime) and not (value is None and (self.kind, name) in OPEN_ENDED):
                    raise ValueError(f"{self.id}: {name!r} must be a GameTime, not {value!r}")
            elif not isinstance(value, str):
                raise ValueError(f"{self.id}: {name!r} is text, not {value!r}")
        if (self.start is None) != (self.kind in ("Game", "Player")):
            raise ValueError(f"{self.id}: start is required for every kind but Game and Player")

    def value(self, name: str) -> str:
        """A text field's value."""
        value = dict(self.values)[name]
        if not isinstance(value, str):
            raise TypeError(f"{self.id}: {name!r} is a time; read it with time()")
        return value

    def time(self, name: str) -> GameTime | None:
        """A time field's value (None only for an open end, ``OPEN_ENDED``)."""
        value = dict(self.values)[name]
        if isinstance(value, str):
            raise TypeError(f"{self.id}: {name!r} is text; read it with value()")
        return value


@dataclass(frozen=True)
class Link:
    node1: str
    node2: str
    name1: str
    name2: str
    description: str
    direction: int
    name: str | None = None  # a one-word link (legacy Link.name); name1/name2 are then ""


@dataclass(frozen=True)
class Graph:
    """Nodes and links. It does not enforce unique node IDs: the legacy layer repeats Harrasment
    IDs (H1), which ``analysis.fixes`` corrects, and the layout's guard G1 refuses duplicates."""

    nodes: tuple[Node, ...]
    links: tuple[Link, ...]
    intervals: str | None = field(default=None)  # the battle windows text (legacy Intervals.csv)
    #: The export fixes the document is built with (``analysis.fixes.EXPORT_FIXES`` with the graph fixes on,
    #: none for the bug-faithful graph): fixes of what the view emits, not of the graph itself (CR-023 B3).
    export_fixes: frozenset[str] = field(default=frozenset())
