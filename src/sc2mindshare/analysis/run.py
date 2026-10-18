"""Run the ported Mindshare layer on a loaded replay (CR-011, T11).

``analyse(replay, support_root)`` does what the legacy ``execs/mindShareReplay.parseReplay`` did
between loading the replay and writing the CSV: it gives the replay the fork's object API
(``reader.fork_api.flavour_replay``), runs the detectors in their fixed order, and returns the
nodes and links in the order ``parseReplay`` handed them to the CSV exporter. Nothing is written.

The detectors still communicate through module globals (``detectors.basesDetector`` ...), so one
replay is analysed at a time; CR-011b replaces them with an AnalysisContext.
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
    d: Any = detectors  # the ported layer is untyped (module globals set by createDetectors)
    d.createDetectors(replay)
    nodes = (
        d.singlesDetector.nodes
        + d.battleDetector.battles
        + d.battleDetector.harrasmentNodes
        + d.simpleDetector.upgrades
        + d.simpleDetector.buildings
        + d.simpleDetector.initializations
        + d.simpleDetector.units
        + d.simpleDetector.stats
        + d.simpleDetector.abilities
        + d.simpleDetector.messages
        + d.simpleDetector.supplyBlocks
        + d.actionsDetector.excessEnergy
        + d.actionsDetector.injectDelays
        + d.actionsDetector.scouting
    )
    links = d.singlesDetector.links + d.battleDetector.links + d.simpleDetector.links
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
