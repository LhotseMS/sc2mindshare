"""Defect fixes (CR-014 onwards), one per ledger entry, each with an entry in tests/golden/CHANGES.md
written before it.

Two kinds. A graph fix here is a function on the domain graph; ``to_domain.to_graph`` applies
``FIXES`` in order. A layer fix (``LAYER_FIXES``) changes how the moved legacy layer computes
something, so it lives at its call site in the layer, switched by its ledger id in
``AnalysisContext.fixes``. Both are off for the bug-faithful run (``analyse(..., fixes=())`` and
``to_graph(..., fixes=())``), so its CSV oracle keeps proving the move changed nothing.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import replace

from sc2mindshare.domain.models import Graph
from sc2mindshare.domain.time import GameTime


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
    """``-hh:mm:ss`` for a negative number of seconds, ``hh:mm:ss`` otherwise (no midnight wrap).

    The one time formatter outside ``export/`` (stated in ``domain.time``): it writes description prose for
    ``pre_game_display``, and ``analysis`` may not import ``export``."""
    sign, rest = ("-", -seconds) if seconds < 0 else ("", seconds)
    return f"{sign}{rest // 3600:02d}:{rest // 60 % 60:02d}:{rest % 60:02d}"


def pre_game_note(start_seconds: int) -> str:
    """The description sentence of a pre-game item: ``Started 71 s before the game (real start -00:01:11).``"""
    return f"Started {-start_seconds} s before the game (real start {signed_hhmmss(start_seconds)})."


def pre_game_display(graph: Graph) -> Graph:
    """P3d (D7a A9), as amended by P3e (D3c): a pre-game item (negative start, the main bases at -71 s)
    shows ``time`` 00:00:00, and its real start goes into its description (``pre_game_note``), not into
    a property: Mindshare refuses an import where nodes of one type have different property keys. The
    legacy text wraps to ``23:58:49``; ``start`` (what the layout reads) is unchanged."""
    nodes = []
    for node in graph.nodes:
        if node.start is not None and node.start.seconds < 0:
            values = tuple((name, GameTime(0) if name == "time" else value) for name, value in node.values)
            note = pre_game_note(node.start.seconds)
            description = node.description
            if note not in description:  # the note once, whatever the description held
                description = f"{description}X_LDX_LD{note}" if description else note
            node = replace(node, values=values, description=description)
        nodes.append(node)
    return replace(graph, nodes=tuple(nodes))


#: The fixes, in ledger order.
FIXES: tuple[Callable[[Graph], Graph], ...] = (unique_harassment_ids, pre_game_display)

#: The layer fixes, by ledger id (CR-023): P1, ``BaseDetector.getClosestBase`` compares real distances;
#: P1b (D8a), it skips a base whose init/born second is after the battle's start; P1c (D10a), and one
#: whose town hall is not standing then (destroyed, not yet rebuilt); S1 (D9a, TD-27), the supply
#: tracker: no double count of the starting units and providers, real provider values by the type at
#: the event, and a block judged once per loop; P8, the last Units interval is written; P2, race words
#: are no longer stripped from inside names (the name cleaning takes the fixes explicitly); P11 (D11a),
#: ``BaseDetector.isNearMinerals`` needs a mineral field within 7 cells on both axes; N1 (D6a), units,
#: buildings and battle killers are named by their type at the time of the event, not their final type;
#: P10, spell effects (Disruptor Phased, Adept Phase Shift) are no units, and eligibility reads the type at
#: the event; S6 (D15a), a unit counts its type's supply when it finishes and the difference at each type
#: change, and a Units group adds its units' supply at their event.
LAYER_FIXES: tuple[str, ...] = ("P1", "P1b", "P1c", "S1", "P8", "P2", "P11", "N1", "P10", "S6")


#: The export fixes, by ledger id (CR-023): fixes of what the view emits, carried by the domain graph
#: (``Graph.export_fixes``) and on with the graph fixes: B3, an Ability's ``combat``, ``queued`` and
#: ``minimap`` are emitted (the workbook never set ``combatSet``); P13 (B11), every time property is
#: ``hh:mm:ss`` of game time (export.time_text); B12 (D16a), ``detail`` lists only properties that exist.
EXPORT_FIXES: tuple[str, ...] = ("B3", "P13", "B12")


def check_layer_fixes(fixes: Iterable[str]) -> frozenset[str]:
    """The layer fix ids as a set; an id that is not in ``LAYER_FIXES`` is refused (a misspelt id would
    otherwise switch nothing on, silently)."""
    chosen = frozenset(fixes)
    unknown = sorted(chosen - set(LAYER_FIXES))
    if unknown:
        raise ValueError(f"unknown layer fix ids {unknown}; the layer fixes are {list(LAYER_FIXES)}")
    return chosen
