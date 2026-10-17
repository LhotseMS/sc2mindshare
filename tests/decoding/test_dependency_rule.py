"""TD-1: `sc2mindshare.decoding` imports only the standard library, sc2reader and itself."""

import ast
import sys
from pathlib import Path

DECODING = Path(__file__).resolve().parents[2] / "src" / "sc2mindshare" / "decoding"
ALLOWED_THIRD_PARTY = {"sc2reader"}


def imported_roots(path: Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module)
    return roots


def test_decoding_imports_only_stdlib_sc2reader_and_itself():
    files = sorted(DECODING.rglob("*.py"))
    assert files
    for path in files:
        for module in imported_roots(path):
            top = module.split(".")[0]
            ok = (
                top in sys.stdlib_module_names
                or top == "__future__"
                or top in ALLOWED_THIRD_PARTY
                or module == "sc2mindshare.decoding"
                or module.startswith("sc2mindshare.decoding.")
            )
            assert ok, f"{path.name} imports {module}"
