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

It also gives upstream objects the fields the fork declared in their ``__init__`` (the Mindshare
layer reads them, and later detectors set them). Since CR-020 (T19) none of this touches the objects:
every field is kept in ``reader.side_fields`` (a map keyed by the object), and the fork-flavoured
classes read it through properties, so each event and unit keeps exactly upstream's attributes and
values.

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

# isort: split
from sc2mindshare.reader import side_fields
from sc2mindshare.reader.side_fields import COPIED_FROM_POINT, COPIED_FROM_TARGET, UNIT_FIELDS


def register_update_event(command: Any, update: Any, replay: Any) -> None:
    """The fork's ``CommandEvent.registerUpdateEvent``."""
    side_fields.get(command, "updateEvents").append(update)
    side_fields.set(update, "targetCommandEvent", command, replay)


def decorate_unit(unit: Any, replay: Any) -> None:
    """Give a unit the fork's extra fields (None) unless it has them already."""
    if unit is not None:
        for name in UNIT_FIELDS:
            if not side_fields.has(unit, name):
                side_fields.set(unit, name, None, replay)


def decorate_game_event(event: Any, replay: Any) -> None:
    """The fields the fork set in game-event ``__init__``s."""
    if isinstance(event, CommandEvent):
        side_fields.set(event, "abilityNode", None, replay)
        side_fields.set(event, "queued", bool(event.flag["queued"]), replay)
        side_fields.set(event, "minimap", bool(event.flag["minimap"]), replay)
        side_fields.set(event, "repeated", bool(event.flag["repeat"]), replay)
        side_fields.set(event, "updateEvents", [], replay)
        if isinstance(event, UpdateTargetPointCommandEvent):
            side_fields.set(event, "targetCommandEvent", None, replay)
    elif isinstance(event, CommandManagerStateEvent):
        side_fields.set(event, "commandEvent", None, replay)
    elif isinstance(event, SelectionEvent):
        side_fields.set(event, "cameraLocation", None, replay)
    elif isinstance(event, CameraEvent):
        side_fields.set(event, "timeLocation", None, replay)


class MindshareContextLoader(ContextLoader):  # type: ignore[misc]  # sc2reader is untyped
    name = "ContextLoader"

    def handleInitGame(self, event: Any, replay: Any) -> None:
        super().handleInitGame(event, replay)
        self.last_point_command_event: dict[int, Any] = {}
        #: Players whose last target command the fork forgot on a selection change (CR-020). Upstream's own
        #: ``last_target_ability_event`` is left as upstream keeps it, so the events' own fields stay upstream's.
        self.fork_forgot_target: set[int] = set()

    def _fork_last_target(self, pid: int) -> Any:
        """The fork's last target command of the player: upstream's, unless a selection change came after it."""
        return None if pid in self.fork_forgot_target else self.last_target_ability_event.get(pid)

    def handleGameEvent(self, event: Any, replay: Any) -> None:
        decorate_game_event(event, replay)
        super().handleGameEvent(event, replay)

    def handleUpdateTargetUnitCommandEvent(self, event: Any, replay: Any) -> None:
        last = self._fork_last_target(event.player.pid)
        if last is not None:
            for name in COPIED_FROM_TARGET:
                side_fields.set(event, name, side_fields.get(last, name), replay)
            register_update_event(last, event, replay)
        else:  # the fork copied nothing: its layer reads the event's own ability_name, before upstream's copy
            side_fields.set(event, "ability_name", event.ability_name, replay)
        # upstream's own handler: it copies ability_name onto the event itself (as a plain upstream load
        # does), then runs handleTargetUnitCommandEvent, which is ours (it decorates the target)
        super().handleUpdateTargetUnitCommandEvent(event, replay)

    def handleTargetPointCommandEvent(self, event: Any, replay: Any) -> None:
        self.last_point_command_event[event.player.pid] = event

    def handleUpdateTargetPointCommandEvent(self, event: Any, replay: Any) -> None:
        last = self.last_point_command_event.get(event.player.pid)
        if last is not None:
            for name in COPIED_FROM_POINT:
                side_fields.set(event, name, side_fields.get(last, name), replay)
            register_update_event(last, event, replay)
        self.handleTargetPointCommandEvent(event, replay)

    def handleSelectionEvent(self, event: Any, replay: Any) -> None:
        super().handleSelectionEvent(event, replay)
        if not replay.datapack:
            return
        self.fork_forgot_target.add(event.player.pid)  # the fork's forgetting; upstream's dict is left alone
        self.last_point_command_event.pop(event.player.pid, None)
        for unit in event.new_units or ():
            decorate_unit(unit, replay)

    def handleTargetUnitCommandEvent(self, event: Any, replay: Any) -> None:
        super().handleTargetUnitCommandEvent(event, replay)  # upstream records this as the player's last target
        self.fork_forgot_target.discard(event.player.pid)
        decorate_unit(getattr(event, "target", None), replay)

    def handleUnitBornEvent(self, event: Any, replay: Any) -> None:
        super().handleUnitBornEvent(event, replay)
        if replay.datapack:
            decorate_unit(event.unit, replay)
            side_fields.set(event.unit, "doneEvent", event, replay)

    def handleUnitInitEvent(self, event: Any, replay: Any) -> None:
        super().handleUnitInitEvent(event, replay)
        if replay.datapack:
            decorate_unit(event.unit, replay)
            side_fields.set(event.unit, "initEvent", event, replay)

    def handleUnitDoneEvent(self, event: Any, replay: Any) -> None:
        super().handleUnitDoneEvent(event, replay)
        if replay.datapack and event.unit_id in replay.objects:
            decorate_unit(event.unit, replay)
            side_fields.set(event.unit, "doneEvent", event, replay)

    def handleUnitDiedEvent(self, event: Any, replay: Any) -> None:
        known = event.unit_id in replay.objects
        super().handleUnitDiedEvent(event, replay)
        if replay.datapack and known:
            decorate_unit(event.unit, replay)
            side_fields.set(event.unit, "deathEvent", event, replay)

    def handleEndGame(self, event: Any, replay: Any) -> None:
        for unit in replay.objects.values():
            decorate_unit(unit, replay)
