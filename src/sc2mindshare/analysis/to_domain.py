"""The analysis result as domain models (CR-012, T12): nodes, links, graph.

Strangler step: the moved legacy node and link objects are read once, at the end of the analysis,
through their own getters (name, description, type, ID, images, properties), and turned into
frozen ``domain`` models with declared fields. Nothing downstream reads the legacy objects.

Times become numbers here (CR-022, T21): the legacy time text is read once into a ``GameTime``
(``typed_values``), and only ``export/`` writes it back as text.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from sc2mindshare.analysis.build_steps import build_order, with_build_order
from sc2mindshare.analysis.fixes import EXPORT_FIXES, FIXES, LAYER_FIXES
from sc2mindshare.analysis.run import AnalysisResult
from sc2mindshare.domain.models import FIELDS, TIME_FIELDS, Graph, Link, Node, Value
from sc2mindshare.domain.steps import NodeSource
from sc2mindshare.domain.time import GameTime
from sc2mindshare.reader.compat import LOOPS_PER_SECOND

#: A separator no legacy text contains, so property values may hold ";" safely.
_SEP = "\x1f"


def _seconds(text: str) -> int:
    """Seconds from the legacy time text: ``HH:MM:SS``, or ``MM:SS`` (Scouting's form)."""
    parts = [int(p) for p in text.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    raise ValueError(f"not a time: {text!r}")


def _start_seconds(kind: str, node: Any, values: dict[str, str]) -> int | None:
    if kind in ("Game", "Player"):
        return None
    if kind == "Building":  # done time minus build time, without the legacy text's midnight wrap (B9)
        return int(node.event.frame / LOOPS_PER_SECOND) - int(node.buildTime)
    if kind == "Upgrade":  # completion minus research time, likewise
        return int(node.event.frame / LOOPS_PER_SECOND) - int(node.upgradeTime)
    return _seconds(values["time"])


def typed_values(
    node_id: str, kind: str, raw: Iterable[tuple[str, str]], start_seconds: int | None
) -> tuple[tuple[tuple[str, Value], ...], GameTime | None]:
    """The fields of a node read from the legacy text, its times as ``GameTime``, and its start.

    A node's ``time`` is its signed start: the legacy text is that second wrapped at midnight
    (tests/analysis/test_time.py), and anything else is refused, so no time changes silently. An
    ``end time`` is its second; ``None`` is an open end."""
    start = None if start_seconds is None else GameTime.from_seconds(start_seconds)
    values: list[tuple[str, Value]] = []
    for name, text in raw:
        if name not in TIME_FIELDS:
            values.append((name, text))
        elif text == "None":
            values.append((name, None))
        elif name == "time":
            if start is None or _seconds(text) != start.seconds % 86400:
                raise ValueError(f"{node_id}: time {text!r} is not its start {start_seconds} s")
            values.append((name, start))
        else:
            values.append((name, GameTime.from_seconds(_seconds(text))))
    return tuple(values), start


def node_source(kind: str, node: Any) -> NodeSource | None:
    """What a legacy node was built from (CR-034): the join of the build steps to the nodes."""
    if kind == "Player":
        return NodeSource(pid=int(node.pid))
    if kind == "Building":
        return NodeSource(unit_ids=(int(node.event.unit.id),))
    if kind == "Units":
        return NodeSource(unit_ids=tuple(int(e.unit.id) for e in node.events))
    if kind == "Upgrade":
        e = node.event
        return NodeSource(pid=int(e.pid), upgrade=str(e.upgrade_type_name), loop=int(e.frame))
    return None


def node_model(node: Any) -> Node:
    kind = str(node.getNodeType())
    raw = str(node.getProperties(_SEP)).split(_SEP)
    if raw and raw[-1] == "":
        raw = raw[:-1]
    names = FIELDS.get(kind)
    if names is None or len(names) != len(raw):
        raise ValueError(f"{node.getNodeID()}: {len(raw)} property values for kind {kind!r}, declared {names}")
    texts = dict(zip(names, raw, strict=True))
    node_id = str(node.getNodeID())
    values, start = typed_values(node_id, kind, texts.items(), _start_seconds(kind, node, texts))
    return Node(
        kind=kind,
        id=node_id,
        name=str(node.getNodeName()),
        description=str(node.getNodeDescription()),
        images=tuple(str(u) for u in node.images),
        values=values,
        start=start,
        source=node_source(kind, node),
    )


def link_model(link: Any) -> Link:
    one_word = link.name is not None
    return Link(
        node1=str(link.node1.getNodeID()),
        node2=str(link.node2.getNodeID()),
        name1="" if one_word else str(link.name1),
        name2="" if one_word else str(link.name2),
        description=str(link.getDescription()),
        direction=int(link.getProperties(_SEP)),
        name=str(link.name) if one_word else None,
    )


def to_graph(result: AnalysisResult, fixes: Sequence[Callable[[Graph], Graph]] | None = None, *, mixed: bool = False) -> Graph:
    """The domain graph of ``result``, with the ledger's graph fixes applied (``fixes=()`` for the
    bug-faithful graph that renders the legacy CSV oracle). The current graph (every layer and graph fix on)
    also carries each player's build order (CR-034, ``analysis.build_steps``; ledger BO1, on by default, D47a),
    made from ``result.exposed``; a mixed run has none (its steps would read names and types the layer fixes
    it leaves out would change, such as N1's type-at-the-time names).

    Only the two pure combinations are accepted: every layer and graph fix on (the default with a result
    of ``analyse``'s default), or none (``fixes=()`` with ``analyse(..., fixes=())``). Any other mix, such as
    a bug-faithful result with the graph fixes, a partial layer set, or some of the graph fixes, is refused
    unless ``mixed=True`` asks for it, so neither output is ever half fixed by accident (CR-023)."""
    graph_fixes = tuple(FIXES if fixes is None else fixes)
    all_off = not graph_fixes and not result.fixes
    all_on = graph_fixes == FIXES and result.fixes == frozenset(LAYER_FIXES)
    if not mixed and not (all_off or all_on):
        if not graph_fixes:
            raise ValueError(
                f"fixes=() asks for the bug-faithful graph; this result has layer fixes {sorted(result.fixes)} (analyse(..., fixes=()))"
            )
        raise ValueError(
            f"a mixed run: layer fixes {sorted(result.fixes)} with {len(graph_fixes)} of {len(FIXES)} graph fixes; "
            "use both all on or both off, or pass mixed=True"
        )
    export_fixes = frozenset(EXPORT_FIXES) if graph_fixes == FIXES else frozenset()
    graph = Graph(
        nodes=tuple(node_model(n) for n in result.nodes),
        links=tuple(link_model(lk) for lk in result.links),
        intervals=result.intervals,
        export_fixes=export_fixes if all_on else export_fixes - {"BO1"},  # the step properties go with the steps
    )
    for fix in graph_fixes:
        graph = fix(graph)
    if all_on:
        if result.exposed is None:
            raise ValueError("the build steps (CR-034) need the exposed values: analyse(..., with_exposed=True)")
        order = build_order(result.exposed, result.fixes)
        for note in order.estimated:  # D60a: an estimated start is a data-quality finding for the run log only
            print(note)
        graph = with_build_order(graph, order, result.fixes)
    return graph
