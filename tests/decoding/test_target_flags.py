"""CR-046 (T3-6): target-unit flags 111 versus 175 on unit-targeted commands and retargets.

Measured on s2protocol's raw events against the tracker stream (literals below):
- flags 111 (0b0110_1111): the target tag is a unit the tracker stream knows (840/840, 1159/1159, 415/415);
- flags 175 (0b1010_1111): the target tag never appears in the tracker stream (0/16, 0/54, 0/8), and the
  target is never the player's own unit.
Hypothesis F3-011 (supported on three replays; engine replay would confirm): 175 marks a target that is a
fog-of-war snapshot (the player's memory of a unit), whose tag is the snapshot's, not the unit's.
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.target_flags import TargetKind, classify, target_flag_summary

EXPECTED = {
    "alcyone": {
        (TargetKind.UNIT, "own"): 450,
        (TargetKind.UNIT, "neutral"): 252,
        (TargetKind.UNIT, "enemy"): 138,
        (TargetKind.SNAPSHOT, "neutral"): 9,
        (TargetKind.SNAPSHOT, "enemy"): 7,
    },
    "spores": {
        (TargetKind.UNIT, "own"): 483,
        (TargetKind.UNIT, "enemy"): 410,
        (TargetKind.UNIT, "neutral"): 266,
        (TargetKind.SNAPSHOT, "enemy"): 39,
        (TargetKind.SNAPSHOT, "neutral"): 15,
    },
    "spine": {
        (TargetKind.UNIT, "own"): 152,
        (TargetKind.UNIT, "enemy"): 135,
        (TargetKind.UNIT, "neutral"): 128,
        (TargetKind.SNAPSHOT, "neutral"): 5,
        (TargetKind.SNAPSHOT, "enemy"): 3,
    },
}
RESOLVED = {"alcyone": (840, 0), "spores": (1159, 0), "spine": (415, 0)}


def test_classify():
    assert classify(111) is TargetKind.UNIT
    assert classify(175) is TargetKind.SNAPSHOT
    assert classify(0) is TargetKind.UNKNOWN


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_flag_kind_by_target_relation(replays, name):
    summary = target_flag_summary(load(replays[name]).replay)
    assert summary.by_kind_and_relation == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_snapshot_tags_never_resolve_to_a_tracked_unit(replays, name):
    summary = target_flag_summary(load(replays[name]).replay)
    assert (summary.resolved[TargetKind.UNIT], summary.resolved[TargetKind.SNAPSHOT]) == RESOLVED[name]
    assert summary.unknown_flags == {}
