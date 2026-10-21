"""CR-009: the dependency direction of the new package (stream1-plan.md §1.2, TD-1, TD-29).

cli -> export -> layout -> domain <- analysis -> reader -> sc2reader; reader -> decoding -> sc2reader.
Only reader/ and decoding/ import sc2reader. domain/ and layout/ import nothing from sc2reader.
decoding/ imports only sc2reader and the standard library. gamedata/ and media/ (CR-069) import only the standard library.
"""

import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "sc2mindshare"

# subpackage -> sc2mindshare subpackages it may import
ALLOWED = {
    "domain": set(),
    "gamedata": set(),
    "config": set(),
    "decoding": set(),
    "reader": {"decoding", "gamedata", "config"},
    "analysis": {"reader", "domain", "gamedata", "config"},
    "layout": {"domain", "config"},
    "export": {"layout", "domain", "config"},
    "media": set(),  # CR-069: the local Mindshare media client
    "cli": {"reader", "analysis", "layout", "export", "domain", "config", "gamedata"},
}
MAY_IMPORT_SC2READER = {"reader", "decoding"}
STDLIB_ONLY = {"decoding": {"sc2reader"}, "gamedata": set(), "media": set()}  # extra third-party roots allowed


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            yield "." * node.level + (node.module or "")


def _subpackage(path):
    rel = path.relative_to(SRC).parts
    return rel[0].removesuffix(".py") if len(rel) > 1 or rel[0] != "__init__.py" else None


def violations():
    problems = []
    for path in sorted(SRC.rglob("*.py")):
        sub = _subpackage(path)
        if sub is None:
            continue
        for name in _imports(path):
            root = name.split(".")[0]
            if name.startswith("."):
                problems.append(f"{path.relative_to(SRC)}: relative import {name} (use absolute sc2mindshare.<x> imports)")
            elif root == "sc2mindshare":
                target = name.split(".")[1] if "." in name else None
                if target and target != sub and target not in ALLOWED.get(sub, set()):
                    problems.append(f"{path.relative_to(SRC)}: {sub} must not import sc2mindshare.{target}")
            elif root == "sc2reader" and sub not in MAY_IMPORT_SC2READER:
                problems.append(f"{path.relative_to(SRC)}: {sub} must not import sc2reader")
            elif sub in STDLIB_ONLY and root not in sys.stdlib_module_names and root not in STDLIB_ONLY[sub]:
                problems.append(f"{path.relative_to(SRC)}: {sub} imports third-party {root}")
    return problems


def test_dependency_direction():
    assert violations() == []


def test_the_rules_bite(tmp_path, monkeypatch):
    fake = tmp_path / "sc2mindshare"
    (fake / "layout").mkdir(parents=True)
    (fake / "layout" / "sweep.py").write_text("import sc2reader\nfrom sc2mindshare.analysis import x\n")
    (fake / "gamedata").mkdir()
    (fake / "gamedata" / "units.py").write_text("import numpy\n")
    monkeypatch.setattr(sys.modules[__name__], "SRC", fake)
    assert violations() == [
        "gamedata/units.py: gamedata imports third-party numpy",
        "layout/sweep.py: layout must not import sc2reader",
        "layout/sweep.py: layout must not import sc2mindshare.analysis",
    ]
