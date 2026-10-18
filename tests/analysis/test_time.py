"""CR-022 (T21): time as a number. Characterisation first (G4): what the legacy time text is, per node
kind and field, and how it relates to the signed start and to the events' loops. These hold on the
code before CR-022 and must still hold after it. Then ``GameTime``, the TD-26 boundary test and the
export formatter.
"""

import contextlib
import io
import json
import os
import pathlib
import re

import pytest
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.domain.time import GameTime
from sc2mindshare.export.time_text import legacy_text, text_values
from sc2mindshare.layout.sweep import win
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
GOLDEN = CHECKOUT / "tests" / "golden"


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
ALCYONE = MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay"

HH_MM_SS = r"\d\d:\d\d:\d\d"
H_MM_SS = r"\d:\d\d:\d\d"  # a Battle's times: Python's timedelta text
MM_SS = r"\d\d:\d\d"

#: The legacy text of every time field, per node kind (the frozen bug-faithful models of both games).
FORMS = {
    ("Ability", "time"): HH_MM_SS,
    ("Battle", "time"): H_MM_SS,
    ("Battle", "end time"): H_MM_SS,
    ("Building", "time"): HH_MM_SS,
    ("Chat", "time"): HH_MM_SS,
    ("Energy Excess", "time"): HH_MM_SS,
    ("Energy Excess", "end time"): HH_MM_SS + "|None",  # an excess still open at the end of the game
    ("Harrasment", "time"): MM_SS,
    ("Harrasment", "end time"): MM_SS,
    ("Initiated", "time"): HH_MM_SS,
    ("Inject Delay", "time"): HH_MM_SS,
    ("Inject Delay", "end time"): HH_MM_SS,
    ("Scouting", "time"): MM_SS,
    ("Stats", "time"): HH_MM_SS,
    ("Supply Block", "time"): HH_MM_SS,
    ("Supply Block", "end time"): HH_MM_SS,
    ("Units", "time"): HH_MM_SS,
    ("Upgrade", "time"): HH_MM_SS,
}


def _fixture_nodes(game):
    return json.loads((GOLDEN / game / "models-faithful.json").read_text(encoding="utf-8"))["nodes"]


def _seconds(text):
    parts = [int(p) for p in text.split(":")]
    return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]


@pytest.mark.parametrize("game", ["alcyone", "spine"])
def test_every_time_field_has_its_kinds_legacy_form(game):
    seen = set()
    for node in _fixture_nodes(game):
        for name, value in node["values"]:
            if name in ("time", "end time"):
                assert re.fullmatch(FORMS[(node["kind"], name)], value), (node["id"], name, value)
                seen.add((node["kind"], name))
    missing = {"alcyone": set(), "spine": {("Supply Block", "time"), ("Supply Block", "end time")}}  # no block in spine
    assert seen == set(FORMS) - missing[game]


@pytest.mark.parametrize("game", ["alcyone", "spine"])
def test_the_time_text_is_the_signed_start_wrapped_at_midnight(game):
    """The layout's signed start and the printed time are the same second; only a pre-game start
    (the main bases at -71 s) wraps, to 23:58:49 (B9, P3)."""
    starts = [
        (n["id"], n["start_seconds"], dict(n["values"])["time"]) for n in _fixture_nodes(game) if n["start_seconds"] is not None
    ]
    assert all(_seconds(text) == start % 86400 for _id, start, text in starts)
    assert [(i, s, t) for i, s, t in starts if s < 0] == [("Building-1", -71, "23:58:49"), ("Building-2", -71, "23:58:49")]


@pytest.fixture(scope="module")
def alcyone_result():
    if not ALCYONE.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {ALCYONE} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {ALCYONE}")
    with contextlib.redirect_stdout(io.StringIO()):
        return analyse(load_replay(ALCYONE), MS_SC)


def test_an_event_nodes_time_is_its_loop_floored_to_the_second(alcyone_result):
    """TD-26: the second the legacy CSV prints for a node made from one event is int(frame / 22.4)."""
    checked = 0
    for node in alcyone_result.nodes:
        if node.getNodeType() in ("Ability", "Chat", "Initiated"):
            text = str(node.getProperties("\x1f")).split("\x1f")[0]
            assert _seconds(text) == int(node.event.frame / 22.4), (node.getNodeID(), text, node.event.frame)
            checked += 1
    assert checked > 100


# --- CR-022: GameTime, the boundary test (TD-26) and the formatter -------------------------------------

TWELVE_HOURS_OF_LOOPS = range(112 * 3600 * 12 // 5)  # 22.4 loops a second


def test_a_loops_second_is_the_legacy_int_frame_over_22_4_for_twelve_hours():
    """TD-26: the exact integer second equals the legacy float expression for every loop of a game."""
    assert all(GameTime(loops).seconds == int(loops / 22.4) for loops in TWELVE_HOURS_OF_LOOPS)


@pytest.mark.parametrize("k", [1, 2, 6, 13, 60, 360, 4319])
def test_items_at_a_window_boundary_stay_in_their_window(k):
    """Leo §12.9: window k-1 is (10(k-1), 10k], so second 10k is its last second and 10k + 1 the next
    window's first. Every loop of those seconds lands where the legacy second put it."""
    for second, window in ((10 * k - 1, k - 1), (10 * k, k - 1), (10 * k + 1, k)):
        first = GameTime.from_seconds(second).loops
        for loops in range(first, GameTime.from_seconds(second + 1).loops):
            assert GameTime(loops).seconds == int(loops / 22.4) == second
            assert win(GameTime(loops).seconds) == window, (k, second, loops)


def test_from_seconds_is_the_first_loop_of_that_second_signed():
    for s in range(-4 * 3600, 12 * 3600):
        t = GameTime.from_seconds(s)
        assert t.seconds == s and GameTime(t.loops - 1).seconds == s - 1, s
    assert GameTime.from_seconds(-71) == GameTime(-1590) and GameTime(-1).seconds == -1  # floored, not truncated


def test_every_event_nodes_model_start_is_its_loops_second(alcyone_result):
    """TD-26 end to end: the model's start of an event node is int(frame / 22.4), so the layout puts it
    in the window of that second."""
    graph = to_graph(alcyone_result, fixes=())
    pairs = [
        (n, m) for n, m in zip(alcyone_result.nodes, graph.nodes, strict=True) if m.kind in ("Ability", "Chat", "Initiated")
    ]
    assert len(pairs) > 100
    for legacy, model in pairs:
        second = int(legacy.event.frame / 22.4)
        assert model.start.seconds == second and win(model.start.seconds) == win(second), model.id


@pytest.mark.parametrize(
    ("kind", "seconds", "text"),
    [
        ("Building", -71, "23:58:49"),  # the midnight wrap (B9, ledger P3)
        ("Ability", 3725, "01:02:05"),
        ("Battle", 122, "0:02:02"),  # timedelta text
        ("Battle", 3608, "1:00:08"),
        ("Scouting", 102, "01:42"),  # Length text ...
        ("Harrasment", 3605, "01:00:05"),  # ... with hours from one hour on
    ],
)
def test_legacy_text(kind, seconds, text):
    assert legacy_text(kind, GameTime.from_seconds(seconds)) == text


def test_an_open_end_is_none_and_a_length_cannot_be_negative():
    assert legacy_text("Energy Excess", None) == "None"
    with pytest.raises(ValueError, match="negative"):
        legacy_text("Scouting", GameTime.from_seconds(-1))


@pytest.mark.parametrize("game", ["alcyone", "spine"])
def test_the_frozen_text_reads_into_times_and_prints_back_the_same(game):
    """Every node of the frozen bug-faithful models: legacy text -> GameTime -> legacy text is the identity."""
    from sc2mindshare.analysis.to_domain import typed_values
    from sc2mindshare.domain.models import Node

    for n in _fixture_nodes(game):
        values, start = typed_values(n["id"], n["kind"], [tuple(v) for v in n["values"]], n["start_seconds"])
        node = Node(n["kind"], n["id"], n["name"], n["description"], tuple(n["images"]), values, start)
        assert [list(v) for v in text_values(node)] == n["values"], n["id"]
        assert (None if start is None else start.seconds) == n["start_seconds"]
