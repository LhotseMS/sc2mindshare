"""The analysis context: what the detectors share, passed explicitly (CR-011b).

The legacy layer kept its five detectors in module globals of ``detectors.py`` and reached them
from ``Battle``, ``BattleNode`` and ``UnitMoveCommand`` by module path, so the creation order was a
hidden contract and only one replay could be analysed per process. Here each detector gets the
context it belongs to, and the order is in ``detectors.createDetectors``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisContext:
    replay: Any
    bases: Any = None  # BaseDetector, built first (the battles and actions use it)
    actions: Any = None  # ActionsDetector
    simple: Any = None  # SimpleDetector
    battles: Any = None  # BattleDetector (expects the units nodes linked to the units)
    singles: Any = None  # SinglesDetector (uses the battles' heatmap ids)
    #: The layer fixes switched on, by ledger id (``analysis.fixes.LAYER_FIXES``); none for the bug-faithful run.
    fixes: frozenset[str] = field(default_factory=frozenset)
