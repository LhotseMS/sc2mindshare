"""Golden comparison (CR-007, T07), built to Vera's design (`qa-golden-design.md` §1).

One pipeline for every golden: parse -> mask (M1-M4, each counted) -> canonicalise
numbers -> compare -> diff report.

CSV level (legacy events CSV): physical lines exactly as written (records are never
repaired), split on ``;``, every field compared as text. Only mask: M1 on column 5 of
node rows (each URL becomes ``<img>``, the ``|`` separators and any non-URL text kept).

JSON level: key order ignored, list order kept, type classes must match (``true`` is
not ``1``), numbers rounded to 4 dp with ``-0.0`` as ``0.0`` (``2 == 2.0``), non-finite
numbers fail. Masks: M1 ``images`` arrays (each URL -> ``<img>``, length kept); M2 clock
nodes (``type == "image"``) mapped back through the clock map to ``<clock:0-50.png>`` and
``<clock:0-50.png>#1``; and, for the view comparison only, M3 Supply Block ``size`` ->
``<layout-owned>`` and M4 (``position`` removed, clock nodes removed).

Records are keyed by ``(ID, occurrence)`` (``Harrasment-0#3``), because node IDs repeat.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

IMG = "<img>"
LAYOUT_OWNED = "<layout-owned>"
CSV_IMAGE_FIELD = 4
MAX_RECORDS_IN_FULL = 50


class GoldenError(AssertionError):
    """A comparison that cannot be made (non-finite number, missing clock map, changed input)."""


class InputMissing(Exception):
    """A golden's input (MS SC/, the legacy venv) is absent: skip, or fail under SC2MS_REQUIRE_GOLDEN=1."""


def require(path: Path, what: str) -> Path:
    if not path.exists():
        raise InputMissing(f"{what} not found: {path}")
    return path


def strict() -> bool:
    return os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1"


# --- pins -------------------------------------------------------------------------


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_pins(path: Path) -> dict[str, str]:
    """``<sha256>  <name>`` per line (``sha256sum`` format)."""
    pins = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split(None, 1)
            pins[name.strip()] = digest
    return pins


def check_pins(pins_file: Path, files: Mapping[str, Path]) -> None:
    pins = read_pins(pins_file)
    for name, path in files.items():
        if name not in pins:
            raise GoldenError(f"no pin for {name} in {pins_file.name}")
        if sha256(path) != pins[name]:
            raise GoldenError(f"input changed: {name}")


# --- reports ----------------------------------------------------------------------


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    changed: list[tuple[str, str]] = field(default_factory=list)  # (record key, field path)
    budget_expected: Counter[str] = field(default_factory=Counter)
    budget_actual: Counter[str] = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.lines

    def __str__(self) -> str:
        return "\n".join(self.lines) if self.lines else "identical"


# --- CSV ----------------------------------------------------------------------------


def _is_link(fields: Sequence[str]) -> bool:
    return "-" in fields[0]


def _is_url(text: str) -> bool:
    # Only URLs are masked: the second half of a row split by a raw newline (P7) is also a
    # "node row" on its own line, and its column 5 holds a time that must stay compared.
    return text.startswith(("http://", "https://"))


def normalise_csv(text: str) -> tuple[list[str], Counter[str]]:
    """Masked physical lines and the mask budget."""
    budget: Counter[str] = Counter()
    out = []
    for line in text.split("\n"):
        fields = line.split(";")
        if not _is_link(fields) and len(fields) > CSV_IMAGE_FIELD and fields[CSV_IMAGE_FIELD] != "":
            parts = fields[CSV_IMAGE_FIELD].split("|")
            budget["M1"] += sum(1 for u in parts if _is_url(u))
            fields[CSV_IMAGE_FIELD] = "|".join(IMG if _is_url(u) else u for u in parts)
        out.append(";".join(fields))
    return out, budget


def csv_keys(lines: Sequence[str]) -> list[str]:
    seen: Counter[str] = Counter()
    keys = []
    for line in lines:
        f = line.split(";")
        if _is_link(f):
            base = f"{f[0]}>{f[1] if len(f) > 1 else ''}>{f[2] if len(f) > 2 else ''}"
        elif len(f) > 3:
            base = f[3]
        else:
            base = "<fragment>"
        seen[base] += 1
        keys.append(f"{base}#{seen[base]}")
    return keys


def diff_csv(expected: str, actual: str) -> Report:
    report = Report()
    if "\r" in actual and "\r" not in expected:
        report.lines.append("line endings differ: actual has \\r")
    if expected.endswith("\n") != actual.endswith("\n"):
        report.lines.append("final newline differs")
    exp, budget_e = normalise_csv(expected)
    act, budget_a = normalise_csv(actual)
    report.budget_expected, report.budget_actual = budget_e, budget_a
    if budget_e != budget_a:
        report.lines.append(f"mask budget differs: expected {dict(budget_e)}, actual {dict(budget_a)}")
    if exp == act:
        return report
    if Counter(exp) == Counter(act):
        first = next(i for i, (e, a) in enumerate(zip(exp, act, strict=True)) if e != a)
        last = max(i for i, (e, a) in enumerate(zip(exp, act, strict=True)) if e != a)
        report.lines.append(f"order differs at lines {first + 1}...{last + 1} (same records)")
        return report
    keys_e, keys_a = csv_keys(exp), csv_keys(act)
    shown = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=exp, b=act, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for k in range(max(i2 - i1, j2 - j1)):
            e = exp[i1 + k] if i1 + k < i2 else None
            a = act[j1 + k] if j1 + k < j2 else None
            key = keys_e[i1 + k] if e is not None else keys_a[j1 + k]
            if e is not None and a is not None:
                fe, fa = e.split(";"), a.split(";")
                fields_changed = [str(n) for n in range(max(len(fe), len(fa))) if (fe + [None] * 99)[n] != (fa + [None] * 99)[n]]
                report.changed += [(key, f"field {n}") for n in fields_changed]
                detail = f"fields {','.join(fields_changed)}: {e[:160]!r} -> {a[:160]!r}"
            elif e is not None:
                report.changed.append((key, "<removed>"))
                detail = f"removed: {e[:160]!r}"
            else:
                report.changed.append((key, "<added>"))
                detail = f"added: {(a or '')[:160]!r}"
            shown += 1
            if shown <= MAX_RECORDS_IN_FULL:
                report.lines.append(f"{key}: {detail}")
    if shown > MAX_RECORDS_IN_FULL:
        report.lines.append(f"... {shown - MAX_RECORDS_IN_FULL} more changed lines")
    return report


# --- JSON ---------------------------------------------------------------------------


def load_clock_map(time_image_tracking_csv: Path) -> dict[str, str]:
    """media id -> file name (``0-50.png``), from ``TimeImageTracking.csv``."""
    out = {}
    for line in time_image_tracking_csv.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip():
            name, media_id = line.strip().split(",")
            out[media_id] = name
    return out


def _canon(value: Any, where: str) -> Any:
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise GoldenError(f"non-finite number at {where}: {value}")
        r = round(float(value), 4)
        return ("num", 0.0 if r == 0 else r)
    if value is None:
        return ("null",)
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, list):
        return ("list", tuple(_canon(v, f"{where}[{i}]") for i, v in enumerate(value)))
    if isinstance(value, dict):
        return ("obj", tuple(sorted((k, _canon(v, f"{where}.{k}")) for k, v in value.items())))
    raise GoldenError(f"unexpected JSON type at {where}: {type(value).__name__}")


def _clock_name(media_id_with_suffix: str, clock_map: Mapping[str, str]) -> tuple[str, str]:
    for suffix in ("1", "2"):
        if media_id_with_suffix.endswith(suffix) and media_id_with_suffix[:-1] in clock_map:
            name = clock_map[media_id_with_suffix[:-1]]
            return f"<clock:{name}>", f"<clock:{name}>#{suffix}"
    return "<clock:unknown>", "<clock:unknown>"


def normalise_nodes(
    nodes: Sequence[Mapping[str, Any]], clock_map: Mapping[str, str] | None, view: bool
) -> tuple[list[dict[str, Any]], Counter[str]]:
    budget: Counter[str] = Counter()
    out = []
    for node in nodes:
        n = dict(node)
        if n.get("type") == "image":
            if view:
                budget["M4 clock"] += 1
                continue
            if clock_map is None:
                raise InputMissing("clock map (TimeImageTracking.csv) needed for clock nodes")
            media = str(n.get("name", "")).rsplit("/", 1)[-1]
            n["name"], _ = _clock_name(media + "1", clock_map)
            _, n["ID"] = _clock_name(str(n.get("ID", "")), clock_map)
            budget["M2"] += 1
        if "images" in n and isinstance(n["images"], list):
            budget["M1"] += len(n["images"])
            n["images"] = [IMG for _ in n["images"]]
        if view:
            if n.get("type") == "Supply Block" and "size" in n:
                n["size"] = LAYOUT_OWNED
                budget["M3"] += 1
            if "position" in n:
                del n["position"]
                budget["M4 position"] += 1
        out.append(n)
    return out, budget


def node_keys(nodes: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: Counter[str] = Counter()
    keys = []
    for n in nodes:
        base = str(n.get("ID"))
        seen[base] += 1
        keys.append(f"{base}#{seen[base]}")
    return keys


def _field_diff(e: Any, a: Any, path: str, out: list[tuple[str, Any, Any]]) -> None:
    if isinstance(e, dict) and isinstance(a, dict):
        for k in sorted(set(e) | set(a)):
            if k not in e or k not in a:
                out.append((f"{path}.{k}".lstrip("."), e.get(k, "<missing>"), a.get(k, "<missing>")))
            else:
                _field_diff(e[k], a[k], f"{path}.{k}", out)
    elif _canon(e, path) != _canon(a, path):
        out.append((path.lstrip("."), e, a))


def diff_json(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    clock_map: Mapping[str, str] | None = None,
    view: bool = False,
) -> Report:
    report = Report()
    exp_nodes, be = normalise_nodes(expected.get("nodes", []), clock_map, view)
    act_nodes, ba = normalise_nodes(actual.get("nodes", []), clock_map, view)
    report.budget_expected, report.budget_actual = be, ba
    if be != ba:
        report.lines.append(f"mask budget differs: expected {dict(be)}, actual {dict(ba)}")
    for key in sorted((set(expected) | set(actual)) - {"nodes", "links"}):
        if key not in expected or key not in actual or _canon(expected[key], key) != _canon(actual[key], key):
            report.lines.append(f"{key}: differs")
            report.changed.append((key, ""))
    _diff_lists(report, "node", exp_nodes, act_nodes, node_keys(exp_nodes), node_keys(act_nodes))
    exp_links, act_links = list(expected.get("links", [])), list(actual.get("links", []))
    link_key = [f"{x.get('node1')}>{x.get('node2')}" for x in exp_links]
    link_key_a = [f"{x.get('node1')}>{x.get('node2')}" for x in act_links]
    _diff_lists(report, "link", exp_links, act_links, _occ(link_key), _occ(link_key_a))
    return report


def _occ(keys: Sequence[str]) -> list[str]:
    seen: Counter[str] = Counter()
    out = []
    for k in keys:
        seen[k] += 1
        out.append(f"{k}#{seen[k]}")
    return out


def _diff_lists(
    report: Report,
    kind: str,
    exp: Sequence[Mapping[str, Any]],
    act: Sequence[Mapping[str, Any]],
    keys_e: Sequence[str],
    keys_a: Sequence[str],
) -> None:
    canon_e = [_canon(x, kind) for x in exp]
    canon_a = [_canon(x, kind) for x in act]
    if canon_e == canon_a:
        return
    if Counter(canon_e) == Counter(canon_a):
        diffs = [i for i, (e, a) in enumerate(zip(canon_e, canon_a, strict=True)) if e != a]
        report.lines.append(f"{kind}s: order differs at positions {diffs[0] + 1}...{diffs[-1] + 1} (same records)")
        report.changed.append((f"{kind}s", "<order>"))
        return
    shown = 0
    summary: Counter[tuple[str, str]] = Counter()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=canon_e, b=canon_a, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for k in range(max(i2 - i1, j2 - j1)):
            e = exp[i1 + k] if i1 + k < i2 else None
            a = act[j1 + k] if j1 + k < j2 else None
            key = keys_e[i1 + k] if e is not None else keys_a[j1 + k]
            if e is not None and a is not None:
                fields: list[tuple[str, Any, Any]] = []
                _field_diff(dict(e), dict(a), "", fields)
                for path, old, new in fields:
                    report.changed.append((key, path))
                    summary[(str(e.get("type", kind)), path)] += 1
                text = "; ".join(f"{p}: {json.dumps(o)[:80]} -> {json.dumps(n)[:80]}" for p, o, n in fields)
            elif e is not None:
                report.changed.append((key, "<removed>"))
                text = "removed"
            else:
                report.changed.append((key, "<added>"))
                text = "added"
            shown += 1
            if shown <= MAX_RECORDS_IN_FULL:
                report.lines.append(f"{kind} {key}: {text}")
    if shown > MAX_RECORDS_IN_FULL:
        report.lines.append(f"... {shown - MAX_RECORDS_IN_FULL} more changed {kind}s")
    for (typ, path), count in sorted(summary.items()):
        report.lines.append(f"summary: {typ} {path} x{count}")
