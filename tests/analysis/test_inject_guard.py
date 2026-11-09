"""CR-075: an inject-named command counts only on the commanding player's own known Hatchery, Lair or Hive.

A follow-up command (``UpdateTargetUnitCommandEvent``) carries the name of the player's last target command, so
after an inject it can be named ``SpawnLarva`` while it aims at any unit, an opponent's hatchery, or nothing. The
inject tracker looked every such target up among its hatcheries and crashed (``KeyError``) on anything else, and it
counted a command on the opponent's hatchery. The guard (``InjectTracker.isOwnKnownHatchery``, the first statement
of ``processInject``) skips them (AC2, AC3, Stefan's D2a); a follow-up on the player's own hatchery still counts,
timed exactly as before (AC4, D1a).

The synthetic tests drive the tracker directly. The guard sits inside ``processInject``, so the follow-up branch
and the inject-command branch of ``processSelectionsAndCommands`` (both only call ``processInject``) are covered by
the same tests; which branch an event came from is not visible to the tracker. "Own" is the event's player against
the target's owner; the tracker never reads the selection, so no test here can (or needs to) set one.

The expected values in AC4 are literals worked out from the tracker at ``dafcf59`` (inject 29 s, threshold 10 s),
never recomputed by the code under test.
"""

import contextlib
import hashlib
import io
import os
import pathlib
from types import SimpleNamespace

import pytest

# Through detectors, which imports trackers in their working order (trackers first is a circular ImportError)
from sc2mindshare.analysis.detectors.detectors import InjectTracker
from sc2mindshare.analysis.run import analyse
from sc2mindshare.reader.loader import load_replay

HATCH_P2 = 49545217  # real-shaped unit ids (index << 18 | recycle)
HATCH_P1 = 81526786
CYBERNETICS_CORE = 53477378


class Player:
    """A hashable player with a pid: the tracker keys ``injectDelays`` by player object."""

    def __init__(self, pid):
        self.pid = pid


P1 = Player(1)
P2 = Player(2)


def unit(uid, name, owner):
    return SimpleNamespace(id=uid, name=name, owner=owner, player=owner)


def command(time, player, target=None):
    """An inject-named command as the reader gives it (the follow-up's ability fields are copied: 3616)."""
    if target is None:
        return SimpleNamespace(time=time, player=player, ability_name="SpawnLarva", ability_id=3616)
    return SimpleNamespace(time=time, player=player, target=target, ability_name="SpawnLarva", ability_id=3616)


def tracker(*hatcheries):
    t = InjectTracker(P1, P2, frozenset())
    for h in hatcheries:
        t.addHatchery(h)
    return t


def statuses(t, uid):
    return [(s.injectTime.strftime("%M.%S"), s.injectedUntil.strftime("%M.%S")) for s in t.hatcheries[uid]]


def delays(t, player):
    return [(n.unitID, n.unitName, n.start, n.end, n.duration, n.threshold) for n in t.injectDelays[player]]


def snapshot(t):
    return (
        {uid: statuses(t, uid) for uid in t.hatcheries},
        delays(t, P1),
        delays(t, P2),
        t.seq,
    )


# --- AC2: a follow-up aimed at something that is not a hatchery is skipped ------------------------------------------


NOT_A_HATCHERY = {
    "opponent building": unit(CYBERNETICS_CORE, "CyberneticsCore", P1),
    "opponent warp gate": unit(53739522, "WarpGate", P1),
    "opponent nexus": unit(42729473, "Nexus", P1),
    "opponent unit": unit(81002497, "VoidRay", P1),
    "neutral mineral field": unit(20447233, "MineralField", None),
    "neutral geyser": unit(20709377, "VespeneGeyser", None),
    "own building": unit(60293121, "SpawningPool", P2),
    "own unit": unit(61341697, "Queen", P2),
}


@pytest.mark.parametrize("name", sorted(NOT_A_HATCHERY))
def test_an_inject_named_command_on_a_non_hatchery_is_skipped(name):
    t = tracker(unit(HATCH_P2, "Hatchery", P2))
    t.processInject(command("01.00", P2, unit(HATCH_P2, "Hatchery", P2)))
    before = snapshot(t)

    t.processInject(command("01.20", P2, NOT_A_HATCHERY[name]))  # KeyError before CR-075

    assert snapshot(t) == before
    assert snapshot(t) == ({HATCH_P2: [("01.00", "01.29")]}, [], [], 0)


def test_an_inject_named_command_on_a_point_is_skipped():
    t = tracker(unit(HATCH_P2, "Hatchery", P2))
    t.processInject(command("01.00", P2, unit(HATCH_P2, "Hatchery", P2)))
    before = snapshot(t)

    t.processInject(command("01.20", P2))  # no target: AttributeError before CR-075

    assert snapshot(t) == before


def test_a_known_hatchery_whose_owner_cannot_be_read_is_skipped():
    hatch = unit(HATCH_P2, "Hatchery", None)
    t = tracker(hatch)

    t.processInject(command("01.00", P2, hatch))

    assert snapshot(t) == ({HATCH_P2: []}, [], [], 0)


# --- AC3: an inject-named command on the opponent's hatchery does not count (D2a) ------------------------------------


@pytest.mark.parametrize("name", ["Hatchery", "Lair", "Hive"])
def test_a_command_on_the_opponents_hatchery_changes_nothing(name):
    theirs = unit(HATCH_P2, name, P2)
    t = tracker(unit(HATCH_P1, "Hatchery", P1), theirs)
    t.processInject(command("01.00", P2, theirs))
    before = snapshot(t)

    t.processInject(command("01.20", P1, theirs))  # counted on P2's hatchery before CR-075

    assert snapshot(t) == before


@pytest.mark.parametrize("name", ["Hatchery", "Lair", "Hive"])
def test_the_opponents_command_does_not_shift_the_owners_later_delay(name):
    theirs = unit(HATCH_P2, name, P2)
    t = tracker(unit(HATCH_P1, "Hatchery", P1), theirs)
    t.processInject(command("01.00", P2, theirs))
    t.processInject(command("01.20", P1, theirs))
    t.processInject(command("02.10", P2, theirs))

    # As if P1's command had never happened: 01.29 to 02.10 without injects (before CR-075: 01.49, 21.0 s)
    assert statuses(t, HATCH_P2) == [("01.00", "01.29"), ("02.10", "02.39")]
    assert delays(t, P2) == [(HATCH_P2, name, "00:01:29", "00:02:10", 41.0, 10)]
    assert delays(t, P1) == []


# --- AC4: a follow-up on the player's own hatchery still counts, exactly as today (D1a) -----------------------------


@pytest.mark.parametrize("name", ["Hatchery", "Lair", "Hive"])
def test_a_follow_up_on_the_players_own_hatchery_counts_as_today(name):
    own = unit(HATCH_P2, name, P2)
    t = tracker(own)

    t.processInject(command("01.00", P2, own))  # a real inject
    t.processInject(command("01.20", P2, own))  # a follow-up on the same hatchery
    t.processInject(command("02.10", P2, own))  # a real inject

    assert statuses(t, HATCH_P2) == [("01.00", "01.29"), ("01.20", "01.49"), ("02.10", "02.39")]
    assert delays(t, P2) == [(HATCH_P2, name, "00:01:49", "00:02:10", 21.0, 10)]
    assert delays(t, P1) == []
    assert t.seq == 1


def test_a_first_command_on_an_own_hatchery_starts_its_inject_as_today():
    own = unit(HATCH_P2, "Hatchery", P2)
    t = tracker(own)

    t.processInject(command("03.00", P2, own))

    assert snapshot(t) == ({HATCH_P2: [("03.00", "03.29")]}, [], [], 0)


# --- AC1: Stefan's Rainfall LE (104) gets past the inject step (opt-in: his replay, read in place) --------------------


def _root():
    d = pathlib.Path(__file__).resolve().parents[2]
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
RAINFALL = MS_SC / "cr-074-recent" / "Rainfall LE (104).SC2Replay"
RAINFALL_SHA256 = "c79e9c643632bb12a86e24abf7626b1f291d1a9322947c9f0a09ab30465b1b41"


def _verdict(tracker_, event):
    """The D2a rule, written out here so the test does not take it from the code under test."""
    target = getattr(event, "target", None)
    if target is None:
        return "skip: no target"
    if target.id not in tracker_.hatcheries:
        return "skip: not a known hatchery"
    if target.owner is None or target.owner.pid != event.player.pid:
        return "skip: not the player's own"
    return "count"


#: Rainfall LE (104)'s casts where the energy check took a lone selected unit as the caster (the Ravager at 10:41 first):
#: E1 finds several of the player's casters with the energy each time, so it charges none and logs the cast (D2a). From
#: Rex's independent probe with CR-075 and E1 (``.scratch/rex/cr-076/v2-a7.json``), not from the code under test.
RAINFALL_LINES = [
    "energy check: 10.41 SpawnLarva: selected Ravager [4E00001]: data doesn't match (3 own Queen with 25 energy)",
    "energy check: 13.58 SpawnLarva: selected Roach [8280004]: data doesn't match (4 own Queen with 25 energy)",
    "energy check: 15.39 PsionicStorm: selected VoidRay [3380004]: data doesn't match (2 own HighTemplar with 75 energy)",
    "energy check: 18.45 FungalGrowth: selected Corruptor [680000B]: data doesn't match (3 own Infestor with 75 energy)",
    *["energy check: 26.30 SpawnLarva: selected Hive [2F40001]: data doesn't match (5 own Queen with 25 energy)"] * 2,
    *["energy check: 26.31 SpawnLarva: selected Hive [2F40001]: data doesn't match (5 own Queen with 25 energy)"] * 4,
]


def test_rainfall_104_gets_past_the_inject_tracker(monkeypatch):
    """AC1 as amended (Stefan's D1a, 19:31): the build gets past the inject step. Before CR-075 it stops at 02:27 in
    ``processInject`` with ``KeyError: 53477378``; with CR-075 alone its next failure was the energy check at 10:41
    (``getEnergyAtTime``, ``KeyError: 81788929``). CR-076 (layer fix E1) landed second and updated this pin, as the
    two stories agreed: the analysis now finishes, with the energy check's 10 'data doesn't match' lines. The
    replay is Stefan's: read in place, never copied into the repository."""
    if not RAINFALL.exists():
        message = f"Rainfall LE (104) not found: {RAINFALL}"
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"{message} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(message)
    assert hashlib.sha256(RAINFALL.read_bytes()).hexdigest() == RAINFALL_SHA256, "Rainfall LE (104) changed"

    calls = []
    trackers = []
    original = InjectTracker.processInject

    def recording(self, event):
        target = getattr(event, "target", None)
        owner = getattr(target, "owner", None)
        calls.append(
            (
                event.time,
                event.player.pid,
                getattr(target, "id", None),
                getattr(target, "name", None),
                getattr(owner, "pid", None),
                _verdict(self, event),
            )
        )
        if self not in trackers:
            trackers.append(self)
        return original(self, event)

    monkeypatch.setattr(InjectTracker, "processInject", recording)

    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        analyse(load_replay(RAINFALL), MS_SC)  # the default fixes: E1 on

    lines = log.getvalue().splitlines()
    found = [line for line in lines if "data doesn't match" in line]
    # CR-080 (CG1): smaller recalled groups give E1's search more lone units with no record (here a zergling the code
    # names Larva, at 02:27 and from 17:55). Rex's 10 lines (before CG1) are all still there, in order; the total is a
    # characterisation of the CG1 build (2026-11-09, ``.scratch/cr-080/probe-lines/rainfall104.json``).
    remaining = iter(found)
    assert all(any(line == other for other in remaining) for line in RAINFALL_LINES)
    assert len(found) == 21
    assert not [line for line in lines if line.startswith("ERROR unit:")]

    counted = [c for c in calls if c[5] == "count"]
    skipped = [c for c in calls if c[5] != "count"]
    print(
        f"Rainfall LE (104): {len(calls)} inject-named calls, {len(counted)} counted, {len(skipped)} skipped:",
        sorted({(c[5], c[3]) for c in skipped}),
    )
    assert len(counted) == 116  # over the whole game now (29 up to the energy stop at 10:41, before CR-076)
    assert {(c[1], c[4]) for c in counted} == {(2, 2)}
    assert {c[3] for c in counted} <= {"Hatchery", "Lair", "Hive"}
    assert skipped == [
        ("02.27", 2, CYBERNETICS_CORE, "CyberneticsCore", 1, "skip: not a known hatchery"),
        ("02.28", 2, CYBERNETICS_CORE, "CyberneticsCore", 1, "skip: not a known hatchery"),
    ]
    assert len(trackers) == 1
    (it,) = trackers
    assert not [n for p in it.injectDelays if p.pid == 1 for n in it.injectDelays[p]]  # no delay for player 1
    assert all(
        n.player.pid == 2 and n.unitName in ("Hatchery", "Lair", "Hive") for p in it.injectDelays for n in it.injectDelays[p]
    )
