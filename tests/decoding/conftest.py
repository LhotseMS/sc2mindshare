"""Stream 3 test setup.

Only this folder goes on sys.path (for decoding_support); the checkout root never does,
because it holds the fork's sc2reader/ until T09 (TD-8).
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
# src/ holds only the sc2mindshare namespace (no src/sc2mindshare/__init__.py before T09, TD-8).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from decoding_support import replay_paths


@pytest.fixture(scope="session")
def replays() -> dict[str, str]:
    paths = replay_paths()
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        reason = "replays missing (D5a data points in MS SC/, never committed, D7a): " + ", ".join(missing)
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":  # QA design §1.4: on this Mac a skip is a failed gate
            pytest.fail(reason)
        pytest.skip(reason)
    return {k: str(v) for k, v in paths.items()}


@pytest.fixture(scope="session")
def alcyone(replays: dict[str, str]) -> str:
    return replays["alcyone"]


@pytest.fixture(scope="session", params=["alcyone", "spores", "spine"])
def any_replay(request: pytest.FixtureRequest, replays: dict[str, str]) -> str:
    return replays[request.param]
