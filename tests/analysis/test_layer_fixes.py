"""CR-023 (T22): the layer fixes, each switched by its ledger id (analysis.fixes.LAYER_FIXES)."""

import contextlib
import io
import os
import pathlib
from types import SimpleNamespace

import pytest
from sc2mindshare.analysis.detectors.detectors import BaseDetector
from sc2mindshare.analysis.fixes import LAYER_FIXES
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"


def test_the_layer_fixes_in_ledger_order():
    assert LAYER_FIXES == ("P1",)


# --- P1: getClosestBase compares real distances ------------------------------------------------------------


class _Base:
    def __init__(self, name, x, y):
        self.name, self.location = name, (x, y)

    def minDistance(self, loc):  # the legacy Base's method name
        return ((self.location[0] - loc[0]) ** 2 + (self.location[1] - loc[1]) ** 2) ** 0.5


BASES = {"p1": [_Base("Main", 0, 0), _Base("Natural", 100, 0)], "p2": [_Base("Main", 50, 50), _Base("Natural", 10, 10)]}


def _closest(location, fixes):
    detector = SimpleNamespace(bases=BASES, ctx=SimpleNamespace(fixes=frozenset(fixes)))
    return BaseDetector.getClosestBase(detector, SimpleNamespace(location=location))


@pytest.mark.parametrize(
    ("location", "nearest"), [((1, 1), ("p1", 0)), ((99, 2), ("p1", 1)), ((48, 47), ("p2", 0)), ((11, 9), ("p2", 1))]
)
def test_p1_the_nearest_base_wins(location, nearest):
    player, index = nearest
    assert _closest(location, {"P1"}) is BASES[player][index]


def test_p1_a_tie_keeps_the_first_base_iterated():
    assert _closest((50, -60), {"P1"}) is BASES["p1"][0]  # 78.1 from Main and from Natural; the others are farther


def test_p1_off_is_bug_faithful_the_second_base_iterated_always_wins():
    assert all(_closest(loc, ()) is BASES["p1"][1] for loc in [(1, 1), (48, 47), (11, 9)])


@pytest.fixture(scope="module")
def battle_names():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    names = {}
    for label, fixes in (("faithful", ()), ("fixed", LAYER_FIXES)):
        with contextlib.redirect_stdout(io.StringIO()):
            graph = to_graph(analyse(load_replay(ALCYONE), MS_SC, fixes=fixes), fixes=())
        names[label] = {n.id: n.name for n in graph.nodes if n.kind == "Battle"}
    return names


def test_p1_on_alcyone_the_battles_name_their_nearest_base(battle_names):
    """The predicted renames of the P1 entry (CHANGES.md), a few pinned; the goldens hold all 30."""
    assert len(battle_names["fixed"]) == 30
    assert all(name.endswith(" near lilTiGGer Natural") for name in battle_names["faithful"].values())
    fixed = battle_names["fixed"]
    assert fixed["Battle-1"] == "Zealot killed ling near blacksquall Natural"
    assert fixed["Battle-6"] == "Adept killed Drone near lilTiGGer 3rd base"
    assert fixed["Battle-22"] == "lings Roachs Hydralisks Overseers Overlords died near lilTiGGer Main base"
    assert fixed["Battle-28"] == "ling killed Pylon near blacksquall Main base"
    assert not any(name.endswith(" near lilTiGGer Natural") for name in fixed.values())
    strip = {k: v.rsplit(" near ", 1)[0] for k, v in fixed.items()}
    assert strip == {k: v.rsplit(" near ", 1)[0] for k, v in battle_names["faithful"].items()}  # only the base part
