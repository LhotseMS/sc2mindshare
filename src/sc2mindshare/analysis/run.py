"""Run the ported Mindshare layer on a loaded replay (CR-011, T11).

``analyse(replay, support_root)`` does what the legacy ``execs/mindShareReplay.parseReplay`` did
between loading the replay and writing the CSV: it gives the replay the fork's object API
(``reader.fork_api.flavour_replay``), runs the detectors in their fixed order, and returns the
nodes and links in the order ``parseReplay`` handed them to the CSV exporter. Nothing is written.

The detectors share an explicit ``AnalysisContext`` (CR-011b), not module globals. FileHandler's
support root and its pass-1 intervals are still class-level, so analyses run one at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.fileHandler import FileHandler
from sc2mindshare.reader.fork_api import flavour_replay


@dataclass(frozen=True)
class AnalysisResult:
    nodes: tuple[Any, ...]
    links: tuple[Any, ...]
    intervals: str | None  # the battle intervals text the legacy code wrote to Intervals.csv


def configure(support_root: str | Path) -> None:
    """Where the support files (unitsInfo.csv, upgradesInfo.csv, ImageTracking.csv) are read from."""
    FileHandler.SOURCE_FOLDER = str(support_root)


def analyse(replay: Any, support_root: str | Path) -> AnalysisResult:
    configure(support_root)
    FileHandler.intervals = None
    flavour_replay(replay)
    layer: Any = detectors  # the ported layer is untyped
    ctx: Any = layer.createDetectors(replay)
    nodes = (
        ctx.singles.nodes
        + ctx.battles.battles
        + ctx.battles.harrasmentNodes
        + ctx.simple.upgrades
        + ctx.simple.buildings
        + ctx.simple.initializations
        + ctx.simple.units
        + ctx.simple.stats
        + ctx.simple.abilities
        + ctx.simple.messages
        + ctx.simple.supplyBlocks
        + ctx.actions.excessEnergy
        + ctx.actions.injectDelays
        + ctx.actions.scouting
    )
    links = ctx.singles.links + ctx.battles.links + ctx.simple.links
    return AnalysisResult(tuple(nodes), tuple(links), FileHandler.intervals)


def legacy_csv(result: AnalysisResult) -> str:
    """The legacy events CSV for ``result`` (the layer's own CSVExporter), as a test oracle only.

    The product never writes the CSV (stream1-plan.md §3). The exporter is imported here, after
    the detectors, because the legacy modules import each other in a cycle that only resolves in
    the legacy entry point's order (detectors first).
    """
    from sc2mindshare.analysis.exports.exporter import CSVExporter

    exporter: Any = CSVExporter(list(result.nodes), list(result.links))
    return str(exporter.getExport())
