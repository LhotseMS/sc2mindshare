"""Defect fixes applied to the domain graph (CR-014 onwards), one function per ledger entry.

The moved legacy layer stays bug-faithful, so its CSV oracle keeps proving the move changed
nothing; each fix here changes the graph on purpose, with an entry in tests/golden/CHANGES.md
written before it. ``to_domain.to_graph`` applies ``FIXES`` in order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import replace

from sc2mindshare.domain.models import Graph


def unique_harassment_ids(graph: Graph) -> Graph:
    """H1: one game-wide Harrasment sequence in node order (the legacy layer numbers per battle)."""
    harassment = [n for n in graph.nodes if n.kind == "Harrasment"]
    old_ids = Counter(n.id for n in harassment)
    linked = {lk.node1 for lk in graph.links} | {lk.node2 for lk in graph.links}
    ambiguous = sorted(i for i, c in old_ids.items() if c > 1 and i in linked)
    if ambiguous:
        raise ValueError(f"H1: links refer to repeated Harrasment IDs {ambiguous}; cannot tell which node they mean")
    renamed = {}
    seq = 0
    nodes = []
    for node in graph.nodes:
        if node.kind == "Harrasment":
            seq += 1
            new = replace(node, id=f"Harrasment-{seq}")
            if old_ids[node.id] == 1:
                renamed[node.id] = new.id
            nodes.append(new)
        else:
            nodes.append(node)
    links = tuple(
        replace(lk, node1=renamed.get(lk.node1, lk.node1), node2=renamed.get(lk.node2, lk.node2)) for lk in graph.links
    )
    return replace(graph, nodes=tuple(nodes), links=links)


#: The fixes, in ledger order.
FIXES: tuple[Callable[[Graph], Graph], ...] = (unique_harassment_ids,)
