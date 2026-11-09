"""CR-081: the move-order step keeps only what the scouting check reads, with every graph unchanged.

``ActionsDetector.addUnitsPointCommand`` gives every commanded unit a believed position and, today, one move-order
record (``UnitMoveCommand``) each; ``analyseScouting`` reads a record only when its order went to one entry
(``len(command.selUnits) == 1``) and confirms a scout by a later position of that unit on the opponent's base, later
to the whole second (``MsUtils.isLater`` on ``"MM.SS"`` texts). CR-081 makes records only for single-entry orders
(Rex's option 2), parses the order's time once (option 3) and compares whole seconds as numbers (option 4), with the
same answers, the hour wrap included.

The characterisation tests (marked "as today") were written and run green on ``ff938f5``, the batch tip before
CR-081 (QA-0), and are kept unchanged. The tests use a bare detector, fake events (subclasses of the reader's classes
with plain attributes), hashable players with a ``pid``, real-shaped unit ids, order times as the fork writes them
(``"MM.SS"``) and a fake base table; they call ``addUnitsPointCommand`` with the commanded list the dispatch would
pass, and ``analyseScouting`` as the detector does after its pass.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.detectors.detectors import ActionsDetector
from sc2mindshare.analysis.detectors.trackers import PositionAccuracy, UnitMoveCommand


class Player:
    def __init__(self, pid):
        self.pid = pid


P1, P2 = Player(1), Player(2)
A_ID, B_ID, C_ID = 37486593, 37224449, 63438849


def unit(uid, player=P1, name="Zergling"):
    return SimpleNamespace(id=uid, player=player, name=name)


def base(name, location, player):
    return SimpleNamespace(name=name, location=location, player=player)


P1_MAIN, P1_NAT = base("Main base", (20, 20), P1), base("Natural", (40, 20), P1)
P2_MAIN, P2_NAT = base("Main base", (150, 150), P2), base("Natural", (130, 150), P2)
BASES = {b.location: b for b in (P1_MAIN, P1_NAT, P2_MAIN, P2_NAT)}
AWAY = (90, 90)  # no base


class Bases:
    def getBaseForLocation(self, x, y):
        return BASES.get((x, y))


class Selection(detectors.SelectionEvent):
    player = new_units = cameraLocation = None

    def __init__(self, player, units, camera):
        self.player, self.new_units, self.cameraLocation = player, units, camera


class Recall(detectors.GetControlGroupEvent):
    player = control_group = None

    def __init__(self, player, group):
        self.player, self.control_group = player, group


class Move(detectors.TargetPointCommandEvent):
    player = time = location = x = y = None

    def __init__(self, player, time_, point):
        self.player, self.time, self.location = player, time_, point
        self.x, self.y = point


def detector(fixes=frozenset()):
    d = ActionsDetector.__new__(ActionsDetector)
    d.ctx = SimpleNamespace(bases=Bases(), fixes=fixes)
    d.lastSelection, d.unitsPositions, d.unitsCommands = {}, {}, {}
    d.scoutIndex, d.scoutedBases = 0, {P1: [], P2: []}
    return d


def order(d, units, time_, point, camera=AWAY, player=None, via=None):
    """A point order to ``units`` (the commanded list itself), its last selection seen at ``camera`` (or ``via``)."""
    player = player or units[0].player
    d.lastSelection[player] = via if via is not None else Selection(player, units, camera)
    e = Move(player, time_, point)
    d.addUnitsPointCommand(units, e)
    return e


def seen(d, u, time_, point):
    """An exact position of ``u`` (``UnitPositionsEvent`` times are ``"MM:SS"``)."""
    when = datetime.strptime(time_, "%M:%S")  # noqa: DTZ007 - naive, as the layer's own position times
    d.addUnitsPositions([(u.id, point)], when, PositionAccuracy.EXACT)


def records(d):
    return {uid: [(c.time, c.x, c.y, c.travelTime, len(c.selUnits)) for c in cs] for uid, cs in d.unitsCommands.items()}


def positions(d):
    return {uid: [(p.time.strftime("%H:%M:%S"), p.x, p.y, p.accuracy.name) for p in ps] for uid, ps in d.unitsPositions.items()}


def scouts(d):
    nodes = d.scoutedBases[P1] + d.scoutedBases[P2]
    return sorted((n.seq, n.unit.id, n.time, n.scoutedBase.name, n.scoutedBase.player.pid) for n in nodes)


# --- AC2: an order given to a single unit is recorded as today (characterisation) ---------------------------------------


def test_a_single_unit_order_from_home_makes_todays_record():
    """QA-3: camera on the player's Main, so the travel time is known (7 s) and the position is PATH."""
    d = detector()
    a = unit(A_ID)
    units = [a]
    selection = Selection(P1, units, (20, 20))
    e = order(d, units, "02.10", (150, 150), via=selection)

    (record,) = d.unitsCommands[A_ID]
    assert (record.time, record.x, record.y, record.travelTime) == ("02.10", 150, 150, 7)
    assert record.targetBase is P2_MAIN and record.selEvent is selection and record.selUnits is units
    assert record.unit is a and e.time == "02.10"
    assert positions(d) == {A_ID: [("00:02:17", 150, 150, "PATH")]}


def test_a_single_unit_order_elsewhere_and_from_a_recalled_group():
    """QA-3: camera away from home (MAYBE, no travel time); a recalled group's list of one unit."""
    d = detector()
    order(d, [unit(A_ID)], "02.10", (130, 150))
    group = [unit(B_ID)]
    recall = Recall(P1, 3)
    order(d, group, "02.20", (150, 150), via=recall)
    assert records(d) == {A_ID: [("02.10", 130, 150, None, 1)], B_ID: [("02.20", 150, 150, None, 1)]}
    assert d.unitsCommands[B_ID][0].selUnits is group and d.unitsCommands[B_ID][0].selEvent is recall
    assert positions(d) == {A_ID: [("00:02:10", 130, 150, "MAYBE")], B_ID: [("00:02:20", 150, 150, "MAYBE")]}


def test_a_unit_ordered_alone_twice_in_one_second_gets_two_records():
    """QA-3 edge."""
    d = detector()
    a = unit(A_ID)
    order(d, [a], "02.10", (150, 150))
    order(d, [a], "02.10", (150, 150))
    assert records(d) == {A_ID: [("02.10", 150, 150, None, 1)] * 2}


# --- AC3: the Scouting steps keep their numbers (characterisation) ------------------------------------------------------


def test_scouting_steps_are_numbered_in_first_command_order():
    """QA-4: A and B are first commanded together (01.10); C scouts first in time (01.30, seen 01:45), B at 02.00
    (seen 02:20), A at 03.00 (seen 03:15). The scouts are numbered A = 0, B = 1, C = 2: keys follow the first
    command, in list order, including a unit first ordered only with others."""
    d = detector()
    a, b, c = unit(A_ID), unit(B_ID), unit(C_ID, P2)
    order(d, [a, b], "01.10", AWAY)
    order(d, [c], "01.30", (40, 20))
    seen(d, c, "01:45", (40, 20))
    order(d, [b], "02.00", (150, 150))
    seen(d, b, "02:20", (150, 150))
    order(d, [a], "03.00", (130, 150))
    seen(d, a, "03:15", (130, 150))

    d.analyseScouting()

    assert list(d.unitsCommands) == [A_ID, B_ID, C_ID]
    assert scouts(d) == [
        (0, A_ID, "03.00", "Natural", 2),
        (1, B_ID, "02.00", "Main base", 2),
        (2, C_ID, "01.30", "Natural", 1),
    ]


def test_a_unit_only_in_several_unit_orders_keeps_its_key_and_scouts_nothing():
    """QA-4, QA-11: its key exists; the scouting check walks it without error."""
    d = detector()
    a, b = unit(A_ID), unit(B_ID)
    order(d, [a, b], "01.10", (150, 150))
    seen(d, a, "01:20", (150, 150))
    d.analyseScouting()
    assert list(d.unitsCommands) == [A_ID, B_ID]
    assert scouts(d) == []


# --- AC5: whole seconds, strictly later (characterisation) --------------------------------------------------------------


@pytest.mark.parametrize(
    ("order_time", "seen_at", "point", "confirmed"),
    [
        ("02.59", None, (130, 150), False),  # 1: its own MAYBE position is in the same second
        ("02.59", "03:00", (130, 150), True),  # 2: one second later, across the minute boundary
        ("02.10", "02:11", (130, 150), True),  # 3
        ("02.10", "02:10", (130, 150), False),  # 3: the same second
        ("02.10", "02:09", (130, 150), False),  # 4: earlier
        ("02.59", "03:30", AWAY, False),  # 5: later, off the base
        ("00.01", "00:01", (130, 150), False),  # 7: two frames of one whole second are not later
        ("00.01", "00:02", (130, 150), True),  # 7: the next whole second is
    ],
)
def test_the_scouting_check_compares_whole_seconds_strictly(order_time, seen_at, point, confirmed):
    """QA-6 (1)-(5), (7)."""
    d = detector()
    c = unit(C_ID)
    order(d, [c], order_time, (130, 150))
    if seen_at:
        seen(d, c, seen_at, point)
    d.analyseScouting()
    assert scouts(d) == ([(0, C_ID, order_time, "Natural", 2)] if confirmed else [])


def test_an_order_from_home_confirms_itself_by_its_path_position():
    """QA-6 (6), as today (not to be 'fixed'): from the Main, the PATH position at +7 s is later and on the target."""
    d = detector()
    order(d, [unit(C_ID)], "02.59", (130, 150), camera=(20, 20))
    d.analyseScouting()
    assert scouts(d) == [(0, C_ID, "02.59", "Natural", 2)]


def test_two_confirmed_orders_in_one_second_give_two_scouts():
    """QA-6 (9)."""
    d = detector()
    c = unit(C_ID)
    order(d, [c], "02.10", (130, 150))
    order(d, [c], "02.10", (130, 150))
    seen(d, c, "02:30", (130, 150))
    d.analyseScouting()
    assert scouts(d) == [(0, C_ID, "02.10", "Natural", 2), (1, C_ID, "02.10", "Natural", 2)]


def test_a_command_never_checked_is_never_parsed():
    """QA-6 (8): a record whose unit has no position, or whose target is no opponent base, has its time read only
    when a position is checked, so an unreadable time there raises nothing, as today."""
    d = detector()
    c = unit(C_ID)
    d.unitsCommands[C_ID] = [UnitMoveCommand(c, "not a time", 130, 150, None, [c], None, d.ctx)]
    d.unitsPositions[C_ID] = []
    d.unitsCommands[A_ID] = [UnitMoveCommand(unit(A_ID), "not a time", 40, 20, None, [unit(A_ID)], None, d.ctx)]
    at_three = datetime(1900, 1, 1, 0, 3)  # noqa: DTZ001 - naive, as the layer's own position times
    d.unitsPositions[A_ID] = [SimpleNamespace(time=at_three, x=40, y=20)]
    d.analyseScouting()
    assert scouts(d) == []


# --- AC5 at the hour; 60 minutes; empty and missing selections (QA-7; characterisation) --------------------------------


def test_a_path_position_past_the_hour_does_not_confirm_as_today():
    """QA-7 (1): from the Main at 59.55 the PATH position is 01:00:02, read as "00.02" (the hour dropped), which is not
    later than 59.55: not confirmed. A comparison without the wrap would confirm it."""
    d = detector()
    order(d, [unit(C_ID)], "59.55", (130, 150), camera=(20, 20))
    assert positions(d) == {C_ID: [("01:00:02", 130, 150, "PATH")]}
    d.analyseScouting()
    assert scouts(d) == []


def test_an_order_at_sixty_minutes_fails_as_today():
    """QA-7 (2): the fork's text is ``HH.MM.SS`` then, and the parse raises the same error."""
    d = detector()
    with pytest.raises(ValueError, match="unconverted data remains"):
        order(d, [unit(A_ID), unit(B_ID)], "01.00.00", (150, 150))


def test_empty_and_missing_selections_as_today():
    """QA-7 (3): an empty commanded list makes nothing (CR-080's return); no last selection raises KeyError."""
    d = detector()
    d.addUnitsPointCommand([], Move(P1, "02.10", (150, 150)))
    assert (d.unitsCommands, d.unitsPositions) == ({}, {})
    with pytest.raises(KeyError):
        d.addUnitsPointCommand([unit(A_ID)], Move(P1, "02.10", (150, 150)))
