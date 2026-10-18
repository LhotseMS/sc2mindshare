"""VBA view reference port (CR-006, T06): test-only, frozen, never shipped.

A literal Python transliteration of what Stefan's workbook does to the legacy
events CSV **before** placement:

- the Power Query import (``Section1.m``: ``;``-separated, cp1250 text, no
  quoting, ``Columns=23``, a row whose first column contains ``-`` is a link);
- ``MindshareTRH__1_2.readNodes`` with ``ScReplayNode.GetView`` and
  ``getCircleSize``;
- the L Import part of ``readLinks`` with ``Link.GetView`` (the Links matrix is
  empty in the workbook, so the matrix part adds nothing);
- the ``importDict`` key order: ``visuals``, ``detail``, ``dataTypes``,
  ``nodes``, ``links``.

Its output with the positions left out is ``G-VIEW-1``, the oracle for the new
pipeline's view (``stream1-plan.md`` §3 step 5). Placement (``Positioner.bas``)
is not ported here: the new layout is built from Leo's fixed spec (TD-21).

VBA semantics kept on purpose (defects included):

- B3: ``combatSet`` is never set, so Ability ``combat``/``queued``/``minimap``
  are never emitted;
- times are ``Format(value, "hh:mm:ss")`` of the CSV text: ``01:42`` (Scouting)
  becomes ``01:42:00`` (B9), ``23:58:49`` stays;
- Battle ``end time`` is the raw CSV text (B11);
- supply values go through ``Replace(".", ",")`` into a Double on Stefan's
  decimal-comma locale, which reads them as decimals (B10 does not fire there);
- ``Integer`` fields overflow above 32767 and fail on non-numeric text, as VBA
  would (error 6 / error 13).

One documented deviation, chosen for ``G-VIEW-1`` (``rejoin_raw_newlines``):
the current code writes some Harrasment descriptions with a raw newline
(python bug 7). The Power Query would split those rows, and ``readLinks`` would
then stop with a type mismatch on the broken row, so the macro cannot run on
the current code's CSV at all. With ``rejoin_raw_newlines=True`` the split
rows are joined first (as if the newline were written as ``X_LD``); the
default ``False`` keeps the literal behaviour, including the failure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

PQ_COLUMNS = 23  # Csv.Document(..., Columns=23)
MIN_FIELDS_PER_RECORD = 7
VBA_INTEGER_MAX = 32767
VBA_INTEGER_MIN = -32768


class VbaError(Exception):
    """A runtime error the VBA itself would raise (type mismatch, overflow)."""


# ---------------------------------------------------------------------------
# Power Query import


def physical_rows(csv_text: str, rejoin_raw_newlines: bool = False) -> list[list[str]]:
    lines = csv_text.splitlines()
    if rejoin_raw_newlines:
        joined: list[str] = []
        pending: str | None = None
        for line in lines:
            pending = line if pending is None else pending + "\n" + line
            if pending.count(";") + 1 >= MIN_FIELDS_PER_RECORD:
                joined.append(pending)
                pending = None
        if pending is not None:
            joined.append(pending)
        lines = joined
    rows = []
    for line in lines:
        fields = line.split(";")[:PQ_COLUMNS]
        rows.append(fields + [""] * (PQ_COLUMNS - len(fields)))
    return rows


def power_query(csv_text: str, rejoin_raw_newlines: bool = False) -> tuple[list[list[str]], list[list[str]]]:
    """(Gameplay rows, L Import rows). A Gameplay row is ``[Index, EmptyColumn, Column1..23]``."""
    rows = physical_rows(csv_text, rejoin_raw_newlines)
    links = [r for r in rows if "-" in r[0]]
    nodes = [[str(i), ""] + r for i, r in enumerate((r for r in rows if "-" not in r[0]), start=1)]
    return nodes, links


# ---------------------------------------------------------------------------
# VBA conversions (Stefan's decimal-comma locale)


def vba_round_half_even(x: float) -> int:
    floor = math.floor(x)
    diff = x - floor
    if diff > 0.5 or (diff == 0.5 and floor % 2 == 1):
        return int(floor) + 1
    return int(floor)


def _comma_decimal(text: str) -> float:
    s = text.strip()
    if s == "":
        raise VbaError(f"type mismatch: {text!r} is not a number")
    try:
        return float(s.replace(",", "."))
    except ValueError as exc:
        raise VbaError(f"type mismatch: {text!r} is not a number") from exc


def vba_integer(text: str) -> int:
    """Assigning cell text to a VBA ``Integer`` (16-bit, banker's rounding)."""
    value = vba_round_half_even(_comma_decimal(text))
    if not VBA_INTEGER_MIN <= value <= VBA_INTEGER_MAX:
        raise VbaError(f"overflow: {text!r} does not fit a VBA Integer")
    return value


def vba_double_from_point_text(text: str) -> float:
    """``Replace(text, ".", ",")`` assigned to a ``Double`` on a decimal-comma locale."""
    return _comma_decimal(text.replace(".", ","))


def vba_boolean(text: str) -> bool:
    s = text.strip().lower()
    if s in ("true", "pravda"):
        return True
    if s in ("false", "nepravda"):
        return False
    try:
        return _comma_decimal(text) != 0
    except VbaError as exc:
        raise VbaError(f"type mismatch: {text!r} is not a Boolean") from exc


def vba_format_hhmmss(text: str) -> str:
    """``Format(text, "hh:mm:ss")``: text that reads as a time of day is reformatted, other text is returned as is."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return text
    h, m = int(parts[0]), int(parts[1])
    s = int(parts[2]) if len(parts) == 3 else 0
    if h > 23 or m > 59 or s > 59:
        return text
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# ScReplayNode


@dataclass
class ScReplayNode:
    name: str = ""
    node_type: str = ""
    description: str = ""
    id: str = ""
    images: str = ""
    time: str = ""
    time_set: bool = False
    player: str = ""
    # supply block
    duration: int = 0
    # battle
    death_count: int = 0
    p1dc: int = 0
    p2dc: int = 0
    battle_supply: float = 0.0
    end_time: str = ""
    # ability (combat_set is never set: B3)
    sub_type: str = ""
    combat: bool = False
    queued: bool = False
    minimap: bool = False
    combat_set: bool = False
    target: str = ""
    # units
    unit_count: int = 0
    unit_supply: float = 0.0
    total_units_count: int = 0
    # stats
    stats: dict[str, int] = field(default_factory=dict)

    def circle_size(self) -> float:
        if self.node_type == "Battle":
            s = self.battle_supply
            if s <= 1:
                return 0.7
            if s <= 3:
                return 0.95
            if s <= 10:
                return 1.2
            if s <= 30:
                return 1.6
            return 2 + s / 100
        if self.node_type == "Units":
            s = self.unit_supply
            if s <= 3:
                return 0.75
            if s <= 10:
                return 1
            if s <= 20:
                return 1.4
            return 1.7
        return 0

    def get_view(self) -> dict[str, Any]:
        view: dict[str, Any] = {
            "name": self.name,
            "description": self.description.replace("X_LD", "\n"),
            "type": self.node_type,
            "ID": self.id,
        }
        props: dict[str, Any] = {}
        if self.time_set:
            props["time"] = self.time
        if self.player != "":
            props["player"] = self.player
        size = self.circle_size()
        if self.images != "":
            view["images"] = self.images.split("|")
        view["size"] = [2.65, 1]
        t = self.node_type
        if t == "Battle":
            props["dead"] = self.death_count
            props["p1 dead"] = self.p1dc
            props["p2 dead"] = self.p2dc
            props["supply dead"] = self.battle_supply
            props["end time"] = self.end_time
            view["size"] = size
        elif t == "Supply Block":
            props["duration"] = self.duration
            props["end time"] = self.end_time
        elif t == "Ability":
            props["type"] = self.sub_type
            if self.combat_set:
                props["combat"] = self.combat
                props["queued"] = self.queued
                props["minimap"] = self.minimap
            if self.target != "":
                props["target"] = self.target
            view["size"] = [1.6, 0.88]
        elif t in ("Building", "Initiated"):
            props["type"] = self.sub_type
        elif t == "Units":
            props["type"] = self.sub_type
            props["count"] = self.unit_count
            props["total at time"] = self.total_units_count
            props["supply"] = self.unit_supply
            view["size"] = size
        elif t == "Stats":
            view["size"] = [2.65, 1.28]
            props.update(self.stats)
        elif t == "Game":
            view["size"] = [10, 3.3]
        elif t == "Player":
            view["size"] = [7.8, 2.2]
        view["properties"] = props
        return view


STATS_COLUMNS = (
    ("cur. Min", 10),
    ("cur. Gas", 11),
    ("col. rate Min", 12),
    ("col. rate Gas", 13),
    ("workers", 14),
    ("army Min", 15),
    ("army Gas", 16),
    ("used Min", 17),
    ("used Gas", 18),
)
STATS_PROPERTY_ORDER = (
    "workers",
    "cur. Min",
    "cur. Gas",
    "col. rate Min",
    "col. rate Gas",
    "army Min",
    "army Gas",
    "used Min",
    "used Gas",
)


def read_node(row: list[str]) -> ScReplayNode:
    """``readNodes`` for one Gameplay row. ``col(n)`` is the VBA ``row.Columns(n)`` (1-based)."""

    def col(n: int) -> str:
        return row[n - 1]

    n = ScReplayNode(name=col(3), description=col(4), node_type=col(5), id=col(6), images=col(7))
    if n.node_type in ("Game", "Player"):
        return n
    if col(8) != "":
        n.time_set = True
        n.time = vba_format_hhmmss(col(8))
    n.player = col(9)
    t = n.node_type
    if t == "Battle":
        n.death_count = vba_integer(col(10))
        n.p1dc = vba_integer(col(11))
        n.p2dc = vba_integer(col(12))
        n.battle_supply = vba_double_from_point_text(col(13))
        n.end_time = col(14)
    elif t == "Supply Block":
        n.end_time = col(10)
        n.duration = vba_integer(col(11))
    elif t == "Ability":
        n.sub_type = col(10)
        n.combat = vba_boolean(col(11))
        n.queued = vba_boolean(col(12))
        n.minimap = vba_boolean(col(13))
        n.target = col(14)
    elif t in ("Building", "Initiated"):
        n.sub_type = col(10)
    elif t == "Units":
        n.sub_type = col(10)
        n.unit_count = vba_integer(col(11))
        n.unit_supply = vba_double_from_point_text(col(12))
        n.total_units_count = vba_integer(col(13))
    elif t == "Stats":
        values = {name: vba_integer(col(c)) for name, c in STATS_COLUMNS}
        n.stats = {name: values[name] for name in STATS_PROPERTY_ORDER}
    return n


def read_link(row: list[str]) -> dict[str, Any]:
    """The L Import part of ``readLinks`` with ``Link.GetView`` (``name`` is never set there)."""
    view: dict[str, Any] = {"name1": row[2], "name2": row[3], "direction": vba_integer(row[5])}
    view["node1"] = row[0]
    view["node2"] = row[1]
    if row[4] != "":
        view["description"] = row[4]
    return view


def build_view(
    csv_text: str,
    visuals: list[dict[str, str]],
    detail: list[dict[str, Any]],
    data_types: dict[str, str],
    rejoin_raw_newlines: bool = False,
) -> dict[str, Any]:
    """The workbook's ``importDict`` before ``PositionNodesVertically``."""
    gameplay, links = power_query(csv_text, rejoin_raw_newlines)
    return {
        "visuals": visuals,
        "detail": detail,
        "dataTypes": data_types,
        "nodes": [read_node(r).get_view() for r in gameplay],
        "links": [read_link(r) for r in links],
    }
