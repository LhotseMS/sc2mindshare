"""The old fork's ContextLoader additions, as a subclass of upstream's (CR-010).

Stefan's fork edited ``sc2reader/engine/plugins/context.py`` in place. This subclass of upstream
1.9.0's ``ContextLoader`` reproduces those edits without touching sc2reader:

- unit back-links: ``unit.initEvent`` (UnitInit), ``unit.doneEvent`` (UnitBorn and UnitDone, when
  the unit is known), ``unit.deathEvent`` (UnitDied, when the unit is known);
- ``Update*CommandEvent``s copy the ability fields of the last target command of the same player
  (``ability_name``, ``has_ability``, ``ability_type``, ``ability_data``, ``ability_id``, ``ability``;
  point updates also ``queued``, ``minimap``, ``repeated``), register themselves on it
  (``updateEvents`` / ``targetCommandEvent``), and become the last target themselves;
- a selection change forgets both last target commands of that player.

It also gives upstream objects the attributes the fork declared in their ``__init__`` (the
Mindshare layer reads them, and later detectors set them), so the strangler port (CR-011) can read
them as before. **This is the one module that sets attributes on sc2reader objects**; CR-020 (T19)
replaces them with maps keyed by id.

Kept as ``name = "ContextLoader"``: the engine re-raises exceptions of a plugin with that name
instead of swallowing them, exactly as for the fork's ContextLoader.
"""

from __future__ import annotations

from typing import Any

from sc2reader.engine.plugins import ContextLoader  # type: ignore[import-untyped]
from sc2reader.events.game import (  # type: ignore[import-untyped]
    CameraEvent,
    CommandEvent,
    CommandManagerStateEvent,
    SelectionEvent,
    UpdateTargetPointCommandEvent,
)

COPIED_FROM_TARGET = ("ability_name", "has_ability", "ability_type", "ability_data", "ability_id", "ability")
COPIED_FROM_POINT = ("queued", "minimap", "repeated", *COPIED_FROM_TARGET)

#: The fork's extra Unit fields (sc2reader/data/__init__.py ``Unit.__init__``), all None at creation.
UNIT_FIELDS = ("baseName", "baseType", "unitsNode", "initNode", "deathEvent", "doneEvent", "initEvent")


def register_update_event(command: Any, update: Any) -> None:
    """The fork's ``CommandEvent.registerUpdateEvent``."""
    command.updateEvents.append(update)
    update.targetCommandEvent = command


def decorate_unit(unit: Any) -> None:
    """Give a unit the fork's extra fields (None) unless it has them already."""
    if unit is not None:
        for name in UNIT_FIELDS:
            if not hasattr(unit, name):
                setattr(unit, name, None)


def decorate_game_event(event: Any) -> None:
    """The fields the fork set in game-event ``__init__``s."""
    if isinstance(event, CommandEvent):
        event.abilityNode = None
        event.queued = bool(event.flag["queued"])
        event.minimap = bool(event.flag["minimap"])
        event.repeated = bool(event.flag["repeat"])
        event.updateEvents = []
        if isinstance(event, UpdateTargetPointCommandEvent):
            event.targetCommandEvent = None
    elif isinstance(event, CommandManagerStateEvent):
        event.commandEvent = None
    elif isinstance(event, SelectionEvent):
        event.cameraLocation = None
    elif isinstance(event, CameraEvent):
        event.timeLocation = None


class MindshareContextLoader(ContextLoader):  # type: ignore[misc]  # sc2reader is untyped
    name = "ContextLoader"

    def handleInitGame(self, event: Any, replay: Any) -> None:
        super().handleInitGame(event, replay)
        self.last_point_command_event: dict[int, Any] = {}

    def handleGameEvent(self, event: Any, replay: Any) -> None:
        decorate_game_event(event)
        super().handleGameEvent(event, replay)

    def handleUpdateTargetUnitCommandEvent(self, event: Any, replay: Any) -> None:
        last = self.last_target_ability_event.get(event.player.pid)
        if last is not None:
            for name in COPIED_FROM_TARGET:
                setattr(event, name, getattr(last, name))
            register_update_event(last, event)
        self.handleTargetUnitCommandEvent(event, replay)

    def handleTargetPointCommandEvent(self, event: Any, replay: Any) -> None:
        self.last_point_command_event[event.player.pid] = event

    def handleUpdateTargetPointCommandEvent(self, event: Any, replay: Any) -> None:
        last = self.last_point_command_event.get(event.player.pid)
        if last is not None:
            for name in COPIED_FROM_POINT:
                setattr(event, name, getattr(last, name))
            register_update_event(last, event)
        self.handleTargetPointCommandEvent(event, replay)

    def handleSelectionEvent(self, event: Any, replay: Any) -> None:
        super().handleSelectionEvent(event, replay)
        if not replay.datapack:
            return
        self.last_target_ability_event.pop(event.player.pid, None)
        self.last_point_command_event.pop(event.player.pid, None)
        for unit in event.new_units or ():
            decorate_unit(unit)

    def handleTargetUnitCommandEvent(self, event: Any, replay: Any) -> None:
        super().handleTargetUnitCommandEvent(event, replay)
        decorate_unit(getattr(event, "target", None))

    def handleUnitBornEvent(self, event: Any, replay: Any) -> None:
        super().handleUnitBornEvent(event, replay)
        if replay.datapack:
            decorate_unit(event.unit)
            event.unit.doneEvent = event

    def handleUnitInitEvent(self, event: Any, replay: Any) -> None:
        super().handleUnitInitEvent(event, replay)
        if replay.datapack:
            decorate_unit(event.unit)
            event.unit.initEvent = event

    def handleUnitDoneEvent(self, event: Any, replay: Any) -> None:
        super().handleUnitDoneEvent(event, replay)
        if replay.datapack and event.unit_id in replay.objects:
            decorate_unit(event.unit)
            event.unit.doneEvent = event

    def handleUnitDiedEvent(self, event: Any, replay: Any) -> None:
        known = event.unit_id in replay.objects
        super().handleUnitDiedEvent(event, replay)
        if replay.datapack and known:
            decorate_unit(event.unit)
            event.unit.deathEvent = event

    def handleEndGame(self, event: Any, replay: Any) -> None:
        for unit in replay.objects.values():
            decorate_unit(unit)
