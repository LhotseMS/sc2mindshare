"""Console colouring as the legacy layer saw it: none.

The legacy layer coloured debug text with termcolor, which emits no codes when stdout is not a
terminal (always the case in its runs: the legacy CSV holds no escape codes). The port keeps the
calls and drops the colours, so no output depends on whether a terminal is attached.
"""

from __future__ import annotations

from typing import Any


def colored(text: Any, *_args: Any, **_kwargs: Any) -> str:
    return str(text)
