"""Camera hotkeys: keep SCameraSaveEvent (game event id 14), which sc2reader parses and drops (CR-044, T3-4).

A save stores the current camera point in a hotkey slot (`slot`, 0-7). Recalling the slot moves
the camera there, which the replay records as an ordinary camera update whose target is exactly
the saved point. On the three replays every exact match belongs to one slot only (finding F3-009).

`CameraSaveEvent` is a direct GameEvent subclass (TD-12): not a CameraEvent, and without the
generic `x`, `y`, `location`, `ability` or `unit` attributes, so no existing filter picks it up.
Its point is in map units (the raw value / 256, as sc2reader does for camera updates).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sc2reader.events.game import CameraEvent, GameEvent  # type: ignore[import-untyped]

EVENT_ID = 14
GAME_EVENTS = "replay.game.events"


class CameraSaveEvent(GameEvent):  # type: ignore[misc]  # sc2reader is untyped
    """A camera location saved to a hotkey slot."""

    def __init__(self, frame: int, pid: int, data: dict[str, Any]) -> None:
        super().__init__(frame, pid)
        #: The hotkey slot, 0-7 (3 bits).
        self.slot: int = data["which"]
        #: The saved camera point in map units.
        self.saved_x: float = data["target"]["x"] / 256.0
        self.saved_y: float = data["target"]["y"] / 256.0

    def __str__(self) -> str:
        return str(self._str_prefix()) + f"{self.name} slot {self.slot} at ({self.saved_x}, {self.saved_y})"


class _KeepCameraSaves:
    """A game-events reader that delegates to sc2reader's own choice, with id 14 kept.

    sc2reader picks the reader when the file is read (the version is known only then), so the
    delegate is chosen inside __call__. A fresh instance of the chosen reader's class is used, so
    the factory's shared reader is never modified.
    """

    def __call__(self, data: bytes, replay: Any) -> Any:
        default = next(
            reader for accepts, reader in replay.registered_readers[GAME_EVENTS] if reader is not self and accepts(replay)
        )
        if EVENT_ID not in default.EVENT_DISPATCH:
            # Readers before GameEventsReader_24247 (Wings of Liberty) have no camera save event (CR-044 review).
            return default(data, replay)
        reader = type(default)()
        _cls, parser = reader.EVENT_DISPATCH[EVENT_ID]
        reader.EVENT_DISPATCH[EVENT_ID] = (CameraSaveEvent, parser)
        return reader(data, replay)


def register_readers(replay: Any) -> None:
    """The stream 3 line for `reader/extensions.register_readers(replay)` (TD-2)."""
    replay.register_reader(GAME_EVENTS, _KeepCameraSaves(), lambda r: True)


@dataclass(frozen=True)
class CameraRecall:
    frame: int
    player_id: int
    slot: int
    x: float
    y: float


def camera_recalls(replay: Any) -> tuple[CameraRecall, ...]:
    """Camera updates that land exactly on a point the same player saved earlier, with the slot."""
    saved: dict[tuple[int, int], tuple[float, float]] = {}
    recalls = []
    for event in sorted(replay.game_events, key=lambda e: e.frame):
        if event.player is None:
            continue
        pid = event.player.pid
        if isinstance(event, CameraSaveEvent):
            saved[(pid, event.slot)] = (event.saved_x, event.saved_y)
        elif isinstance(event, CameraEvent):
            point = (event.x, event.y)
            slots = sorted(slot for (owner, slot), at in saved.items() if owner == pid and at == point)
            if slots:
                recalls.append(CameraRecall(event.frame, pid, slots[0], event.x, event.y))
    return tuple(recalls)
