#!/usr/bin/env python3
"""Check a golden change against its entry in tests/golden/CHANGES.md (CR-007; QA design §5).

    scripts/py-env .venv/bin/python scripts/check_golden_delta.py --entry P1 \
        --old <golden before> --new <golden after> [--clock-map <TimeImageTracking.csv>]
    scripts/py-env .venv/bin/python scripts/check_golden_delta.py --entry P1 --git <base>..<head>

Entries are fenced ``json`` blocks in CHANGES.md:

    {"entry": "P1", "task": "CR-023", "golden": ["G-JSON-current"], "base_sha256": "...",
     "changes": [{"select": {"type": "Battle"}, "fields": ["name", "description"], "count": 30}],
     "added": [], "removed": []}

Checks: C3 the diff equals the entry both ways (``unlisted change`` / ``listed but not
changed``, counts equal); C4 ``base_sha256`` is the old golden; C1 the entry was added (absent
in the parent's CHANGES.md) in a commit before the first commit that changes a golden or product
file (test modules ``test_*.py`` are not product files); C2 CHANGES.md only grew.
(``renumber`` entries are not implemented yet: they fail loudly until a task needs them.)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

CHECKOUT = Path(__file__).resolve().parents[1]
CHANGES = CHECKOUT / "tests" / "golden" / "CHANGES.md"
_spec = importlib.util.spec_from_file_location("golden", CHECKOUT / "tests" / "golden" / "golden.py")
assert _spec and _spec.loader
golden = importlib.util.module_from_spec(_spec)
sys.modules["golden"] = golden
_spec.loader.exec_module(golden)

FENCE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
WATCHED = ("tests/golden/", "src/", "sc2reader/", "legacy/", "execs/")


def entries(text: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for block in FENCE.findall(text):
        entry = json.loads(block)
        if entry["entry"] in out:
            raise ValueError(f"entry {entry['entry']} appears twice")
        out[entry["entry"]] = entry
    return out


def _selected(selector: Mapping[str, str], key: str, record_type: str | None) -> bool:
    if "ID" in selector:
        wanted = selector["ID"]
        return key == wanted if "#" in wanted else key.rsplit("#", 1)[0] == wanted
    if "type" in selector:
        return record_type == selector["type"]
    return False


def _field_listed(path: str, fields: Sequence[str]) -> bool:
    return any(path == f or path.startswith((f + ".", f + "[")) for f in fields)


def check_delta(entry: Mapping[str, Any], old: Path, new: Path, clock_map: Mapping[str, str] | None = None) -> list[str]:
    """C3 and C4 for one golden file; returns the problems (empty = ok)."""
    problems: list[str] = []
    if entry.get("renumber"):
        return ["renumber entries are not implemented yet"]
    if golden.sha256(old) != entry["base_sha256"]:
        problems.append(f"C4 base_sha256 does not match {old.name}")
    if old.suffix == ".json":
        old_doc, new_doc = json.loads(old.read_text(encoding="utf-8")), json.loads(new.read_text(encoding="utf-8"))
        report = golden.diff_json(old_doc, new_doc, clock_map)
        types: dict[str, str | None] = {}
        for doc in (old_doc, new_doc):
            for key, node in zip(golden.node_keys(doc.get("nodes", [])), doc.get("nodes", []), strict=True):
                types[key] = node.get("type")
    else:
        report = golden.diff_csv(old.read_text(encoding="utf-8"), new.read_text(encoding="utf-8"))
        types = {}
    changes = list(entry.get("changes", []))
    hits: Counter[int] = Counter()
    seen_records: dict[int, set[str]] = {i: set() for i in range(len(changes))}
    added = set(entry.get("added", []))
    removed = set(entry.get("removed", []))
    for key, path in report.changed:
        if path == "<added>":
            if key not in added:
                problems.append(f"unlisted change: {key} added")
            continue
        if path == "<removed>":
            if key not in removed:
                problems.append(f"unlisted change: {key} removed")
            continue
        match = next(
            (
                i
                for i, c in enumerate(changes)
                if _selected(c["select"], key, types.get(key)) and _field_listed(path, c.get("fields", []))
            ),
            None,
        )
        if match is None:
            problems.append(f"unlisted change: {key} {path}")
        else:
            seen_records[match].add(key)
            hits[match] += 1
    for i, c in enumerate(changes):
        if not seen_records[i]:
            problems.append(f"listed but not changed: {c['select']} {c.get('fields')}")
        elif len(seen_records[i]) != c["count"]:
            problems.append(f"count differs for {c['select']}: listed {c['count']}, changed {len(seen_records[i])}")
    reported = {k for k, p in report.changed}
    for key in added | removed:
        if key not in reported:
            problems.append(f"listed but not changed: {key}")
    return problems


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _adds(repo: Path, sha: str, changes_rel: str, marker: str) -> bool:
    """The commit adds the entry: present in its CHANGES.md, absent in its parent's (or no parent file)."""
    if marker not in _git(repo, "show", f"{sha}:{changes_rel}"):
        return False
    before = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}^:{changes_rel}"], check=False, capture_output=True, text=True
    )
    return before.returncode != 0 or marker not in before.stdout


def _is_product_change(path: str, changes_rel: str) -> bool:
    """A golden or product file; the ledger itself and test modules (``test_*.py``) are not."""
    return path.startswith(WATCHED) and path != changes_rel and not Path(path).name.startswith("test_")


def check_git(repo: Path, rev_range: str, entry_id: str, changes_rel: str = "tests/golden/CHANGES.md") -> list[str]:
    """C1 (entry before the change) and C2 (CHANGES.md append-only) on a commit range."""
    problems: list[str] = []
    log = _git(repo, "log", "--reverse", "--format=@%H", "--name-only", rev_range)
    entry_commit: int | None = None
    first_change: int | None = None
    commits = [c for c in log.split("@") if c.strip()]
    marker = f'"entry": "{entry_id}"'
    for index, chunk in enumerate(commits):
        sha, *files = [line for line in chunk.splitlines() if line.strip()]
        if changes_rel in files and entry_commit is None and _adds(repo, sha, changes_rel, marker):
            entry_commit = index
        if first_change is None and any(_is_product_change(f, changes_rel) for f in files):
            first_change = index
    if entry_commit is None:
        problems.append(f"C1 entry {entry_id} not added in {rev_range}")
    elif first_change is not None and first_change <= entry_commit:
        problems.append("C1 the entry was not committed before the first golden or product change")
    diff = _git(repo, "diff", rev_range, "--", changes_rel)
    removed_lines = [line for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    if removed_lines:
        problems.append(f"C2 CHANGES.md is append-only; removed or changed lines: {removed_lines[:3]}")
    return problems


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entry", required=True)
    parser.add_argument("--old", type=Path)
    parser.add_argument("--new", type=Path)
    parser.add_argument("--clock-map", type=Path)
    parser.add_argument("--git", help="<base>..<head>")
    parser.add_argument("--changes", type=Path, default=CHANGES)
    args = parser.parse_args(argv)
    problems: list[str] = []
    if args.old and args.new:
        entry = entries(args.changes.read_text(encoding="utf-8"))[args.entry]
        clock_map = golden.load_clock_map(args.clock_map) if args.clock_map else None
        problems += check_delta(entry, args.old, args.new, clock_map)
    if args.git:
        problems += check_git(CHECKOUT, args.git, args.entry)
    for p in problems:
        print(p)
    print("ok" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
