"""Decoding: what a replay holds beyond what sc2reader exposes (stream 3).

Reader layer: imports only sc2reader's public API and the standard library (TD-1), and is
plugged into stream 1's loader through `reader/extensions.py` (TD-2, after T10).

    from sc2mindshare.decoding import load
    decoded = load("game.SC2Replay")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sc2reader  # type: ignore[import-untyped]  # sc2reader ships no type information

__all__ = ["DecodedReplay", "load"]


@dataclass(frozen=True)
class DecodedReplay:
    """A loaded replay plus what the decoders found in it."""

    replay: Any  # sc2reader.resources.Replay
    warnings: tuple[str, ...] = ()


def load(path: str) -> DecodedReplay:
    """Load a replay with the pinned sc2reader (no map download) and run the decoders."""
    replay = sc2reader.load_replay(path, load_level=4, load_map=False)
    return DecodedReplay(replay=replay)
