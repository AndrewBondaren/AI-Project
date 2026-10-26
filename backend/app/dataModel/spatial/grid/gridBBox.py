"""Inclusive sampled grid bounds — GEO-1 PC-0G1 shared value contract."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GridBBox:
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    def diagonal(self) -> float:
        w = max(1, self.x_max - self.x_min)
        h = max(1, self.y_max - self.y_min)
        return math.hypot(w, h)
