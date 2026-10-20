"""The Mindshare import document (CR-013, T13): config parts, nodes and links.

Key order as the workbook's ``importDict``: ``visuals``, ``detail``, ``dataTypes``, ``nodes``,
``links``. The config parts come from the package data extracted from Stefan's workbook (CR-005).
Positions are added by the layout (CR-014); until then nodes carry none.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from sc2mindshare.domain.models import Graph
from sc2mindshare.export.view import link_view, node_view


def load_config() -> dict[str, Any]:
    root = files("sc2mindshare") / "config"
    return {
        "visuals": json.loads((root / "visuals.json").read_text(encoding="utf-8")),
        "detail": json.loads((root / "details.json").read_text(encoding="utf-8")),
        "dataTypes": json.loads((root / "data_types.json").read_text(encoding="utf-8")),
    }


def build_document(graph: Graph, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config if config is not None else load_config()
    return {
        "visuals": cfg["visuals"],
        "detail": cfg["detail"],
        "dataTypes": cfg["dataTypes"],
        "nodes": [node_view(n) for n in graph.nodes],
        "links": [link_view(lk) for lk in graph.links],
    }


def to_json(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=1) + "\n"
