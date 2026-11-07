"""The Mindshare import document (CR-013, T13): config parts, nodes and links.

Key order as the workbook's ``importDict``: ``visuals``, ``detail``, ``dataTypes``, ``nodes``,
``links``. The config parts come from the package data extracted from Stefan's workbook (CR-005).
With a layout result (CR-014), nodes carry the layout's size and position, and the clock
image nodes are appended, in the local Mindshare's form (CR-069: ``nodeImage`` = the picture ID).
"""

from __future__ import annotations

import dataclasses
import json
from importlib.resources import files
from typing import Any

from sc2mindshare.domain.exposed import Exposed
from sc2mindshare.domain.models import Graph
from sc2mindshare.export.view import CHECK_PROPERTIES, GAME_PROPERTIES, STEP_PROPERTIES, link_view, node_view
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
                {  # CR-069: the local Mindshare's picture node: the picture by its ID, named by its file
                    "type": "image",
                    "name": clock.file_name,
                    "ID": f"clock-{clock.file_name.removesuffix('.png')}-{clock.side}",
                    "nodeImage": clock.media_id,
                    "size": [_num(v) for v in prof.clock_size],
                    "properties": {},
                    "position": {"x": _num(clock.x), "y": _num(clock.y), "z": 0.01},
                }
            )
    check_same_properties(nodes)
    document = {
        "visuals": visuals_for(cfg["visuals"], graph.export_fixes),
        "detail": detail_for(cfg["detail"], graph.export_fixes),
        "dataTypes": data_types_for(cfg["dataTypes"], graph.export_fixes),
        "nodes": nodes,
        "links": [link_view(lk) for lk in graph.links],
    }
    if analysis is not None:
        document["analysis"] = analysis_doc(analysis)
    return document


def check_same_properties(nodes: list[dict[str, Any]]) -> None:
    """CR-063 (AC-5): every node of a type must carry the same property names in the same order, or Mindshare
    refuses the whole import ("node 'Building-4' has different parameters than node 'Building-1' but the same
    type"). Raises a ValueError naming the type, the type's first node, the first node that differs from it and
    the first property that differs. Properties only: ``images`` is not compared (D5a)."""
    first: dict[str, tuple[str, tuple[str, ...]]] = {}
    for node in nodes:
        keys = tuple(node["properties"])
        first_id, first_keys = first.setdefault(node["type"], (node["ID"], keys))
        if keys != first_keys:
            raise ValueError(
                f"node type {node['type']!r}: node {node['ID']!r} has different properties than node {first_id!r} "
                f"({_first_difference(first_id, first_keys, node['ID'], keys)}); Mindshare refuses such a file"
            )


def _first_difference(id1: str, keys1: tuple[str, ...], id2: str, keys2: tuple[str, ...]) -> str:
    """The first position where two different property-name tuples differ, said in words."""
    i = next((i for i, (a, b) in enumerate(zip(keys1, keys2, strict=False)) if a != b), min(len(keys1), len(keys2)))
    if i < len(keys1) and keys1[i] not in keys2:
        return f"{id2!r} lacks property {keys1[i]!r}"
    if i < len(keys2) and keys2[i] not in keys1:
        return f"{id2!r} has property {keys2[i]!r}, which {id1!r} lacks"
    return f"property {keys1[i]!r} is at position {i + 1} in {id1!r} but at position {keys2.index(keys1[i]) + 1} in {id2!r}"


#: CR-035 BC1 (Vera's F3; Iris's qa-fix.md, P0-6 §7): the card and the missing entry as boxes, the card in the
#: workbook's Comparison blue, the missing entry with a grey border (AC5 "grey"); after the workbook's entries.
CHECK_VISUALS: tuple[dict[str, str], ...] = (
    {"nodeType": "Build Comparison", "shape": "rectangle", "borderColor": "#000066"},
    {"nodeType": "Missing Step", "shape": "rectangle", "borderColor": "#8c8c8c"},
)


def visuals_for(visuals: list[dict[str, Any]], export_fixes: frozenset[str]) -> list[dict[str, Any]]:
    """The workbook's ``visuals``; with ``BC1`` (CR-035) the build check's two node types follow, as boxes (without an
    entry Mindshare draws a small default circle). The workbook-faithful document keeps the workbook's list."""
    if "BC1" not in export_fixes:
        return visuals
    if clash := sorted({v["nodeType"] for v in CHECK_VISUALS} & {v.get("nodeType") for v in visuals}):
        raise ValueError(f"the added node types {clash} already have visuals")
    return [*visuals, *(dict(v) for v in CHECK_VISUALS)]


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
    """The workbook's ``dataTypes``; with the export fix ``G2`` (CR-067) the Game properties' types follow, and with
    ``BO1`` (CR-034) the step properties' types, and with ``BC1`` (CR-035) the build check's, after the workbook's
    entries, none of which changes (their names are new: ``view.GAME_PROPERTIES``, ``view.STEP_PROPERTIES``,
    ``view.CHECK_PROPERTIES``)."""
    added: dict[str, str] = {}
    if "G2" in export_fixes:
        added |= {name: data_type for name, _field, data_type in GAME_PROPERTIES}
    if "BO1" in export_fixes:
        added |= dict(STEP_PROPERTIES)
    if "BC1" in export_fixes:  # CR-035: one global type per name, so a name two kinds share has one type
        for properties in CHECK_PROPERTIES.values():
            for name, data_type in properties:
                if added.setdefault(name, data_type) != data_type:
                    raise ValueError(f"BC1: {name!r} is declared as {added[name]!r} and as {data_type!r}")
    if clash := sorted(set(added) & set(data_types)):
        raise ValueError(f"the added properties {clash} are already declared in dataTypes")
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
