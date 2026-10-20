"""Layout items from the domain graph (CR-014; layout-spec.md §3).

``t`` is the node's signed start in seconds (``Node.start_seconds``: main bases at -71, B9);
``order`` is the node's position in the graph (the TD-20 tie-break); Supply Block ``t_end`` comes
from its "end time"; the radius basis is a Battle's "supply dead" and a Units node's "supply".
"""

from __future__ import annotations

from collections.abc import Sequence

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
    t_end = _seconds(values["end time"]) if node.kind in ("Supply Block", "Scouting Gap") else None
    basis = None
    if node.kind == "Battle":
        basis = float(values["supply dead"])
    elif node.kind == "Units":
        basis = float(values["supply"])
    return LayoutItem(node.id, node.kind, node.start_seconds, order, player=player, t_end=t_end, size_basis=basis)


def ghost_time(
    *,
    horizon: float,
    guide_time: float | None = None,
    guide_supply: float | None = None,
    trigger_time: float | None = None,
    food_used: Sequence[tuple[float, float]] = (),
) -> float:
    """The time a Missing Step or Checkpoint ghost is placed at (spec §13.3 rule 1; TD-43, TD-44).

    A guide step with a time: the guide time. Supply only: the first moment the player's ``food_used``
    reached the guide supply (``food_used`` = (seconds, food used) samples, in time order), or the
    horizon if it never did. Trigger only: the trigger moment if it could be evaluated, otherwise the
    horizon. This places the node only; its ``time`` property keeps the guide's value.
    """
    if guide_time is not None:
        return guide_time
    if guide_supply is not None:
        return next((t for t, used in food_used if used >= guide_supply), horizon)
    return trigger_time if trigger_time is not None else horizon


def items(graph: Graph) -> list[LayoutItem]:
    return [item(n, i) for i, n in enumerate(graph.nodes)]
