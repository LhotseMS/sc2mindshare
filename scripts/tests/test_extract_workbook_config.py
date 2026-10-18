"""Tests for scripts/extract_workbook_config.py against Stefan's workbook (CR-005, T05).

The workbook stays in <root>/MS SC/ (not committed, D7a). These tests skip with a
reason when it is absent, and check the committed config files against it.
"""

import importlib.util
import json
import os
import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("extract_workbook_config", _SCRIPTS / "extract_workbook_config.py")
assert _spec and _spec.loader
ewc = importlib.util.module_from_spec(_spec)
sys.modules["extract_workbook_config"] = ewc
_spec.loader.exec_module(ewc)

CHECKOUT = _SCRIPTS.parent
CONFIG = CHECKOUT / "src" / "sc2mindshare" / "config"


def _root() -> pathlib.Path:
    d = CHECKOUT
    while d != d.parent and not (d / ".tools").is_dir():
        d = d.parent
    return d


WORKBOOK = pathlib.Path(
    os.environ.get(
        "SC2MS_WORKBOOK",
        _root() / "MS SC" / "Alcyone LE__lilTiGGer_vs_blacksquall" / "Replay v1.4 - lilTiGGer_vs_blacksquall.xlsm",
    )
)
VBA_TRH = pathlib.Path(os.environ.get("SC2MS_VBA_TRH", _root() / ".scratch" / "plan" / "vba" / "MindshareTRH__1_2.bas"))
needs_workbook = pytest.mark.skipif(not WORKBOOK.is_file(), reason=f"workbook not found: {WORKBOOK}")


@pytest.fixture(scope="module")
def extracted():
    return ewc.extract(WORKBOOK)


@needs_workbook
def test_committed_config_equals_a_fresh_extraction(extracted):
    for name, value in extracted.items():
        assert json.loads((CONFIG / name).read_text(encoding="utf-8")) == value, name


@needs_workbook
def test_visuals_follow_the_sheet_row_by_row(extracted):
    visuals = extracted["visuals.json"]
    assert len(visuals) == 13
    assert visuals[0] == {"nodeType": "Battle", "shape": "circle", "borderColor": "#f5222d"}
    assert {"nodeType": "image", "shape": "canvas-image", "borderColor": "#edf0f9"} in visuals
    assert {"nodeType": "Comment", "shape": "rectangle", "borderColor": "d1ff20"} in visuals  # no '#', as in the sheet
    assert visuals[-1]["nodeType"] == "Supply Block"


@needs_workbook
def test_details_are_the_green_cells_only(extracted):
    by_type = {d["nodeType"]: d["properties"] for d in extracted["details.json"]}
    assert by_type["Building"] == ["time", "type"]
    assert by_type["Units"] == ["time", "total at time"]
    assert by_type["Stats"] == [
        "workers",
        "cur. Min",
        "cur. Gas",
        "col. rate Min",
        "col. rate Gas",
        "army Min",
        "army Gas",
        "eco Min",
    ]  # C7-J7 are green, B7 ("time") is not; K7-N7 lie past the VBA's B-J range
    assert by_type["Initiated"] == ["time", "subtype"]
    assert "Battle" not in by_type  # its cells have no fill


def test_data_types_keep_the_first_position_of_a_repeated_key():
    types = ewc.data_types()
    assert len(types) == 32  # 33 assignments, "workers" twice
    assert list(types)[16] == "workers"
    assert types["time"] == "time[h:m:s]" and types["supply dead"] == "dec"


@pytest.mark.skipif(not VBA_TRH.is_file(), reason=f"extracted VBA not found: {VBA_TRH}")
def test_data_types_source_matches_the_vba():
    pairs = ewc.parse_vba_data_types(VBA_TRH.read_text(encoding="utf-8", errors="replace"))
    assert tuple(pairs) == ewc.DATA_TYPES_SOURCE


class _FakeBook:
    def __init__(self, cells):
        self._cells = cells

    def cells(self, sheet):
        return self._cells


def test_a_theme_coloured_detail_cell_fails_loudly():
    book = _FakeBook({(2, 1): ("Battle", None), (2, 2): ("time", ewc.THEME_FILL)})
    with pytest.raises(ValueError, match="theme-coloured"):
        ewc.details(book)


def test_green_cells_are_details_and_others_are_not():
    book = _FakeBook({(2, 1): ("Units", None), (2, 2): ("time", ewc.DETAIL_GREEN), (2, 3): ("count", "FF0000")})
    assert ewc.details(book) == [{"nodeType": "Units", "properties": ["time"]}]
