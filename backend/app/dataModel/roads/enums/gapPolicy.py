"""Wire gap fill policy for road/settlement layouts."""

from __future__ import annotations

from enum import StrEnum


class GapPolicy(StrEnum):
    CLIP = "clip"
    FILL = "fill"
    RANDOM = "random"
