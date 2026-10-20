"""CR-007c (Morgan's N1 on the batch merges): the legacy environment follows the checkout's layout. Its .pth file
holds an import line that puts the fork tree on sys.path when Python starts: <checkout>/legacy when
legacy/sc2reader exists (from CR-009), else the checkout itself (the fork at the root, before CR-009)."""

import importlib.util
import pathlib
import subprocess
import sys

_PATH = pathlib.Path(__file__).resolve().parent.parent / "legacy_pth.py"


def _module():
    spec = importlib.util.spec_from_file_location("legacy_pth", _PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _path_added(line, tmp_path):
    out = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            f"import sys; before = list(sys.path); exec({line!r}); print([p for p in sys.path if p not in before])",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    return out.stdout.strip()


def test_the_pth_line_follows_the_layout(tmp_path):
    checkout = tmp_path / "a checkout"  # a space too
    (checkout / "sc2reader").mkdir(parents=True)
    line = _module().pth_line(str(checkout))
    assert line.startswith("import ") and "\n" not in line  # a .pth file runs a line only when it starts with import
    assert _path_added(line, tmp_path) == str([str(checkout)])  # the fork at the root (before CR-009)
    (checkout / "legacy" / "sc2reader").mkdir(parents=True)
    assert _path_added(line, tmp_path) == str([str(checkout / "legacy")])  # from CR-009: legacy/


def test_legacy_env_writes_the_import_line():
    text = (_PATH.parent / "legacy-env").read_text(encoding="utf-8")
    assert "legacy_pth.py" in text and "fork_root" not in text
