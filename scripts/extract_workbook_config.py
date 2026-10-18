#!/usr/bin/env python3
"""Extract the Mindshare export config from Stefan's workbook (CR-005, T05).

    scripts/py-env .venv/bin/python scripts/extract_workbook_config.py \
        "<root>/MS SC/Alcyone LE__lilTiGGer_vs_blacksquall/Replay v1.4 - lilTiGGer_vs_blacksquall.xlsm" \
        src/sc2mindshare/config

Writes the three parts of the workbook's JSON export that are configuration,
not replay data, exactly as the VBA builds them:

- ``visuals.json``: ``getVisualsCollection`` (Visuals sheet): rows 1 to the last
  row with a value in column A, every row whose column C is not empty, as
  ``{nodeType: A, shape: D, borderColor: C}``;
- ``details.json``: ``readNodes`` (Details sheet): rows 1 to the last row with a
  value in column A; per row the non-empty cells of columns B to J whose fill
  is RGB(0, 100, 0), as ``{nodeType: A, properties: [...]}``, rows without one
  left out (a theme-coloured fill in that range fails loudly). The VBA first runs
  ``updateTypesSheet "Details"``, which deletes rows of absent types and appends
  new types without fills; on today's data that changes no green cell, so the
  saved sheet is read as it is;
- ``data_types.json``: the hard-coded ``dataTypes`` dictionary of
  ``MindshareTRH__1_2.readNodes``, in insertion order (a repeated key keeps its
  first position, as a Scripting.Dictionary does).

Standard library only; reads the .xlsm (a zip) directly.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
DETAIL_GREEN = "006400"  # VBA rgb(0, 100, 0)
THEME_FILL = "<theme>"

# MindshareTRH__1_2.bas, readNodes: dataTypes("<name>") = "<type>", in source order.
DATA_TYPES_SOURCE: tuple[tuple[str, str], ...] = (
    ("player", "typelist"),
    ("time", "time[h:m:s]"),
    ("duration", "int"),
    ("type", "typelist"),
    ("count", "int"),
    ("total at time", "int"),
    ("supply", "dec"),
    ("dead", "dec"),
    ("p1 dead", "dec"),
    ("p2 dead", "dec"),
    ("supply dead", "dec"),
    ("end time", "time[h:m:s]"),
    ("combat", "bool"),
    ("queued", "bool"),
    ("minimap", "bool"),
    ("target", "string"),
    ("workers", "int"),
    ("Bank", "string"),
    ("Mining", "string"),
    ("Army", "string"),
    ("Eco", "string"),
    ("Tech", "string"),
    ("workers", "int"),
    ("cur. Min", "int"),
    ("cur. Gas", "int"),
    ("col. rate Min", "int"),
    ("col. rate Gas", "int"),
    ("army Min", "int"),
    ("army Gas", "int"),
    ("used Min", "int"),
    ("used Gas", "int"),
    ("tech Min", "int"),
    ("tech Gas", "int"),
)

_CELL_REF = re.compile(r"([A-Z]+)([0-9]+)")


def data_types(pairs: Sequence[tuple[str, str]] = DATA_TYPES_SOURCE) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, kind in pairs:
        out[name] = kind  # re-assignment keeps the first position, like Scripting.Dictionary
    return out


def parse_vba_data_types(bas_text: str) -> list[tuple[str, str]]:
    """The ``dataTypes("x") = "y"`` assignments of a VBA module, in order."""
    return re.findall(r'^\s*dataTypes\("([^"]+)"\)\s*=\s*"([^"]+)"', bas_text, re.MULTILINE)


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


class Workbook:
    def __init__(self, path: Path) -> None:
        self.zip = zipfile.ZipFile(path)
        self.shared = self._shared_strings()
        self.fill_of_style = self._style_fills()
        self.sheet_paths = self._sheet_paths()

    def _xml(self, name: str) -> ET.Element:
        return ET.fromstring(self.zip.read(name))

    def _shared_strings(self) -> list[str]:
        root = self._xml("xl/sharedStrings.xml")
        return ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in root.findall("m:si", NS)]

    def _style_fills(self) -> list[str | None]:
        root = self._xml("xl/styles.xml")
        fills: list[str | None] = []
        for fill in root.findall("m:fills/m:fill", NS):
            fg = fill.find("m:patternFill/m:fgColor", NS)
            rgb = fg.get("rgb") if fg is not None else None
            if rgb:
                fills.append(rgb[-6:].upper())
            elif fg is not None and (fg.get("theme") is not None or fg.get("indexed") not in (None, "64")):
                fills.append(THEME_FILL)  # a theme or palette colour: its RGB is not in the cell's style
            else:
                fills.append(None)
        return [fills[int(xf.get("fillId", "0"))] for xf in root.findall("m:cellXfs/m:xf", NS)]

    def _sheet_paths(self) -> dict[str, str]:
        rels = self._xml("xl/_rels/workbook.xml.rels")
        targets = {r.get("Id"): r.get("Target") for r in rels}
        book = self._xml("xl/workbook.xml")
        return {s.get("name", ""): "xl/" + str(targets[s.get(REL_NS)]) for s in book.findall("m:sheets/m:sheet", NS)}

    def cells(self, sheet: str) -> dict[tuple[int, int], tuple[str, str | None]]:
        """(row, column) -> (value as text, fill RGB or None) for every cell with a value."""
        root = self._xml(self.sheet_paths[sheet])
        out: dict[tuple[int, int], tuple[str, str | None]] = {}
        for c in root.iter(f"{{{NS['m']}}}c"):
            match = _CELL_REF.fullmatch(c.get("r", ""))
            if not match:
                continue
            v = c.find("m:v", NS)
            is_ = c.find("m:is", NS)
            if c.get("t") == "s" and v is not None:
                value = self.shared[int(v.text or "0")]
            elif c.get("t") == "inlineStr" and is_ is not None:
                value = "".join(t.text or "" for t in is_.iter(f"{{{NS['m']}}}t"))
            elif v is not None:
                value = v.text or ""
            else:
                continue
            style = int(c.get("s", "0"))
            fill = self.fill_of_style[style] if style < len(self.fill_of_style) else None
            out[(int(match.group(2)), _col_index(match.group(1)))] = (value, fill)
        return out


def _last_row_in_a(cells: dict[tuple[int, int], tuple[str, str | None]]) -> int:
    rows = [r for (r, c), (v, _) in cells.items() if c == 1 and v != ""]
    return max(rows) if rows else 0


def visuals(book: Workbook) -> list[dict[str, str]]:
    cells = book.cells("Visuals")
    out = []
    for row in range(1, _last_row_in_a(cells) + 1):
        color = cells.get((row, 3), ("", None))[0]
        if color != "":
            out.append(
                {
                    "nodeType": cells.get((row, 1), ("", None))[0],
                    "shape": cells.get((row, 4), ("", None))[0],
                    "borderColor": color,
                }
            )
    return out


def details(book: Workbook) -> list[dict[str, Any]]:
    cells = book.cells("Details")
    out: list[dict[str, Any]] = []
    for row in range(1, _last_row_in_a(cells) + 1):
        for col in range(2, 11):
            if (row, col) in cells and cells[(row, col)][0] != "" and cells[(row, col)][1] == THEME_FILL:
                raise ValueError(
                    f"Details row {row} column {col}: a theme-coloured fill; cannot tell whether it is RGB(0,100,0)"
                )
        props = [
            cells[(row, col)][0]
            for col in range(2, 11)
            if (row, col) in cells and cells[(row, col)][0] != "" and cells[(row, col)][1] == DETAIL_GREEN
        ]
        if props:
            out.append({"nodeType": cells.get((row, 1), ("", None))[0], "properties": props})
    return out


def extract(xlsm: Path) -> dict[str, Any]:
    book = Workbook(xlsm)
    return {"visuals.json": visuals(book), "details.json": details(book), "data_types.json": data_types()}


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main(argv: Sequence[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    xlsm, out = Path(argv[0]), Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, value in extract(xlsm).items():
        (out / name).write_text(dump(value), encoding="utf-8")
        print(f"wrote {out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
