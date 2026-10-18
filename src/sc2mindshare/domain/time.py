"""Game time as a number: a count of game loops (CR-022, T21; TD-30).

The domain carries every time as a ``GameTime``; only ``export/`` turns one into text. The real
second is computed with integers: 22.4 loops per second is 112 / 5, so ``seconds`` is exact for
every loop and equals the legacy ``int(frame / 22.4)`` for every loop of a game (TD-26, proven over
twelve hours of loops in tests/analysis/test_time.py), so an item at a window boundary stays in the
window the legacy layer put it in.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Game loops per real second (LotV "faster").
LOOPS_PER_SECOND = 22.4
_LOOPS, _PER_SECONDS = 112, 5  # LOOPS_PER_SECOND as a fraction


@dataclass(frozen=True, order=True)
class GameTime:
    """A moment of the game in loops since 0:00, signed: a main base built before the game starts
    at a negative time (B9)."""

    loops: int

    def __post_init__(self) -> None:
        if type(self.loops) is not int:
            raise TypeError(f"GameTime needs a whole number of loops, not {self.loops!r}")

    @classmethod
    def from_seconds(cls, seconds: int) -> GameTime:
        """The first loop of the whole real second ``seconds``, so ``from_seconds(s).seconds == s``.

        The legacy layer knows its times only as whole seconds; until its detectors are rewritten, a
        time read from it is the first loop of its second."""
        return cls(-((-_LOOPS * seconds) // _PER_SECONDS))

    @property
    def seconds(self) -> int:
        """The whole real second this loop falls in, floored (so -0.5 s is second -1)."""
        return (_PER_SECONDS * self.loops) // _LOOPS
