"""CR-047 (T3-7): control-group update kinds and the selection subgroup (tab) index.

Literals measured on s2protocol's raw events (an oracle independent of sc2reader):
- F3-012 (supported on three replays): the kinds are upstream sc2reader's (0 set, 1 add, 2 recall,
  3 clear, 4 steal and set, 5 steal and add), not the fork's (it calls 3 plain, 4 steal, 5 weird). After
  a steal the client generates, in the same game loop, events on the other groups that remove the stolen
  units: a recall, a selection change, then a set (group still holds units) or a clear (group now empty).
  Every clear in the three replays is one of those generated events.
- The subgroup index is always lower than the number of distinct unit types in the tracked selection.
"""

from collections import Counter

import pytest
import sc2reader
from sc2mindshare.decoding import load
from sc2mindshare.decoding.control_groups import Kind, control_group_activity, kind_of
from sc2reader.engine.plugins import ContextLoader, SelectionTracker

P, A = "player", "auto"
EXPECTED = {
    "alcyone": {
        1: {
            (Kind.ADD, P): 52,
            (Kind.CLEAR, A): 3,
            (Kind.RECALL, A): 40,
            (Kind.RECALL, P): 376,
            (Kind.SELECTION, A): 41,
            (Kind.SELECTION, P): 990,
            (Kind.SET, A): 7,
            (Kind.SET, P): 5,
            (Kind.STEAL_ADD, P): 2,
            (Kind.STEAL_SET, P): 5,
        },
        2: {
            (Kind.ADD, P): 25,
            (Kind.CLEAR, A): 3,
            (Kind.RECALL, A): 50,
            (Kind.RECALL, P): 195,
            (Kind.SELECTION, A): 52,
            (Kind.SELECTION, P): 369,
            (Kind.SET, A): 6,
            (Kind.SET, P): 13,
            (Kind.STEAL_SET, P): 13,
        },
    },
    "spores": {
        1: {(Kind.RECALL, P): 416, (Kind.SELECTION, P): 600, (Kind.SET, P): 64},
        2: {
            (Kind.ADD, P): 20,
            (Kind.CLEAR, A): 3,
            (Kind.RECALL, A): 49,
            (Kind.RECALL, P): 274,
            (Kind.SELECTION, A): 49,
            (Kind.SELECTION, P): 1150,
            (Kind.SET, A): 10,
            (Kind.SET, P): 1,
            (Kind.STEAL_SET, P): 13,
        },
    },
    "spine": {
        1: {
            (Kind.ADD, P): 13,
            (Kind.CLEAR, A): 4,
            (Kind.RECALL, A): 30,
            (Kind.RECALL, P): 125,
            (Kind.SELECTION, A): 28,
            (Kind.SELECTION, P): 532,
            (Kind.SET, A): 3,
            (Kind.SET, P): 2,
            (Kind.STEAL_SET, P): 12,
        },
        2: {
            (Kind.ADD, P): 9,
            (Kind.CLEAR, A): 1,
            (Kind.RECALL, A): 4,
            (Kind.RECALL, P): 46,
            (Kind.SELECTION, A): 3,
            (Kind.SELECTION, P): 252,
            (Kind.SET, A): 1,
            (Kind.STEAL_SET, P): 3,
        },
    },
}


def test_kinds_are_upstreams():
    assert [kind_of(t) for t in range(7)] == [
        Kind.SET,
        Kind.ADD,
        Kind.RECALL,
        Kind.CLEAR,
        Kind.STEAL_SET,
        Kind.STEAL_ADD,
        Kind.UNKNOWN,
    ]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_activity_split_into_player_and_client_generated(replays, name):
    assert control_group_activity(load(replays[name]).replay) == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_clear_is_generated_by_a_steal(replays, name):
    activity = control_group_activity(load(replays[name]).replay)
    assert all(counts.get((Kind.CLEAR, P), 0) == 0 for counts in activity.values())


def _type_at(unit, frame):
    name = None
    for f, t in sorted(unit.type_history.items()):
        if f <= frame:
            name = t.name
    return name or unit.name


class _SubgroupProbe:
    name = "SubgroupProbe"

    def __init__(self):
        self.rows = Counter()

    def handleSelectionEvent(self, event, replay):
        if event.control_group == 10 and event.player is not None:
            types = {_type_at(u, event.frame) for u in event.player.selection[10]}
            self.rows[event.subgroup_index < max(len(types), 1)] += 1


@pytest.mark.parametrize(("name", "count"), [("alcyone", 1320), ("spores", 1684), ("spine", 778)])
def test_subgroup_index_is_within_the_selections_unit_types(replays, name, count):
    probe = _SubgroupProbe()
    engine = sc2reader.engine.GameEngine(plugins=[ContextLoader(), SelectionTracker(), probe])
    replay = sc2reader.load_replay(replays[name], load_level=4, load_map=False, engine=engine)
    assert probe.rows == {True: count}
    assert [p.selection_errors for p in replay.players] == [0, 0]
