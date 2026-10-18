"""CR-022 (T21): time as a number. Characterisation first (G4): what the legacy time text is, per node
kind and field, and how it relates to the signed start and to the events' loops. These hold on the
code before CR-022 and must still hold after it.
"""

import contextlib
import io
import json
import os
import pathlib
import re

import pytest
from sc2mindshare.analysis.run import analyse
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
