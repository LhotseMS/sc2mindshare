"""The fork's fields on sc2reader objects, kept beside the objects instead of on them (CR-020, T19).

Stefan's fork set fields on sc2reader's events and units in their ``__init__`` and in its
ContextLoader, and the Mindshare layer sets more while it runs (``unit.initEvent``,
``unit.baseName``, ``event.updateEvents``, ``event.timeLocation`` ...). Some of them also replaced
upstream's own values (``event.second`` as frame / 22.4; the ability fields an update event copies
from its target command). Here they live in a map keyed by the object's **identity**, so every sc2reader
object keeps exactly upstream's attributes and values. Each entry belongs to the generation of the
replay that adopted its object; the entries go together when that replay is collected, and the
objects themselves are freed one collection pass after the replay. Entries go per replay, not per
object, because the stored values point at other keyed objects (``initEvent``, ``doneEvent`` ...): the
store itself would keep those objects alive, so they never go on their own.

Identity, not equality: sc2reader's ``Unit`` compares and hashes by its unit id, so two replays' units
with the same id are equal, and a ``WeakKeyDictionary`` would give one the other's fields.

``get`` reads the map and falls back to the object's own attribute, so an upstream field nobody
replaced reads as upstream's. ``set`` writes the map only. ``field`` makes a property that does both,
for the fork-flavoured classes (``fork_api``), so the ported layer's ``unit.initEvent`` and
``event.second = ...`` work unchanged.
"""

from __future__ import annotations

import builtins
import itertools
import weakref
from collections.abc import Callable
from typing import Any

#: id(obj) -> (a weak reference to obj, its fields, the generation it belongs to). Reads check that the entry
#: still belongs to obj (an id can be reused once its object is gone).
_STORE: dict[int, tuple[weakref.ref[Any], dict[str, Any], int]] = {}
#: generation -> the ids of its entries; id(replay) -> its generation.
_GENERATIONS: dict[int, builtins.set[int]] = {}
_OWNERS: dict[int, int] = {}
_NEXT = itertools.count(1)


def _drop(generation: int, owner_id: int) -> None:
    """The replay is gone: its entries go, so the objects they hold can go too."""
    for key in _GENERATIONS.pop(generation, ()):
        _STORE.pop(key, None)
    _OWNERS.pop(owner_id, None)


def owner(replay: Any) -> int:
    """The generation of ``replay``: every entry of its objects belongs to it, and all are dropped when the
    replay is collected (weakref.finalize). The stored values point back at the keyed objects (initEvent
    -> event -> unit), so per-object weak references alone would keep every replay alive (CR-020 P1)."""
    generation = _OWNERS.get(id(replay))
    if generation is None:
        generation = _OWNERS[id(replay)] = next(_NEXT)
        _GENERATIONS[generation] = builtins.set()
        weakref.finalize(replay, _drop, generation, id(replay))
    return generation


def _forget(key: int, generation: int) -> Callable[[weakref.ref[Any]], None]:
    """The weak reference's callback: an object that dies on its own takes its entry with it."""

    def callback(_ref: weakref.ref[Any]) -> None:
        _STORE.pop(key, None)
        _GENERATIONS.get(generation, builtins.set()).discard(key)

    return callback


def _fields(obj: Any) -> dict[str, Any] | None:
    entry = _STORE.get(id(obj))
    if entry is None or entry[0]() is not obj:
        return None
    return entry[1]


def adopt(obj: Any, replay: Any) -> None:
    """Give ``obj`` an (empty) entry in ``replay``'s generation, unless it has one."""
    if _fields(obj) is None:
        key, generation = id(obj), owner(replay)
        _STORE[key] = (weakref.ref(obj, _forget(key, generation)), {}, generation)
        _GENERATIONS[generation].add(key)


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


def set(obj: Any, name: str, value: Any, replay: Any = None) -> None:  # the module is used as side_fields.set
    """Set the fork field ``name`` of ``obj``: in the map, never on the object. An object without an entry
    must name its ``replay`` (whose generation the entry joins); otherwise this is a programming error."""
    fields = _fields(obj)
    if fields is None:
        if replay is None:
            raise LookupError(f"{type(obj).__name__} has no side fields yet: pass the replay it belongs to")
        adopt(obj, replay)
        fields = _fields(obj)
        assert fields is not None
    fields[name] = value


def field(name: str) -> property:
    """A property reading and writing the fork field ``name`` (for the fork-flavoured classes)."""

    def read(self: Any) -> Any:
        return get(self, name)

    def write(self: Any, value: Any) -> None:
        set(self, name, value)

    return property(read, write, doc=f"The fork's {name!r}, kept in reader.side_fields")
