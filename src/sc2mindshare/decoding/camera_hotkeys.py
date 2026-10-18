"""Camera hotkeys: keep SCameraSaveEvent (game event id 14), which sc2reader parses and drops (CR-044, T3-4).

A save stores the current camera point in a hotkey slot (`slot`, 0-7). Recalling the slot moves
the camera there, which the replay records as an ordinary camera update whose target is exactly
the saved point. On the three replays every exact match belongs to one slot only (finding F3-009); in the
corpus 3 of 40 replays save one point in two slots (E1), and then the lowest slot is reported.

`CameraSaveEvent` is a direct GameEvent subclass (TD-12): not a CameraEvent, and without the
generic `x`, `y`, `location`, `ability` or `unit` attributes, so no existing filter picks it up.
Its point is in map units (the raw value / 256, as sc2reader does for camera updates).

The saves never enter ``replay.game_events``, ``replay.events`` or ``player.events`` (CR-044 part 2,
CR-010 review): they are kept in a separate store, read with ``camera_saves(replay)``. Registering the
reader therefore changes nothing that stream 1 or sc2reader's plugins see. Each save records its place in
the event stream (``stream_position``: the number of other game events before it), so recalls are paired
in stream order.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Any

from sc2reader.events.game import CameraEvent, GameEvent  # type: ignore[import-untyped]

EVENT_ID = 14
GAME_EVENTS = "replay.game.events"

#: replay -> its camera saves, in stream order (a weak map: no attribute is set on the Replay).
_SAVES: weakref.WeakKeyDictionary[Any, tuple[CameraSaveEvent, ...]] = weakref.WeakKeyDictionary()


class CameraSaveEvent(GameEvent):  # type: ignore[misc]  # sc2reader is untyped
    """A camera location saved to a hotkey slot."""

    def __init__(self, frame: int, pid: int, data: dict[str, Any]) -> None:
        super().__init__(frame, pid)
        #: The hotkey slot, 0-7 (3 bits).
        self.slot: int = data["which"]
        #: The saved camera point in map units.
        self.saved_x: float = data["target"]["x"] / 256.0
        self.saved_y: float = data["target"]["y"] / 256.0
        #: How many other game events came before this save in the stream (set by the reader).
        self.stream_position: int = -1

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
        kept: list[Any] = []
        saves: list[CameraSaveEvent] = []
        for event in reader(data, replay):
            if isinstance(event, CameraSaveEvent):
                event.stream_position = len(kept)
                saves.append(event)
            else:
                kept.append(event)
        _SAVES[replay] = tuple(saves)
        return kept


def register_readers(replay: Any) -> None:
    """The stream 3 line for `reader/extensions.register_readers(replay)` (TD-2)."""
    replay.register_reader(GAME_EVENTS, _KeepCameraSaves(), lambda r: True)


def camera_saves(replay: Any) -> tuple[CameraSaveEvent, ...]:
    """The replay's camera saves, in stream order, each with its player resolved.

    The player is resolved the way sc2reader's ContextLoader resolves it for builds with this event (the
    event's pid is a user id), without adding the save to ``player.events``.
    """
    saves = _SAVES.get(replay, ())
    humans = list(getattr(replay, "humans", ()))
    for save in saves:
        if save.player is None and save.pid < len(humans):
            save.player = replay.human[save.pid]
    return saves


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
    pending = list(camera_saves(replay))
    for index, event in enumerate(replay.game_events):
        while pending and pending[0].stream_position <= index:
            save = pending.pop(0)
            if save.player is not None:
                saved[(save.player.pid, save.slot)] = (save.saved_x, save.saved_y)
        if event.player is None:
            continue
        pid = event.player.pid
        if isinstance(event, CameraEvent):
            point = (event.x, event.y)
            slots = sorted(slot for (owner, slot), at in saved.items() if owner == pid and at == point)
            if slots:
                recalls.append(CameraRecall(event.frame, pid, slots[0], event.x, event.y))
    return tuple(recalls)
