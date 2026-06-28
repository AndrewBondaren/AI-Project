from dataclasses import dataclass

from app.application.worldData.generators.climate.climateAnchor import ClimateAnchorPoint


def _dist_sq(x1: int, y1: int, x2: int, y2: int) -> int:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


@dataclass(frozen=True)
class ClimateAnchorField:
    """Nearest climate anchor lookup in world surface grid space."""

    anchors: tuple[ClimateAnchorPoint, ...]

    def nearest(self, gx: int, gy: int) -> ClimateAnchorPoint | None:
        best      = None
        best_dist = float("inf")
        for anchor in self.anchors:
            d = _dist_sq(gx, gy, anchor.gx, anchor.gy)
            if d < best_dist:
                best_dist = d
                best      = anchor
        return best

    def is_empty(self) -> bool:
        return not self.anchors
