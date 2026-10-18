"""CR-045 (T3-5): SCommandManagerStateEvent and the retarget (SCmdUpdateTarget*) events.

Findings measured on s2protocol's raw events (an oracle independent of sc2reader), literals below:
- F3-010: every SCmdUpdateTargetPoint/Unit event is followed, in the same game loop and by the same
  player, by a SCommandManagerStateEvent with state 1 (2139/2139, 2567/2567, 977/977).
- m_state is 1 in every command-manager event of the three replays.
- The remaining ("unpaired") command-manager events have no established meaning yet.
"""

import pytest
from sc2mindshare.decoding import load
from sc2mindshare.decoding.command_manager import CommandActivity, command_activity, command_manager_states

EXPECTED = {
    "alcyone": {
        1: CommandActivity(commands=609, retargets=1473, paired_states=1473, unpaired_states=591, retargets_after_selection=490),
        2: CommandActivity(commands=471, retargets=666, paired_states=666, unpaired_states=101, retargets_after_selection=215),
    },
    "spores": {
        1: CommandActivity(commands=635, retargets=1312, paired_states=1312, unpaired_states=130, retargets_after_selection=459),
        2: CommandActivity(commands=728, retargets=1255, paired_states=1255, unpaired_states=475, retargets_after_selection=224),
    },
    "spine": {
        1: CommandActivity(commands=300, retargets=325, paired_states=325, unpaired_states=200, retargets_after_selection=89),
        2: CommandActivity(commands=301, retargets=652, paired_states=652, unpaired_states=125, retargets_after_selection=206),
    },
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_command_activity_per_player(replays, name):
    assert command_activity(load(replays[name]).replay) == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_retarget_has_its_paired_state(replays, name):
    """F3-010, supported on three replays."""
    for activity in command_activity(load(replays[name]).replay).values():
        assert activity.paired_states == activity.retargets


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_state_is_always_one(replays, name):
    assert command_manager_states(load(replays[name]).replay) == {1}


def test_spam_filtered_count_excludes_the_paired_states():
    a = CommandActivity(commands=10, retargets=4, paired_states=4, unpaired_states=3, retargets_after_selection=1)
    assert a.actions_without_paired_states == 17  # 10 + 4 + 3: each retarget counts once, not twice
