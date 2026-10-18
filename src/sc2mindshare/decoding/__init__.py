"""Decoding: what a replay holds beyond what sc2reader exposes (stream 3).

Reader layer: imports only sc2reader's public API and the standard library (TD-1), and is
plugged into stream 1's loader through `reader/extensions.py` (TD-2, after T10):
`register_readers(replay)` is the line stream 3 adds to the hook.

    from sc2mindshare.decoding import load
    decoded = load("game.SC2Replay")

`load` is the standalone entry point for stream 3's tools and tests. Once T10 lands, product
code loads replays through stream 1's loader (one Replay subclass, TD-2), not through `load`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sc2reader  # type: ignore[import-untyped]  # sc2reader ships no type information
from sc2reader.resources import Replay  # type: ignore[import-untyped]

# isort: split
# (sc2mindshare is first-party once pyproject.toml exists, CR-009; before that ruff sees it as third-party)
from sc2mindshare.decoding import camera_hotkeys
from sc2mindshare.decoding.metadata import GameMetadata

__all__ = ["DecodedReplay", "load", "register_readers"]


def register_readers(replay: Any) -> None:
    """Every stream 3 reader registration, for stream 1's `reader/extensions.register_readers` (TD-2)."""
    camera_hotkeys.register_readers(replay)


class _DecodingReplay(Replay):  # type: ignore[misc]  # sc2reader is untyped
    def register_default_readers(self) -> None:
        super().register_default_readers()
        register_readers(self)


@dataclass(frozen=True)
class DecodedReplay:
    """A loaded replay plus what the decoders found in it."""

    replay: Any  # sc2reader.resources.Replay
    metadata: GameMetadata
    warnings: tuple[str, ...] = ()


def load(path: str) -> DecodedReplay:
    """Load a replay with the pinned sc2reader (no map download) and run the decoders."""
    factory = sc2reader.factories.SC2Factory()
    replay = factory.load(_DecodingReplay, path, load_level=4, load_map=False)
    metadata = GameMetadata.from_replay(replay)
    return DecodedReplay(replay=replay, metadata=metadata, warnings=metadata.warnings)
