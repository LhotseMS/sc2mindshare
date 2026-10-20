"""The Mindshare import document (CR-013, T13): config parts, nodes and links.

Key order as the workbook's ``importDict``: ``visuals``, ``detail``, ``dataTypes``, ``nodes``,
``links``. The config parts come from the package data extracted from Stefan's workbook (CR-005).
With a layout result (CR-014), nodes carry the layout's size and position, and the clock
image nodes are appended.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from sc2mindshare.domain.models import Graph
from sc2mindshare.export.view import link_view, node_view
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutResult

#: The Mindshare data type of each property a ledger fix may add (domain.models.EXTRA_FIELDS).
#: "pre-game time" is text: ``time[h:m:s]`` cannot hold a negative time.
EXTRA_DATA_TYPES: dict[str, str] = {"pre-game time": "string"}


def load_config() -> dict[str, Any]:
    root = files("sc2mindshare") / "config"
    return {
        "visuals": json.loads((root / "visuals.json").read_text(encoding="utf-8")),
        "detail": json.loads((root / "details.json").read_text(encoding="utf-8")),
        "dataTypes": json.loads((root / "data_types.json").read_text(encoding="utf-8")),
    }


def _num(value: float) -> float:
    """4 decimal places, and no -0.0 (layout-spec.md §2)."""
    r = round(float(value), 4)
    return 0.0 if r == 0 else r


def _size(size: Any) -> Any:
    return [_num(v) for v in size] if isinstance(size, list | tuple) else _num(size)


def build_document(
    graph: Graph, placed: LayoutResult | None = None, config: dict[str, Any] | None = None, profile: Profile | None = None
) -> dict[str, Any]:
    """The Mindshare document; with ``placed`` (the layout's result) every node gets its size and
    position, and the clock image nodes follow the graph's nodes (layout-spec.md §6)."""
    cfg = config if config is not None else load_config()
    prof = profile or Profile()
    nodes = []
    for node in graph.nodes:
        view = node_view(node)
        if placed is not None:
            view["size"] = _size(placed.sizes[node.id])
            x, y = placed.positions[node.id]
            view["position"] = {"x": _num(x), "y": _num(y), "z": 0.01}
        nodes.append(view)
    if placed is not None:
        for clock in placed.extra_nodes:
            nodes.append(
                {
                    "type": "image",
                    "name": prof.clock_host + clock.media_id,
                    "ID": clock.media_id + str(clock.side),
                    "size": [_num(v) for v in prof.clock_size],
                    "properties": {},
                    "position": {"x": _num(clock.x), "y": _num(clock.y), "z": 0.01},
                }
            )
    used = {name for node in graph.nodes for name, _ in node.extra}
    data_types = cfg["dataTypes"] | {name: kind for name, kind in EXTRA_DATA_TYPES.items() if name in used}
    return {
        "visuals": cfg["visuals"],
        "detail": cfg["detail"],
        "dataTypes": data_types,
        "nodes": nodes,
        "links": [link_view(lk) for lk in graph.links],
    }


def _vba_numbers(value: Any) -> Any:
    """Whole-number floats as integers, as VBA-JSON writes a Double (``2``, not ``2.0``; D7a A12)."""
    if isinstance(value, float) and value.is_integer():
        return int(value)  # -0.0 becomes 0
    if isinstance(value, dict):
        return {k: _vba_numbers(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_vba_numbers(v) for v in value]
    return value


def to_json(document: dict[str, Any]) -> str:
    """The document as text, numbers in VBA-JSON's format (after the 4-decimal rounding of ``_num``)."""
    return json.dumps(_vba_numbers(document), ensure_ascii=False, indent=1) + "\n"
