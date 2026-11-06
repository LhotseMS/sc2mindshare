"""Test-session setup shared by every test under this folder.

No GIT_* variable reaches a test: a GIT_DIR (or GIT_WORK_TREE, GIT_INDEX_FILE, ...) set by whoever runs
the suite would override ``git -C <temporary repository>`` and send the git-based tests' commits into a
real repository (incident 2026-10-18 12:38, decision D1a). The git helpers also pass an environment
without them, so this is the second guard, not the only one.

No test reaches the network (CR-069): the guard in ``network_guard.py`` (shared with scripts/tests) fails every
connection to an address that is not this computer's loopback, unless the test is marked ``network``. Name
lookups (DNS) are not covered.
"""

import importlib.util
import os
import sys
from pathlib import Path


def _network_guard_module():
    spec = importlib.util.spec_from_file_location("sc2ms_network_guard", Path(__file__).with_name("network_guard.py"))
    assert spec and spec.loader
    module = sys.modules.get("sc2ms_network_guard") or importlib.util.module_from_spec(spec)
    if "sc2ms_network_guard" not in sys.modules:
        sys.modules["sc2ms_network_guard"] = module
        spec.loader.exec_module(module)
    return module


network_guard = _network_guard_module().guard  # an autouse fixture


def pytest_configure(config):
    for name in [k for k in os.environ if k.startswith("GIT_")]:
        del os.environ[name]
