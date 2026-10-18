"""D30a (nothing is written outside the project root): every temporary file or folder the scripts make is
created under <root>/.tools/tmp, named explicitly with ``dir=`` rather than taken from whatever TMPDIR
the caller's environment has (Morgan's CR-019 review)."""

import ast
import pathlib

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
MAKERS = {"TemporaryDirectory", "mkdtemp", "mkstemp", "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile"}


def _temp_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if name in MAKERS:
                yield node


@pytest.mark.parametrize("path", sorted(SCRIPTS.glob("*.py")), ids=lambda p: p.name)
def test_every_temporary_file_or_folder_names_its_dir(path):
    missing = [f"{path.name}:{call.lineno}" for call in _temp_calls(path) if not any(k.arg == "dir" for k in call.keywords)]
    assert missing == []


def test_the_check_bites(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import tempfile\nwith tempfile.TemporaryDirectory() as t:\n    pass\n", encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text("import tempfile\nwith tempfile.TemporaryDirectory(dir='x') as t:\n    pass\n", encoding="utf-8")
    assert [c.lineno for c in _temp_calls(bad) if not any(k.arg == "dir" for k in c.keywords)] == [2]
    assert [c.lineno for c in _temp_calls(good) if not any(k.arg == "dir" for k in c.keywords)] == []
