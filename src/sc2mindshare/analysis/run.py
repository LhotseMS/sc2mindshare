"""Run the ported Mindshare layer on a loaded replay (CR-011, T11).

``analyse(replay, support_root)`` does what the legacy ``execs/mindShareReplay.parseReplay`` did
between loading the replay and writing the CSV: it gives the replay the fork's object API
(``reader.fork_api.flavour_replay``), runs the detectors in their fixed order, and returns the
nodes and links in the order ``parseReplay`` handed them to the CSV exporter. Nothing is written.

The detectors share an explicit ``AnalysisContext`` (CR-011b), not module globals. FileHandler's
support root and its pass-1 intervals are still class-level, so analyses run one at a time.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sc2mindshare.analysis.detectors import detectors
from sc2mindshare.analysis.exposed import expose
from sc2mindshare.analysis.fileHandler import FileHandler
from sc2mindshare.analysis.fixes import LAYER_FIXES, check_layer_fixes
from sc2mindshare.domain.exposed import Exposed
from sc2mindshare.reader.fork_api import flavour_replay


@dataclass(frozen=True)
class AnalysisResult:
    nodes: tuple[Any, ...]
    links: tuple[Any, ...]
    intervals: str | None  # the battle intervals text the legacy code wrote to Intervals.csv
    #: The values stream 2 reads (CR-021, T20, P0-2): not in the default JSON; None when ``analyse`` was told not
    #: to compute them.
    exposed: Exposed | None = None
    #: The layer fixes this result was computed with (empty: the bug-faithful run). The bug-faithful
    #: outputs (``legacy_csv``, ``to_graph(..., fixes=())``) refuse a result with any (CR-023).
    fixes: frozenset[str] = frozenset()


def configure(support_root: str | Path) -> None:
    """Where the support files (unitsInfo.csv, upgradesInfo.csv, ImageTracking.csv) are read from."""
    FileHandler.SOURCE_FOLDER = str(support_root)


def analyse(
    replay: Any, support_root: str | Path, *, with_exposed: bool = True, fixes: Iterable[str] = LAYER_FIXES
) -> AnalysisResult:
    """Run the layer on ``replay``. **Consumes the replay**: its events, units and players are
    switched to their fork-flavoured classes in place (``flavour_replay``), so hand ``analyse`` a
    replay of its own (stream 3's decoders read theirs first, or load it a second time).

    ``with_exposed`` also computes ``AnalysisResult.exposed`` (``analysis.exposed.expose``, which
    reads the support tables' bytes too). On by default since CR-034: the current graph's build steps are
    built from it (D47a); it was off before so that nothing it does could break a build that did not ask
    for it (Morgan's G6 N1 on CR-021). ``fixes``: the layer fixes to apply, by ledger id
    (``analysis.fixes.LAYER_FIXES``, all of them by default); ``()`` for the bug-faithful run, the one
    the legacy CSV oracle and the frozen models describe."""
    applied = check_layer_fixes(fixes)
    configure(support_root)
    FileHandler.intervals = None
    flavour_replay(replay)
    layer: Any = detectors  # the ported layer is untyped
    ctx: Any = layer.createDetectors(replay, applied)
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
    exposed = expose(replay, ctx, Path(support_root)) if with_exposed else None
    return AnalysisResult(tuple(nodes), tuple(links), FileHandler.intervals, exposed, applied)


def legacy_csv(result: AnalysisResult) -> str:
    """The legacy events CSV for ``result`` (the layer's own CSVExporter), as a test oracle only.

    The product never writes the CSV (stream1-plan.md §3). The exporter is imported here, after
    the detectors, because the legacy modules import each other in a cycle that only resolves in
    the legacy entry point's order (detectors first).
    """
    if result.fixes:
        raise ValueError(
            f"the legacy CSV is a bug-faithful output; this result has layer fixes {sorted(result.fixes)} (analyse(..., fixes=()))"
        )
    from sc2mindshare.analysis.exports.exporter import CSVExporter

    exporter: Any = CSVExporter(list(result.nodes), list(result.links))
    return str(exporter.getExport())
