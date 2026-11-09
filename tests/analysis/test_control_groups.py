"""CR-080 (layer fix CG1): a control group follows the game's meaning of set, add and steal.

A group's unit list only grew: every set, add or steal wrote the old units plus the selection, and a steal never
took the stolen units out of their old group. Under CG1 (Stefan's D1a, D1b, Q-2 Set): set (update type 0) and
steal-and-set (4) make the group exactly the selection; add (1) and steal-and-add (5) put the selection beside the
units it holds; a unit is in a group once, by its id; a steal takes the stolen units out of every other group of
the stealing player, and a group it empties stays, empty. A move order to an empty group moves no unit (AC7, an
unconditional guard with no id). The bug-faithful run (``fixes=()``) keeps today's lists.

The unit tests drive ``ControlGroup`` and ``ActionsDetector.updateCG`` on a bare detector with fake events (the
fields the code reads: ``player``, ``control_group``, ``update_type``, ``second``, ``pid``, ``playerName``) and fake
units with real-shaped ids, taking the dispatch's own steps for the control-group events (``processSelectionsAndCommands``:
a steal-and-set first calls ``removeUnitsFromOtherCGs(player, "", e)``, then ``updateCG``). Expected lists are written
from the rule, by hand. The AC4 test builds Stefan's three long games, read in place by SHA-256, each in a child of
its own (process group, ``os.wait4``), killed at 30 s or 1 GiB; it runs in every gate on this Mac
(``SC2MS_REQUIRE_GOLDEN=1``) and is skipped elsewhere when the replays are absent.
"""

import contextlib
import csv
import hashlib
import io
import json
import os
import pathlib
import platform
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.detectors.detectors import ActionsDetector, EnergyTracker
from sc2mindshare.analysis.fixes import LAYER_FIXES
from sc2mindshare.analysis.game import ControlGroup

CG1 = frozenset(LAYER_FIXES)
FAITHFUL = frozenset()
SET, ADD, STEAL_SET, STEAL_ADD = 0, 1, 4, 5


class Player:
    def __init__(self, pid):
        self.pid = pid


P1, P2 = Player(1), Player(2)


def unit(uid, player=P1):
    return SimpleNamespace(id=uid, player=player, name="Zergling", is_worker=False)


A, B, C, D, E = (unit(53477378 + i * 262144) for i in range(5))
W, X, Y, Z = (unit(61341697 + i * 262144) for i in range(4))


def cg_event(kind, group, second, player=P1):
    return SimpleNamespace(
        update_type=kind, control_group=group, second=second, player=player, pid=player.pid, playerName=f"P{player.pid}"
    )


class Selection(detectors.SelectionEvent):
    player = new_units = None

    def __init__(self, player, units):
        self.player, self.new_units = player, units


class Recall(detectors.GetControlGroupEvent):
    player = control_group = None

    def __init__(self, player, group):
        self.player, self.control_group = player, group


def detector(fixes=CG1):
    d = ActionsDetector.__new__(ActionsDetector)
    d.ctx = SimpleNamespace(fixes=fixes)
    d.CONTROL_GROUPS = {P1: {}, P2: {}}
    d.lastSelection = {}
    d.unitsPositions, d.unitsCommands = {}, {}
    return d


def select(d, units, player=P1):
    d.setSelection(Selection(player, list(units)))


def recall(d, group, player=P1):
    d.setSelection(Recall(player, group))


def cg(d, kind, group, second, player=P1):
    """The dispatch's steps for a control-group event (``processSelectionsAndCommands``)."""
    e = cg_event(kind, group, second, player)
    if kind == STEAL_SET:
        d.removeUnitsFromOtherCGs(e.player, "", e)
    d.updateCG(e)


def group(d, no, player=P1):
    return [u.id for u in d.CONTROL_GROUPS[player][no].getLatestUnits()]


def ids(*units):
    return [u.id for u in units]


def put(d, no, units, second, player=P1):
    """Group ``no`` is set from these units."""
    select(d, units, player)
    cg(d, SET, no, second, player)


# --- AC1: setting a group replaces its units --------------------------------------------------------------------------


def test_a_set_replaces_the_groups_units():
    """QA-1 (a); before CR-080: [A, B, C, D, E]."""
    d = detector()
    put(d, 1, [A, B, C], 10)
    put(d, 1, [D, E], 20)
    assert group(d, 1) == ids(D, E)


def test_a_set_with_overlap_keeps_only_the_selection_each_once():
    """QA-1 (b); before CR-080: [A, B, C, B, D]."""
    d = detector()
    put(d, 1, [A, B, C], 10)
    put(d, 1, [B, D], 20)
    assert group(d, 1) == ids(B, D)


def test_a_set_from_a_recalled_group_shares_no_list():
    """QA-1 (c), Morgan's finding 7: the recalled group's own list is the selection; the set must copy it. Must
    fail against a CG1 that stores the selection list itself or appends in place."""
    d = detector()
    put(d, 2, [A, B], 10)
    recall(d, 2)
    cg(d, SET, 1, 20)
    assert d.CONTROL_GROUPS[P1][1].getLatestUnits() is not d.CONTROL_GROUPS[P1][2].getLatestUnits()
    select(d, [C])
    cg(d, ADD, 2, 30)
    assert group(d, 1) == ids(A, B)
    assert group(d, 2) == ids(A, B, C)


def test_a_set_keeps_the_earlier_history_entry():
    """QA-1 (d)."""
    d = detector()
    put(d, 1, [A, B, C], 10)
    put(d, 1, [D], 20)
    assert [u.id for u in d.CONTROL_GROUPS[P1][1].unitsHistory[10]] == ids(A, B, C)


def test_a_group_created_by_a_set_holds_each_unit_once():
    """QA-1 (e): the constructor's write takes the CG1 path too."""
    d = detector()
    put(d, 1, [A, A, B], 10)
    assert group(d, 1) == ids(A, B)


def test_two_unit_objects_with_one_id_are_one_unit():
    """QA-7 (E9): ids, not objects; two units of a type with different ids are two."""
    d = detector()
    put(d, 1, [A, unit(A.id), B], 10)
    assert group(d, 1) == ids(A, B)


# --- AC2: adding keeps the units already there --------------------------------------------------------------------------


def test_an_add_puts_the_selection_beside_the_units_held():
    """QA-2 (a)."""
    d = detector()
    put(d, 1, [A, B], 10)
    select(d, [C])
    cg(d, ADD, 1, 20)
    assert group(d, 1) == ids(A, B, C)


def test_an_add_never_lists_a_unit_twice():
    """QA-2 (b), (c); before CR-080: [A, B, B, C] and [A, B, A, B]."""
    d = detector()
    put(d, 1, [A, B], 10)
    select(d, [B, C])
    cg(d, ADD, 1, 20)
    assert group(d, 1) == ids(A, B, C)
    put(d, 2, [A, B], 30)
    select(d, [A, B])
    cg(d, ADD, 2, 40)
    assert group(d, 2) == ids(A, B)


def test_an_add_leaves_the_units_in_their_other_groups():
    """QA-2 (f), D1b: what tells add from steal. Must fail against a CG1 that runs the steal removal for an add."""
    d = detector()
    put(d, 2, [A], 10)
    select(d, [A])
    cg(d, ADD, 1, 20)
    assert group(d, 1) == ids(A)
    assert group(d, 2) == ids(A)
    assert list(d.CONTROL_GROUPS[P1][2].unitsHistory) == [10]


# --- AC3: stealing moves a unit out of its old group (D1b; Q-2 Set) -----------------------------------------------------


def test_a_steal_takes_the_unit_out_of_its_old_group():
    """QA-3 (a): A in group 1 {A, Y}, group 2 {X}; steal {A} into 2. Before CR-080 group 1 still held A."""
    for kind, receiving in ((STEAL_ADD, ids(X, A)), (STEAL_SET, ids(A))):
        d = detector()
        put(d, 1, [A, Y], 10)
        put(d, 2, [X], 11)
        select(d, [A])
        cg(d, kind, 2, 20)
        assert group(d, 1) == ids(Y), kind
        assert group(d, 2) == receiving, kind


def test_a_unit_in_two_other_groups_leaves_both_and_an_emptied_group_stays():
    """QA-3 (b), AC7's 'the group stays'."""
    d = detector()
    put(d, 1, [A], 10)
    put(d, 4, [A, Z], 11)
    select(d, [A])
    cg(d, STEAL_ADD, 2, 20)
    assert group(d, 1) == [] and 1 in d.CONTROL_GROUPS[P1]
    assert group(d, 4) == ids(Z)


def test_a_steal_into_the_group_that_holds_it():
    """QA-3 (c)."""
    for kind, receiving in ((STEAL_ADD, ids(X, A)), (STEAL_SET, ids(A))):
        d = detector()
        put(d, 1, [A], 10)
        put(d, 2, [X, A], 11)
        put(d, 3, [W], 12)
        select(d, [A])
        cg(d, kind, 2, 20)
        assert (group(d, 1), group(d, 2), group(d, 3)) == ([], receiving, ids(W)), kind


def test_a_steal_from_a_recall_of_the_source_group_reads_the_selection_first():
    """QA-3 (d): recall 2 {A, B}, steal into 3 {W}. Must fail against a design that removes before it reads."""
    for kind, receiving in ((STEAL_ADD, ids(W, A, B)), (STEAL_SET, ids(A, B))):
        d = detector()
        put(d, 2, [A, B], 10)
        put(d, 3, [W], 11)
        recall(d, 2)
        cg(d, kind, 3, 20)
        assert (group(d, 2), group(d, 3)) == ([], receiving), kind


def test_a_steal_of_several_units_one_already_held():
    """QA-3 (e)."""
    for kind, receiving in ((STEAL_ADD, ids(X, A, B)), (STEAL_SET, ids(A, B))):
        d = detector()
        put(d, 1, [B], 10)
        put(d, 2, [X, A], 11)
        select(d, [A, B])
        cg(d, kind, 2, 20)
        assert (group(d, 1), group(d, 2)) == ([], receiving), kind


def test_a_group_created_by_a_steal():
    """QA-3 (f)."""
    for kind in (STEAL_ADD, STEAL_SET):
        d = detector()
        put(d, 1, [A, C], 10)
        put(d, 2, [B], 11)
        select(d, [A, A, B])
        cg(d, kind, 3, 20)
        assert (group(d, 1), group(d, 2), group(d, 3)) == (ids(C), [], ids(A, B)), kind


def test_a_steal_never_touches_the_other_players_groups():
    """QA-3 (g)."""
    d = detector()
    theirs = unit(A.id, P2)  # the same id shape, the other player
    put(d, 1, [theirs], 5, P2)
    put(d, 1, [A], 10)
    select(d, [A])
    cg(d, STEAL_ADD, 2, 20)
    assert group(d, 1, P2) == [A.id]
    assert list(d.CONTROL_GROUPS[P2][1].unitsHistory) == [5]


def test_writes_on_one_second_replace_that_seconds_entry():
    """QA-3 (h), QA-7 (E2)."""
    d = detector()
    put(d, 1, [A, Y], 10)
    put(d, 1, [A, Y], 20)  # group 1 already has an entry at 20
    put(d, 2, [X], 20)
    select(d, [A])
    cg(d, STEAL_SET, 2, 20)
    assert list(d.CONTROL_GROUPS[P1][1].unitsHistory) == [10, 20] and group(d, 1) == ids(Y)
    assert list(d.CONTROL_GROUPS[P1][2].unitsHistory) == [20] and group(d, 2) == ids(A)


def test_a_selection_that_cannot_be_read_changes_no_group():
    """QA-3 (i), QA-7 (E8): ``getLastSelectionUnits`` gives None for any other kind of last selection. No new
    history entry (before CR-080, an add raised ``TypeError``)."""
    for kind in (SET, ADD, STEAL_SET, STEAL_ADD):
        d = detector()
        put(d, 1, [A], 10)
        put(d, 2, [X], 11)
        d.lastSelection[P1] = object()
        cg(d, kind, 2, 20)
        assert (group(d, 1), group(d, 2)) == (ids(A), ids(X)), kind
        assert list(d.CONTROL_GROUPS[P1][2].unitsHistory) == [11], kind


def test_a_steal_writes_new_lists_and_keeps_the_history():
    """QA-3 (j), (k)."""
    d = detector()
    put(d, 1, [A, Y], 10)
    select(d, [A])
    selection = d.lastSelection[P1].new_units
    cg(d, STEAL_ADD, 2, 20)
    lists = [d.CONTROL_GROUPS[P1][n].getLatestUnits() for n in (1, 2)]
    assert lists[0] is not lists[1] and all(x is not selection for x in lists)
    assert [u.id for u in d.CONTROL_GROUPS[P1][1].unitsHistory[10]] == ids(A, Y)


def test_a_steal_and_set_drops_the_unselected_units_without_moving_them():
    """QA-3 (m): group 2 {X, Y}, X also in group 5; steal {A} into 2: [A]; X stays in group 5, Y goes nowhere."""
    d = detector()
    put(d, 2, [X, Y], 10)
    put(d, 5, [X], 11)
    put(d, 1, [A], 12)
    select(d, [A])
    cg(d, STEAL_SET, 2, 20)
    assert (group(d, 1), group(d, 2), group(d, 5)) == ([], ids(A), ids(X))


def test_a_steal_and_set_from_a_recall_of_an_emptied_group():
    """QA-3 (n): the receiving group becomes empty, nothing else changes."""
    d = detector()
    put(d, 1, [A], 10)
    select(d, [A])
    cg(d, STEAL_ADD, 3, 15)  # empties group 1
    put(d, 2, [X], 16)
    recall(d, 1)
    cg(d, STEAL_SET, 2, 20)
    assert (group(d, 1), group(d, 2), group(d, 3)) == ([], [], ids(A))


# --- AC6: the bug-faithful run keeps today's lists ----------------------------------------------------------------------


def test_the_bug_faithful_run_keeps_todays_lists():
    """QA-6, QA-3 (l): literals from the tip (old + selection, duplicates included; no removal)."""
    d = detector(FAITHFUL)
    put(d, 1, [A, B, C], 10)
    put(d, 1, [D, E], 20)
    assert group(d, 1) == ids(A, B, C, D, E)
    put(d, 2, [A, B], 30)
    select(d, [B, C])
    cg(d, ADD, 2, 40)
    assert group(d, 2) == ids(A, B, B, C)
    put(d, 3, [X], 50)
    select(d, [A])
    cg(d, STEAL_SET, 3, 60)
    assert group(d, 1) == ids(A, B, C, D, E)  # no removal: the steal leaves group 1 as it was
    assert group(d, 3) == ids(X, A)  # old + stolen


# --- AC7: a group a steal emptied can be recalled and ordered -----------------------------------------------------------


class Move(detectors.TargetPointCommandEvent):
    player = time = location = x = y = None

    def __init__(self, player, time_, x, y):
        self.player, self.time, self.x, self.y, self.location = player, time_, x, y, (x, y)


def emptied(d):
    """Group 1 {A} emptied by a steal of A into group 2; the selection before that was {Z}."""
    put(d, 1, [A], 10)
    select(d, [Z])
    select(d, [A])
    cg(d, STEAL_ADD, 2, 20)
    recall(d, 1)


def test_a_move_order_to_an_emptied_group_moves_no_unit():
    """QA-12 (a), (e): no exception (``IndexError`` without the guard), no record, no position, not even Z's or A's;
    twice."""
    d = detector()
    emptied(d)
    for second in ("00.30", "00.31"):
        d.addUnitsPointCommand(d.getLastSelectionUnits(P1), Move(P1, second, 50, 60))
    assert (d.unitsCommands, d.unitsPositions) == ({}, {})
    assert group(d, 1) == []


def test_the_build_carries_on_after_it():
    """QA-12 (b), (c): a later order of group 2 is recorded as usual; group 1 is filled again by an add or a set."""
    d = detector()
    d.ctx.bases = SimpleNamespace(getBaseForLocation=lambda x, y: None)
    emptied(d)
    d.addUnitsPointCommand(d.getLastSelectionUnits(P1), Move(P1, "00.30", 50, 60))
    recall(d, 2)
    d.addUnitsPointCommand(d.getLastSelectionUnits(P1), Move(P1, "00.32", 70, 80))
    assert list(d.unitsCommands) == [A.id]
    select(d, [B])
    cg(d, ADD, 1, 40)
    assert group(d, 1) == ids(B)
    put(d, 1, [C, D], 50)
    assert group(d, 1) == ids(C, D)


def test_an_energy_cast_from_an_emptied_group_charges_no_unit():
    """QA-12 (d), (d2): no exception, one 'No unit found' line, no energy taken from anyone (CR-076's E1 on)."""
    d = detector()
    emptied(d)
    et = EnergyTracker(P1, P2, CG1)
    for uid in (A.id, Z.id):  # two Queens of the player with the ids of the stolen and the earlier selected unit
        queen = SimpleNamespace(id=uid, name="Queen", player=P1, owner=P1, doneEvent=SimpleNamespace(time="00:00"))
        queen.deathEvent = None
        et.registerEnergyUnit(queen, "00:00")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        et.processEnergyEvent("00.30", d.getLastSelectionUnits(P1), "SpawnLarva", player=P1)
    assert [line.split(" [")[0] for line in out.getvalue().splitlines()] == ["No unit found 00.30"]
    assert all(len(h) == 1 for h in et.energyHistory.values())
    assert not any(u.is_worker for u in d.getLastSelectionUnits(P1))


def test_no_last_selection_still_raises_as_today():
    """QA-7 (E5), Morgan's finding 8 (characterisation): a player with no last selection."""
    d = detector()
    with pytest.raises(KeyError):
        cg(d, SET, 1, 10)


# --- AC4: the three long games build in an ordinary time ---------------------------------------------------------------


def _root():
    d = pathlib.Path(__file__).resolve().parents[2]
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
RECENT = MS_SC / "cr-074-recent"
GUARD = pathlib.Path(__file__).resolve().parents[1] / "network_guard.py"

#: AC4's three games by SHA-256 (the folder also holds At Eternity's Edge LE (110): the file is picked by its hash).
LONG_GAMES = {
    "Lockdown LE (103)": "7550fc544eb479b336b000688e9e213a35fe14a8e9d77f2d4e6f36e77e4a5b92",
    "Washout LE (107)": "5a5477d9a9173871765adc0316012556d3de393293535bbf6a62e53f35504761",
    "At Eternity's Edge LE (109)": "afdce013d21d7cb2ea0c03ebb2294ed2c50334bdf59174ae0f7cbe8698ca0b4f",
}
BOUND_S, BOUND_BYTES = 10, 500 * 1000 * 1000  # AC4: 10 s, 500 MB
KILL_S, KILL_KIB = 30, 1024 * 1024  # QA-4, QA-10: kill at 30 s or 1 GiB resident
SAMPLE_S = 0.25

#: The child: one CLI build with the default fixes, the network guard on; it streams each energy cast the check
#: reaches (flushed) and, at the end, the largest group list and the number of lists holding a unit twice.
CHILD = """
import contextlib, importlib.util, io, json, socket, sys
replay, out, casts_path, groups_path, config, guard_path = sys.argv[1:7]
spec = importlib.util.spec_from_file_location("sc2ms_network_guard", guard_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
socket.socket.connect = guard._guarded_connect
socket.socket.connect_ex = guard._guarded_connect_ex
from sc2mindshare import cli
from sc2mindshare.analysis.detectors.detectors import EnergyTracker
from sc2mindshare.analysis.game import ControlGroup
casts = open(casts_path, "w", encoding="utf-8")
process = EnergyTracker.processEnergyEvent
def streamed(self, time, units, abilityName, *args, **kwargs):
    casts.write(f"{time} {abilityName}\\n")
    casts.flush()
    return process(self, time, units, abilityName, *args, **kwargs)
EnergyTracker.processEnergyEvent = streamed
sizes = {"largest": 0, "doubled": 0}
def watched(method):
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        listed = [u.id for u in self.getLatestUnits()]
        sizes["largest"] = max(sizes["largest"], len(listed))
        sizes["doubled"] += len(listed) != len(set(listed))
        return result
    return wrapper
ControlGroup.addUnits = watched(ControlGroup.addUnits)
ControlGroup.removeUnits = watched(ControlGroup.removeUnits)
log, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(log), contextlib.redirect_stderr(err):
    code = cli.main(["build", replay, "--out", out, "--config-root", config])
json.dump({**sizes, "exit": code, "stderr": err.getvalue()[-2000:]}, open(groups_path, "w"))
sys.exit(code)
"""


def _rss_kib(pid):
    out = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, check=False).stdout
    return int(out.strip() or 0)


def run_build(argv, out_dir, *, kill_s=KILL_S, kill_kib=KILL_KIB):
    """Run ``argv`` (a Python interpreter, nothing between) in its own session; kill its whole process group at
    ``kill_s`` seconds or ``kill_kib`` KiB of resident memory (sampled every ``SAMPLE_S``), also on any exception;
    reap it with ``os.wait4``. Returns ``{"stopped": None | "timeout" | "memory cap", "seconds", "peak_bytes",
    "last_sample_kib", "exit"}``; ``peak_bytes`` is the child's own ``ru_maxrss`` (bytes on macOS, KiB on Linux)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "child.out").open("w") as out, (out_dir / "child.err").open("w") as err:
        child = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
    start, stopped, sample, status, usage, reaped = time.monotonic(), None, 0, 0, None, False
    try:
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)  # (0, 0, zeroed usage) while it runs
            if pid:
                reaped = True
                break
            if time.monotonic() - start > kill_s:
                stopped = "timeout"
                break
            sample = _rss_kib(child.pid)
            if sample > kill_kib:
                stopped = "memory cap"
                break
            time.sleep(SAMPLE_S)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)  # the whole group: the build and anything it started
        if not reaped:
            _, status, usage = os.wait4(child.pid, 0)
        child.returncode = 0  # reaped here; keeps Popen from waiting again
    peak = usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss * 1024
    return {
        "stopped": stopped,
        "seconds": round(time.monotonic() - start, 2),
        "peak_bytes": peak,
        "last_sample_kib": sample,
        "exit": os.waitstatus_to_exitcode(status),
    }


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    return path


def _by_sha256(sha256):
    """The replay in the recent folder whose content has this hash (never a name match)."""
    _need(RECENT)
    found = [p for p in sorted(RECENT.glob("*.SC2Replay")) if hashlib.sha256(p.read_bytes()).hexdigest() == sha256]
    assert len(found) == 1, f"{len(found)} files with SHA-256 {sha256[:12]}"
    return found[0]


def last_energy_event(path):
    """The replay's last command the dispatch hands to the energy check (time ``MM.SS``, ability), read from the
    events: an update command whose player gave a unit command before it, or a target command whose ability is
    eligible; in both, an ability in the check's table. Loads the replay only; no analysis."""
    from sc2mindshare.reader.compat import game_time
    from sc2mindshare.reader.loader import load_replay

    et, last, gave_unit_command = EnergyTracker(None, None, frozenset()), None, set()
    for e in load_replay(path).events:
        if isinstance(e, (detectors.UpdateTargetUnitCommandEvent, detectors.UpdateTargetPointCommandEvent)):
            if e.player in gave_unit_command and et.isEnergyAbility(e.ability_name):
                last = (game_time(e), e.ability_name)
        elif isinstance(e, (detectors.TargetUnitCommandEvent, detectors.TargetPointCommandEvent)):
            eligible = e.has_ability and not e.ability_name.startswith(detectors.EventsDetector.OMIT_ABILITIES)
            if eligible and et.isEnergyAbility(e.ability_name):
                last = (game_time(e), e.ability_name)
            if isinstance(e, detectors.TargetUnitCommandEvent):
                gave_unit_command.add(e.player)
    return last


def build_bounded(replay, out_dir, config):
    """One timed CLI build of ``replay`` under the AC4 harness; the record with its casts and group sizes."""
    casts, groups = out_dir / "casts.txt", out_dir / "groups.json"
    argv = [sys.executable, "-I", "-B", "-c", CHILD, str(replay), str(out_dir / "game" / "graph.json"), str(casts),
            str(groups), str(config), str(GUARD)]  # fmt: skip
    record = run_build(argv, out_dir)
    reached = casts.read_text(encoding="utf-8").splitlines() if casts.exists() else []
    record["casts"], record["last_cast"] = len(reached), (reached[-1] if reached else None)
    record.update(json.loads(groups.read_text(encoding="utf-8")) if groups.exists() else {})
    return record


def config_root(root):
    root.mkdir(parents=True, exist_ok=True)
    for name in ("unitsInfo.csv", "upgradesInfo.csv", "ImageTracking.csv"):
        shutil.copyfile(_need(MS_SC / name), root / name)
    shutil.copyfile(CHECKOUT / "tests" / "golden" / "clock-record-fixture.csv", root / "ClockImageRecord.csv")
    return root


def head(checkout=CHECKOUT):
    """The commit built, for AC4's report; it never fails the test. ``SC2MS_COMMIT``, when set, is reported as given:
    a copy that is not a git checkout (QA's ``git archive`` export) passes the commit it was made from. Otherwise git is
    asked about ``checkout`` itself, never a folder above it, with whether the tracked tree differs from that commit
    (numbers from a dirty tree are not its); and when that fails, "not a git checkout" (CR-080, Vera's QA blocker)."""
    given = os.environ.get("SC2MS_COMMIT", "").strip()
    if given:
        return f"{given} (SC2MS_COMMIT)"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CEILING_DIRECTORIES"] = str(pathlib.Path(checkout).resolve().parent)

    def git(*args):
        return subprocess.run(["git", "-C", str(checkout), *args], capture_output=True, text=True, check=False, env=env)

    try:
        rev, status = git("rev-parse", "--short", "HEAD"), git("status", "--porcelain", "--untracked-files=no")
    except OSError:
        return "not a git checkout (no git)"
    if rev.returncode or status.returncode:
        return "not a git checkout"
    return f"{rev.stdout.strip()}{' (dirty tree)' if status.stdout.strip() else ''}"


def test_the_commit_report_works_outside_a_git_checkout(tmp_path, monkeypatch):
    """Vera's CR-080 QA blocker: in an exported copy the AC4 test must still run and state the commit it is given."""
    monkeypatch.delenv("SC2MS_COMMIT", raising=False)
    assert head(tmp_path) == "not a git checkout"
    monkeypatch.setenv("SC2MS_COMMIT", "b015f46")
    assert head(tmp_path) == "b015f46 (SC2MS_COMMIT)"
    monkeypatch.setenv("SC2MS_COMMIT", "")
    assert head(tmp_path) == "not a git checkout"


@pytest.mark.parametrize("name", sorted(LONG_GAMES))
def test_a_long_game_builds_in_an_ordinary_time(name, tmp_path):
    """AC4 (QA-4): the build finishes (so it gets past the energy step and the move-command step) in at most 10 s
    and 500 MB of its own peak memory; no group lists a unit twice; for Lockdown LE (103) and Washout LE (107) the
    last energy cast reached is the replay's last energy event (D2a, moved from CR-076). Before CR-080 they ran past
    300 s and into GBs, and are never built here without the fix."""
    replay = _by_sha256(LONG_GAMES[name])

    record = build_bounded(replay, tmp_path, config_root(tmp_path / "config"))

    last = last_energy_event(replay)
    print(
        f"{name} ({replay.name}): {record['seconds']} s, peak {record['peak_bytes'] / 1e6:.0f} MB (ru_maxrss, bytes), "
        f"largest group list {record.get('largest')}, last cast reached {record['last_cast']}, last energy event "
        f"{last}; {platform.machine()} {platform.mac_ver()[0]}, commit {head()}"
    )
    assert record["stopped"] is None, record
    assert record["exit"] == 0, record
    assert record["seconds"] <= BOUND_S and record["peak_bytes"] <= BOUND_BYTES, record
    assert record["doubled"] == 0
    if name != "At Eternity's Edge LE (109)":
        assert last is not None and record["last_cast"] == " ".join(last)


# --- QA-10: the harness kills the build process itself -----------------------------------------------------------------

STAND_IN = """
import os, signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open(sys.argv[1], "w").write(f"{os.getpid()} {grandchild.pid}")
if sys.argv[2] == "grow":
    hoard = []
    for _ in range(20):
        hoard.append(bytearray(10 * 1024 * 1024))
        time.sleep(0.1)
time.sleep(60)
"""


def _gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def _wait_for(path):
    for _ in range(100):
        if path.exists() and path.read_text().strip():
            return [int(x) for x in path.read_text().split()]
        time.sleep(0.05)
    raise AssertionError("the stand-in did not start")


def test_the_harness_kills_the_child_and_its_grandchild_at_the_timeout(tmp_path):
    """QA-10 (a), (b): a child that ignores SIGTERM and starts a grandchild is killed with its whole group."""
    pids = tmp_path / "pids"
    record = run_build([sys.executable, "-c", STAND_IN, str(pids), "sleep"], tmp_path, kill_s=1)
    child, grandchild = _wait_for(pids)
    assert record["stopped"] == "timeout" and record["seconds"] < 5
    time.sleep(0.2)
    assert _gone(child) and _gone(grandchild)


def test_the_harness_kills_the_child_on_an_exception(tmp_path, monkeypatch):
    """QA-10 (c): an exception after ``Popen`` still kills the group."""
    pids = tmp_path / "pids"

    def broken(pid):
        _wait_for(pids)
        raise RuntimeError("interrupted")

    monkeypatch.setattr(sys.modules[__name__], "_rss_kib", broken)
    with pytest.raises(RuntimeError):
        run_build([sys.executable, "-c", STAND_IN, str(pids), "sleep"], tmp_path)
    child, grandchild = _wait_for(pids)
    time.sleep(0.2)
    assert _gone(child) and _gone(grandchild)


def test_the_harness_kills_the_child_at_its_memory_cap(tmp_path):
    """QA-10 (d): a child growing past 50 MB in 10 MB steps is stopped by the cap, not the timeout."""
    pids = tmp_path / "pids"
    record = run_build([sys.executable, "-c", STAND_IN, str(pids), "grow"], tmp_path, kill_s=60, kill_kib=50 * 1024)
    child, grandchild = _wait_for(pids)
    assert record["stopped"] == "memory cap" and record["seconds"] < 10 and record["last_sample_kib"] > 50 * 1024
    time.sleep(0.2)
    assert _gone(child) and _gone(grandchild)


# --- the 29-game comparison set (AC4's Then): listed here, measured by the report run -----------------------------------


def comparison_set():
    """The recent games of 16:00 to 22:59 in the manifest (file name, length)."""
    with (RECENT / "manifest.csv").open(encoding="utf-8", newline="") as f:
        rows = [(r["file"], r["length"]) for r in csv.DictReader(f)]
    return sorted((name, length) for name, length in rows if 16 <= int(length.split(":")[0]) <= 22)


def test_the_comparison_set_is_the_29_games_of_16_to_22_minutes():
    _need(RECENT / "manifest.csv")
    games = comparison_set()
    assert len(games) == 29
    names = {name.removesuffix(".SC2Replay") for name, _ in games}
    assert set(LONG_GAMES) <= names
