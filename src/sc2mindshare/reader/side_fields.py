"""The fork's fields on sc2reader objects, kept beside the objects instead of on them (CR-020, T19).

Stefan's fork set fields on sc2reader's events and units in their ``__init__`` and in its
ContextLoader, and the Mindshare layer sets more while it runs (``unit.initEvent``,
``unit.baseName``, ``event.updateEvents``, ``event.timeLocation`` ...). Some of them also replaced
upstream's own values (``event.second`` as frame / 22.4; the ability fields an update event copies
from its target command). Here they live in a map keyed by the object's **identity** (an entry goes
when its object goes), so every sc2reader object keeps exactly upstream's attributes and values.

Identity, not equality: sc2reader's ``Unit`` compares and hashes by its unit id, so two replays' units
with the same id are equal, and a ``WeakKeyDictionary`` would give one the other's fields.

``get`` reads the map and falls back to the object's own attribute, so an upstream field nobody
replaced reads as upstream's. ``set`` writes the map only. ``field`` makes a property that does both,
for the fork-flavoured classes (``fork_api``), so the ported layer's ``unit.initEvent`` and
``event.second = ...`` work unchanged.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any

#: id(obj) -> (a weak reference to obj, its fields). The weak reference's callback removes the entry when
#: obj dies, before its id can be reused; reads also check that the entry still belongs to obj.
_STORE: dict[int, tuple[weakref.ref[Any], dict[str, Any]]] = {}


def _forget(key: int) -> Callable[[weakref.ref[Any]], None]:
    """The weak reference's callback: drop the entry of the object that has just died."""

    def callback(_ref: weakref.ref[Any]) -> None:
        _STORE.pop(key, None)

    return callback


def _fields(obj: Any) -> dict[str, Any] | None:
    entry = _STORE.get(id(obj))
    if entry is None or entry[0]() is not obj:
        return None
    return entry[1]


#: The fork's extra Unit fields (its ``Unit.__init__``), None until set.
UNIT_FIELDS = ("baseName", "baseType", "unitsNode", "initNode", "deathEvent", "doneEvent", "initEvent")
#: The ability fields an Update*CommandEvent copies from the last target command (upstream's own names).
COPIED_FROM_TARGET = ("ability_name", "has_ability", "ability_type", "ability_data", "ability_id", "ability")
#: Point updates also copy these (fields the fork added to command events).
COPIED_FROM_POINT = ("queued", "minimap", "repeated", *COPIED_FROM_TARGET)
#: The fork's extra command-event fields.
COMMAND_FIELDS = ("abilityNode", "queued", "minimap", "repeated", "updateEvents", "targetCommandEvent")


def get(obj: Any, name: str, default: Any = None) -> Any:
    """The object's fork field ``name``; else its own (upstream) attribute; else ``default``."""
    fields = _fields(obj)
    if fields is not None and name in fields:
        return fields[name]
    return obj.__dict__.get(name, default)


def has(obj: Any, name: str) -> bool:
    fields = _fields(obj)
    return fields is not None and name in fields


def set(obj: Any, name: str, value: Any) -> None:  # the module is used as side_fields.set
    """Set the fork field ``name`` of ``obj``: in the map, never on the object."""
    fields = _fields(obj)
    if fields is None:
        key = id(obj)
        fields = {}
        _STORE[key] = (weakref.ref(obj, _forget(key)), fields)
    fields[name] = value


def field(name: str) -> property:
    """A property reading and writing the fork field ``name`` (for the fork-flavoured classes)."""

    def read(self: Any) -> Any:
        return get(self, name)

    def write(self: Any, value: Any) -> None:
        set(self, name, value)

    return property(read, write, doc=f"The fork's {name!r}, kept in reader.side_fields")
