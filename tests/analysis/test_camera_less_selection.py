"""CR-078: a selection made before the player's camera is known gives no position (Stefan's D3a).

``ActionsDetector.processUnitPositionEvent`` places a selection's new units at the player's last camera, and
``addUnitsPointCommand`` takes a move's travel time from the base at the selection's camera. A player who selects
before the game has recorded any camera for him has none: the first raised a ``KeyError`` naming the player, and a
move after such a selection a ``TypeError`` on its empty camera location. Guard (a): the selection takes no position
and its ``cameraLocation`` stays None. Guard (b): the move takes the path a move after a control-group selection
already takes (no travel time, a MAYBE position at its target). Everything after the player's first camera, and the
game's exact positions, are as before.

The synthetic tests use a bare detector and fake events: subclasses of the reader's event classes with plain
attributes, hashable players with a ``pid``, selection and command times ``"MM.SS"`` and ``UnitPositionsEvent`` times
``"MM:SS"`` (what each branch parses), real-shaped unit ids. They take the dispatch's own steps in its order
(``processSelectionsAndCommands``): a camera event sets ``lastCamera``; a selection with new units runs
``processUnitPositionEvent`` then ``setSelection``; a point command runs ``addUnitsPointCommand`` on the last
selection's units. Expected positions are worked out by hand from the rule (a travel time of 7 s from a main base or
natural), never taken from the code under test.

The replay tests read Stefan's games in place from ``MS SC/`` by SHA-256; they run in every gate on this Mac
(``SC2MS_REQUIRE_GOLDEN=1``) and are skipped elsewhere when the replays are absent.
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
from sc2mindshare.analysis.detectors.detectors import ActionsDetector


class Player:
    """A hashable player with a pid: the detector keys ``lastCamera`` and ``lastSelection`` by player object."""

    def __init__(self, pid):
        self.pid = pid


A = Player(1)
B = Player(2)
U1 = 53477378
U2 = 53739522
U3 = 61341697


def unit(uid, player):
    return SimpleNamespace(id=uid, player=player, name="Zergling")


class Camera(detectors.CameraEvent):
    player = time = location = None

    def __init__(self, time, player, location):
        self.time, self.player, self.location = time, player, location


class Selection(detectors.SelectionEvent):
    player = time = new_units = cameraLocation = None

    def __init__(self, time, player, units):
        self.time, self.player, self.new_units = time, player, units


class Move(detectors.TargetPointCommandEvent):
    player = time = location = x = y = None

    def __init__(self, time, player, x, y):
        self.time, self.player, self.x, self.y, self.location = time, player, x, y, (x, y)


class Exact(detectors.UnitPositionsEvent):
    time = positions = None

    def __init__(self, time, positions):
        self.time, self.positions = time, positions


class Recall:
    """Stands in for a control-group selection: anything that is not a ``SelectionEvent``."""


MAIN = SimpleNamespace(name="Main base", location=(10, 10))
THIRD = SimpleNamespace(name="Third", location=(90, 90))


class Bases:
    """The camera at (10, 10) sees the main base, at (90, 90) a third base; nothing anywhere else."""

    def getBaseForLocation(self, x, y):
        return {(10, 10): MAIN, (90, 90): THIRD}.get((x, y))


def detector():
    d = ActionsDetector.__new__(ActionsDetector)
    d.ctx = SimpleNamespace(bases=Bases(), fixes=frozenset())
    d.lastCamera, d.lastSelection, d.unitsPositions, d.unitsCommands = {}, {}, {}, {}
    return d


def dispatch(d, events):
    """The dispatch's own steps for these event kinds, in its order (``processSelectionsAndCommands``)."""
    for e in events:
        if isinstance(e, detectors.CameraEvent):
            d.lastCamera[e.player] = e
        elif isinstance(e, detectors.UnitPositionsEvent):
            d.processUnitPositionEvent(e)
        elif isinstance(e, detectors.SelectionEvent) and e.new_units:
            d.processUnitPositionEvent(e)
            d.setSelection(e)
        elif isinstance(e, detectors.TargetPointCommandEvent):
            d.addUnitsPointCommand(d.getLastSelectionUnits(e.player), e)


def positions(d):
    return {uid: [(p.time.strftime("%M:%S"), p.x, p.y, p.accuracy.name) for p in ps] for uid, ps in d.unitsPositions.items()}


def commands(d):
    return {uid: [(c.time, c.x, c.y, c.travelTime) for c in cs] for uid, cs in d.unitsCommands.items()}


# --- AC2: the sequence of QA-2 --------------------------------------------------------------------------------------


def test_a_selection_before_the_camera_gives_no_position_and_its_move_no_travel_time():
    """QA-2: A selects U1 and U2 before any camera of his (00.05) and moves them to (50, 60) (00.06); his first
    camera, at his main base (00.07); he selects U1 (00.10) and moves it to (70, 80) (00.11); the game's exact
    position of U2 (00:12). Before CR-078, ``KeyError`` at the first selection."""
    u1, u2 = unit(U1, A), unit(U2, A)
    d = detector()

    dispatch(
        d,
        [
            Selection("00.05", A, [u1, u2]),
            Move("00.06", A, 50, 60),
            Camera("00.07", A, (10, 10)),
            Selection("00.10", A, [u1]),
            Move("00.11", A, 70, 80),
            Exact("00:12", [(U2, (30, 40))]),
        ],
    )

    assert positions(d) == {
        # no SCREEN position at 00:05; the move: MAYBE at its target, at its own time; then as today: SCREEN at the
        # camera, and from the main base a PATH position at the target 7 s after the move
        U1: [("00:06", 50, 60, "MAYBE"), ("00:10", 10, 10, "SCREEN"), ("00:18", 70, 80, "PATH")],
        U2: [("00:06", 50, 60, "MAYBE"), ("00:12", 30, 40, "EXACT")],
    }
    assert commands(d) == {U1: [("00.06", 50, 60, None), ("00.11", 70, 80, 7)], U2: [("00.06", 50, 60, None)]}
    assert d.lastSelection[A].cameraLocation == (10, 10)


def test_the_move_after_a_camera_less_selection_is_recorded_as_after_a_control_group_selection():
    """QA-2 (3): the same move, once after a camera-less selection and once after a control-group recall."""
    moved, control = detector(), detector()
    u1, u2 = unit(U1, A), unit(U2, A)
    dispatch(moved, [Selection("00.05", A, [u1, u2]), Move("00.06", A, 50, 60)])
    control.lastSelection[A] = Recall()
    control.addUnitsPointCommand([u1, u2], Move("00.06", A, 50, 60))

    assert positions(moved) == positions(control) == {U1: [("00:06", 50, 60, "MAYBE")], U2: [("00:06", 50, 60, "MAYBE")]}
    assert commands(moved) == commands(control)


def test_guard_a_a_selection_before_the_camera_takes_no_position():
    """Guard (a) alone: before CR-078, ``KeyError`` on the player in ``processUnitPositionEvent``."""
    d = detector()
    selection = Selection("00.05", A, [unit(U1, A)])

    d.processUnitPositionEvent(selection)

    assert d.unitsPositions == {}
    assert selection.cameraLocation is None


def test_guard_b_a_move_after_a_selection_without_a_camera_location():
    """Guard (b) alone: the last selection has no camera location (a camera-less selection that guard (a) let
    through). Before CR-078, ``TypeError: 'NoneType' object is not subscriptable`` in ``addUnitsPointCommand``."""
    d = detector()
    d.lastSelection[A] = Selection("00.05", A, [unit(U1, A)])

    d.addUnitsPointCommand([unit(U1, A)], Move("00.06", A, 50, 60))

    assert positions(d) == {U1: [("00:06", 50, 60, "MAYBE")]}
    assert commands(d) == {U1: [("00.06", 50, 60, None)]}


# --- QA-4 edges ------------------------------------------------------------------------------------------------------


def test_a_player_with_no_camera_at_all_gets_no_screen_position():
    """E1: every selection of his gives no position, and the build goes on."""
    d = detector()
    dispatch(d, [Selection("00.05", A, [unit(U1, A)]), Selection("01.00", A, [unit(U2, A)])])
    assert d.unitsPositions == {}


def test_the_other_players_camera_never_stands_in():
    """E2: B's camera comes first; A's selection still has none of his own."""
    d = detector()
    dispatch(d, [Camera("00.03", B, (10, 10)), Selection("00.05", A, [unit(U1, A)]), Selection("00.06", B, [unit(U3, B)])])
    assert positions(d) == {U3: [("00:06", 10, 10, "SCREEN")]}


@pytest.mark.parametrize(
    ("order", "expected"),
    [("camera first", {U1: [("00:05", 90, 90, "SCREEN")]}), ("selection first", {})],
)
def test_on_the_same_second_the_event_order_decides(order, expected):
    """E3: a camera and a selection on one second."""
    camera, selection = Camera("00.05", A, (90, 90)), Selection("00.05", A, [unit(U1, A)])
    d = detector()
    dispatch(d, [camera, selection] if order == "camera first" else [selection, camera])
    assert positions(d) == expected


def test_exact_positions_before_the_camera_are_recorded_as_today():
    """E7 (characterisation)."""
    d = detector()
    dispatch(d, [Exact("00:02", [(U1, (30, 40)), (U2, (31, 41))])])
    assert positions(d) == {U1: [("00:02", 30, 40, "EXACT")], U2: [("00:02", 31, 41, "EXACT")]}


def test_a_move_after_a_camera_at_the_main_base_gets_its_travel_time_as_today():
    """Characterisation: SCREEN at the camera, then a PATH position at the target 7 s after the move."""
    d = detector()
    dispatch(d, [Camera("00.04", A, (10, 10)), Selection("00.05", A, [unit(U1, A)]), Move("00.06", A, 50, 60)])
    assert positions(d) == {U1: [("00:05", 10, 10, "SCREEN"), ("00:13", 50, 60, "PATH")]}
    assert commands(d) == {U1: [("00.06", 50, 60, 7)]}


def test_a_move_after_a_camera_away_from_main_and_natural_gets_no_travel_time_as_today():
    """Characterisation: camera at a third base: a SCREEN position there, then MAYBE at the target, no travel time."""
    d = detector()
    dispatch(d, [Camera("00.04", A, (90, 90)), Selection("00.05", A, [unit(U1, A)]), Move("00.06", A, 50, 60)])
    assert positions(d) == {U1: [("00:05", 90, 90, "SCREEN"), ("00:06", 50, 60, "MAYBE")]}
    assert commands(d) == {U1: [("00.06", 50, 60, None)]}


# --- AC1, AC3: Stefan's games (read in place; every gate on this Mac) -------------------------------------------------


def _root():
    d = pathlib.Path(__file__).resolve().parents[2]
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


CHECKOUT = pathlib.Path(__file__).resolve().parents[2]
MS_SC = pathlib.Path(os.environ.get("SC2MS_MS_SC", _root() / "MS SC"))
RECENT = MS_SC / "cr-074-recent"

#: The 2 recent games whose first failure at 872bfc7 is the unit positions (QA-1's SHA-256s), with their selections
#: before the player's first camera (count, units), from Rex's probe (``.scratch/rex/cr-077-078/probe-078p.jsonl``).
CAMERA_LESS = {
    "Rainfall LE (91)": ("fab9b488632177de0fbf0f074db1378e70fadf877b5e3ea2ab98c186ff6b4585", (5, 8)),
    "Sanctuary III LE (100)": ("cee88f0e39f7a7ba5b576d0145fdb47faf8b9184d5ed4443ad1c1fbcd6a3ba79", (6, 8)),
}
GOLDEN_REPLAYS = {
    "alcyone": MS_SC / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Alcyone LE__lilTiGGer_vs_blacksquall.SC2Replay",
    "spine": MS_SC / "200k dmg spine crawler ZvP.SC2Replay",
}


def _need(path):
    if not path.exists():
        if os.environ.get("SC2MS_REQUIRE_GOLDEN") == "1":
            pytest.fail(f"missing input {path} (SC2MS_REQUIRE_GOLDEN=1)")
        pytest.skip(f"missing input {path}")
    return path


def camera_less_selections(path):
    """(selections, units) of every player's selections with new units before his first camera event, in the order
    the dispatch reads the events. Loads the replay only (no analysis)."""
    from sc2mindshare.reader.loader import load_replay

    seen, count, units = set(), 0, 0
    for e in load_replay(path).events:
        if isinstance(e, detectors.CameraEvent):
            seen.add(e.player)
        elif isinstance(e, detectors.SelectionEvent) and e.new_units and e.player not in seen:
            count, units = count + 1, units + len(e.new_units)
    return count, units


@pytest.mark.parametrize("name", sorted(GOLDEN_REPLAYS))
def test_the_reference_games_have_no_selection_before_a_camera(name):
    """AC3's Given, shown (QA-3): neither guard can fire on Alcyone or spine, so their goldens hold."""
    assert camera_less_selections(_need(GOLDEN_REPLAYS[name])) == (0, 0)


@pytest.fixture
def config(tmp_path):
    """A config root with the real support tables and the committed clock fixture, as ``tests/test_cli.py`` uses."""
    root = tmp_path / "config"
    root.mkdir()
    for name in ("unitsInfo.csv", "upgradesInfo.csv", "ImageTracking.csv"):
        shutil.copyfile(_need(MS_SC / name), root / name)
    shutil.copyfile(CHECKOUT / "tests" / "golden" / "clock-record-fixture.csv", root / "ClockImageRecord.csv")
    return root


@pytest.mark.parametrize("name", sorted(CAMERA_LESS))
def test_a_recent_game_with_a_camera_less_selection_builds(name, tmp_path, config):
    """AC1 (QA-1), AC2 on real data: the game has its camera-less selections, and it builds through the CLI with no
    error in the position or move-command step, nor later. Before CR-078, a ``KeyError`` naming a player in
    ``processUnitPositionEvent``. Rainfall LE (91) builds fully because CR-077 is on the batch branch."""
    sha256, expected = CAMERA_LESS[name]
    replay = _need(RECENT / f"{name}.SC2Replay")
    assert hashlib.sha256(replay.read_bytes()).hexdigest() == sha256, f"{name} changed"
    assert camera_less_selections(replay) == expected
    out = tmp_path / "game" / "graph.json"

    stderr = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
        code = cli.main(["build", str(replay), "--out", str(out), "--config-root", str(config)])

    assert code == 0, stderr.getvalue()
    assert "Traceback" not in (out.parent / "graph.log").read_text(encoding="utf-8")
    doc = json.loads(out.read_text(encoding="utf-8"))
    print(f"{name}: {len(doc['nodes'])} nodes")
