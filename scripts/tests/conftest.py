"""Test-session setup shared by every test under this folder.

No GIT_* variable reaches a test: a GIT_DIR (or GIT_WORK_TREE, GIT_INDEX_FILE, ...) set by whoever runs
the suite would override ``git -C <temporary repository>`` and send the git-based tests' commits into a
real repository (incident 2026-10-18 12:38, decision D1a). The git helpers also pass an environment
without them, so this is the second guard, not the only one.
"""

import os


def pytest_configure(config):
    for name in [k for k in os.environ if k.startswith("GIT_")]:
        del os.environ[name]
