"""Golden comparison helpers (CR-007, T07): one normaliser and one diff for every golden test.

Masking rules (stream1-plan.md §3 step 7, TD-21):

- image URLs are never compared: a CSV node row's image field, a JSON node's
  ``images`` array, and the ``name`` (a media URL) and ``ID`` (a media id plus
  1 or 2) of time-image nodes (``type == "image"``);
- floats are rounded to 4 decimals and ``-0.0`` is ``0.0``;
- key order inside an object is ignored; list order (node order) is kept;
- Supply Block ``size`` can be masked for view parity (the layout owns it,
  TD-21), with ``mask_supply_block_size=True``.
"""

from __future__ import annotations

import json
from typing import Any

MASK = "<masked>"
CSV_IMAGE_FIELD = 4
CSV_MIN_FIELDS = 7


# --- legacy events CSV ----------------------------------------------------------


def csv_records(text: str) -> list[str]:
    """Logical rows: a short physical line is the start of a field holding a raw newline."""
    out: list[str] = []
    pending: str | None = None
    for line in text.splitlines():
        pending = line if pending is None else pending + "\n" + line
        if pending.count(";") + 1 >= CSV_MIN_FIELDS:
            out.append(pending)
            pending = None
    if pending is not None:
        out.append(pending)
    return out


def normalise_csv(text: str) -> list[str]:
    rows = []
    for record in csv_records(text):
        fields = record.split(";")
        if "-" not in fields[0] and len(fields) > CSV_IMAGE_FIELD:
            fields[CSV_IMAGE_FIELD] = MASK
        rows.append(";".join(fields))
    return rows


def diff_csv(expected: str, actual: str, limit: int = 20) -> list[str]:
    """Readable differences, keyed by node ID (field 4) or by the link's two IDs."""
    exp, act = normalise_csv(expected), normalise_csv(actual)
    if exp == act:
        return []
    lines = [f"rows: expected {len(exp)}, actual {len(act)}"]
    for i, (e, a) in enumerate(zip(exp, act, strict=False)):
        if e != a:
            lines.append(f"row {i + 1} [{_csv_key(e)}]:\n  expected {e[:200]}\n  actual   {a[:200]}")
            if len(lines) > limit:
                break
    if len(exp) != len(act):
        longer, name = (exp, "expected") if len(exp) > len(act) else (act, "actual")
        for row in longer[min(len(exp), len(act)) : min(len(exp), len(act)) + 3]:
            lines.append(f"extra {name} row [{_csv_key(row)}]: {row[:200]}")
    return lines


def _csv_key(row: str) -> str:
    f = row.split(";")
    return f"{f[0]}>{f[1]}" if "-" in f[0] else (f[3] if len(f) > 3 else f[0])


# --- Mindshare JSON -------------------------------------------------------------


def _round(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        r = round(value, 4)
        return 0.0 if r == 0 else r
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def normalise_node(node: dict[str, Any], mask_supply_block_size: bool = False) -> dict[str, Any]:
    n = {k: v for k, v in node.items() if k != "images"}
    if n.get("type") == "image":
        n["name"] = MASK
        n["ID"] = MASK
    if mask_supply_block_size and n.get("type") == "Supply Block" and "size" in n:
        n["size"] = MASK
    result: dict[str, Any] = _round(n)
    return result


def normalise_json(doc: dict[str, Any], mask_supply_block_size: bool = False, drop_positions: bool = False) -> dict[str, Any]:
    out = dict(doc)
    nodes = []
    for node in doc.get("nodes", []):
        n = normalise_node(node, mask_supply_block_size)
        if drop_positions:
            n.pop("position", None)
        nodes.append(n)
    out["nodes"] = nodes
    result: dict[str, Any] = _round(out)
    return result


def diff_json(
    expected: dict[str, Any],
    actual: dict[str, Any],
    mask_supply_block_size: bool = False,
    drop_positions: bool = False,
    limit: int = 20,
) -> list[str]:
    exp = normalise_json(expected, mask_supply_block_size, drop_positions)
    act = normalise_json(actual, mask_supply_block_size, drop_positions)
    if exp == act:
        return []
    lines: list[str] = []
    for key in sorted(set(exp) | set(act)):
        if key in ("nodes", "links"):
            continue
        if exp.get(key) != act.get(key):
            lines.append(f"{key}: expected {_short(exp.get(key))}, actual {_short(act.get(key))}")
    lines += _diff_items("node", exp.get("nodes", []), act.get("nodes", []), limit)
    lines += _diff_items("link", exp.get("links", []), act.get("links", []), limit)
    return lines


def _item_key(kind: str, item: dict[str, Any]) -> str:
    if kind == "node":
        return str(item.get("ID"))
    return f"{item.get('node1')}>{item.get('node2')}"


def _diff_items(kind: str, exp: list[dict[str, Any]], act: list[dict[str, Any]], limit: int) -> list[str]:
    lines: list[str] = []
    if len(exp) != len(act):
        lines.append(f"{kind}s: expected {len(exp)}, actual {len(act)}")
    for i, (e, a) in enumerate(zip(exp, act, strict=False)):
        if e != a:
            fields = sorted(k for k in set(e) | set(a) if e.get(k) != a.get(k))
            details = ", ".join(f"{k}: {_short(e.get(k))} != {_short(a.get(k))}" for k in fields)
            lines.append(f"{kind} {i + 1} [{_item_key(kind, e)}]: {details}")
            if len(lines) >= limit:
                break
    return lines


def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= 120 else text[:117] + "..."
