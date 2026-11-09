"""CR-076 (layer fix E1): the energy check charges the real caster where the fork's check stopped, else logs the cast;
the five spellcaster types without a spare-energy threshold get no spare-energy check.

``EnergyTracker.processEnergyEvent`` takes the one selected unit as the caster when exactly one is selected. A
follow-up command carries the name of the player's last target command, so that unit can be anything (a lone
Ravager for an inject on Stefan's Rainfall LE (104)); it has no energy record and ``getEnergyAtTime`` raised a
``KeyError``. Only there (D1a, Kevin's reading of 19:49-19:52) E1 searches the player's own registered units of the
ability's caster type, alive and finished at the cast and with at least the cost: exactly one is charged (AC2);
none or several are charged nothing and leave one ``data doesn't match`` line in the run log (AC3, D2a). Every
other cast is handled as before (AC4). A Sentry, Oracle, Infestor, High Templar or Overseer cast while the
player's spare-energy period runs asked ``getThreshold`` for a type it has no threshold for (another ``KeyError``);
E1 runs the spare-energy part only for a type with a threshold (AC5, D2a), and leaves the period running (Q-F, D1a).

The synthetic tests drive the tracker directly with fakes shaped like the reader's objects (Morgan's P3-6): a unit
has ``id`` (real-shaped), ``name``, ``player`` and ``owner`` (a hashable player with a ``pid``), ``doneEvent.time``
and ``deathEvent.time`` as tracker times ``"MM:SS"`` (None when absent); a cast time is a game time ``"MM.SS"``.
Every expected energy is a literal worked out by hand from the check's rule (Queen 25 at the start, every other
type 50; 0.7905 a second), never recomputed by the code under test. The AC4 literals hold on the code before E1.

The corpus tests (AC1) build Stefan's recent games, read in place from ``MS SC/cr-074-recent/`` by SHA-256, each in
a child process of its own under a wall-time limit (60 s) and a memory cap (1 GiB); they run in every gate on this
Mac and are skipped elsewhere when the replays are absent.
"""

import contextlib
import csv
import hashlib
import io
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

# Through detectors, which imports trackers in their working order (trackers first is a circular ImportError)
from sc2mindshare.analysis.detectors.detectors import EnergyTracker
from sc2mindshare.analysis.fixes import LAYER_FIXES

WITH_E1 = frozenset(LAYER_FIXES)
FAITHFUL = frozenset()


class Player:
    """A hashable player with a pid: the tracker keys ``excessEnergy`` by player object."""

    def __init__(self, pid):
        self.pid = pid


P = Player(1)  # the opponent
Z = Player(2)  # the commanding player

# Real-shaped unit ids (index << 18 | recycle)
RAVAGER = 81788929  # 0x4E00001, Rainfall LE (104)'s lone Ravager
LAIR = 118489090  # 0x7100002, spores' lone Lair (L1)
QUEEN_1 = 61341697
QUEEN_2 = 62652417
QUEEN_3 = 63963137
QUEEN_P1 = 70254593
QUEEN_P2 = 71565313
OVERSEER_1 = 67895297
OVERSEER_2 = 69206017
PROBE = 20971521
NEXUS_1 = 9175041
NEXUS_2 = 10485761
DRONE = 23855105


def unit(uid, name, owner, done="00:00", died=None):
    return SimpleNamespace(
        id=uid,
        name=name,
        owner=owner,
        player=owner,
        doneEvent=None if done is None else SimpleNamespace(time=done),
        deathEvent=None if died is None else SimpleNamespace(time=died),
    )


def tracker(*registered, fixes=WITH_E1):
    """A tracker with each (unit, tracker time) registered, as the done and born events do."""
    t = EnergyTracker(P, Z, fixes)
    for u, at in registered:
        t.registerEnergyUnit(u, at)
    return t


def cast(t, time_, units, ability, player=None):
    """One cast; returns the lines it printed (the run log, ``graph.log`` in a CLI build). The casts that reach the
    search pass the commanding player, as the two call sites do; the others are called as the code before E1 was
    (no ``player``), so their literals hold on it too."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        if player is None:
            t.processEnergyEvent(time_, units, ability)
        else:
            t.processEnergyEvent(time_, units, ability, player=player)
    return out.getvalue().splitlines()


def history(t, u):
    return [(s.time, round(s.energy, 4), s.abilityName, s.uId) for s in t.energyHistory[u.id]]


def histories(t):
    return {uid: [(s.time, round(s.energy, 4), s.abilityName) for s in h] for uid, h in t.energyHistory.items()}


def excess(t):
    return {p.pid: [(n.unitName, n.unitID, n.start, n.end) for n in t.excessEnergy[p]] for p in t.excessEnergy}


# --- AC2: a cast that would stop today is charged to the one unit that fits -----------------------------------------


def test_a_lone_non_caster_is_charged_to_the_one_queen_that_fits_the_rainfall_case():
    """QA-2 (a): before E1, ``KeyError: 81788929`` in ``getEnergyAtTime``."""
    queen = unit(QUEEN_1, "Queen", Z, done="01:00")
    ravager = unit(RAVAGER, "Ravager", Z, done="00:40")
    t = tracker((queen, "01:00"))

    lines = cast(t, "01.20", [ravager], "SpawnLarva", player=Z)

    # 25 at 01:00, + 20 s x 0.7905 = 40.81, - 25
    assert history(t, queen) == [("01:00", 25, "", QUEEN_1), ("01.20", 15.81, "SpawnLarva", QUEEN_1)]
    assert RAVAGER not in t.energyHistory
    assert lines == []
    # Today's spare-energy rule for her: 40.81 is over 25 since 80 - 15.81 / tan(38.33 deg) = 60 s; the cast ends it
    assert excess(t) == {1: [], 2: [("Queen", QUEEN_1, "00:01:00", "00:01:20")]}

    control = tracker((queen, "01:00"))  # the same cast, with the Queen selected
    cast(control, "01.20", [queen], "SpawnLarva")
    assert histories(t) == histories(control)
    assert excess(t) == excess(control)


def test_a_lone_unit_of_the_right_type_without_a_record_is_charged_to_the_one_that_fits():
    """QA-2 (b): a lone Overseer with no record; the player's one other Overseer with a record and enough is charged."""
    other = unit(OVERSEER_2, "Overseer", Z, done="01:00")
    lone = unit(OVERSEER_1, "Overseer", Z, done="01:10")
    t = tracker((other, "01:00"))

    lines = cast(t, "01.10", [lone], "SpawnChangeling", player=Z)

    # 50 at 01:00, + 10 s x 0.7905 = 57.905, - 50
    assert history(t, other) == [("01:00", 50, "", OVERSEER_2), ("01.10", 7.905, "SpawnChangeling", OVERSEER_2)]
    assert OVERSEER_1 not in t.energyHistory
    assert lines == []


def test_a_queen_with_exactly_the_cost_fits_and_is_charged_to_zero():
    """QA-2 (c), QA-8 (E3): 25.0 fits (at least the cost)."""
    queen = unit(QUEEN_1, "Queen", Z, done="01:00")
    t = tracker((queen, "01:00"))

    lines = cast(t, "01.00", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva", player=Z)

    assert history(t, queen) == [("01:00", 25, "", QUEEN_1), ("01.00", 0, "SpawnLarva", QUEEN_1)]
    assert lines == []


def test_only_the_commanding_players_own_units_are_candidates():
    """QA-2 (d): the opponent's two able Queens are never considered."""
    mine = unit(QUEEN_1, "Queen", Z, done="01:00")
    theirs = [unit(QUEEN_P1, "Queen", P, done="00:30"), unit(QUEEN_P2, "Queen", P, done="00:30")]
    t = tracker((mine, "01:00"), (theirs[0], "00:30"), (theirs[1], "00:30"))

    lines = cast(t, "01.20", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva", player=Z)

    assert history(t, mine)[-1] == ("01.20", 15.81, "SpawnLarva", QUEEN_1)
    assert [history(t, q) for q in theirs] == [[("00:30", 25, "", QUEEN_P1)], [("00:30", 25, "", QUEEN_P2)]]
    assert lines == []


@pytest.mark.parametrize(
    "other",
    [
        pytest.param({"done": "00:30", "died": "01:10"}, id="died before the cast (its record stays)"),
        pytest.param({"done": "00:30", "died": "01:20"}, id="died at the cast second"),
        pytest.param({"done": "01:21"}, id="done after the cast"),
        pytest.param({"done": None}, id="never done"),
    ],
)
def test_a_dead_or_unfinished_queen_is_never_a_candidate(other):
    """QA-2 (e), QA-8 (E1, E2): with the able Queen, only it counts; no line."""
    able = unit(QUEEN_1, "Queen", Z, done="01:00")
    ghost = unit(QUEEN_2, "Queen", Z, **other)
    t = tracker((able, "01:00"), (ghost, "00:30"))

    lines = cast(t, "01.20", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva", player=Z)

    assert history(t, able)[-1] == ("01.20", 15.81, "SpawnLarva", QUEEN_1)
    assert history(t, ghost) == [("00:30", 25, "", QUEEN_2)]
    assert lines == []


def test_a_chrono_boost_with_a_lone_probe_is_charged_to_the_one_nexus():
    """QA-8 (E4): ChronoBoostEnergyCost (50) with a lone Probe selected."""
    nexus = unit(NEXUS_1, "Nexus", Z, done="00:00")
    t = tracker((nexus, "00:00"))

    lines = cast(t, "00.20", [unit(PROBE, "Probe", Z)], "ChronoBoostEnergyCost", player=Z)

    # 50 at 00:00, + 20 s x 0.7905 = 65.81, - 50
    assert history(t, nexus) == [("00:00", 50, "", NEXUS_1), ("00.20", 15.81, "ChronoBoostEnergyCost", NEXUS_1)]
    assert lines == []


# --- AC3: a cast that would stop today and that no single unit fits is kept, charged to no one, and logged -----------


def _no_fit(case):
    """The tracker, the registered units and the expected line's reason for each QA-3 case (cast at 01.25)."""
    if case == "none has enough":  # QA-3 (a), QA-8 (E3): 0 at 01:00, + 25 s x 0.7905 = 19.7625 < 25
        queen = unit(QUEEN_1, "Queen", Z, done="01:00")
        t = tracker((queen, "01:00"))
        cast(t, "01.00", [queen], "SpawnLarva")
        return t, "no own Queen with 25 energy"
    if case == "none of that type":  # QA-3 (b), QA-8 (E6): only the opponent has a Queen
        return tracker((unit(QUEEN_P1, "Queen", P, done="00:30"), "00:30")), "no own Queen with 25 energy"
    if case == "only a dead one":  # QA-3 (c), QA-8 (E1)
        return tracker((unit(QUEEN_1, "Queen", Z, done="00:30", died="01:00"), "00:30")), "no own Queen with 25 energy"
    if case == "only an unfinished one":  # QA-3 (c), QA-8 (E2)
        return tracker((unit(QUEEN_1, "Queen", Z, done="01:30"), "00:30")), "no own Queen with 25 energy"
    if case == "two fit":  # QA-3 (d): 25 + 25 s x 0.7905 = 44.7625 and 25 + 55 s x 0.7905 = 68.4775
        t = tracker((unit(QUEEN_1, "Queen", Z, done="01:00"), "01:00"), (unit(QUEEN_2, "Queen", Z, done="00:30"), "00:30"))
        return t, "2 own Queen with 25 energy"
    raise AssertionError(case)


NO_FIT = ["none has enough", "none of that type", "only a dead one", "only an unfinished one", "two fit"]


@pytest.mark.parametrize("case", NO_FIT)
def test_a_cast_no_single_unit_fits_charges_no_one_and_writes_one_line(case):
    """QA-3 (a)-(d): every history unchanged, nothing for the selected unit, no excess change, exactly one line."""
    t, reason = _no_fit(case)
    before = (histories(t), excess(t))

    lines = cast(t, "01.25", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva", player=Z)

    assert (histories(t), excess(t)) == before
    assert RAVAGER not in t.energyHistory
    assert lines == [f"energy check: 01.25 SpawnLarva: selected Ravager [4E00001]: data doesn't match ({reason})"]


def test_two_queens_of_which_one_fits_is_ac2():
    """QA-3 (e): Queens at 19.7625 and 68.4775 energy: the able one is charged, no line."""
    low = unit(QUEEN_1, "Queen", Z, done="01:00")
    able = unit(QUEEN_2, "Queen", Z, done="00:30")
    t = tracker((low, "01:00"), (able, "00:30"))
    cast(t, "01.00", [low], "SpawnLarva")

    lines = cast(t, "01.25", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva", player=Z)

    assert history(t, low) == [("01:00", 25, "", QUEEN_1), ("01.00", 0, "SpawnLarva", QUEEN_1)]
    assert history(t, able) == [("00:30", 25, "", QUEEN_2), ("01.25", 43.4775, "SpawnLarva", QUEEN_2)]
    assert lines == []


def test_the_line_names_the_selected_unit_by_type_and_hex_id_the_spores_case():
    """The line's form on spores' lone Lair (L1): no player name, the unit as ``Type [hex id]``."""
    t = tracker((unit(QUEEN_1, "Queen", Z, done="01:00"), "01:00"), (unit(QUEEN_2, "Queen", Z, done="00:30"), "00:30"))

    lines = cast(t, "13.47", [unit(LAIR, "Lair", Z)], "SpawnLarva", player=Z)

    assert lines == ["energy check: 13.47 SpawnLarva: selected Lair [7100002]: data doesn't match (2 own Queen with 25 energy)"]


def test_a_cast_before_any_caster_exists_is_logged():
    """QA-8 (E8): a cast at 00:01 before any Queen exists."""
    t = tracker((unit(NEXUS_1, "Nexus", Z, done="00:00"), "00:00"))

    lines = cast(t, "00.01", [unit(DRONE, "Drone", Z)], "SpawnLarva", player=Z)

    assert lines == [
        "energy check: 00.01 SpawnLarva: selected Drone [16C0001]: data doesn't match (no own Queen with 25 energy)"
    ]


def test_a_chrono_boost_with_a_lone_probe_and_two_able_nexuses_is_logged():
    """QA-8 (E4): two able Nexuses: several fit."""
    t = tracker((unit(NEXUS_1, "Nexus", Z), "00:00"), (unit(NEXUS_2, "Nexus", Z, done="00:10"), "00:10"))

    lines = cast(t, "01.00", [unit(PROBE, "Probe", Z)], "ChronoBoostEnergyCost", player=Z)

    assert lines == [
        "energy check: 01.00 ChronoBoostEnergyCost: selected Probe [1400001]: data doesn't match (2 own Nexus with 50 energy)"
    ]
    assert histories(t) == {NEXUS_1: [("00:00", 50, "")], NEXUS_2: [("00:10", 50, "")]}


def test_a_call_without_the_player_charges_no_ones_unit():
    """Morgan's P3-7: ``player`` is a new keyword; without it the search has no own unit, so it charges nothing."""
    t = tracker((unit(QUEEN_1, "Queen", Z, done="01:00"), "01:00"))

    lines = cast(t, "01.20", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva")

    assert histories(t) == {QUEEN_1: [("01:00", 25, "")]}
    assert lines == [
        "energy check: 01.20 SpawnLarva: selected Ravager [4E00001]: data doesn't match (no own Queen with 25 energy)"
    ]


def test_the_bug_faithful_run_still_stops_where_the_fork_did():
    """E1 is off for ``fixes=()``: the lone pick without a record still raises, as the legacy code does (L1)."""
    t = tracker((unit(QUEEN_1, "Queen", Z, done="01:00"), "01:00"), fixes=FAITHFUL)
    with pytest.raises(KeyError, match="81788929"):
        cast(t, "01.20", [unit(RAVAGER, "Ravager", Z)], "SpawnLarva")


# --- AC4: casts that don't stop the build today are handled exactly as today -----------------------------------------


@pytest.mark.parametrize("fixes", [WITH_E1, FAITHFUL], ids=["E1", "faithful"])
def test_a_lone_queen_with_a_record_is_charged_and_nothing_is_searched(fixes):
    """QA-4 (a): two more able Queens are never touched."""
    queen = unit(QUEEN_1, "Queen", Z, done="01:00")
    others = [unit(QUEEN_2, "Queen", Z, done="00:30"), unit(QUEEN_3, "Queen", Z, done="00:30")]
    t = tracker((queen, "01:00"), (others[0], "00:30"), (others[1], "00:30"), fixes=fixes)

    lines = cast(t, "01.20", [queen], "SpawnLarva")

    assert history(t, queen)[-1] == ("01.20", 15.81, "SpawnLarva", QUEEN_1)
    assert [len(history(t, q)) for q in others] == [1, 1]
    assert lines == []


@pytest.mark.parametrize("fixes", [WITH_E1, FAITHFUL], ids=["E1", "faithful"])
def test_a_lone_unit_of_the_wrong_type_with_a_record_is_charged_as_today(fixes):
    """QA-4 (b), QA-8 (E4): a Sentry selected for a Chrono Boost is charged, though the Nexus could fit."""
    sentry = unit(67108865, "Sentry", Z, done="01:00")
    nexus = unit(NEXUS_1, "Nexus", Z)
    t = tracker((nexus, "00:00"), (sentry, "01:00"), fixes=fixes)

    lines = cast(t, "01.00", [sentry], "ChronoBoostEnergyCost")

    assert history(t, sentry) == [("01:00", 50, "", 67108865), ("01.00", 0, "ChronoBoostEnergyCost", 67108865)]
    assert history(t, nexus) == [("00:00", 50, "", NEXUS_1)]
    assert lines == []


@pytest.mark.parametrize("fixes", [WITH_E1, FAITHFUL], ids=["E1", "faithful"])
def test_a_lone_queen_with_too_little_energy_goes_below_zero_as_today(fixes):
    """QA-4 (c): 0 at 01.00, + 10 s x 0.7905 = 7.905, - 25 = -17.095; no search, no line."""
    queen = unit(QUEEN_1, "Queen", Z, done="01:00")
    able = unit(QUEEN_2, "Queen", Z, done="00:30")
    t = tracker((queen, "01:00"), (able, "00:30"), fixes=fixes)
    cast(t, "01.00", [queen], "SpawnLarva")

    lines = cast(t, "01.10", [queen], "SpawnLarva")

    assert history(t, queen)[-1] == ("01.10", -17.095, "SpawnLarva", QUEEN_1)
    assert history(t, able) == [("00:30", 25, "", QUEEN_2)]
    assert lines == []


@pytest.mark.parametrize("fixes", [WITH_E1, FAITHFUL], ids=["E1", "faithful"])
def test_several_selected_take_the_first_that_qualifies_as_today(fixes):
    """QA-4 (d), QA-8 (E9): the first done unit with a record and enough, not the one with the most energy."""
    first = unit(QUEEN_1, "Queen", Z, done="00:50")  # 25 + 30 s x 0.7905 = 48.715 at 01.20
    richer = unit(QUEEN_2, "Queen", Z, done="00:10")  # 25 + 70 s x 0.7905 = 80.335
    t = tracker((first, "00:50"), (richer, "00:10"), fixes=fixes)

    lines = cast(t, "01.20", [first, richer], "SpawnLarva")

    assert history(t, first)[-1] == ("01.20", 23.715, "SpawnLarva", QUEEN_1)
    assert history(t, richer) == [("00:10", 25, "", QUEEN_2)]
    assert lines == []


@pytest.mark.parametrize("fixes", [WITH_E1, FAITHFUL], ids=["E1", "faithful"])
def test_several_selected_of_which_none_qualifies_charge_none_with_todays_line(fixes):
    """QA-4 (e): a Drone (no record) and a Queen with 7.905: today's 'No unit found' line, no new line."""
    queen = unit(QUEEN_1, "Queen", Z, done="01:00")
    able = unit(QUEEN_2, "Queen", Z, done="00:30")
    t = tracker((queen, "01:00"), (able, "00:30"), fixes=fixes)
    cast(t, "01.00", [queen], "SpawnLarva")
    before = histories(t)

    lines = cast(t, "01.10", [unit(DRONE, "Drone", Z), queen], "SpawnLarva")

    assert histories(t) == before
    assert len(lines) == 1 and lines[0].startswith("No unit found 01.10 [") and lines[0].endswith("] SpawnLarva")
    assert "data doesn't match" not in lines[0]


# --- AC5: spellcasters with no threshold get no spare-energy check ---------------------------------------------------

#: Each type, an ability of it and the energy left; the caster is registered at 01:00 with 50 and casts at 02.40:
#: 50 + 100 s x 0.7905 = 129.05, less the cost (50; FungalGrowth 75).
NO_THRESHOLD = {
    "Sentry": ("ForceField", 79.05),
    "Oracle": ("StasisWard", 79.05),
    "Infestor": ("FungalGrowth", 54.05),
    "HighTemplar": ("Feedback", 79.05),
    "Overseer": ("SpawnChangeling", 79.05),
}
CASTER = 74448897


def _with_running_period():
    """Z's Nexus opens a spare-energy period: a Chrono Boost at 00.00 leaves it 0; at 02.30 it has 150 s x 0.7905 =
    118.575, over its threshold (50 up to 3:00), and the Chrono Boost then leaves 68.575, still over, so the period
    runs on."""
    nexus = unit(NEXUS_1, "Nexus", Z)
    t = tracker((nexus, "00:00"))
    cast(t, "00.00", [nexus], "ChronoBoostEnergyCost")
    cast(t, "02.30", [nexus], "ChronoBoostEnergyCost")
    assert [(n.unitName, n.end) for n in t.excessEnergy[Z]] == [("Nexus", None)]
    return t


@pytest.mark.parametrize("name", sorted(NO_THRESHOLD))
def test_a_no_threshold_cast_with_no_period_running_is_charged_and_makes_no_node(name):
    """QA-5 (a)."""
    ability, left = NO_THRESHOLD[name]
    caster = unit(CASTER, name, Z, done="01:00")
    t = tracker((caster, "01:00"))

    lines = cast(t, "02.40", [caster], ability)

    assert history(t, caster) == [("01:00", 50, "", CASTER), ("02.40", left, ability, CASTER)]
    assert excess(t) == {1: [], 2: []}
    assert lines == []


@pytest.mark.parametrize("name", sorted(NO_THRESHOLD))
def test_a_no_threshold_cast_while_a_period_runs_leaves_it_running(name):
    """QA-5 (b), QA-8 (E10), Q-F answered (a) by Stefan's D1a: before E1, ``KeyError`` naming the type in
    ``getThreshold``."""
    ability, left = NO_THRESHOLD[name]
    t = _with_running_period()
    caster = unit(CASTER, name, Z, done="01:00")
    t.registerEnergyUnit(caster, "01:00")
    before = excess(t)

    lines = cast(t, "02.40", [caster], ability)

    assert history(t, caster) == [("01:00", 50, "", CASTER), ("02.40", left, ability, CASTER)]
    assert excess(t) == before
    assert [n.unitName for p in t.excessEnergy for n in t.excessEnergy[p]] == ["Nexus"]
    assert lines == []


def test_the_bug_faithful_run_still_asks_the_threshold():
    """E1 is off for ``fixes=()``: the no-threshold cast while a period runs still raises, as the legacy code does."""
    nexus = unit(NEXUS_1, "Nexus", Z)
    t = tracker((nexus, "00:00"), fixes=FAITHFUL)
    cast(t, "00.00", [nexus], "ChronoBoostEnergyCost")
    cast(t, "02.30", [nexus], "ChronoBoostEnergyCost")
    assert [(n.unitName, n.end) for n in t.excessEnergy[Z]] == [("Nexus", None)]
    caster = unit(CASTER, "Infestor", Z, done="01:00")
    t.registerEnergyUnit(caster, "01:00")
    with pytest.raises(KeyError, match="Infestor"):
        cast(t, "02.40", [caster], "FungalGrowth")


def test_a_cast_with_a_threshold_still_ends_the_running_period():
    """The energy rule for the types that have a threshold is unchanged: Z's Queen at 02.40 ends the Nexus's period,
    since her energy after the cast is at or below her threshold (25 up to 3:00): 25 + 10 s x 0.7905 - 25 = 7.905."""
    t = _with_running_period()
    queen = unit(QUEEN_1, "Queen", Z, done="02:30")
    t.registerEnergyUnit(queen, "02:30")

    cast(t, "02.40", [queen], "SpawnLarva")

    assert [(n.unitName, n.end) for n in t.excessEnergy[Z]] == [("Nexus", "00:02:40")]


# --- AC1: Stefan's recent games get past the energy step (his replays, read in place; every gate on this Mac) ------


def _root():
    d = pathlib.Path(__file__).resolve().parents[2]
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
RECENT = MS_SC / "cr-074-recent"
GUARD = pathlib.Path(__file__).resolve().parents[1] / "network_guard.py"

#: The 45 of the description's 47 whose first failure at 6315553 is the energy check: 36 on a unit with no energy
#: record, 9 on a type with no threshold. Lockdown LE (103) and Washout LE (107) are held up by CR-080 (a control
#: group's unit list that only grows) once the energy step passes, and are not built here.
RECENT_45 = {
    "At Eternity's Edge LE (102)": "376d61287aff36acb9b99b8b4e579776f84bfdcdcdc9a6932726576085a5d57a",
    "Blackrock LE (86)": "efeeba5274c38cf4e57b2ec87d4c77bcef54692d6e9313b3c42ead9e7c271c75",
    "Blackrock LE (92)": "e3355f311c7279fcefd9d84410b4ac991cfbd1dad3ccb62d85017d1dfa7384bb",
    "Blackrock LE (96)": "52f0962e5af018739ed0d9eb59606d99e20288a0734515f720033e7cb705450f",
    "Fear and Faith LE (45)": "55f2ae1de8507e9471685228055a8aa58801843c56ff249aa4e49fa042bc3b25",
    "Lockdown LE (101)": "a33e972d73c7a5687839855a35fa28e2df90508280d1072c0f1011461ad84301",
    "Lockdown LE (107)": "87f9e4bc37647f75c39c122152fb824bb793e1fafad2c45550c428eab9dfe7ae",
    "Lockdown LE (108)": "a631bbc1a4534a397f279dbc1530c0e46d1d0ac1dc4c7c29c7840cd22a224e25",
    "Lockdown LE (98)": "3df1024b7bea81acdf50a613d4a1f71217f5b553eeb23907f3506a6aa5e118b8",
    "Lockdown LE (99)": "7baa26703fd159fb3c414300ea2f984893a403878f2fc9bbf19ab1c3dad9ed2b",
    "Old Sun Temple LE (74)": "afb107fb7e9f6acfc467ebb8f0d9f0093ea3b03ac9441e6521cf767f6293e591",
    "Old Sun Temple LE (75)": "478820026ba2dbc49e8b1ef669c53a090bb4e5d2a0cbec15b456d764208d7a6f",
    "Rainfall LE (103)": "70b436fecd8733473afb26b61f725bd137173181223d0ee1456278cb9ffe42e5",
    "Rainfall LE (106)": "dadeecdc773987da57301f8675f1125af8fc50adb1a30884625c1267d70720bd",
    "Rainfall LE (93)": "974b43e32b12edb5a10449ef186f65a3c582b96ac00ec5efd2b12a9d75ccc51c",
    "Rainfall LE (94)": "7c3edaedb52d87496f66628d94c43e96c6e8e4c50d7c0f07ee96b5f2bf477448",
    "Rainfall LE (95)": "c8672ce61f390ee8589b2462abc199def2a3e47dcc4ee10be9367cf62a25709a",
    "Rorschach LE (100)": "80d01a964cd04cbd12a7e26d85dcb6ad9a575956ae1bdf98e6ab2bcec4f9e485",
    "Rorschach LE (102)": "9dd353282b7863d6a25f1560c0d726a448233ea44bcc1ab9f7bec4510360f6a3",
    "Rorschach LE (103)": "7d0fd345f43f055b0d938d6cc2f77e157033d15828fa6c485eca29c83ab620d6",
    "Rorschach LE (104)": "96363badd821a9bc9aa4ba8abd2a1da3a996745275a442ae5d58032751846e7b",
    "Rorschach LE (105)": "75321efd23f758cd13d7fb35cf3c860789eb729aa73be7f34fa92382cb00964a",
    "Rorschach LE (107)": "e9446f980a85023f6b445d5d3022f73da6700de56eccadc85c351c11dde77180",
    "Rorschach LE (96)": "0f6a0c603f1d80294d98e2cf8d0e9f39f421b1927fa8cbb66e8b6739c14ae30d",
    "Rorschach LE (99)": "4e8e86159af1861e8ce180e3c09782e61acba5a285146abbaff7e94e35e66538",
    "Sanctuary III LE (102)": "4dba3dae0736d18d2377e924fbb00828dfc3e732822b6e0c1572c39681fc6e07",
    "Sanctuary III LE (103)": "b3ce96666fec1ef4b81dccb43cd2f694459f0042fce60a18d7df0dda2d6634de",
    "Sanctuary III LE (104)": "6f22555898137ed06ad3f6de49f42f38040f07997e591a02063f8537bd4bb38d",
    "Sanctuary III LE (91)": "233842ffdca4418153d490bc4ffa40f991b57f1e2df809f8e12ee16ae1b9ca8a",
    "Sanctuary III LE (92)": "8ab9902a00f67b11a295859feddd571f2cc6ea30df452ca2c49b752cc51aa459",
    "Sanctuary III LE (94)": "3294f0bbbd59d3f019ba4dba12131fb2bd7923f6aee3645183ce9c5d332204aa",
    "Sanctuary III LE (95)": "fb592a461caa90b96f6942caafcb4c770b2faee22678beae1a6d8b64d59d2901",
    "Sanctuary III LE (97)": "33e1b4b8b216f5b5b542ef547a96d8c70d62742b0d39beb48db04ef1929d2d84",
    "Sanctuary III LE (99)": "9441a06123d47f6251ce9c0bea44a40d9e46893d72ab524a54b4b695c79f827d",
    "Washout LE (104)": "fdc83befe09513d86b7748b1c078c713253e8c1f395bfc4dca4b304b0837fef6",
    "Washout LE (106)": "45980ad5ab08f0a3fb9512c38a8b0a522b06864d080ae41347963a4b1d4e1787",
    "At Eternity's Edge LE (104)": "579a1ee430ec3d6ee6eb3a4d9cffa4d5f4c707a3b17973eb8ad71e1cd882f449",
    "At Eternity's Edge LE (106)": "bead54e6e9e954fdae5bbdfd7fb263cb7969c629b7837d13349882552c6b9d4d",
    "Blackrock LE (90)": "f183436ac3e42cfcbce67c0fe46a728fa57f9dec2af89b6df473b70ff042e965",
    "Blackrock LE (91)": "186f8f4bcfc215fa00dd214783db9b0438e0cadda7af2f7a49572eba42990ca9",
    "Blackrock LE (93)": "7235adcc7ae4ef2abd9a70fc04bdf878786c3b9ec9bc7f31a87ea066673fba60",
    "Rainfall LE (100)": "452b3c4baf2b62fcbfc5c1999be211a20c48907961b3586673481fe323da5147",
    "Rorschach LE (110)": "0dd573c6bb2607054064bcfba38b6e62e4e3922c0591c772203553a5b67f9902",
    "Rorschach LE (98)": "7c2b49068cb6e84b4308c8933da8fe04487adf454507c5147e97e366ec808f0b",
    "Washout LE (105)": "5111526e386359cdb71b9e9cf2c7a93ac86c39b81da609005b09de1da8f19228",
}
#: Built by CR-080's AC4 test (``tests/analysis/test_control_groups.py``), under its tighter bounds.
NOT_BUILT = ("Lockdown LE (103)", "Washout LE (107)", "At Eternity's Edge LE (109)")

#: Lockdown LE (101) and Washout LE (105) were pinned as stopped at the cap by CR-080's defect (control-group lists
#: that only grew); CR-080 (layer fix CG1) flipped that pin (QA-13): they finish under the same limits, and reach the
#: last energy cast that CR-076 measured when they were built to the end outside the gate.
LAST_CAST = {"Lockdown LE (101)": "23.08 FungalGrowth", "Washout LE (105)": "13.11 PsionicStorm"}

#: The games peak at 70-600 MiB and finish within 12 s here (2026-11-09), so 1 GiB and 60 s leave room and still
#: catch a growth like CR-080's defect within seconds.
WALL_S = 60
RSS_KIB = 1024 * 1024  # 1 GiB of resident memory
POLL_S = 0.05  # how often the child's memory is read; a fast-growing child is killed within one interval
ENERGY_STEP = {"getEnergyAtTime", "getThreshold", "processEnergyEvent", "findRealCaster"}

#: The child: analyse one replay with the default fixes, its prints captured as the CLI captures them for
#: graph.log, the network guard on; one JSON line on stdout. Each energy cast the check reaches is streamed to the
#: casts file (time and ability, flushed), so a child killed at a limit still tells the last cast it reached.
CHILD = """
import contextlib, importlib.util, io, json, socket, sys, traceback
replay, support, guard_path, casts_path = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("sc2ms_network_guard", guard_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
socket.socket.connect = guard._guarded_connect
socket.socket.connect_ex = guard._guarded_connect_ex
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.detectors.detectors import EnergyTracker
from sc2mindshare.reader.loader import load_replay
casts = open(casts_path, "w", encoding="utf-8")
process = EnergyTracker.processEnergyEvent
def streamed(self, time, units, abilityName, *args, **kwargs):
    casts.write(f"{time} {abilityName}\\n")
    casts.flush()
    return process(self, time, units, abilityName, *args, **kwargs)
EnergyTracker.processEnergyEvent = streamed
log = io.StringIO()
record = {"result": "finished"}
try:
    with contextlib.redirect_stdout(log):
        analyse(load_replay(replay), support)
except Exception as exc:
    frames = traceback.extract_tb(exc.__traceback__)
    record = {"result": "failed", "error": f"{type(exc).__name__}: {exc}", "frames": [f.name for f in frames]}
lines = log.getvalue().splitlines()
record["mismatch"] = [x for x in lines if "data doesn't match" in x]
record["error_unit"] = [x for x in lines if x.startswith("ERROR unit:")]
sys.stdout.write(json.dumps(record))
"""


def _rss_kib(pid):
    out = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, check=False).stdout
    return int(out.strip() or 0)


def run_bounded(replay, out_dir, *, wall_s=WALL_S, rss_kib=RSS_KIB):
    """Analyse ``replay`` in a child process in its own process group; the whole group is killed when it runs past
    ``wall_s`` seconds or its resident memory passes ``rss_kib`` KiB. Returns the child's record, or
    ``{"result": "stopped", "limit": "wall" | "memory"}``, with ``seconds``, ``peak_kib``, and ``casts`` and
    ``last_cast`` (the energy casts the check reached, and the last of them as ``"MM.SS Ability"``)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout, stderr, casts = out_dir / "child.json", out_dir / "child.err", out_dir / "casts.txt"
    start = time.monotonic()
    peak = 0
    limit = None
    with stdout.open("w") as out, stderr.open("w") as err:
        child = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", CHILD, str(replay), str(MS_SC), str(GUARD), str(casts)],
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        try:
            while child.poll() is None:
                if time.monotonic() - start > wall_s:
                    limit = "wall"
                    break
                peak = max(peak, _rss_kib(child.pid))
                if peak > rss_kib:
                    limit = "memory"
                    break
                time.sleep(POLL_S)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    reached = casts.read_text(encoding="utf-8").splitlines() if casts.exists() else []
    stats = {"seconds": round(time.monotonic() - start, 1), "peak_kib": peak, "casts": len(reached)}
    stats["last_cast"] = reached[-1] if reached else None
    if limit is not None:
        return {"result": "stopped", "limit": limit, **stats}
    text = stdout.read_text(encoding="utf-8")
    assert text, f"the child wrote nothing (exit {child.returncode}): {stderr.read_text(encoding='utf-8')[-2000:]}"
    return {**json.loads(text), **stats}


def _need_recent(name):
    path = RECENT / f"{name}.SC2Replay"
    if not path.exists():
        message = f"{name} not found: {path}"
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"{message} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(message)
    return path


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_45_are_the_manifests_files():
    """The literal SHA-256s are the manifest's (Stefan's ``manifest.csv``, read for the two columns only)."""
    manifest = RECENT / "manifest.csv"
    if not manifest.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"{manifest} not found (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"{manifest} not found")
    with manifest.open(encoding="utf-8", newline="") as f:
        listed = {row["file"].removesuffix(".SC2Replay"): row["sha256"] for row in csv.DictReader(f)}
    assert {name: listed.get(name) for name in RECENT_45} == RECENT_45
    assert len(RECENT_45) == 45 and not set(NOT_BUILT) & set(RECENT_45)


@pytest.mark.parametrize("name", sorted(RECENT_45))
def test_a_recent_game_gets_past_the_energy_step(name, tmp_path):
    """AC1 (QA-1): the game builds, under 1 GiB and 60 s, without an error in the energy step and without an
    ``ERROR unit:`` line; at 6315553 each of them stopped there. The 'data doesn't match' lines are counted for the
    record (QA-10). Runs in every gate on this Mac (``SC2MS_REQUIRE_GOLDEN=1``); skipped elsewhere when the replays
    are absent."""
    path = _need_recent(name)
    assert _sha256(path) == RECENT_45[name], f"{name} changed"

    record = run_bounded(path, tmp_path)

    lines = len(record.get("mismatch", []))
    print(f"{name}: {record['result']} in {record['seconds']} s, peak {record['peak_kib'] // 1024} MiB, {lines} lines")
    assert not ENERGY_STEP & set(record.get("frames", ())), record  # no error in the energy step
    assert record["result"] == "finished", record  # nor later: each of the 45 builds to the end (no later failure)
    assert record["error_unit"] == []
    if name in LAST_CAST:  # CR-080, QA-13
        assert record["last_cast"] == LAST_CAST[name]


def test_the_bounded_run_kills_the_child_at_its_limits(tmp_path):
    """The limits work: a normal game (Alcyone) stopped by a 1 s wall limit, then by a 50 MiB memory cap, and its
    process group is gone."""
    path = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"{path} not found (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"{path} not found")

    wall = run_bounded(path, tmp_path / "wall", wall_s=1)
    memory = run_bounded(path, tmp_path / "memory", rss_kib=50 * 1024)

    assert (wall["result"], wall["limit"]) == ("stopped", "wall")
    assert wall["seconds"] < 5
    assert (memory["result"], memory["limit"]) == ("stopped", "memory")
    assert memory["peak_kib"] > 50 * 1024
