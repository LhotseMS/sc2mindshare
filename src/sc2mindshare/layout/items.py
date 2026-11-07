"""Layout items from the domain graph (CR-014; layout-spec.md §3).

``t`` is the node's signed start in whole seconds (``Node.start``: main bases at -71, B9; the
second is floored exactly as the legacy layer printed it, TD-26);
``order`` is the node's position in the graph (the TD-20 tie-break); ``t_end`` comes from the "end time"
of a Supply Block, Scouting Gap, Energy Excess or Inject Delay (CR-073), and ``open_end`` marks an Energy
Excess still open when the game ends; the radius basis is a Battle's "supply dead" and a Units node's "supply".
"""

from __future__ import annotations

from collections.abc import Sequence

from sc2mindshare.domain.models import OPEN_ENDED, Graph, Node
from sc2mindshare.layout.sweep import LayoutItem

#: The kinds the layout reads an end from (a Harrasment's end is unused: its card sits at its start, D7a).
ENDED = frozenset({"Supply Block", "Scouting Gap", "Energy Excess", "Inject Delay"})


def item(node: Node, order: int) -> LayoutItem:
    if node.kind == "Player":
        player = node.value("name")
    elif node.kind == "Game":
        player = None
    else:
        player = node.value("player")
    end = node.time("end time") if node.kind in ENDED else None
    t_end = None if end is None else end.seconds
    open_end = end is None and (node.kind, "end time") in OPEN_ENDED
    basis = None
    if node.kind == "Battle":
        basis = float(node.value("supply dead"))
    elif node.kind == "Units":
        basis = float(node.value("supply"))
    t = None if node.start is None else node.start.seconds
    return LayoutItem(node.id, node.kind, t, order, player=player, t_end=t_end, size_basis=basis, open_end=open_end)


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
