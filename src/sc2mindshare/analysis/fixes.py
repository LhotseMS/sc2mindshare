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
    """H1: one game-wide Harrasment sequence in node order (the legacy layer numbers per battle).

    The new sequence starts at ``Harrasment-1``; the legacy one started at ``Harrasment-0``."""
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


def signed_hhmmss(seconds: int) -> str:
    """``-hh:mm:ss`` for a negative number of seconds, ``hh:mm:ss`` otherwise (no midnight wrap)."""
    sign, rest = ("-", -seconds) if seconds < 0 else ("", seconds)
    return f"{sign}{rest // 3600:02d}:{rest // 60 % 60:02d}:{rest % 60:02d}"


def pre_game_note(start_seconds: int) -> str:
    """The description sentence of a pre-game item: ``Started 71 s before the game (real start -00:01:11).``"""
    return f"Started {-start_seconds} s before the game (real start {signed_hhmmss(start_seconds)})."


def pre_game_display(graph: Graph) -> Graph:
    """P3d (D7a A9), as amended by P3e (D3c): a pre-game item (negative start, the main bases at -71 s)
    shows ``time`` 00:00:00, and its real start goes into its description (``pre_game_note``), not into
    a property: Mindshare refuses an import where nodes of one type have different property keys. The
    legacy text wraps to ``23:58:49``; ``start_seconds`` (what the layout reads) is unchanged."""
    nodes = []
    for node in graph.nodes:
        if node.start_seconds is not None and node.start_seconds < 0:
            note = pre_game_note(node.start_seconds)
            if note not in node.description:
                values = tuple((name, "00:00:00" if name == "time" else value) for name, value in node.values)
                description = f"{node.description}X_LDX_LD{note}" if node.description else note
                node = replace(node, values=values, description=description)
        nodes.append(node)
    return replace(graph, nodes=tuple(nodes))


#: The fixes, in ledger order.
FIXES: tuple[Callable[[Graph], Graph], ...] = (unique_harassment_ids, pre_game_display)
