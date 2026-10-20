"""Upstream sc2reader v1.9.0's own suite, run unchanged against the pin (TD-7, D6a).

The test files are upstream's at tag v1.9.0 (32a0b83), byte-identical (git blob ids checked
at CR-009). They open replays by paths relative to the repository root, so every test runs
from there. Some tests load maps over the network (``load_map=True``), as upstream's do.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


#: Upstream tests that load maps from Battle.net (``load_map=True``): they need the network.
#: Offline, deselect them with ``-m "not network"``. sc2reader keeps downloaded maps in memory
#: only (no file cache unless SC2READER_CACHE_DIR is set, which scripts/py-env unsets).
NETWORK_TESTS = {"test_map_info", "test_creepTracker"}


def pytest_collection_modifyitems(items):
    for item in items:
        if Path(str(item.fspath)).resolve().is_relative_to(Path(__file__).resolve().parent):
            item.add_marker(pytest.mark.pin_conformance)
            if item.name in NETWORK_TESTS:
                item.add_marker(pytest.mark.network)


@pytest.fixture(autouse=True)
def _run_from_the_repository_root(monkeypatch):
    monkeypatch.chdir(ROOT)
