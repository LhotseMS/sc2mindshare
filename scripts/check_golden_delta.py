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

A ``renumber`` entry (QA design Addendum A) states the IDs of one node type that change: ``key`` (the
field paths that identify a node on both sides), ``retype`` (old ID -> its new ``properties.type``),
``merged`` (old ID -> the old ID of the node it joins), ``ids_changed`` and ``links_dropped``. The
checker derives the ID map by aligning the nodes on their keys and must find exactly what the entry
states (R1 keys and consistency, R2 pairing, R3 merges, R6 other types and ``ids_changed``, R4 the
rewrite of the old golden and its dropped links), then runs C3 on the rewritten old golden (R5), pairing records by ID (``diff_by_key``).
The rest of a renumber entry is written in the new IDs; a link the rewrite drops is listed in
``removed`` by its old IDs or counted in ``links_dropped``.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
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


def _get(record: Mapping[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        value = value.get(part) if isinstance(value, Mapping) else None
    return value


def _occurrences(keys: Sequence[str]) -> list[str]:
    seen: Counter[str] = Counter()
    out = []
    for k in keys:
        seen[k] += 1
        out.append(f"{k}#{seen[k]}")
    return out


def renumber_map(
    spec: Mapping[str, Any],
    old_doc: Mapping[str, Any],
    new_doc: Mapping[str, Any],
    removed: set[str],
    added: set[str] | None = None,
) -> tuple[dict[str, str], list[str], dict[str, Any] | None]:
    """Addendum A, R1, R2, R3, R6 and R4: the old -> new ID map of ``spec["type"]``, the problems, and
    (when there are none) ``{"old_doc": the rewritten old golden, "consumed": the removed keys R2 and R4
    used}`` for the C3 run (R5). Stops at the first rule that fails."""
    if "from_position" in spec or "shift" in spec:
        return {}, ["renumber: the single-shift form is retired (QA design Addendum A); state key, retype and merged"], None
    added = added or set()
    typ, paths = spec["type"], list(spec["key"])
    retype: dict[str, str] = dict(spec.get("retype", {}))
    merged: dict[str, str] = dict(spec.get("merged", {}))
    old_nodes, new_nodes = list(old_doc.get("nodes", [])), list(new_doc.get("nodes", []))
    old_occ, new_occ = golden.node_keys(old_nodes), golden.node_keys(new_nodes)
    old_of_type = {n["ID"]: n for n in old_nodes if n.get("type") == typ}

    # R1: merged and retype against each other, then keys (unique on the new side)
    problems = [f"R1: retype names {i}, which is not a {typ} node of the old golden" for i in retype if i not in old_of_type]
    for source, target in merged.items():
        if source not in retype:
            problems.append(f"R1: merged source {source} has no retype")
        if target in merged:
            problems.append(f"R1: merged target {target} is itself a merged source")
        if source not in old_of_type or target not in old_of_type:
            problems.append(f"R1: merged {source} -> {target}: both must be {typ} nodes of the old golden")
        elif source in retype and _get(old_of_type[target], "properties.type") != retype[source]:
            problems.append(
                f"R1: merged {source} -> {target}: the target's old type {_get(old_of_type[target], 'properties.type')!r} "
                f"is not the source's retype {retype[source]!r}"
            )
    if problems:
        return {}, problems, None

    def key_of(node: Mapping[str, Any], old_side: bool) -> str:
        values = []
        for path in paths:
            value = _get(node, path)
            if old_side and path == "properties.type" and node["ID"] in retype:
                value = retype[node["ID"]]
            values.append(value)
        return json.dumps(values)

    new_by_key: dict[str, tuple[str, str]] = {}
    for node, occ in zip(new_nodes, new_occ, strict=True):
        if node.get("type") != typ:
            continue
        k = key_of(node, old_side=False)
        if k in new_by_key:
            problems.append(f"R1: ambiguous alignment: {new_by_key[k][0]} and {node['ID']} share the key {k}")
        new_by_key[k] = (node["ID"], occ)
    if problems:
        return {}, problems, None
    old_by_key: dict[str, list[tuple[str, str]]] = {}
    for node, occ in zip(old_nodes, old_occ, strict=True):
        if node.get("type") == typ:
            old_by_key.setdefault(key_of(node, old_side=True), []).append((node["ID"], occ))

    # R2: pairing by key
    consumed: set[str] = set()
    for k, members in old_by_key.items():
        if k not in new_by_key:
            for node_id, occ in members:
                if occ in removed:
                    consumed.add(occ)
                else:
                    problems.append(f"R2: unlisted removal: {node_id} (key {k}) pairs with no new node")
    for k, (node_id, occ) in new_by_key.items():
        if k not in old_by_key and occ not in added:
            problems.append(f"R2: unlisted addition: {node_id} (key {k}) pairs with no old node")
    if problems:
        return {}, problems, None

    # R3: the merges the keys show must be the ones stated
    derived: dict[str, str] = {}
    for k, members in old_by_key.items():
        if len(members) < 2 or k not in new_by_key:
            continue
        ids = [node_id for node_id, _ in members]
        targets = [i for i in ids if i not in merged]
        if len(targets) != 1:
            problems.append(f"R3: {', '.join(ids)} share the key {k}, but merged does not say which joins which")
            continue
        derived.update({i: targets[0] for i in ids if i != targets[0]})
    for source in sorted(set(merged) | set(derived)):
        if merged.get(source) != derived.get(source):
            problems.append(f"R3: merged states {source} -> {merged.get(source)}, the keys give {derived.get(source)}")
    if problems:
        return {}, problems, None

    # R6: no other type's ID changes; ids_changed as stated
    other_old = [n["ID"] for n, occ in zip(old_nodes, old_occ, strict=True) if n.get("type") != typ and occ not in removed]
    other_new = [n["ID"] for n, occ in zip(new_nodes, new_occ, strict=True) if n.get("type") != typ and occ not in added]
    if other_old != other_new:
        first = next((i for i, (a, b) in enumerate(zip(other_old, other_new)) if a != b), min(len(other_old), len(other_new)))
        problems.append(
            f"R6: an ID of another node type changes (first at position {first + 1}: {other_old[first : first + 1]} -> {other_new[first : first + 1]})"
        )
    id_map = {node_id: new_by_key[k][0] for k, members in old_by_key.items() if k in new_by_key for node_id, _ in members}
    ids_changed = sum(1 for o, n in id_map.items() if o not in merged and o != n)
    if ids_changed != spec.get("ids_changed", 0):
        problems.append(f"R6: ids_changed states {spec.get('ids_changed', 0)}, the map changes {ids_changed}")
    if problems:
        return {}, problems, None

    # R4: rewrite the old golden; every link it drops is listed in removed (old IDs) or counted
    rewritten = copy.deepcopy(dict(old_doc))
    nodes = []
    for node, occ in zip(rewritten.get("nodes", []), old_occ, strict=True):
        if node.get("type") == typ:
            if node["ID"] in merged or occ in consumed:
                continue
            node["ID"] = id_map[node["ID"]]
        nodes.append(node)
    rewritten["nodes"] = nodes
    old_links = list(rewritten.get("links", []))
    link_occ = _occurrences([f"{lk.get('node1')}>{lk.get('node2')}" for lk in old_links])
    links, seen, dropped = [], [], 0
    for link, occ in zip(old_links, link_occ, strict=True):
        link["node1"] = id_map.get(link.get("node1"), link.get("node1"))
        link["node2"] = id_map.get(link.get("node2"), link.get("node2"))
        if link["node1"] == link["node2"] or link in seen:
            if occ in removed:
                consumed.add(occ)
            else:
                dropped += 1
            continue
        seen.append(link)
        links.append(link)
    rewritten["links"] = links
    if dropped != spec.get("links_dropped", 0):
        problems.append(
            f"R4: links_dropped states {spec.get('links_dropped', 0)}, the rewrite drops {dropped} links not listed in removed"
        )
        return {}, problems, None
    return id_map, [], {"old_doc": rewritten, "consumed": consumed}


def diff_by_key(old_doc: Mapping[str, Any], new_doc: Mapping[str, Any], clock_map: Mapping[str, str] | None) -> Any:
    """R5's diff: nodes paired by their ``ID#n`` key and links by their ``node1>node2#n`` key, with the
    same masks as ``golden.diff_json`` (which pairs records by sequence alignment, so after a renumber a
    changed node next to an added one would be compared with its neighbour). The order of records is
    not compared: after a renumber it follows the IDs."""
    report = golden.Report()
    old_nodes, budget_old = golden.normalise_nodes(old_doc.get("nodes", []), clock_map, False)
    new_nodes, budget_new = golden.normalise_nodes(new_doc.get("nodes", []), clock_map, False)
    if budget_old != budget_new:
        report.lines.append(f"mask budget differs: expected {dict(budget_old)}, actual {dict(budget_new)}")
    for key in sorted((set(old_doc) | set(new_doc)) - {"nodes", "links"}):
        if key not in old_doc or key not in new_doc or golden._canon(old_doc[key], key) != golden._canon(new_doc[key], key):
            report.lines.append(f"{key}: differs")
            report.changed.append((key, ""))
    old_links, new_links = list(old_doc.get("links", [])), list(new_doc.get("links", []))
    pairs = (
        (
            dict(zip(golden.node_keys(old_nodes), old_nodes, strict=True)),
            dict(zip(golden.node_keys(new_nodes), new_nodes, strict=True)),
        ),
        (
            dict(zip(_occurrences([f"{x.get('node1')}>{x.get('node2')}" for x in old_links]), old_links, strict=True)),
            dict(zip(_occurrences([f"{x.get('node1')}>{x.get('node2')}" for x in new_links]), new_links, strict=True)),
        ),
    )
    for before, after in pairs:
        for key in before:
            if key not in after:
                report.changed.append((key, "<removed>"))
                report.lines.append(f"{key}: removed")
        for key, record in after.items():
            if key not in before:
                report.changed.append((key, "<added>"))
                report.lines.append(f"{key}: added")
                continue
            fields: list[tuple[str, Any, Any]] = []
            golden._field_diff(dict(before[key]), dict(record), "", fields)
            for path, _old, _new in fields:
                report.changed.append((key, path))
                report.lines.append(f"{key}: {path}")
    return report


def check_delta(entry: Mapping[str, Any], old: Path, new: Path, clock_map: Mapping[str, str] | None = None) -> list[str]:
    """C3 and C4 for one golden file; returns the problems (empty = ok). A ``renumber`` entry first
    runs R1, R2, R3, R6 and R4 (``renumber_map``), then C3 on the rewritten old golden (R5)."""
    problems: list[str] = []
    if golden.sha256(old) != entry["base_sha256"]:
        problems.append(f"C4 base_sha256 does not match {old.name}")
    consumed: set[str] = set()
    if old.suffix == ".json":
        old_doc, new_doc = json.loads(old.read_text(encoding="utf-8")), json.loads(new.read_text(encoding="utf-8"))
        if entry.get("renumber"):
            spec = entry["renumber"]
            id_map, rproblems, result = renumber_map(
                spec, old_doc, new_doc, set(entry.get("removed", [])), set(entry.get("added", []))
            )
            if rproblems or result is None:
                return problems + rproblems
            old_doc, consumed = result["old_doc"], result["consumed"]
            print(f"renumber map ({spec['type']}, {len(id_map)} old IDs):")
            for o, n in id_map.items():
                if o != n:
                    print(f"  {o} -> {n}" + (" (merged)" if o in spec.get("merged", {}) else ""))
        report = (
            diff_by_key(old_doc, new_doc, clock_map) if entry.get("renumber") else golden.diff_json(old_doc, new_doc, clock_map)
        )
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
    removed = set(entry.get("removed", [])) - consumed  # removals the renumber (R2, R4) already accounted for
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


def git_env() -> dict[str, str]:
    """The environment without any GIT_* variable, for every git call of the golden tooling and its tests.

    A GIT_DIR (or GIT_WORK_TREE, GIT_INDEX_FILE, ...) in the caller's environment overrides ``git -C``:
    on 2026-10-18 a test run with GIT_DIR set made the throwaway test repositories commit into the
    checkout's own .git (incident, decision D1a). Without these variables ``-C`` decides the repository."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=git_env()).stdout


def _adds(repo: Path, sha: str, changes_rel: str, marker: str) -> bool:
    """The commit adds the entry: present in its CHANGES.md, absent in its parent's (or no parent file)."""
    if marker not in _git(repo, "show", f"{sha}:{changes_rel}"):
        return False
    before = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}^:{changes_rel}"], check=False, capture_output=True, text=True, env=git_env()
    )
    return before.returncode != 0 or marker not in before.stdout


def _is_product_change(path: str, changes_rel: str) -> bool:
    """A golden or product file; the ledger itself and test modules (``test_*.py``) are not.

    Test edits under ``tests/golden/`` are therefore reviewed, not gated: C1 does not order them against
    an entry, so the reviewer checks that a test change does not weaken what the goldens prove."""
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
