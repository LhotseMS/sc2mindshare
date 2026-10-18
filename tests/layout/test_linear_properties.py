"""CR-017 (T16): the linear timeline's properties (layout-spec.md §8; stream1-plan.md §3 step 9; TD-24).

Only ``row()`` differs between the modes: linear ``row(w) = w``. So, against the compressed layout of
the same game: the same occupied windows; every swept node at x = 2.5 x its window and never left of its
compressed x; y identical except for battles, and sizes identical except supply-block widths, which
equal the window span; clock nodes only on occupied windows without Stats, and empty rows stay blank.
Checked on two real games.

Battles are exempt from the y identity (Leo's CR-017 check): the collision distance is measured along x,
so two battles with an empty window between them may shift in compressed mode and not in linear
(test_lanes.test_3_battle_collision_depends_on_the_mode). The determinism invariant I13 runs in both
modes (test_alcyone.test_i13_determinism_and_shuffled_input).
"""

import contextlib
import csv
import io
import os
import pathlib

import pytest
from sc2mindshare.analysis.run import analyse
from sc2mindshare.analysis.to_domain import to_graph
from sc2mindshare.layout.items import items
from sc2mindshare.layout.profile import Profile
from sc2mindshare.layout.sweep import ANCHORS, layout, win
from sc2mindshare.reader.loader import load_replay

CHECKOUT = pathlib.Path(__file__).resolve().parents[2]


def _root():
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
GAMES = {
    "alcyone": MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
    "spine": MS_SC / "200k dmg spine crawler ZvP.SC2Replay",
}
PITCH = Profile().row_pitch
assert PITCH == 2.5  # the literals below are in units of the row pitch (spec §4)
SUPPLY_BLOCKS = {"alcyone": 7, "spine": 2}  # after CR-023 S1 with S5 (D9a): 11 -> 7 on Alcyone, and spine has 2 (it had none)


@pytest.fixture(scope="module", params=sorted(GAMES))
def game(request):
    path = GAMES[request.param]
    for needed in (path, MS_SC / "TimeImageTracking.csv"):
        if not needed.exists():
            if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
                pytest.fail(f"missing input {needed} (SC2MS_REQUIRE_GOLDEN=1)")
            pytest.skip(f"missing input {needed}")
    with (MS_SC / "TimeImageTracking.csv").open(encoding="utf-8") as f:
        clock_map = {r["imageName"]: r["imageID"] for r in csv.DictReader(f)}
    with contextlib.redirect_stdout(io.StringIO()):
        graph = to_graph(analyse(load_replay(path), MS_SC))
    its = items(graph)
    compressed = layout(its, Profile(timeline="compressed"), clock_map)
    linear = layout(its, Profile(timeline="linear"), clock_map)
    return request.param, its, compressed, linear


def _swept(its, *, supply_blocks=False):
    """The items placed on the timeline (not the anchors or the grid)."""
    kinds = {"Battle", "Building", "Upgrade", "Initiated", "Units", "Stats", "Chat", "Ability"}
    if supply_blocks:
        kinds = {"Supply Block"}
    return [i for i in its if i.type in kinds and i.t is not None and i.type not in ANCHORS]


def test_rows_are_the_windows(game):
    _name, _its, compressed, linear = game
    assert [w for _r, w, _x in linear.rows] == [w for _r, w, _x in compressed.rows]  # the same occupied windows
    assert all(r == w and x == w * PITCH for r, w, x in linear.rows)
    assert [r for r, _w, _x in compressed.rows] == list(range(len(compressed.rows)))


def test_every_swept_node_sits_at_its_window_and_never_left_of_compressed(game):
    _name, its, compressed, linear = game
    window_at = {x: w for _r, w, x in compressed.rows}  # a compressed x names its window
    for item in _swept(its):
        xc, xl = compressed.positions[item.id][0], linear.positions[item.id][0]
        assert xl == window_at[xc] * PITCH, item.id
        assert xl >= xc, item.id


def test_y_and_sizes_are_identical_except_battle_y_and_supply_block_widths(game):
    _name, its, compressed, linear = game
    for item in its:
        if item.type != "Battle":  # a battle's shift depends on the x distance to the previous battle
            assert linear.positions[item.id][1] == compressed.positions[item.id][1], item.id
        if item.type == "Supply Block":
            assert linear.sizes[item.id][1:] == compressed.sizes[item.id][1:], item.id
        else:
            assert linear.sizes[item.id] == compressed.sizes[item.id], item.id
    anchored = [
        i
        for i in its
        if i.type not in {"Battle", "Building", "Upgrade", "Initiated", "Units", "Stats", "Chat", "Ability", "Supply Block"}
    ]
    for item in anchored:  # anchors and the grid do not move at all
        assert linear.positions[item.id] == compressed.positions[item.id], item.id


def test_supply_block_widths_are_the_window_span(game):
    name, its, _compressed, linear = game
    blocks = _swept(its, supply_blocks=True)
    assert len(blocks) == SUPPLY_BLOCKS[name]
    for b in blocks:
        ws = win(b.t)
        we = max(ws, win(b.t_end))
        assert linear.sizes[b.id][0] == (we - ws + 1) * PITCH, b.id
        assert linear.positions[b.id][0] == (ws + we) / 2 * PITCH, b.id


def test_clocks_only_on_occupied_windows_and_empty_rows_stay_blank(game):
    _name, its, compressed, linear = game
    occupied = {w for _r, w, _x in linear.rows}
    stats = {win(i.t) for i in its if i.type == "Stats" and i.t is not None}
    expected = sorted(w * PITCH for w in occupied - stats)
    assert sorted({c.x for c in linear.extra_nodes}) == expected
    assert [c.file_name for c in linear.extra_nodes] == [c.file_name for c in compressed.extra_nodes]
    empty = set(range(max(occupied) + 1)) - occupied
    assert empty  # both games have empty windows, so the property is exercised
    xs = {linear.positions[i.id][0] for i in _swept(its)} | {c.x for c in linear.extra_nodes}
    assert not {w * PITCH for w in empty} & xs
