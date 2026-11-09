"""CR-077: a game with no battle gets past the battle finder (Stefan's D4a).

``BattleDetector.findBattles`` ends by dropping the empty "battle" its loop appends at the first death after 0:03
(``self.battles.pop(0)``). In a game with no countable death, or with deaths only at 0:00-0:03, nothing was
appended and the pop raised ``IndexError: pop from empty list``. The guard drops the first entry only when there is
one; everything else, the last cluster that is never closed and a real first battle at 0:00-0:03 that is popped
included, is as before (CR-079's).

The synthetic tests run ``findBattles`` on a bare detector with only what it reads: the deaths by second (in place
of ``sortDeaths``) and a recorder in place of ``BattleNode``. Their expected battles are worked out by hand from the
loop's rule (a battle closes when the next death second is more than 4 s after the previous one; the first death
second after 0:03 closes an empty one from it to -1), never taken from the code under test.

The replay tests build Stefan's 9 no-battle games through the CLI, read in place from ``MS SC/cr-074-recent/`` by
SHA-256; they run in every gate on this Mac (``SC2MS_REQUIRE_GOLDEN=1``) and are skipped elsewhere when the replays
are absent. All 9 last 2:35 or less and have no countable death.
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

# --- findBattles on given deaths (E1-E5) -----------------------------------------------------------------------------


class RecordedBattle:
    """Stands in for ``BattleNode``: keeps what the loop gave it, and offers what the loop reads back."""

    def __init__(self, player1, player2, start, end, events, seconds, seq, ctx):
        self.span = (start, end, seq)
        self.harrasmentNodes = []
        self.allAbilities = []

    def getCountableDeaths(self):
        return []


def battles_for(death_seconds, monkeypatch):
    """The battles ``findBattles`` keeps for one death at each of ``death_seconds``, as (start, end, seq)."""
    monkeypatch.setattr(detectors, "BattleNode", RecordedBattle)
    d = BattleDetector.__new__(BattleDetector)
    d.replay = SimpleNamespace(events=[])
    d.ctx = SimpleNamespace(fixes=frozenset())
    d.player1 = d.player2 = None
    d.currentSecond = 0
    d.battleStart = 0
    d.resetBuffers()
    d.previousSecond = -1
    d.battles, d.harrasmentNodes, d.unitLinks, d.battleLinks, d.abilityLinks = [], [], [], [], []
    d.deathsByTime = {s: [SimpleNamespace(unit=None)] for s in death_seconds}
    d.sortDeaths = lambda: None
    d.findBattles()
    return [b.span for b in d.battles]


def test_no_death_gives_no_battle(monkeypatch):
    """E1: before CR-077, ``IndexError: pop from empty list``."""
    assert battles_for([], monkeypatch) == []


def test_deaths_only_in_the_first_three_seconds_give_no_battle(monkeypatch):
    """E2: no empty first battle is made and no gap closes one; before CR-077, ``IndexError``."""
    assert battles_for([1, 2, 3], monkeypatch) == []


def test_one_cluster_after_three_seconds_gives_no_battle_as_today(monkeypatch):
    """E3 (characterisation): the empty battle (10 to -1) is made and dropped; the one cluster is never closed."""
    assert battles_for([10, 11], monkeypatch) == []


def test_a_first_cluster_in_the_first_three_seconds_is_dropped_as_today(monkeypatch):
    """E4 (characterisation): no empty battle is made, so the pop drops the real first one (1 to 2)."""
    assert battles_for([1, 2, 20, 21], monkeypatch) == []


def test_two_clusters_after_three_seconds_give_the_first_as_today(monkeypatch):
    """E5 (characterisation): the empty battle (10 to -1, seq 0) is dropped; 10 to 11 (seq 1) stays."""
    assert battles_for([10, 11, 30, 31], monkeypatch) == [(10, 11, 1)]


# --- AC1, AC2: Stefan's 9 no-battle games build (his replays, read in place; every gate on this Mac) ------------------


def _root():
    d = pathlib.Path(__file__).resolve().parents[2]
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
RECENT = MS_SC / "cr-074-recent"

#: The 9 recent games whose first failure at a5be966 is the battle finder (QA-1's SHA-256s).
NO_BATTLE = {
    "At Eternity's Edge LE (107)": "05ea259f89ad600e74fc5f62446f1f3060f0204acba9202abb6483a7f7e5a0c4",
    "Blackrock LE (87)": "f0252c1c8ab4fb9d649e8871e9a3383e3dcdc47f8676151b9812d46505840b4a",
    "Blackrock LE (88)": "e58944302a046c2688729a0ed2170611562a270d846bb49ae24543c070c4f292",
    "Fear and Faith LE (43)": "c99cfc3d2ecff0fc656f2fbb142de390c205548db556197a5e877faad38ea0cc",
    "Lockdown LE (102)": "3a45d6cd4e2c3d8cbcd79f210b5456bbab1683b3440303d6ac25cdb316e568d3",
    "Lockdown LE (96)": "76bc84cb847149617515ba544c71b9716a3622c350b12f5cb2976afdacb79d22",
    "Rainfall LE (97)": "a0d2323cdd1c8f7a1e44e6a3ea1feaa2a2d699569674ff56d66fe81a18900cd8",
    "Rorschach LE (101)": "c5abaa130e0023e08aac1de77b94cad6de851e91f771b7d4ea387ce3aaaff90e",  # 0:00, no unit dies
    "Rorschach LE (92)": "1af6a90f07d403288f795da565fd5c9a3438a2ee66b200499a79367dd9dd6c58",  # 2:35, the longest
}


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    return path


@pytest.fixture
def config(tmp_path):
    """A config root with the real support tables and the committed clock fixture, as ``tests/test_cli.py`` uses."""
    root = tmp_path / "config"
    root.mkdir()
    for name in ("unitsInfo.csv", "upgradesInfo.csv", "ImageTracking.csv"):
        shutil.copyfile(_need(MS_SC / name), root / name)
    shutil.copyfile(CHECKOUT / "tests" / "golden" / "clock-record-fixture.csv", root / "ClockImageRecord.csv")
    return root


@pytest.mark.parametrize("name", sorted(NO_BATTLE))
def test_a_no_battle_game_builds_a_graph_without_battles(name, tmp_path, config):
    """AC1, AC2 (QA-1, QA-2): the build gets past the battle finder and succeeds; the graph has no Battle node and
    no link to one, and every other kind of node as usual; the battle-window files hold only their header (D4a).
    Before CR-077, ``IndexError: pop from empty list`` in ``findBattles``."""
    replay = _need(RECENT / f"{name}.SC2Replay")
    assert hashlib.sha256(replay.read_bytes()).hexdigest() == NO_BATTLE[name], f"{name} changed"
    out = tmp_path / "game" / "graph.json"

    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(["build", str(replay), "--out", str(out), "--config-root", str(config)])

    assert code == 0, stderr.getvalue()
    assert "no battle intervals" not in stderr.getvalue()
    doc = json.loads(out.read_text(encoding="utf-8"))
    nodes = {n["ID"]: n for n in doc["nodes"]}
    types = [n["type"] for n in doc["nodes"]]
    assert "Battle" not in types
    assert {"Game", "Player"} <= set(types) and types.count("Player") == 2
    ends = [(lk["node1"], lk["node2"]) for lk in doc["links"]]
    assert all(a in nodes and b in nodes for a, b in ends)  # no link to a node that is not there (a dropped battle)
    assert not [e for e in ends if any(x.startswith("Battle-") for x in e)]  # the battle links all end at a Battle
    assert (out.parent / "Intervals.csv").read_bytes() == b"start,end,id\n"
    intervals = json.loads((out.parent / "intervals.json").read_text(encoding="utf-8"))
    assert (intervals["graph"], intervals["intervals"]) == ("graph.json", [])
    assert "Traceback" not in (out.parent / "graph.log").read_text(encoding="utf-8")
    print(f"{name}: {len(types)} nodes, {sorted(set(types))}")
