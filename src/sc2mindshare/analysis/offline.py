"""Stand-ins for the legacy image side of the layer (images and uploads are out of scope).

The ported detectors still import the media-API client and the heatmap generator, which only
the legacy "pass 2" uses (when an ``Intervals.csv`` exists). The new pipeline always runs pass 1,
so these stand-ins keep the constants the CSV text uses and refuse any real work.
"""

from __future__ import annotations

from typing import Any


class ImageUploader:
    RESOURCE_URL = "https://media.api.mindshareapp.com/media/resource"  # as in legacy imageUploader.py (python bug 6)
    SERVER_URL = "https://media.api.mindshareapp.com/media"

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(f"ImageUploader.{name}: media uploads are out of scope in the new pipeline")


def generateBattleHeatMap(*_args: Any, **_kwargs: Any) -> None:  # noqa: N802 (legacy name)
    raise RuntimeError("heatmaps are out of scope in the new pipeline")
