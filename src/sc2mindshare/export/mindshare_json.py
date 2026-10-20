"""The Mindshare import document (CR-013, T13): config parts, nodes and links.

Key order as the workbook's ``importDict``: ``visuals``, ``detail``, ``dataTypes``, ``nodes``,
``links``. The config parts come from the package data extracted from Stefan's workbook (CR-005).
With a layout result (CR-014), nodes carry the layout's size and position, and the clock
image nodes are appended.
"""

from __future__ import annotations

import dataclasses
import json
from importlib.resources import files
from typing import Any

from sc2mindshare.domain.exposed import Exposed
from sc2mindshare.domain.models import Graph
from sc2mindshare.export.view import GAME_PROPERTIES, link_view, node_view
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import LayoutResult


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


def analysis_doc(exposed: Exposed) -> dict[str, Any]:
    """The exposed analysis values (CR-021) as plain JSON data; tuples become lists."""

    def lists(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: lists(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [lists(v) for v in value]
        return value

    return dict(lists(dataclasses.asdict(exposed)))


def build_document(
    graph: Graph,
    placed: LayoutResult | None = None,
    config: dict[str, Any] | None = None,
    profile: Profile | None = None,
    analysis: Exposed | None = None,
) -> dict[str, Any]:
    """The Mindshare document; with ``placed`` (the layout's result) every node gets its size and
    position, and the clock image nodes follow the graph's nodes (layout-spec.md §6). With
    ``analysis`` (opt-in, CR-021) the exposed values follow as a top-level ``analysis`` object."""
    cfg = config if config is not None else load_config()
    prof = profile or Profile()
    nodes = []
    for node in graph.nodes:
        view = node_view(node, graph.export_fixes)
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
    document = {
        "visuals": cfg["visuals"],
        "detail": detail_for(cfg["detail"], graph.export_fixes),
        "dataTypes": data_types_for(cfg["dataTypes"], graph.export_fixes),
        "nodes": nodes,
        "links": [link_view(lk) for lk in graph.links],
    }
    if analysis is not None:
        document["analysis"] = analysis_doc(analysis)
    return document


def detail_for(detail: list[dict[str, Any]], export_fixes: frozenset[str]) -> list[dict[str, Any]]:
    """The workbook's ``detail``; with the export fix ``B12`` (CR-023, D16a) only properties that exist: Stats'
    "eco Min" (the layer emits no economy spending) is dropped and Initiated's "subtype" is its "type"; with ``G2``
    (CR-067) a Game entry follows the others."""
    out = list(detail)
    if "B12" in export_fixes:
        out = []
        for entry in detail:
            props = [p for p in entry["properties"] if not (entry["nodeType"] == "Stats" and p == "eco Min")]
            if entry["nodeType"] == "Initiated":
                props = ["type" if p == "subtype" else p for p in props]
            out.append({**entry, "properties": props})
    if "G2" in export_fixes:  # CR-067 G2: the Game node's date and length as its details
        out.append({"nodeType": "Game", "properties": list(GAME_DETAIL)})
    return out


#: CR-067 G2: the Game properties its Details entry names.
GAME_DETAIL = ("date played (UTC)", "length")


def data_types_for(data_types: dict[str, str], export_fixes: frozenset[str]) -> dict[str, str]:
    """The workbook's ``dataTypes``; with the export fix ``G2`` (CR-067) the Game properties' types follow, after the
    workbook's entries, none of which changes (their names are new: ``view.GAME_PROPERTIES``)."""
    if "G2" not in export_fixes:
        return data_types
    added = {name: data_type for name, _field, data_type in GAME_PROPERTIES}
    if clash := sorted(set(added) & set(data_types)):
        raise ValueError(f"G2: the Game properties {clash} are already declared in dataTypes")
    return data_types | added


def _vba_numbers(value: Any) -> Any:
    """Whole-number floats as integers, as VBA-JSON writes a Double (``2``, not ``2.0``; D7a A12).

    Other floats keep Python's ``repr``, which matches VBA's text only while it has no exponent form.
    That holds for the layout's numbers because ``_num`` rounds them to 4 decimal places first (the
    smallest non-zero value is 0.0001, written ``0.0001``; repr switches to ``1e-05`` below 1e-4 and to
    ``1e+16`` at 1e16). A float that skipped the rounding could print an exponent VBA would not."""
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
