"""Frozen models of the Mindshare graph (CR-012, T12).

Each node kind declares its fields in ``FIELDS``; a ``Node`` with other field names cannot be
built, so a value can no longer shift into another column (the legacy hand-kept column counts,
python bugs 4 and 5, cannot happen here). Field values are still the legacy layer's text, bugs
included (CR-022, T21, turns times into numbers); ``start_seconds`` is the one number the layout
needs now: the node's game time in real seconds, **signed** (a main base built before 0:00 has a
negative start, where the legacy text wraps to ``23:58:49``; Leo's B9 condition), or None for the
Game and Player nodes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

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

#: Properties a ledger fix may add to a node, beyond its kind's legacy fields (``Node.extra``).
#: "pre-game time": the signed start of a pre-game item as ``-hh:mm:ss`` (P3d, D7a A9).
EXTRA_FIELDS: tuple[str, ...] = ("pre-game time",)


@dataclass(frozen=True)
class Node:
    kind: str
    id: str
    name: str
    description: str
    images: tuple[str, ...]
    values: tuple[tuple[str, str], ...]
    start_seconds: int | None
    #: Properties added by ledger fixes (names from EXTRA_FIELDS), exported after the kind's own.
    extra: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in FIELDS:
            raise ValueError(f"unknown node kind {self.kind!r} ({self.id})")
        names = tuple(name for name, _ in self.values)
        if names != FIELDS[self.kind]:
            raise ValueError(f"{self.id}: fields {names} are not the declared {FIELDS[self.kind]}")
        if (self.start_seconds is None) != (self.kind in ("Game", "Player")):
            raise ValueError(f"{self.id}: start_seconds is required for every kind but Game and Player")
        extra_names = [name for name, _ in self.extra]
        if undeclared := [name for name in extra_names if name not in EXTRA_FIELDS]:
            raise ValueError(f"{self.id}: undeclared extra properties {undeclared} (EXTRA_FIELDS)")
        if len(set(extra_names)) != len(extra_names):
            raise ValueError(f"{self.id}: repeated extra properties {extra_names}")

    def value(self, name: str) -> str:
        return dict(self.values)[name]


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
