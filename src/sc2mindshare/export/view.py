"""One node or link as the workbook showed it to Mindshare, before placement (CR-013, T13).

The rules of the workbook's ``ScReplayNode.GetView``, ``getCircleSize`` and ``Link.GetView``,
applied to the domain models instead of Excel cells, bug-faithful for now (G-VIEW-1 is the
oracle): B3 (an Ability's ``combat``/``queued``/``minimap`` are never emitted; emitted with the
export fix ``B3``, CR-023), B9 (``01:42`` is read as ``01:42:00``), B11 (a Battle's ``end time`` is
the raw text). The defect fixes change these later, each with a golden ledger entry.
"""

from __future__ import annotations

import math
from typing import Any

from sc2mindshare.domain.models import Link, Node
from sc2mindshare.export.time_text import text_values

X_LD = "X_LD"

#: CR-067 (export fix G2; D24a): the Game node's properties in their order, each with the domain field it reads
#: (``FIELDS["Game"]``) and its Mindshare data type. The names avoid ``duration`` and ``type``, which other node
#: types already declare with other data types.
GAME_PROPERTIES: tuple[tuple[str, str, str], ...] = (
    ("date played (UTC)", "date", "string"),
    ("time zone", "timezone", "typelist"),
    ("length", "duration", "time[h:m:s]"),
    ("game type", "type", "typelist"),
    ("ladder", "ladder", "bool"),
    ("category", "category", "typelist"),
    ("speed", "speed", "typelist"),
)

#: The Stats properties in the order the workbook wrote them.
STATS_ORDER = (
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


def vba_integer(text: str) -> int:
    """Cell text assigned to a VBA Integer: banker's rounding (the values are whole numbers today)."""
    x = float(text)
    floor = math.floor(x)
    diff = x - floor
    return int(floor) + (1 if diff > 0.5 or (diff == 0.5 and floor % 2 == 1) else 0)


def hhmmss(text: str) -> str:
    """VBA ``Format(text, "hh:mm:ss")``: a time of day is reformatted, other text is kept."""
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return text
    h, m = int(parts[0]), int(parts[1])
    s = int(parts[2]) if len(parts) == 3 else 0
    if h > 23 or m > 59 or s > 59:
        return text
    return f"{h:02d}:{m:02d}:{s:02d}"


def battle_size(supply_dead: float) -> float:
    if supply_dead <= 1:
        return 0.7
    if supply_dead <= 3:
        return 0.95
    if supply_dead <= 10:
        return 1.2
    if supply_dead <= 30:
        return 1.6
    return 2 + supply_dead / 100


def units_size(supply: float) -> float:
    if supply <= 3:
        return 0.75
    if supply <= 10:
        return 1
    if supply <= 20:
        return 1.4
    return 1.7


def node_view(node: Node, export_fixes: frozenset[str] = frozenset()) -> dict[str, Any]:
    v = dict(text_values(node, export_fixes))  # the workbook read the legacy text: its rules apply to that (CR-022)
    view: dict[str, Any] = {
        "name": node.name,
        "description": node.description.replace(X_LD, "\n"),
        "type": node.kind,
        "ID": node.id,
    }
    props: dict[str, Any] = {}
    if node.kind not in ("Game", "Player"):
        if v["time"] != "":
            props["time"] = hhmmss(v["time"])
        if v["player"] != "":
            props["player"] = v["player"]
    if node.images:
        view["images"] = list(node.images)
    view["size"] = [2.65, 1]
    kind = node.kind
    if kind == "Battle":
        supply = float(v["supply dead"])
        props |= {
            "dead": vba_integer(v["dead"]),
            "p1 dead": vba_integer(v["p1 dead"]),
            "p2 dead": vba_integer(v["p2 dead"]),
            "supply dead": supply,
            "end time": v["end time"],
        }
        view["size"] = battle_size(supply)
    elif kind == "Supply Block":
        props |= {"duration": vba_integer(v["duration"]), "end time": v["end time"]}
    elif kind == "Ability":
        props["type"] = v["type"]
        if "B3" in export_fixes:  # CR-023 B3: the flags the workbook never emitted, as booleans
            props |= {flag: v[flag] == "True" for flag in ("combat", "queued", "minimap")}
        if v["target"] != "":
            props["target"] = v["target"]
        view["size"] = [1.6, 0.88]
    elif kind in ("Building", "Initiated"):
        props["type"] = v["type"]
    elif kind == "Units":
        supply = float(v["supply"])
        props |= {
            "type": v["type"],
            "count": vba_integer(v["count"]),
            "total at time": vba_integer(v["total at time"]),
            "supply": supply,
        }
        view["size"] = units_size(supply)
    elif kind == "Stats":
        view["size"] = [2.65, 1.28]
        props |= {name: vba_integer(v[name]) for name in STATS_ORDER}
    elif kind == "Game":
        view["size"] = [10, 3.3]
        if "G2" in export_fixes:  # CR-067 G2: the values the workbook view dropped, in D24a's order
            props |= {
                name: v[field] == "True" if data_type == "bool" else v[field] for name, field, data_type in GAME_PROPERTIES
            }
    elif kind == "Player":
        view["size"] = [7.8, 2.2]
    view["properties"] = props
    return view


def link_view(link: Link) -> dict[str, Any]:
    """The workbook's ``Link.GetView`` for a link read from the CSV (``name`` is never set there)."""
    view: dict[str, Any] = {
        "name1": link.name if link.name is not None else link.name1,
        "name2": "" if link.name is not None else link.name2,
        "direction": link.direction,
        "node1": link.node1,
        "node2": link.node2,
    }
    if link.description != "":
        view["description"] = link.description
    return view
