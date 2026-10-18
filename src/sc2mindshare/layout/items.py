"""Layout items from the domain graph (CR-014; layout-spec.md §3).

``t`` is the node's signed start in seconds (``Node.start_seconds``: main bases at -71, B9);
``order`` is the node's position in the graph (the TD-20 tie-break); Supply Block ``t_end`` comes
from its "end time"; the radius basis is a Battle's "supply dead" and a Units node's "supply".
"""

from __future__ import annotations

from sc2mindshare.domain.models import Graph, Node
from sc2mindshare.layout.sweep import LayoutItem


def _seconds(text: str) -> int:
    parts = [int(p) for p in text.split(":")]
    return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]


def item(node: Node, order: int) -> LayoutItem:
    values = dict(node.values)
    if node.kind == "Player":
        player = values["name"]
    elif node.kind == "Game":
        player = None
    else:
        player = values["player"]
    t_end = _seconds(values["end time"]) if node.kind == "Supply Block" else None
    basis = None
    if node.kind == "Battle":
        basis = float(values["supply dead"])
    elif node.kind == "Units":
        basis = float(values["supply"])
    return LayoutItem(node.id, node.kind, node.start_seconds, order, player=player, t_end=t_end, size_basis=basis)


def items(graph: Graph) -> list[LayoutItem]:
    return [item(n, i) for i, n in enumerate(graph.nodes)]
