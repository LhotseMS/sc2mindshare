"""CR-016 (T15): the battle intervals for the screenshot tool (Intervals.csv, intervals.json)."""

import json
import pathlib

import pytest

from sc2mindshare.export.intervals import Interval, intervals_csv, intervals_json, parse_intervals

GOLDEN = pathlib.Path(__file__).resolve().parents[1] / "golden" / "alcyone"


def test_the_legacy_text_is_parsed():
    text = (GOLDEN / "Intervals-1.csv").read_text(encoding="utf-8")
    intervals = parse_intervals(text)
    assert len(intervals) == 30
    assert intervals[0] == Interval("Battle-1", "0:02:00", "0:02:04", 120, 124)
    assert [i.id for i in intervals] == [f"Battle-{n}" for n in range(1, 31)]
    assert all(i.start_seconds <= i.end_seconds for i in intervals)


def test_intervals_csv_is_the_legacy_text_byte_for_byte():
    """screenshotGame.py reads Intervals.csv with pandas (columns start, end, id; %H:%M:%S times)."""
    text = (GOLDEN / "Intervals-1.csv").read_text(encoding="utf-8")
    assert intervals_csv(text) == text


def test_intervals_json():
    text = "start,end,id\n0:02:00,0:02:04,Battle-1\n1:00:08,1:00:20,Battle-2\n"
    doc = json.loads(intervals_json(parse_intervals(text)))
    assert doc == {
        "intervals": [
            {"id": "Battle-1", "start": "0:02:00", "end": "0:02:04", "start_seconds": 120, "end_seconds": 124},
            {"id": "Battle-2", "start": "1:00:08", "end": "1:00:20", "start_seconds": 3608, "end_seconds": 3620},
        ]
    }


def test_no_battles_is_an_empty_list():
    assert parse_intervals("start,end,id\n") == ()
    assert json.loads(intervals_json(())) == {"intervals": []}


@pytest.mark.parametrize(
    "text",
    [
        "",  # no header
        "end,start,id\n",  # another header
        "start,end,id\n0:02:00,0:02:04\n",  # a field missing
        "start,end,id\n0:02,0:02:04,Battle-1\n",  # not h:mm:ss
        "start,end,id\n-1 day, 23:59:58,0:00:02,Battle-1\n",  # a negative timedelta as Python prints it
        "start,end,id\n0:02:04,0:02:00,Battle-1\n",  # ends before it starts
        "start,end,id\n0:02:00,0:02:04,Battle-1",  # no final newline
    ],
)
def test_unknown_text_is_an_error_not_a_guess(text):
    with pytest.raises(ValueError):
        parse_intervals(text)
