"""Load Blizzard's s2protocol schema modules on Python 3.12+ (stream 3 tooling, CR-040).

s2protocol is a test oracle and inventory reference for stream 3, never a runtime
dependency of sc2mindshare. Its `s2protocol.versions` package imports `imp`, which
Python 3.12 removed, so this module loads the per-build protocol files directly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import s2protocol

VERSIONS_DIR = Path(s2protocol.__file__).parent / "versions"


def available_builds() -> list[int]:
    return sorted(int(p.stem.removeprefix("protocol")) for p in VERSIONS_DIR.glob("protocol[0-9]*.py"))


def protocol_build_for(base_build: int) -> int:
    """The protocol module for a replay's base build.

    s2protocol ships a module per schema change, not per build (there is no 81433), so a
    build without its own module uses the newest module at or below it.
    """
    candidates = [b for b in available_builds() if b <= base_build]
    if not candidates:
        raise LookupError(f"no s2protocol module at or below base build {base_build}")
    return candidates[-1]


def load_protocol(build: int) -> ModuleType:
    """Import s2protocol's protocol<build>.py by path (it needs only s2protocol.decoders)."""
    name = f"s2protocol_protocol{build}"
    if name in sys.modules:
        return sys.modules[name]
    path = VERSIONS_DIR / f"protocol{build}.py"
    if not path.exists():
        raise LookupError(f"s2protocol has no protocol module for build {build}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LookupError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[name] = module
    return module


def latest_protocol() -> ModuleType:
    return load_protocol(available_builds()[-1])
