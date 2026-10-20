"""Load a replay once, through the Mindshare Replay subclass and engine (CR-010, TD-2).

Differences from the old fork's ``sc2reader.load_replay(path, debug=True, load_map=True)``:

- upstream ``sc2reader==1.9.0``, unmodified;
- ``load_map=False`` by default: the map is used only for heatmaps, which are out of scope;
- the engine: upstream's GameHeartNormalizer, the Mindshare ContextLoader (upstream's with the
  fork's additions, ``plugins.mindshare_context``) and upstream's SelectionTracker, then stream 3's
  plugins. The fork's broken CreepTracker is not registered.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sc2reader  # type: ignore[import-untyped]  # sc2reader ships no type information
from sc2reader.engine import GameEngine  # type: ignore[import-untyped]
from sc2reader.engine.plugins import GameHeartNormalizer, SelectionTracker  # type: ignore[import-untyped]
from sc2reader.resources import Replay  # type: ignore[import-untyped]

from sc2mindshare.reader import extensions
from sc2mindshare.reader.plugins.mindshare_context import MindshareContextLoader


class MindshareReplay(Replay):  # type: ignore[misc]  # sc2reader is untyped
    """A Replay that lets stream 3 register extra readers before the files are read."""

    def register_default_readers(self) -> None:
        super().register_default_readers()
        extensions.register_readers(self)


def build_engine() -> Any:
    """A fresh engine with the Mindshare plugins, in the fork's order, then stream 3's."""
    engine = GameEngine()
    engine.register_plugin(GameHeartNormalizer())
    engine.register_plugin(MindshareContextLoader())
    engine.register_plugin(SelectionTracker())
    extensions.register_plugins(engine)
    return engine


def load_replay(path: str | Path, load_map: bool = False) -> Any:
    """The replay at ``path``, fully loaded (load level 4) with the Mindshare engine."""
    factory = sc2reader.factories.SC2Factory()
    return factory.load(MindshareReplay, str(path), load_level=4, load_map=load_map, engine=build_engine())
