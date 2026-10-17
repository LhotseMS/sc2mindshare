"""Test helpers for stream 3: load tools/decoding modules by path, locate the replays."""

import importlib.util
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from types import ModuleType

CHECKOUT = Path(__file__).resolve().parents[2]
TOOLS = CHECKOUT / "tools" / "decoding"


def load_tool(name: str) -> ModuleType:
    """Import tools/decoding/<name>.py without putting the checkout root on sys.path.

    The checkout root holds the fork's sc2reader/ until T09, so it must never be importable.
    """
    key = f"decoding_tools_{name}"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, TOOLS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def project_root() -> Path:
    for parent in CHECKOUT.parents:
        if (parent / ".tools").is_dir():
            return parent
    raise RuntimeError("no project root with .tools/ above " + str(CHECKOUT))


def _single(found: Iterable[Path], pattern: Path) -> Path:
    matches = sorted(found)
    return matches[0] if len(matches) == 1 else pattern  # a missing or ambiguous match fails the fixture


def replay_paths() -> dict[str, Path]:
    """The three replays in MS SC/ (D5a: data points, never committed, D7a)."""
    ms_sc = Path(os.environ.get("MS_SC_ROOT", project_root() / "MS SC"))
    return {
        "alcyone": _single(ms_sc.glob("Alcyone LE__*/*.SC2Replay"), ms_sc / "Alcyone LE__*"),
        "spores": ms_sc / "1000 spores ZvP.SC2Replay",
        "spine": ms_sc / "200k dmg spine crawler ZvP.SC2Replay",
    }
