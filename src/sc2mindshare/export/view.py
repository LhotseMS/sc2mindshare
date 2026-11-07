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
from sc2mindshare.domain.time import GameTime
from sc2mindshare.export.time_text import game_hms, text_values

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

#: CR-034 (export fix BO1; P0-6, Iris; D57a, D62b): the step properties, with their Mindshare data types, on every
#: node of the kinds that hold steps. Not detail properties (the node face is unchanged).
STEP_PROPERTIES: tuple[tuple[str, str], ...] = (
    ("step #", "int"),
    ("at supply", "int"),
    ("started at", "time[h:m:s]"),
    ("steps", "string"),
    # CR-035 (D2a, D6a; Kevin's call 13): the range the step's supply lies in, "17–19", where the reading cannot pin it
    # to one value; "" on every other node (Mindshare refuses a blank int, D62b)
    ("supply range", "string"),
)
STEP_KINDS = frozenset({"Building", "Upgrade", "Units"})

#: CR-035 (export fix BC1; P0-6 §4.0-§4.2, Iris; Kevin's calls 1 and 2): the build check's properties per node kind,
#: with their Mindshare data types. On every Building, Upgrade and Units node the four step entries, "" where nothing
#: was compared (Mindshare refuses a blank number, D62b, so they are text); on every Player node ``build check``; the
#: card's and the missing entry's own. ``at supply`` (CR-034) is the supply the player was on: not declared twice.
CHECK_PROPERTIES: dict[str, tuple[tuple[str, str], ...]] = {
    "Building": (("verdict", "string"), ("guide time", "string"), ("off by s", "string"), ("guide supply", "string")),
    "Player": (("build check", "string"),),
    "Build Comparison": (
        ("build order guide", "string"),
        ("graded by", "string"),
        ("picked", "string"),
        ("team draft", "bool"),
        ("patch", "string"),
        ("old guide", "bool"),
        ("covers to", "time[h:m:s]"),
        ("on time", "int"),
        ("a bit late", "int"),
        ("late", "int"),
        ("early", "int"),
        ("done", "int"),
        ("missing", "int"),
        ("extra", "int"),
        ("not compared", "int"),
    ),
    "Missing Step": (
        ("item", "string"),
        ("guide supply", "string"),
        ("done later at", "string"),
        ("build order guide", "string"),
    ),
}
CHECK_PROPERTIES = {**CHECK_PROPERTIES, "Upgrade": CHECK_PROPERTIES["Building"], "Units": CHECK_PROPERTIES["Building"]}
#: The kinds whose entries may be blank (every node of the kind carries them, compared or not).
_BLANK_ALLOWED = STEP_KINDS | {"Player"}

#: The legacy text of a bool and its value (CR-067 G2's ``ladder``); any other text is a KeyError.
BOOL_TEXT = {"True": True, "False": False}

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
        # CR-063 (D4a, in both documents): always written, a blank as "" (the workbook left a blank out), so every
        # node of a type has the same properties; Mindshare accepts the blank (AC-3). A time is never blank.
        if "time" in v:  # a Build Comparison card has none (CR-035)
            props["time"] = hhmmss(v["time"])
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
        props["target"] = v["target"]  # CR-063: always, last; a blank as ""
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
            # a bool reads only "True" or "False": any other text fails rather than reading as false (Rex's N1)
            props |= {
                name: BOOL_TEXT[v[field]] if data_type == "bool" else v[field] for name, field, data_type in GAME_PROPERTIES
            }
    elif kind in ("Player", "Build Comparison"):  # CR-035: the card has the Player card's size (spec §13.2)
        view["size"] = [7.8, 2.2]
    if "BO1" in export_fixes and kind in STEP_KINDS:
        props |= step_properties(node)
    if "BC1" in export_fixes and kind in CHECK_PROPERTIES:
        props |= check_properties(node)
    view["properties"] = props
    return view


def step_properties(node: Node) -> dict[str, Any]:
    """CR-034 BO1: the first step's number, supply and start, and the list of the node's steps when it holds two
    or more (AC-2), and (CR-035) the first step's supply range; a node holding no step carries 0, 0, 00:00:00, ""
    and "" (D62b: Mindshare needs every node of a
    type to have the same keys, and refuses null or a blank int)."""
    first = node.steps[0] if node.steps else None
    return {
        "step #": first.number if first else 0,
        "at supply": first.supply if first else 0,
        # a pre-game start shows 00:00:00, as every pre-game time property does (P3d); its sign is in the line
        "started at": game_hms(max(0, first.second) if first else 0),
        "steps": " / ".join(s.line() for s in node.steps) if len(node.steps) > 1 else "",
        "supply range": supply_range_text(first.supply_range) if first else "",
    }


def check_properties(node: Node) -> dict[str, Any]:
    """CR-035 BC1: the build check's entries of ``node`` (``Node.added``) in the declared order; on a Building,
    Upgrade, Units or Player node an entry not given is "" (not compared). An entry that is not declared, or a card's or
    missing entry's entry that is not given, is an error rather than a node that differs from the others of its type."""
    declared = CHECK_PROPERTIES[node.kind]
    added = dict(node.added)
    if unknown := sorted(set(added) - {name for name, _ in declared}):
        raise ValueError(f"{node.id}: build check entries {unknown} are not declared for {node.kind}")
    out: dict[str, Any] = {}
    for name, _ in declared:
        if name not in added and node.kind not in _BLANK_ALLOWED:
            raise ValueError(f"{node.id}: the build check entry {name!r} is missing")
        value = added.get(name, "")
        out[name] = game_hms(value.seconds) if isinstance(value, GameTime) else value
    return out


def supply_range_text(supply_range: tuple[int, int] | None) -> str:
    """CR-035 (call 13): a ≈ step's range, low–high with an en dash ("17–19"); "" when the supply is exact."""
    return "" if supply_range is None else f"{supply_range[0]}\u2013{supply_range[1]}"


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
