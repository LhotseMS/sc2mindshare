"""Tests for scripts/regen_golden.py: the non-frozen goldens are what the code makes now, byte for byte.

diff_json compares numbers as numbers (``2`` equals ``2.0``), so a change that only alters the text of
the document (the number format, key order, indentation) passes every semantic golden test. This test
compares the bytes: such a change fails here until the golden is regenerated under its CHANGES.md entry.
"""

import importlib.util
import json
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "regen_golden.py"
_spec = importlib.util.spec_from_file_location("regen_golden", _PATH)
assert _spec and _spec.loader
regen = importlib.util.module_from_spec(_spec)
sys.modules["regen_golden"] = regen
_spec.loader.exec_module(regen)


def _need_inputs():
    try:
        regen.golden.require(regen.root() / "MS SC" / "TimeImageTracking.csv", "TimeImageTracking.csv")
        regen.golden.require(regen._alcyone(), "Alcyone replay")
    except regen.golden.InputMissing as exc:
        if regen.golden.strict():
            pytest.fail(str(exc))
        pytest.skip(str(exc))


def test_the_regenerable_goldens_are_the_non_frozen_ones():
    assert set(regen.REGENERABLE) == {"G-VIEW-current.json", "G-SNAP-current-compressed.json", "G-SNAP-current-linear.json"}
    assert not set(regen.REGENERABLE) & regen.FROZEN


@pytest.mark.parametrize("name", sorted(regen.REGENERABLE))
def test_each_non_frozen_golden_is_what_the_code_makes_byte_for_byte(name):
    _need_inputs()
    assert regen.REGENERABLE[name]() == (regen.GOLDEN / name).read_text(encoding="utf-8"), (
        f"{name} differs from the current code's output: write a CHANGES.md entry, then "
        f"scripts/regen_golden.py --entry <id> --golden {name} --write"
    )


@pytest.mark.parametrize("name", sorted(regen.REGENERABLE))
def test_whole_numbers_have_no_decimal_part(name):
    """D7a A12 (VBA-JSON's number format): no number literal in a non-frozen golden is a whole number
    written with a decimal part. Strings such as "50.0" are text and are not looked at."""
    literals = []

    def keep(text):
        literals.append(text)
        return float(text)

    json.loads((regen.GOLDEN / name).read_text(encoding="utf-8"), parse_float=keep)
    assert literals and [t for t in literals if float(t).is_integer()] == []


def test_a_frozen_golden_is_never_regenerated(capsys):
    assert regen.main(["--entry", "H1", "--golden", "G-VIEW-1.json"]) == 2
    assert "frozen" in capsys.readouterr().out


def test_regeneration_needs_an_entry(capsys):
    assert regen.main(["--golden", "G-VIEW-current.json"]) == 2
    assert "--entry is required" in capsys.readouterr().out
    assert regen.main(["--entry", "NO-SUCH-ENTRY", "--golden", "G-VIEW-current.json"]) == 2
    assert "write the entry first" in capsys.readouterr().out


def test_an_entry_for_another_golden_is_refused(capsys):
    # H1 lists only G-VIEW-current.json
    assert regen.main(["--entry", "H1", "--golden", "G-SNAP-current-linear.json"]) == 2
    assert "does not list" in capsys.readouterr().out


def test_an_entry_already_applied_is_reported_and_passes(capsys, monkeypatch):
    """At the head, the golden is the code's output and no longer the entry's base (C4 would fail):
    regenerating reports that the entry is already applied and exits 0 without writing. (The history
    lookup is stubbed here, so the test also runs in a git archive copy; it is tested on its own below.)"""
    _need_inputs()
    monkeypatch.setattr(regen, "_was_in_history", lambda name, sha256, **kw: True)
    before = (regen.GOLDEN / "G-SNAP-current-linear.json").read_bytes()
    assert regen.main(["--entry", "A12-snap-linear", "--golden", "G-SNAP-current-linear.json", "--write"]) == 0
    assert "already applied" in capsys.readouterr().out
    assert (regen.GOLDEN / "G-SNAP-current-linear.json").read_bytes() == before


def test_a_live_copy_looks_up_the_frozen_goldens_history_too():
    """Addendum B: an entry moved to G-SNAP-current has its base in G-SNAP-1's history (the versions before
    the freeze), so 'already applied' searches both files; a golden that no freeze copied has one history."""
    assert regen.history_names("G-SNAP-current-linear.json") == ["G-SNAP-current-linear.json", "G-SNAP-1-linear.json"]
    assert regen.history_names("G-SNAP-current-compressed.json")[1] == "G-SNAP-1-compressed.json"
    assert regen.history_names("G-VIEW-current.json") == ["G-VIEW-current.json"]


def test_an_entry_never_applied_is_not_reported_as_applied(tmp_path, monkeypatch, capsys):
    """'Already applied' needs the entry's base to be in the golden's git history (Morgan's review): an
    entry whose base never was the golden goes to the C3/C4 check and fails it."""
    _need_inputs()
    fake = tmp_path / "CHANGES.md"
    fake.write_text(
        '```json\n{"entry": "X1", "task": "t", "golden": ["alcyone/G-SNAP-current-linear.json"], '
        '"base_sha256": "' + "0" * 64 + '", "changes": [], "added": [], "removed": []}\n```\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(regen, "CHANGES", fake)
    assert regen.main(["--entry", "X1", "--golden", "G-SNAP-current-linear.json"]) == 1
    out = capsys.readouterr().out
    assert "already applied" not in out and "C4" in out


def _git(repo, *args):
    import subprocess

    cmd = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args]
    subprocess.run(cmd, check=True, capture_output=True, env=regen.check_golden_delta.git_env())  # never a caller's GIT_DIR


def test_the_history_lookup(tmp_path):
    """True only for a sha256 some committed version of the golden had; False outside a repository."""
    import hashlib

    golden_file = tmp_path / "tests" / "golden" / "alcyone" / "G.json"
    golden_file.parent.mkdir(parents=True)
    _git(tmp_path, "init", "-q")
    golden_file.write_text("v1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "v1")
    golden_file.write_text("v2\n", encoding="utf-8")
    _git(tmp_path, "commit", "-qam", "v2")
    v1, v3 = hashlib.sha256(b"v1\n").hexdigest(), hashlib.sha256(b"v3\n").hexdigest()
    assert regen._was_in_history("G.json", v1, repo=tmp_path) is True
    assert regen._was_in_history("G.json", v3, repo=tmp_path) is False
    not_a_repo = tmp_path.parent / (tmp_path.name + "-plain")
    not_a_repo.mkdir()
    assert regen._was_in_history("G.json", v1, repo=not_a_repo) is False


def test_the_history_lookup_ignores_a_set_git_dir(tmp_path, monkeypatch, capsys):
    """A GIT_DIR naming another repository must not change which history is read (incident 2026-10-18)."""
    import hashlib

    golden_file = tmp_path / "real" / "tests" / "golden" / "alcyone" / "G.json"
    golden_file.parent.mkdir(parents=True)
    real = tmp_path / "real"
    _git(real, "init", "-q")
    golden_file.write_text("v1\n", encoding="utf-8")
    _git(real, "add", ".")
    _git(real, "commit", "-qm", "v1")
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git(decoy, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    assert regen._was_in_history("G.json", hashlib.sha256(b"v1\n").hexdigest(), repo=real) is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert regen._was_in_history("G.json", "0" * 64, repo=plain) is False
    assert "history unavailable (not a git repository): checking against the entry's base" in capsys.readouterr().out


# --- CR-035 (Kevin's call 14): spine's current goldens, and a golden that does not exist yet -----------------


def _new_golden_setup(tmp_path, monkeypatch, entry):
    """A fake ledger holding ``entry``, a replay folder with no golden yet, and a fixed regenerated text."""
    fake = tmp_path / "CHANGES.md"
    fake.write_text("```json\n" + json.dumps(entry) + "\n```\n", encoding="utf-8")
    monkeypatch.setattr(regen, "CHANGES", fake)
    monkeypatch.setattr(regen, "golden_dir", lambda replay="alcyone": tmp_path / replay)
    monkeypatch.setattr(regen.golden, "load_clock_map", lambda path: {})
    monkeypatch.setitem(regen.REGENERABLE, "G-VIEW-current.json", lambda replay="alcyone": '{"nodes": []}\n')
    (tmp_path / "spine").mkdir()
    return tmp_path / "spine" / "G-VIEW-current.json"


def _sha(text):
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_replays_are_alcyone_and_spine():
    assert set(regen.REPLAYS) == {"alcyone", "spine"}
    assert regen.replay_path("spine").name == "200k dmg spine crawler ZvP.SC2Replay"
    assert regen.golden_dir("spine") == regen.CHECKOUT / "tests" / "golden" / "spine"
    assert regen.golden_dir() == regen.GOLDEN


def test_a_new_golden_is_written_under_an_entry_that_changes_nothing(tmp_path, monkeypatch, capsys):
    entry = {
        "entry": "N1",
        "task": "t",
        "golden": ["spine/G-VIEW-current.json"],
        "base_sha256": _sha('{"nodes": []}\n'),
        "changes": [],
        "added": [],
        "removed": [],
    }
    target = _new_golden_setup(tmp_path, monkeypatch, entry)
    assert regen.main(["--entry", "N1", "--golden", "G-VIEW-current.json", "--replay", "spine"]) == 0
    assert not target.exists()  # checked, not written
    assert "new golden, matches entry N1" in capsys.readouterr().out
    assert regen.main(["--entry", "N1", "--golden", "G-VIEW-current.json", "--replay", "spine", "--write"]) == 0
    assert target.read_text(encoding="utf-8") == '{"nodes": []}\n'


def test_a_new_golden_whose_text_is_not_the_entrys_base_is_refused(tmp_path, monkeypatch, capsys):
    entry = {
        "entry": "N2",
        "task": "t",
        "golden": ["spine/G-VIEW-current.json"],
        "base_sha256": "0" * 64,
        "changes": [],
        "added": [],
        "removed": [],
    }
    target = _new_golden_setup(tmp_path, monkeypatch, entry)
    assert regen.main(["--entry", "N2", "--golden", "G-VIEW-current.json", "--replay", "spine", "--write"]) == 1
    assert "C4" in capsys.readouterr().out and not target.exists()


def test_a_new_goldens_entry_may_list_no_change(tmp_path, monkeypatch, capsys):
    entry = {
        "entry": "N3",
        "task": "t",
        "golden": ["spine/G-VIEW-current.json"],
        "base_sha256": _sha('{"nodes": []}\n'),
        "changes": [{"select": {"type": "Battle"}, "fields": ["name"], "count": 1}],
        "added": [],
        "removed": [],
    }
    target = _new_golden_setup(tmp_path, monkeypatch, entry)
    assert regen.main(["--entry", "N3", "--golden", "G-VIEW-current.json", "--replay", "spine", "--write"]) == 1
    assert "lists changes" in capsys.readouterr().out and not target.exists()


def test_an_alcyone_entry_does_not_regenerate_a_spine_golden(capsys):
    assert regen.main(["--entry", "H1", "--golden", "G-VIEW-current.json", "--replay", "spine"]) == 2
    assert "does not list spine/G-VIEW-current.json" in capsys.readouterr().out
