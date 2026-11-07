"""CR-035 (AC8, AC9, AC11; S28): the shipped build order guides and the guide check.

One invalid fixture per P0-1 §7 rule, each rejected with exactly its player-facing message: P0-1 §7's for V1, V4
and V5, Iris's O-6 table (CR-035 Notes for Developer, "Answers to QA open points") for V2, V3 and V6-V11. A message
a player sees never says "benchmark". The fixtures are copies of a shipped guide with one thing broken.
"""

import copy
import json

import pytest

from sc2mindshare.analysis.guides import GuideError, check, check_library, library, load, parse

SHIPPED = (
    "pvz-gate-nexus-core-project",
    "pvz-stargate-opener-project",
    "zvp-12-pool-economic-liquipedia",
    "zvp-3-hatch-before-pool-liquipedia",
    "zvx-17-hatch-17-gas-17-pool-liquipedia",
)


@pytest.fixture(scope="module")
def guides():
    return {g.id: g for g in library()}


def _base():
    """The 12 Pool guide as JSON (a valid file to break)."""
    guide = next(g for g in library() if g.id == "zvp-12-pool-economic-liquipedia")
    from importlib.resources import files

    path = files("sc2mindshare") / "config" / "guides" / f"{guide.id}.benchmark.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_five_shipped_guides_load_and_pass_the_check(guides):
    assert tuple(sorted(guides)) == SHIPPED
    assert check_library(guides.values()) == []


def test_the_shipped_guides_as_read(guides):
    pool = guides["zvp-12-pool-economic-liquipedia"]
    assert (pool.name, pool.race, pool.vs, pool.patch, pool.horizon, len(pool.steps)) == (
        "12 Pool (economic)",
        "Zerg",
        "Protoss",
        None,
        180,
        8,
    )
    assert pool.steps[1].trigger == "@100% Spawning Pool" and pool.steps[1].count == 6
    assert pool.attribution == (
        'Liquipedia contributors, "12 Pool", revision 1812113, https://liquipedia.net/starcraft2/12_Pool'
    )
    hatch3 = guides["zvp-3-hatch-before-pool-liquipedia"]
    assert [(s.time, s.time_source) for s in hatch3.steps[1:3]] == [(52, "source"), (85, "source")]
    stargate = guides["pvz-stargate-opener-project"]
    assert stargate.steps[-1].items == ("Oracle", "VoidRay") and stargate.horizon == 300
    assert guides["pvz-gate-nexus-core-project"].steps[-1].optional is True
    assert guides["zvx-17-hatch-17-gas-17-pool-liquipedia"].vs == "Any"


def test_ac8_the_team_drafts_are_the_two_pvz_guides(guides):
    assert sorted(g.id for g in guides.values() if g.team_draft) == [
        "pvz-gate-nexus-core-project",
        "pvz-stargate-opener-project",
    ]
    assert all(g.attribution and "CC BY-SA 3.0" == g.source["licence"] for g in guides.values() if not g.team_draft)


def test_a_guide_matches_its_race_and_matchup_and_vs_any_matches_every_opponent(guides):
    assert guides["zvp-12-pool-economic-liquipedia"].matches("Zerg", "Protoss")
    assert not guides["zvp-12-pool-economic-liquipedia"].matches("Zerg", "Terran")
    assert not guides["pvz-stargate-opener-project"].matches("Zerg", "Protoss")
    assert guides["zvx-17-hatch-17-gas-17-pool-liquipedia"].matches("Zerg", "Terran")


def _broken(change):
    data = _base()
    change(data)
    return data


def _step(data, n):
    return data["steps"][n - 1]


@pytest.mark.parametrize(
    ("rule", "change", "message"),
    [
        ("V1 missing", lambda d: d.pop("race"), "`race` is missing"),
        ("V1 type", lambda d: d.update(name=12), "`name` must be text"),
        ("V1 date", lambda d: d.update(as_of="2020-02-30"), "`as_of` must be a date"),
        ("V3", lambda d: d.update(era="HotS"), "Only Legacy of the Void build orders are supported"),
        ("V4", lambda d: _step(d, 3).update(item="Extracter"), "Step 3: unknown item `Extracter`"),
        ("V4 race", lambda d: _step(d, 3).update(item="Pylon"), "Step 3: unknown item `Pylon`"),
        ("V5 both", lambda d: _step(d, 3).update(supply_range=[14, 15]), "Step 3: give one of supply, time or trigger"),
        (
            "V5 descending",
            lambda d: (_step(d, 3).pop("supply"), _step(d, 3).update(supply_range=[16, 14])),
            "Step 3: give one of supply, time or trigger",
        ),
        ("V5 none", lambda d: _step(d, 3).pop("supply"), "Step 3: give one of supply, time or trigger"),
        (
            "V6",
            lambda d: _step(d, 1).update(supply=9),
            "Step 1: supply below 12; is this a build order from before Legacy of the Void?",
        ),
        (
            "V7",
            lambda d: (
                _step(d, 3).update(time="1:30", time_source="source"),
                _step(d, 4).update(time="1:10", time_source="source"),
            ),
            "Step 4: its time is earlier than the step before it",
        ),
        (
            "V8",
            lambda d: d["steps"].insert(0, {"item": "Drone", "text": "12 Drones", "kind": "worker", "count": 12, "supply": 12}),
            "Step 1: the units you start with (workers, town hall, first Overlord) are not steps",
        ),
        ("V9", lambda d: _step(d, 3).update(time="1:30"), "Step 3: has a time but no `time_source`"),
        (
            "V10 spawning tool",
            lambda d: d.update(source={"kind": "spawningtool-link", "title": "12 Pool", "url": "https://x"}),
            "Spawning Tool build orders can only be linked, not copied in",
        ),
        (
            "V10 attribution",
            lambda d: d["source"].pop("attribution"),
            "`attribution` is required for a liquipedia source",
        ),
        (
            "V11 late",
            lambda d: d.update(horizon="15:01"),
            "`horizon` (how far into the game it goes) must be after the first step and no later than 15:00",
        ),
        (
            "V11 before the first step",
            lambda d: (_step(d, 1).update(time="0:20", time_source="source"), d.update(horizon="0:10")),
            "`horizon` (how far into the game it goes) must be after the first step and no later than 15:00",
        ),
    ],
)
def test_s28_each_rule_rejects_with_its_message(rule, change, message):
    data = _broken(change)
    assert check(data)[0] == message, rule
    with pytest.raises(GuideError) as raised:
        parse(data)
    assert str(raised.value) == message
    assert "benchmark" not in message.lower()


def test_s28_v2_two_guides_with_one_id():
    a = parse(_base())
    b = parse(_base())
    assert check_library([a, b]) == ["Two build order guides have the same id `zvp-12-pool-economic-liquipedia`"]


def test_a_spawning_tool_link_with_no_steps_is_valid_and_another_kind_needs_steps():
    link = _base()
    link.update(source={"kind": "spawningtool-link", "title": "12 Pool", "url": "https://x"}, steps=[])
    assert check(link) == []
    empty = _base()
    empty["steps"] = []
    assert check(empty) == ["`steps` is required for a liquipedia source"]


def test_a_file_that_is_not_json_is_unreadable(tmp_path):
    bad = tmp_path / "bad.benchmark.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(GuideError, match="it is not a JSON file"):
        load(bad)
    good = tmp_path / "good.benchmark.json"
    good.write_text(json.dumps(_base()), encoding="utf-8")
    assert load(good).id == "zvp-12-pool-economic-liquipedia" and load(good).file == "good.benchmark.json"


def test_a_guide_without_a_horizon_reaches_6_00():
    data = copy.deepcopy(_base())
    data.pop("horizon")
    assert parse(data).horizon == 360 and parse(data).window == 390
