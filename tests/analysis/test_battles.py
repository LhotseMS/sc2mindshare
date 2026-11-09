"""CR-079 (layer fix BT1): every game's last battle is a Battle node, and a battle in the first 3 seconds is kept.

``BattleDetector.findBattles`` closes a battle only when it meets a gap of more than 4 s between death seconds, and
nothing closed the last open group; it also drops its first battle as the empty placeholder it makes only when the
first death second is above 3, so a real battle whose first deaths fall at 0-3 s was dropped. Under BT1 the last
group is closed by the same rule (Stefan's D1a: it ends at its last death), and in the 0-3 s case the same
placeholder is made first, so the placeholder is always what is dropped (numbering from Battle-1, the same links).

The synthetic tests run ``findBattles`` on a bare detector with the deaths by second given (``sortDeaths`` replaced)
and recorders in place of ``BattleNode``, ``BattleLink`` and ``AbilityBattleLink``: each recorded battle that holds
seconds of dying brings one harassment node and one ability, as a real battle can. Expected battles are written by
hand from the rule: (start, end, number). They fail on the commit before BT1 (ba543b3). The replay test builds
Stefan's one-battle game, read in place by SHA-256 (every gate on this Mac; skipped elsewhere when absent).
"""

import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
from types import SimpleNamespace

import pytest

from sc2mindshare import cli
from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.detectors.detectors import BattleDetector

BT1 = frozenset({"BT1"})
FAITHFUL = frozenset()


class RecordedBattle:
    def __init__(self, player1, player2, start, end, events, seconds, seq, ctx):
        self.span = (start, end, seq)
        self.harrasmentNodes = [SimpleNamespace(battle=self)] if seconds else []
        self.allAbilities = [SimpleNamespace(abilityNode=SimpleNamespace(battle=self))] if seconds else []

    def getCountableDeaths(self):
        return []


class RecordedLink:
    def __init__(self, n1, n2):
        self.n1, self.n2 = n1, n2


def found(death_seconds, fixes, monkeypatch):
    """(battles as (start, end, number), battle links as number pairs, the detector) for one death per second."""
    monkeypatch.setattr(detectors, "BattleNode", RecordedBattle)
    monkeypatch.setattr(detectors, "BattleLink", RecordedLink)
    monkeypatch.setattr(detectors, "AbilityBattleLink", RecordedLink)
    d = BattleDetector.__new__(BattleDetector)
    d.replay = SimpleNamespace(events=[])
    d.ctx = SimpleNamespace(fixes=fixes)
    d.player1 = d.player2 = None
    d.currentSecond = 0
    d.battleStart = 0
    d.resetBuffers()
    d.previousSecond = -1
    d.battles, d.harrasmentNodes, d.unitLinks, d.battleLinks, d.abilityLinks = [], [], [], [], []
    d.deathsByTime = {s: [SimpleNamespace(unit=None)] for s in death_seconds}
    d.sortDeaths = lambda: None
    d.findBattles()
    battles = [b.span for b in d.battles]
    links = [(lk.n1.span[2], lk.n2.span[2]) for lk in d.battleLinks]
    return battles, links, d


# --- AC1, AC2: the last battle ---------------------------------------------------------------------------------------


def test_the_last_battle_is_closed():
    """AC1: two groups after 0:03 give both battles, the second ending at its last death, and their link."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([10, 11, 30, 31], BT1, mp)[:2] == ([(10, 11, 1), (30, 31, 2)], [(1, 2)])


def test_three_groups_give_three_battles_and_two_links():
    with pytest.MonkeyPatch.context() as mp:
        assert found([10, 30, 60], BT1, mp)[:2] == ([(10, 10, 1), (30, 30, 2), (60, 60, 3)], [(1, 2), (2, 3)])


def test_a_game_with_one_battle_shows_it():
    """AC2 (synthetic): one group, one battle, no link."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([10, 11], BT1, mp)[:2] == ([(10, 11, 1)], [])


def test_no_death_still_gives_no_battle():
    """CR-077's case, with BT1 on."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([], BT1, mp)[:2] == ([], [])


# --- AC3: a battle in the first 3 seconds -----------------------------------------------------------------------------


@pytest.mark.parametrize("first", [2, 3])
def test_a_battle_whose_first_deaths_fall_in_the_first_3_seconds_is_kept(first):
    """AC3: no placeholder is made at 0-3 s, so the forced one is; the real battle is Battle-1, as in any game."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([first, 60], BT1, mp)[:2] == ([(first, first, 1), (60, 60, 2)], [(1, 2)])


def test_a_first_death_at_4_s_takes_the_natural_placeholder_with_the_same_result():
    """AC3's other side: from 4 s the loop makes the placeholder itself; no extra empty battle appears."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([4, 60], BT1, mp)[:2] == ([(4, 4, 1), (60, 60, 2)], [(1, 2)])


def test_a_first_death_at_second_0_keeps_todays_start():
    """Out of scope (Morgan's finding 5, Vera's G2): a start of 0 reads as "not set", so the battle starts at the next
    death second (1); the battle itself is kept."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([0, 1, 60], BT1, mp)[:2] == ([(1, 1, 1), (60, 60, 2)], [(1, 2)])


def test_a_first_death_at_second_0_then_a_gap_gives_an_inverted_battle_as_today():
    """Characterisation (Rex's F1 on CR-079), expected values from his hand trace of the loop, not from a build.
    Out of Scope: "a start of 0 reads as not set". With deaths at 0 s and 10 s, ``battleStart`` stays 0 at the first
    second and becomes 10 at the next, where the gap closes a battle from 10 to 0: under BT1 it is kept as Battle-1
    (start 10, end 0; its battle window would read ``0:00:08,0:00:02``), then the last group 10-10 is Battle-2. Before
    BT1 that inverted entry was the one ``pop(0)`` dropped. It cannot happen in a real game: no unit dies at 0:00, and
    the first death in Stefan's 100 recent games is at 16 s or later. A later fix of the "start 0" habit flips this
    test on purpose."""
    with pytest.MonkeyPatch.context() as mp:
        assert found([0, 10], BT1, mp)[:2] == ([(10, 0, 1), (10, 10, 2)], [(1, 2)])


@pytest.mark.parametrize("deaths", [[2, 60], [3, 4, 30], [10, 30, 60]])
def test_no_link_or_harassment_node_points_at_a_missing_battle(deaths):
    """AC3, CR-077's review point (c): before BT1 a real battle at 0-3 s was dropped after its links and harassment
    nodes were made, which then pointed at no Battle."""
    with pytest.MonkeyPatch.context() as mp:
        _, _, d = found(deaths, BT1, mp)
    kept = {id(b) for b in d.battles}
    assert all(id(lk.n1) in kept and id(lk.n2) in kept for lk in d.battleLinks)
    assert all(id(lk.n1) in kept for lk in d.abilityLinks)
    assert all(id(h.battle) in kept for h in d.harrasmentNodes)
    assert d.abilityLinks and d.harrasmentNodes


# --- AC5: the bug-faithful run keeps today's battles -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("deaths", "today"),
    [
        ([10, 30, 60], ([(10, 10, 1), (30, 30, 2)], [(1, 2)])),  # the last group is missing
        ([10, 11], ([], [])),  # a one-battle game shows none
        ([2, 60], ([], [])),  # the real first battle is dropped as the placeholder
    ],
)
def test_the_bug_faithful_run_keeps_todays_battles(deaths, today):
    with pytest.MonkeyPatch.context() as mp:
        assert found(deaths, FAITHFUL, mp)[:2] == today


# --- AC2 on a real game: Stefan's one-battle game -----------------------------------------------------------------------


def _root():
    d = pathlib.Path(__file__).resolve().parents[2]
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ONE_BATTLE = MS_SC / "cr-074-recent" / "Rorschach LE (93).SC2Replay"
ONE_BATTLE_SHA256 = "b91b9bfa8e69eab2fe47b87e8e4b887b499a99d472bc95fbb0f5cf1f308589be"


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    return path


def test_rorschach_93_shows_its_one_battle(tmp_path):
    """AC2: Rorschach LE (93), the one game of the 100 recent ones with exactly one battle (01:11), has Battle-1 at
    00:01:08 and its one battle window (Rex's Step 3 probe). Before BT1: no Battle node and no window."""
    replay = _need(ONE_BATTLE)
    assert hashlib.sha256(replay.read_bytes()).hexdigest() == ONE_BATTLE_SHA256
    config = tmp_path / "config"
    config.mkdir()
    for name in ("unitsInfo.csv", "upgradesInfo.csv", "ImageTracking.csv"):
        shutil.copyfile(_need(MS_SC / name), config / name)
    shutil.copyfile(CHECKOUT / "tests" / "golden" / "clock-record-fixture.csv", config / "ClockImageRecord.csv")
    out = tmp_path / "game" / "graph.json"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = cli.main(["build", str(replay), "--out", str(out), "--config-root", str(config)])
    assert code == 0
    battles = [n for n in json.loads(out.read_text(encoding="utf-8"))["nodes"] if n["type"] == "Battle"]
    assert [(n["ID"], n["properties"]["time"]) for n in battles] == [("Battle-1", "00:01:08")]
    assert battles[0]["name"].startswith("Probe killed Nexus near ")
    assert (out.parent / "Intervals.csv").read_text(encoding="utf-8") == "start,end,id\n0:01:06,0:01:10,Battle-1\n"
