#!/usr/bin/env python3
"""The .pth line of this checkout's legacy environment (CR-007c, Morgan's N1 on the batch merges).

    scripts/py-env .venv-legacy/bin/python scripts/legacy_pth.py <checkout>   # prints the line

A .pth line that starts with ``import`` runs when Python starts, so the fork tree is chosen then, from the
checkout's layout as it is at that moment: ``<checkout>/legacy`` when ``legacy/sc2reader`` exists (from CR-009),
else the checkout itself (the fork at the root, before CR-009). A fixed path, as before, went stale when the
checkout moved between the two layouts (the batch merge of CR-007 hit it).
"""

from __future__ import annotations

import sys


def pth_line(checkout: str) -> str:
    """The one-line .pth entry for ``checkout``."""
    return (
        f"import os, sys; _c = {checkout!r}; "
        "sys.path.append(os.path.join(_c, 'legacy') if os.path.isdir(os.path.join(_c, 'legacy', 'sc2reader')) else _c)"
    )


if __name__ == "__main__":
    print(pth_line(sys.argv[1]))
