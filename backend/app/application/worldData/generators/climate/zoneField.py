from dataclasses import dataclass

from app.application.worldData.generators.coordinates import (
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

ZONE_LOCATION_TYPES = frozenset({"region", "kingdom", "empire", "duchy"})


def _dist_sq(x1: int, y1: int, x2: int, y2: int) -> int:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


@dataclass(frozen=True)
class ZoneClimateField:
    """Nearest zone anchor lookup in world surface grid space."""

    zone_centers: dict[tuple[int, int], NamedLocation]

    def nearest_zone(self, gx: int, gy: int) -> NamedLocation | None:
        best      = None
        best_dist = float("inf")
        for (cx, cy), loc in self.zone_centers.items():
            d = _dist_sq(gx, gy, cx, cy)
            if d < best_dist:
                best_dist = d
                best      = loc
        return best


def build_zone_field(
    world: World,
    locations: list[NamedLocation],
    cell_m: int,
) -> ZoneClimateField:
    anchors = [
        loc for loc in locations
        if loc.map_x is not None and loc.map_y is not None
        and loc.map_z is not None and not loc.is_mobile
    ]
    zone_list = [loc for loc in anchors if loc.system_location_type in ZONE_LOCATION_TYPES]
    zone_centers = {
        (
            meters_to_grid_x(zone.map_x, cell_m),
            meters_to_grid_y(zone.map_y, cell_m),
        ): zone
        for zone in zone_list
    }
    return ZoneClimateField(zone_centers=zone_centers)
