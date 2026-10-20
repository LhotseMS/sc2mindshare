"""The analysis result as domain models (CR-012, T12): nodes, links, graph.

Strangler step: the moved legacy node and link objects are read once, at the end of the analysis,
through their own getters (name, description, type, ID, images, properties), and turned into
frozen ``domain`` models with declared fields. Nothing downstream reads the legacy objects.
"""

from __future__ import annotations

from typing import Any

from sc2mindshare.analysis.run import AnalysisResult
from sc2mindshare.domain.models import FIELDS, Graph, Link, Node
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


def node_model(node: Any) -> Node:
    kind = str(node.getNodeType())
    raw = str(node.getProperties(_SEP)).split(_SEP)
    if raw and raw[-1] == "":
        raw = raw[:-1]
    names = FIELDS.get(kind)
    if names is None or len(names) != len(raw):
        raise ValueError(f"{node.getNodeID()}: {len(raw)} property values for kind {kind!r}, declared {names}")
    values = dict(zip(names, raw, strict=True))
    return Node(
        kind=kind,
        id=str(node.getNodeID()),
        name=str(node.getNodeName()),
        description=str(node.getNodeDescription()),
        images=tuple(str(u) for u in node.images),
        values=tuple(values.items()),
        start_seconds=_start_seconds(kind, node, values),
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


def to_graph(result: AnalysisResult) -> Graph:
    return Graph(
        nodes=tuple(node_model(n) for n in result.nodes),
        links=tuple(link_model(lk) for lk in result.links),
        intervals=result.intervals,
    )
