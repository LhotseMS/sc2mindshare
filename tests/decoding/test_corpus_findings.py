"""The corpus sweep's counting, pinned on a fixed subset of test_replays/ (CR-056, E1).

Literal results from the full sweep (`tools/decoding/corpus_findings.py`, 345 replays); one replay per
outcome: a contradiction of F3-009, of F3-016 and of F3-018, and a replay plain sc2reader cannot load.
"""

import pytest
from decoding_support import CHECKOUT, load_tool

sweep = load_tool("corpus_findings")

SUBSET = {
    "5.0.0.80949/2020-07-28 - (T)Ocrucius VS (Z)Rairden.SC2Replay": {
        "base_build": 80949,
        "parity": True,
        "F3-009": False,
        "F3-016": True,
        "F3-017": True,
        "F3-018": True,
        "F3-020": True,
    },
    "3.0.0.38215/third.SC2Replay": {
        "base_build": 38215,
        "parity": True,
        "F3-016": False,
        "F3-017": True,
        "F3-018": True,
    },
    "2.0.0.23925/Akilon Wastes.SC2Replay": {"base_build": 23925, "parity": True, "F3-017": True, "F3-018": False},
    "2.0.9.26147/bad_unit_ids_2.SC2Replay": {"could_not_load": "CorruptTrackerFileError"},
}


@pytest.fixture(scope="module")
def results():
    paths = [CHECKOUT / "test_replays" / rel for rel in SUBSET]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        pytest.fail("corpus replays missing: " + ", ".join(missing))  # committed in the checkout, never optional
    return {rel: sweep.check_replay(p) for rel, p in zip(SUBSET, paths, strict=True)}


@pytest.mark.parametrize("rel", sorted(SUBSET))
def test_outcome_per_finding(results, rel):
    row = results[rel]
    assert {k: v for k, v in row.items() if k not in ("path", "detail")} == SUBSET[rel]


def test_contradiction_details(results):
    rows = list(results.values())
    assert [(f, b, d) for f, b, _p, d in sweep.contradictions(rows)] == [
        ("F3-009", 80949, {"exact": 151, "ambiguous": 35}),
        ("F3-016", 38215, {"resume_minus_first_leave": -79}),
        ("F3-018", 23925, [67120825]),
    ]
    detail = results["5.0.0.80949/2020-07-28 - (T)Ocrucius VS (Z)Rairden.SC2Replay"]["detail"]["F3-020"]
    assert detail == {
        "not_alive": 0,
        "no_creator_after_loop_0": {"Broodling": 9},
        "other_owner": {"Changeling->ChangelingMarineShield": 3},
    }


def test_summary_counts(results):
    summary = sweep.summarise(results.values())
    assert summary["corpus"] == {"replays": 4, "could_not_load": 1}
    assert summary["parity"] == {"checked": 3, "holds": 3, "contradicts": 0, "not_applicable": 0}
    assert summary["F3-016"] == {"checked": 2, "holds": 1, "contradicts": 1, "not_applicable": 1}
    assert summary["F3-017"] == {"checked": 3, "holds": 3, "contradicts": 0, "not_applicable": 0}
    assert summary["F3-018"] == {"checked": 3, "holds": 2, "contradicts": 1, "not_applicable": 0}
    assert summary["F3-020"] == {"checked": 1, "holds": 1, "contradicts": 0, "not_applicable": 2}
