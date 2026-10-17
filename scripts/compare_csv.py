#!/usr/bin/env python3
"""Compare two legacy Mindshare events CSVs with the image URLs masked (CR-004, T04).

    scripts/py-env .venv/bin/python scripts/compare_csv.py A.csv B.csv [--a-encoding cp1250]

The legacy CSV is ``;``-separated with no quoting. A node row's description can
contain a raw newline (legacy defect P7), so a physical line with fewer than
``MIN_FIELDS`` fields is joined to the line after it (shown as ``\\n``). Like
the workbook's Power Query, a row whose first field contains ``-`` is a link.
The image field (field 5 of a node row) is masked. Standard library only.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

MIN_FIELDS = 7
IMAGE_FIELD = 4


@dataclass(frozen=True)
class Record:
    text: str
    physical_lines: int


@dataclass
class Result:
    counts_a: Counter[tuple[str, str]]
    counts_b: Counter[tuple[str, str]]
    only_a_by_kind: dict[tuple[str, str], int]
    only_b_by_kind: dict[tuple[str, str], int]
    padding_only: int
    same_order: bool
    identical: bool
    only_a: list[str] = field(default_factory=list)
    only_b: list[str] = field(default_factory=list)


def records(text: str) -> list[Record]:
    """Logical records: a short physical line is the first part of a field that
    holds a raw newline, so it is joined to the line after it."""
    out: list[Record] = []
    pending: Record | None = None
    for line in text.splitlines():
        if pending is not None:
            pending = Record(pending.text + "\\n" + line, pending.physical_lines + 1)
        else:
            pending = Record(line, 1)
        if pending.text.count(";") + 1 >= MIN_FIELDS:
            out.append(pending)
            pending = None
    if pending is not None:
        out.append(pending)
    return out


def kind(row: str) -> tuple[str, str]:
    fields = row.split(";")
    if "-" in fields[0]:
        target = fields[1] if len(fields) > 1 else ""
        return ("link", f"{fields[0].rsplit('-', 1)[0]}>{target.rsplit('-', 1)[0]}")
    return ("node", fields[2] if len(fields) > 2 else "")


def mask(row: str) -> str:
    fields = row.split(";")
    if "-" not in fields[0] and len(fields) > IMAGE_FIELD:
        fields[IMAGE_FIELD] = "<images>"
    return ";".join(fields)


def node_id(row: str) -> str | None:
    fields = row.split(";")
    if "-" in fields[0] or len(fields) <= 3:
        return None
    return fields[3]


def duplicate_ids(recs: Sequence[Record]) -> dict[str, int]:
    counts = Counter(i for r in recs if (i := node_id(r.text)) is not None)
    return {k: v for k, v in counts.items() if v > 1}


def compare(text_a: str, text_b: str) -> Result:
    rows_a = [mask(r.text) for r in records(text_a)]
    rows_b = [mask(r.text) for r in records(text_b)]
    multi_a, multi_b = Counter(rows_a), Counter(rows_b)
    only_a = list((multi_a - multi_b).elements())
    only_b = list((multi_b - multi_a).elements())
    padding = Counter(r.rstrip(";") for r in only_a) & Counter(r.rstrip(";") for r in only_b)
    padding_only = sum(padding.values())
    rest_a = _without(only_a, padding)
    rest_b = _without(only_b, padding)
    common = multi_a & multi_b
    order_a = [r for r in rows_a if r in common]
    order_b = [r for r in rows_b if r in common]
    return Result(
        counts_a=Counter(kind(r) for r in rows_a),
        counts_b=Counter(kind(r) for r in rows_b),
        only_a_by_kind=dict(Counter(kind(r) for r in rest_a)),
        only_b_by_kind=dict(Counter(kind(r) for r in rest_b)),
        padding_only=padding_only,
        same_order=order_a == order_b,
        identical=rows_a == rows_b,
        only_a=rest_a,
        only_b=rest_b,
    )


def _without(rows: Sequence[str], padding: Counter[str]) -> list[str]:
    pool = Counter(padding)
    rest = []
    for r in rows:
        key = r.rstrip(";")
        if pool[key] > 0:
            pool[key] -= 1
        else:
            rest.append(r)
    return rest


def report(result: Result, name_a: str, name_b: str) -> str:
    lines = [f"A = {name_a}", f"B = {name_b}", ""]
    lines.append(f"identical (images masked): {result.identical}")
    lines.append(f"common rows in the same order: {result.same_order}")
    lines.append(f"rows differing only in trailing ';' padding: {result.padding_only}")
    lines.append("")
    lines.append("| Kind | Type | A | B |")
    lines.append("|---|---|---|---|")
    for key in sorted(set(result.counts_a) | set(result.counts_b)):
        if key[0] == "node":
            lines.append(f"| node | {key[1]} | {result.counts_a[key]} | {result.counts_b[key]} |")
    links_a = sum(v for k, v in result.counts_a.items() if k[0] == "link")
    links_b = sum(v for k, v in result.counts_b.items() if k[0] == "link")
    lines.append(f"| link | (all) | {links_a} | {links_b} |")
    lines.append("")
    lines.append(f"only in A (beyond padding): {dict(sorted(result.only_a_by_kind.items()))}")
    lines.append(f"only in B (beyond padding): {dict(sorted(result.only_b_by_kind.items()))}")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--a-encoding", default="utf-8")
    parser.add_argument("--b-encoding", default="utf-8")
    args = parser.parse_args(argv)
    text_a = args.a.read_text(encoding=args.a_encoding)
    text_b = args.b.read_text(encoding=args.b_encoding)
    result = compare(text_a, text_b)
    print(report(result, str(args.a), str(args.b)))
    for name, text in (("A", text_a), ("B", text_b)):
        recs = records(text)
        split = sum(1 for r in recs if r.physical_lines > 1)
        print(f"\n{name}: {len(text.splitlines())} physical lines, {len(recs)} records, {split} split by raw newlines")
        dups = duplicate_ids(recs)
        if dups:
            print(f"{name}: repeated node IDs: {dups}")
    return 0 if result.identical else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
