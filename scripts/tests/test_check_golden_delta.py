"""Tests for scripts/check_golden_delta.py (QA design §5, break family F11)."""

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "check_golden_delta.py"
_spec = importlib.util.spec_from_file_location("check_golden_delta", _PATH)
assert _spec and _spec.loader
cgd = importlib.util.module_from_spec(_spec)
sys.modules["check_golden_delta"] = cgd
_spec.loader.exec_module(cgd)

BASE = {
    "nodes": [
        {"ID": "Battle-1", "type": "Battle", "name": "near A", "description": "d", "properties": {"time": "00:02:02"}},
        {"ID": "Battle-2", "type": "Battle", "name": "near A", "description": "d", "properties": {"time": "00:02:18"}},
        {"ID": "Stats-1", "type": "Stats", "name": "s", "properties": {"workers": 14}},
        {"ID": "Harrasment-0", "type": "Harrasment", "name": "h1", "properties": {}},
        {"ID": "Harrasment-0", "type": "Harrasment", "name": "h2", "properties": {}},
    ],
    "links": [],
}


def _write(path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _entry(old, changes, added=(), removed=()):
    return {
        "entry": "P1",
        "task": "CR-023",
        "golden": ["x"],
        "base_sha256": cgd.golden.sha256(old),
        "changes": changes,
        "added": list(added),
        "removed": list(removed),
    }


@pytest.fixture
def files(tmp_path):
    new = json.loads(json.dumps(BASE))
    for n in new["nodes"][:2]:
        n["name"] = "near B"
    return _write(tmp_path / "old.json", BASE), new, tmp_path


def test_a_regen_that_matches_its_entry_passes(files):
    old, new, tmp = files
    entry = _entry(old, [{"select": {"type": "Battle"}, "fields": ["name"], "count": 2}])
    assert cgd.check_delta(entry, old, _write(tmp / "new.json", new)) == []


def test_f11_an_unlisted_change_fails(files):
    old, new, tmp = files
    new["nodes"][2]["properties"]["workers"] = 15
    entry = _entry(old, [{"select": {"type": "Battle"}, "fields": ["name"], "count": 2}])
    assert cgd.check_delta(entry, old, _write(tmp / "new.json", new)) == ["unlisted change: Stats-1#1 properties.workers"]


def test_f11_a_listed_change_that_did_not_happen_fails(files):
    old, new, tmp = files
    entry = _entry(
        old,
        [
            {"select": {"type": "Battle"}, "fields": ["name"], "count": 2},
            {"select": {"ID": "Stats-1"}, "fields": ["properties.workers"], "count": 1},
        ],
    )
    problems = cgd.check_delta(entry, old, _write(tmp / "new.json", new))
    assert problems == ["listed but not changed: {'ID': 'Stats-1'} ['properties.workers']"]


def test_counts_must_be_equal(files):
    old, new, tmp = files
    entry = _entry(old, [{"select": {"type": "Battle"}, "fields": ["name"], "count": 30}])
    assert cgd.check_delta(entry, old, _write(tmp / "new.json", new)) == [
        "count differs for {'type': 'Battle'}: listed 30, changed 2"
    ]


def test_repeated_ids_are_selected_by_occurrence(files):
    old, _, tmp = files
    new = json.loads(json.dumps(BASE))
    new["nodes"][4]["name"] = "h2 fixed"
    ok = _entry(old, [{"select": {"ID": "Harrasment-0#2"}, "fields": ["name"], "count": 1}])
    wrong = _entry(old, [{"select": {"ID": "Harrasment-0#1"}, "fields": ["name"], "count": 1}])
    path = _write(tmp / "new.json", new)
    assert cgd.check_delta(ok, old, path) == []
    assert "unlisted change: Harrasment-0#2 name" in cgd.check_delta(wrong, old, path)


def test_c4_a_stale_base_fails(files):
    old, new, tmp = files
    entry = _entry(old, [{"select": {"type": "Battle"}, "fields": ["name"], "count": 2}])
    entry["base_sha256"] = "0" * 64
    assert cgd.check_delta(entry, old, _write(tmp / "new.json", new))[0].startswith("C4")


def test_entries_are_parsed_from_fenced_json_blocks():
    text = 'intro\n```json\n{"entry": "A1", "changes": []}\n```\nprose\n```json\n{"entry": "A2", "changes": []}\n```\n'
    assert list(cgd.entries(text)) == ["A1", "A2"]
    with pytest.raises(ValueError, match="twice"):
        cgd.entries(text + '```json\n{"entry": "A1"}\n```\n')


def _git(repo, *args):
    cmd = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args]
    subprocess.run(cmd, check=True, capture_output=True, env=cgd.git_env())  # never a caller's GIT_DIR


def _repo(tmp_path, entry_first):
    repo = tmp_path / "repo"
    (repo / "tests" / "golden").mkdir(parents=True)
    _git(repo, "init", "-q")
    changes = repo / "tests" / "golden" / "CHANGES.md"
    changes.write_text("# ledger\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    steps = [("CHANGES.md", '```json\n{"entry": "P1"}\n```\n'), ("g.json", "{}")]
    if not entry_first:
        steps.reverse()
    for name, content in steps:
        target = changes if name == "CHANGES.md" else repo / "tests" / "golden" / name
        target.write_text(target.read_text() + content if target.exists() and name == "CHANGES.md" else content)
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", name)
    return repo


def test_c1_entry_before_the_change_passes(tmp_path):
    assert cgd.check_git(_repo(tmp_path, entry_first=True), "HEAD~2..HEAD", "P1") == []


def test_c1_entry_after_the_change_fails(tmp_path):
    problems = cgd.check_git(_repo(tmp_path, entry_first=False), "HEAD~2..HEAD", "P1")
    assert problems == ["C1 the entry was not committed before the first golden or product change"]


def test_c2_changes_md_is_append_only(tmp_path):
    repo = _repo(tmp_path, entry_first=True)
    changes = repo / "tests" / "golden" / "CHANGES.md"
    changes.write_text(changes.read_text().replace("# ledger", "# rewritten"))
    _git(repo, "commit", "-qam", "rewrite")
    assert any(p.startswith("C2") for p in cgd.check_git(repo, "HEAD~3..HEAD", "P1"))


def test_c1_entry_and_change_in_the_same_commit_fails(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests" / "golden").mkdir(parents=True)
    _git(repo, "init", "-q")
    changes = repo / "tests" / "golden" / "CHANGES.md"
    changes.write_text("# ledger\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    changes.write_text(changes.read_text() + '```json\n{"entry": "P1"}\n```\n')
    (repo / "tests" / "golden" / "g.json").write_text("{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "entry and change together")
    assert cgd.check_git(repo, "HEAD~1..HEAD", "P1") == [
        "C1 the entry was not committed before the first golden or product change"
    ]


def test_c1_an_entry_that_existed_before_the_range_is_not_added_in_it(tmp_path):
    """C1 needs the entry to be added inside the range: an entry already in CHANGES.md at the base passes
    nothing, even when a commit in the range touches CHANGES.md before the golden change."""
    repo = _repo(tmp_path, entry_first=True)  # P1 added in HEAD~1
    changes = repo / "tests" / "golden" / "CHANGES.md"
    changes.write_text(changes.read_text() + '```json\n{"entry": "P2"}\n```\n')
    _git(repo, "commit", "-qam", "another entry")
    (repo / "tests" / "golden" / "g.json").write_text('{"a": 1}')
    _git(repo, "commit", "-qam", "a golden change")
    assert cgd.check_git(repo, "HEAD~2..HEAD", "P1") == ["C1 entry P1 not added in HEAD~2..HEAD"]
    assert cgd.check_git(repo, "HEAD~2..HEAD", "P2") == []


def test_c1_a_test_file_under_tests_golden_is_not_a_golden_change(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests" / "golden").mkdir(parents=True)
    _git(repo, "init", "-q")
    changes = repo / "tests" / "golden" / "CHANGES.md"
    changes.write_text("# ledger\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    (repo / "tests" / "golden" / "test_golden.py").write_text("def test_x():\n    pass\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "a test edit")
    changes.write_text(changes.read_text() + '```json\n{"entry": "P1"}\n```\n')
    _git(repo, "commit", "-qam", "entry")
    (repo / "tests" / "golden" / "g.json").write_text("{}")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "golden")
    assert cgd.check_git(repo, "HEAD~3..HEAD", "P1") == []
    # the harness module itself still counts: a golden.py edit before the entry fails C1
    (repo / "tests" / "golden" / "golden.py").write_text("X = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "harness")
    changes.write_text(changes.read_text() + '```json\n{"entry": "P3"}\n```\n')
    _git(repo, "commit", "-qam", "entry P3")
    assert cgd.check_git(repo, "HEAD~2..HEAD", "P3") == [
        "C1 the entry was not committed before the first golden or product change"
    ]


def test_a_set_git_dir_is_ignored(tmp_path, monkeypatch):
    """The 2026-10-18 incident: with GIT_DIR pointing at a real repository, the throwaway repositories'
    commits went there. Now the helpers and check_git ignore every GIT_* variable."""
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    subprocess.run(["git", "init", "-q", str(decoy)], check=True, capture_output=True, env=cgd.git_env())
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    repo = _repo(tmp_path, entry_first=True)
    assert (repo / ".git").is_dir()  # the test repository is a repository of its own
    assert cgd.check_git(repo, "HEAD~2..HEAD", "P1") == []
    log = subprocess.run(
        ["git", "-C", str(decoy), "log", "--oneline"], check=False, capture_output=True, text=True, env=cgd.git_env()
    )
    assert log.returncode != 0 and "does not have any commits" in log.stderr  # nothing reached the decoy
    assert "GIT_DIR" not in cgd.git_env() and "GIT_WORK_TREE" not in cgd.git_env()
