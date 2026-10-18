"""CR-011c grep gate: the layer's text never relies on an sc2reader object's ``__str__``.

Units and players are turned into text by ``compat.object_text`` (the fork's ``__str__`` output,
made explicit); ``reader/fork_api.py`` overrides no ``__str__``. This test scans the analysis
package for ``str(x.unit)``, ``"...".format(x.player)``, ``f"{x.unit}"`` and the like, outside
``print(...)`` debug output. The golden (byte-identical CSV) catches what a name-based scan cannot.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "sc2mindshare"
OBJECT_ATTRS = {"unit", "killing_unit", "player", "player1", "player2", "owner", "unit_upkeeper", "unit_controller", "killer"}


def _is_object(node):
    return (isinstance(node, ast.Attribute) and node.attr in OBJECT_ATTRS) or (
        isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "players"
    )


def _inside_print(parents, node):
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            return True
    return False


def offences(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    found = []
    for node in ast.walk(tree):
        args = []
        if isinstance(node, ast.Call) and (
            (isinstance(node.func, ast.Name) and node.func.id == "str")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "format")
        ):
            args = node.args
        elif isinstance(node, ast.FormattedValue):
            args = [node.value]
        for arg in args:
            if _is_object(arg) and not _inside_print(parents, node):
                found.append(f"{path.relative_to(SRC)}:{node.lineno}: {ast.unparse(arg)}")
    return found


def test_no_unit_or_player_is_turned_into_text_implicitly():
    found = [o for p in sorted((SRC / "analysis").rglob("*.py")) for o in offences(p)]
    assert found == []


def test_fork_api_overrides_no_str():
    tree = ast.parse((SRC / "reader" / "fork_api.py").read_text(encoding="utf-8"))
    names = {f.name for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for f in c.body if isinstance(f, ast.FunctionDef)}
    assert "__str__" not in names and "__repr__" not in names


def test_the_scan_catches_the_patterns(tmp_path):
    sample = tmp_path / "x.py"
    sample.write_text(
        "a = str(e.unit)\nb = '{} {}'.format(self.player1, p.players[0])\nc = f'{e.killing_unit} died'\nprint(str(e.unit))\nd = object_text(e.unit)\n"
    )
    global SRC
    old, SRC = SRC, tmp_path
    try:
        assert [o.split(": ", 1)[1] for o in offences(sample)] == ["e.unit", "self.player1", "p.players[0]", "e.killing_unit"]
    finally:
        SRC = old
