from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.climate.locations import static_map_anchors
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _bounds_dict(world: World) -> dict | None:
    raw = world.world_bounds
    if not isinstance(raw, dict):
        return None
    keys = ("x_min", "x_max", "y_min", "y_max")
    if not all(k in raw for k in keys):
        return None
    return raw


def grid_bbox_from_locations(
    world: World,
    locations: list[NamedLocation],
    padding: int,
) -> GridBBox | None:
    declared = _bounds_dict(world)
    if declared is not None:
        return GridBBox(
            x_min=int(declared["x_min"]),
            x_max=int(declared["x_max"]),
            y_min=int(declared["y_min"]),
            y_max=int(declared["y_max"]),
        )

    anchors = static_map_anchors(locations)
    if not anchors:
        return None
    cell_m = cell_size_m(world)
    positions = [
        (meters_to_grid_x(l.map_x, cell_m), meters_to_grid_y(l.map_y, cell_m))
        for l in anchors
    ]
    return GridBBox(
        x_min=min(p[0] for p in positions) - padding,
        x_max=max(p[0] for p in positions) + padding,
        y_min=min(p[1] for p in positions) - padding,
        y_max=max(p[1] for p in positions) + padding,
    )
