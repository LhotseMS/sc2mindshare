"""Stream 3's two hooks into the loader (TD-2). Created empty by CR-010; stream 3 adds one line in each.

``register_readers(replay)`` runs inside ``MindshareReplay.register_default_readers``, so a reader
registered here is used for this replay (sc2reader registers and runs its readers inside
``Replay.__init__``). ``register_plugins(engine)`` runs when the Mindshare engine is built, after
the Mindshare plugins.
"""

from __future__ import annotations

from typing import Any


def register_readers(replay: Any) -> None:
    """Register stream 3's extra readers on ``replay`` (``replay.register_reader(...)``)."""


def register_plugins(engine: Any) -> None:
    """Register stream 3's engine plugins on ``engine`` (``engine.register_plugin(...)``)."""
