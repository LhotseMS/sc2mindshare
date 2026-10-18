"""The battle intervals for the screenshot tool (CR-016, T15): ``Intervals.csv`` and ``intervals.json``.

The battle detector produces the text the legacy code wrote to ``Intervals.csv`` (``Graph.intervals``):
the header ``start,end,id``, then one ``H:MM:SS,H:MM:SS,Battle-N`` row per battle (its start minus 2 s,
its end plus 2 s). ``execs/screenshotGame.py`` reads that file with pandas and parses the times as
``%H:%M:%S``, so ``intervals_csv`` writes the text unchanged. ``intervals_json`` gives the same intervals
with their times in seconds. Any other text is an error, never a guess.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

HEADER = "start,end,id"
_TIME = re.compile(r"(\d+):([0-5]\d):([0-5]\d)")


@dataclass(frozen=True)
class Interval:
    id: str
    start: str
    end: str
    start_seconds: int
    end_seconds: int


def _seconds(text: str, row: int) -> int:
    m = _TIME.fullmatch(text)
    if m is None:
        raise ValueError(f"intervals row {row}: {text!r} is not H:MM:SS")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def parse_intervals(text: str) -> tuple[Interval, ...]:
    if not text.endswith("\n"):
        raise ValueError("intervals text does not end with a newline")
    lines = text[:-1].split("\n")
    if lines[0] != HEADER:
        raise ValueError(f"intervals header is {lines[0]!r}, expected {HEADER!r}")
    out = []
    for row, line in enumerate(lines[1:], start=2):
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError(f"intervals row {row}: {line!r} does not have 3 fields")
        start, end, interval_id = fields
        interval = Interval(interval_id, start, end, _seconds(start, row), _seconds(end, row))
        if interval.end_seconds < interval.start_seconds:
            raise ValueError(f"intervals row {row}: {line!r} ends before it starts")
        out.append(interval)
    return tuple(out)


def intervals_csv(text: str) -> str:
    """The text for ``Intervals.csv``: the legacy text itself, once it has been checked."""
    parse_intervals(text)
    return text


def intervals_json(intervals: tuple[Interval, ...]) -> str:
    return json.dumps({"intervals": [asdict(i) for i in intervals]}, ensure_ascii=False, indent=1) + "\n"
