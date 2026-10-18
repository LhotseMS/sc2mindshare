"""Tests for the VBA view reference port (CR-006, T06). Expected values are literals read off the VBA source."""

import importlib.util
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("vba_view", _HERE / "vba_view.py")
assert _spec and _spec.loader
vv = importlib.util.module_from_spec(_spec)
sys.modules["vba_view"] = vv
_spec.loader.exec_module(vv)

PAD = ";" * 12


def gameplay_row(csv_line):
    nodes, _ = vv.power_query(csv_line)
    assert len(nodes) == 1
    return nodes[0]


# --- conversions -------------------------------------------------------------


@pytest.mark.parametrize(("text", "expected"), [("3", 3), ("0", 0), ("-1", -1), ("2,5", 2), ("3,5", 4), ("32767", 32767)])
def test_vba_integer(text, expected):
    assert vv.vba_integer(text) == expected


@pytest.mark.parametrize("text", ["", "blacksquall", "32768"])
def test_vba_integer_fails_like_vba(text):
    with pytest.raises(vv.VbaError):
        vv.vba_integer(text)


def test_supply_text_reads_as_a_decimal_on_the_decimal_comma_locale():
    assert vv.vba_double_from_point_text("0.5") == 0.5
    assert vv.vba_double_from_point_text("12") == 12.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [("00:02:02", "00:02:02"), ("23:58:49", "23:58:49"), ("01:42", "01:42:00"), ("0:02:02", "00:02:02"), ("x", "x")],
)
def test_format_hhmmss(text, expected):
    assert vv.vba_format_hhmmss(text) == expected


# --- Power Query -------------------------------------------------------------


def test_power_query_splits_nodes_and_links_on_a_hyphen_in_column_1():
    text = "\n".join(["Game;d;Game;Game-1;;" + PAD, "Game-1;Player-1;played;played by;same units;-1" + PAD])
    nodes, links = vv.power_query(text)
    assert [r[:3] for r in nodes] == [["1", "", "Game"]]
    assert links[0][:6] == ["Game-1", "Player-1", "played", "played by", "same units", "-1"]
    assert len(nodes[0]) == 2 + vv.PQ_COLUMNS
    assert len(links[0]) == vv.PQ_COLUMNS


def test_power_query_keeps_only_23_columns():
    assert len(vv.physical_rows(";".join(str(i) for i in range(30)))[0]) == 23


def test_raw_newline_rows_split_unless_rejoined():
    broken = "5 died;5 workers died.\nPull occured after -16.0s.;Harrasment;Harrasment-1;;07:49;blacksquall;07:56;5" + PAD
    nodes, links = vv.power_query(broken)
    assert len(nodes) == 1 and len(links) == 1  # the second half starts with "Pull ... -16.0s" and counts as a link
    with pytest.raises(vv.VbaError):  # readLinks: direction = "blacksquall" is a type mismatch
        vv.read_link(links[0])
    nodes, links = vv.power_query(broken, rejoin_raw_newlines=True)
    assert len(nodes) == 1 and links == []
    view = vv.read_node(nodes[0]).get_view()
    assert view["description"] == "5 workers died.\nPull occured after -16.0s."
    assert view["properties"] == {"time": "07:49:00", "player": "blacksquall"}


# --- readNodes / GetView -------------------------------------------------------


def test_battle_view():
    row = gameplay_row(
        "Zealot killed ling near X;lost 1 units.X_LDAt 0:02:02.;Battle;Battle-1;u1|u2;00:02:02;Common;1;1;0;0.5;0:02:02" + PAD
    )
    assert vv.read_node(row).get_view() == {
        "name": "Zealot killed ling near X",
        "description": "lost 1 units.\nAt 0:02:02.",
        "type": "Battle",
        "ID": "Battle-1",
        "images": ["u1", "u2"],
        "size": 0.7,
        "properties": {
            "time": "00:02:02",
            "player": "Common",
            "dead": 1,
            "p1 dead": 1,
            "p2 dead": 0,
            "supply dead": 0.5,
            "end time": "0:02:02",
        },
    }


@pytest.mark.parametrize(("supply", "size"), [("1", 0.7), ("3", 0.95), ("10", 1.2), ("30", 1.6), ("50", 2.5)])
def test_battle_circle_size(supply, size):
    row = gameplay_row(f"b;d;Battle;Battle-2;;00:01:00;Common;1;1;0;{supply};0:01:00" + PAD)
    assert vv.read_node(row).get_view()["size"] == size


@pytest.mark.parametrize(("supply", "size"), [("3", 0.75), ("3.5", 1), ("10", 1), ("20", 1.4), ("21", 1.7)])
def test_units_circle_size_and_property_order(supply, size):
    row = gameplay_row(f"12 Drones;d;Units;Units-1;;00:00:00;p1;Drone;12;{supply};12" + PAD)
    view = vv.read_node(row).get_view()
    assert view["size"] == size
    assert list(view["properties"]) == ["time", "player", "type", "count", "total at time", "supply"]


def test_ability_never_emits_combat_flags_b3():
    row = gameplay_row("SpawnLarva;d;Ability;Ability-1;;00:03:00;p1;SpawnLarva;False;True;False;Hatchery" + PAD)
    view = vv.read_node(row).get_view()
    assert view["properties"] == {"time": "00:03:00", "player": "p1", "type": "SpawnLarva", "target": "Hatchery"}
    assert view["size"] == [1.6, 0.88]


def test_supply_block_and_stats_views():
    sb = vv.read_node(gameplay_row("SB;d;Supply Block;Supply Block-1;;00:00:00;p1;00:00:57;57" + PAD)).get_view()
    assert sb["properties"] == {"time": "00:00:00", "player": "p1", "duration": 57, "end time": "00:00:57"}
    assert sb["size"] == [2.65, 1]
    st = vv.read_node(gameplay_row("S;d;Stats;Stats-1;;00:01:04;p1;330;0;839;0;14;0;0;1250;0" + PAD)).get_view()
    assert st["properties"] == {
        "time": "00:01:04",
        "player": "p1",
        "workers": 14,
        "cur. Min": 330,
        "cur. Gas": 0,
        "col. rate Min": 839,
        "col. rate Gas": 0,
        "army Min": 0,
        "army Gas": 0,
        "used Min": 1250,
        "used Gas": 0,
    }
    assert st["size"] == [2.65, 1.28]


def test_game_and_player_have_no_properties():
    g = vv.read_node(gameplay_row("Ladder Alcyone LE;d;Game;Game-1;;Normal;True;1v1;Ladder;00:16:38" + PAD)).get_view()
    assert (g["size"], g["properties"]) == ([10, 3.3], {})
    p = vv.read_node(gameplay_row("lilTiGGer;d;Player;Player-1;;lilTiGGer;Zerg;eu;1" + PAD)).get_view()
    assert (p["size"], p["properties"]) == ([7.8, 2.2], {})


def test_scouting_time_reads_as_hours_b9():
    row = gameplay_row("Scout;d;Scouting;Scouting-1;;01:42;p1;Drone;Natural" + PAD)
    assert vv.read_node(row).get_view()["properties"]["time"] == "01:42:00"


def test_link_view_key_order():
    _, links = vv.power_query("Battle-1;Battle-2;previous;next;Two consecutive battles;1" + PAD)
    view = vv.read_link(links[0])
    assert list(view) == ["name1", "name2", "direction", "node1", "node2", "description"]
    assert view == {
        "name1": "previous",
        "name2": "next",
        "direction": 1,
        "node1": "Battle-1",
        "node2": "Battle-2",
        "description": "Two consecutive battles",
    }


def test_build_view_key_order():
    view = vv.build_view("Game;d;Game;Game-1;;" + PAD, [{"nodeType": "Game"}], [], {"time": "time[h:m:s]"})
    assert list(view) == ["visuals", "detail", "dataTypes", "nodes", "links"]
