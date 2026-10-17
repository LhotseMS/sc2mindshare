"""Tests for scripts/package_ages.py (the 14-day package rule report)."""

import datetime as dt
import importlib.util
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "package_ages.py"
_spec = importlib.util.spec_from_file_location("package_ages", _PATH)
assert _spec and _spec.loader
package_ages = importlib.util.module_from_spec(_spec)
sys.modules["package_ages"] = package_ages  # dataclasses look the module up here
_spec.loader.exec_module(package_ages)

NOW = dt.datetime(2026, 10, 18, 12, 0, tzinfo=dt.UTC)


def test_parse_lock_reads_pins_and_skips_comments_and_blank_lines():
    text = "# frozen\n\npytest==8.4.2\nruff==0.13.0  # lint\nMarkupSafe==3.0.2\n"
    assert package_ages.parse_lock(text) == [
        ("pytest", "8.4.2"),
        ("ruff", "0.13.0"),
        ("MarkupSafe", "3.0.2"),
    ]


def test_parse_lock_rejects_unpinned_lines():
    with pytest.raises(ValueError, match="not pinned with ==: pytest>=8"):
        package_ages.parse_lock("pytest>=8\n")


def test_parse_lock_rejects_editable_and_url_lines():
    with pytest.raises(ValueError, match="not pinned with ==: -e"):
        package_ages.parse_lock("-e file:///x\n")


def test_newest_upload_uses_the_latest_file_of_the_release():
    release = {
        "urls": [
            {"upload_time_iso_8601": "2026-09-01T10:00:00.000000Z"},
            {"upload_time_iso_8601": "2026-09-03T08:30:00.123456Z"},
        ]
    }
    assert package_ages.newest_upload(release) == dt.datetime(2026, 9, 3, 8, 30, 0, 123456, tzinfo=dt.UTC)


def test_newest_upload_fails_when_a_release_has_no_files():
    with pytest.raises(ValueError, match="no uploaded files"):
        package_ages.newest_upload({"urls": []})


def test_report_marks_packages_younger_than_14_days():
    uploads = {
        ("old", "1.0"): dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        ("edge", "2.0"): dt.datetime(2026, 10, 4, 12, 0, tzinfo=dt.UTC),  # exactly 14 days
        ("almost", "2.5"): dt.datetime(2026, 10, 4, 12, 0, 1, tzinfo=dt.UTC),  # 13 days, 23:59:59
        ("young", "3.0"): dt.datetime(2026, 10, 10, tzinfo=dt.UTC),
    }
    rows = package_ages.report(
        [("old", "1.0"), ("edge", "2.0"), ("almost", "2.5"), ("young", "3.0")],
        fetch=lambda name, version: uploads[(name, version)],
        now=NOW,
    )
    assert [(r.name, r.version, r.age_days, r.too_young) for r in rows] == [
        ("old", "1.0", 290, False),
        ("edge", "2.0", 14, False),
        ("almost", "2.5", 13, True),
        ("young", "3.0", 8, True),
    ]


def test_format_rows_is_a_markdown_table_with_dates():
    rows = [package_ages.Row("old", "1.0", dt.datetime(2026, 1, 1, tzinfo=dt.UTC), 290, False)]
    assert package_ages.format_rows(rows) == (
        "| Package | Version | Uploaded (UTC) | Age (days) | OK |\n|---|---|---|---|---|\n| old | 1.0 | 2026-01-01 | 290 | yes |"
    )


def test_main_returns_1_when_any_package_is_too_young(tmp_path, capsys):
    lock = tmp_path / "x.lock"
    lock.write_text("young==3.0\n")
    code = package_ages.main(
        [str(lock)],
        fetch=lambda name, version: dt.datetime(2026, 10, 10, tzinfo=dt.UTC),
        now=NOW,
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "| young | 3.0 | 2026-10-10 | 8 | NO |" in out
    assert "1 package(s) younger than 14 days" in out


def test_main_returns_0_when_all_packages_are_old_enough(tmp_path, capsys):
    lock = tmp_path / "x.lock"
    lock.write_text("old==1.0\n")
    code = package_ages.main(
        [str(lock)],
        fetch=lambda name, version: dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        now=NOW,
    )
    assert code == 0
    assert "all 1 package(s) are at least 14 days old" in capsys.readouterr().out
