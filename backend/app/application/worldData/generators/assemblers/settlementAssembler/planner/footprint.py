from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    DEFAULT_DISTRICT_TEMPLATES,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    DEFAULT_FOOTPRINT_MULTIPLIER,
)
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    grid_dimension,
    settlement_grid_rect as _settlement_grid_rect,
    settlement_meter_rect as _settlement_meter_rect,
    settlement_origin_m,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

# Re-export convert hub (legacy import path for settlement stack).
__all__ = [
    "cell_in_footprint_grid",
    "cell_in_footprint_meters",
    "cell_size_m",
    "district_templates",
    "footprint_gate_coordinates",
    "footprint_gate_line_coords",
    "footprint_grid_rect",
    "footprint_meter_rect",
    "footprint_multiplier",
    "footprint_side_m",
    "grid_dimension",
    "settlement_grid_rect",
    "settlement_meter_rect",
    "settlement_origin",
]


def footprint_multiplier(world: World, system_city_size: str | None) -> float:
    registry = world.city_size_registry or []
    for entry in registry:
        if entry.get("system_size") == system_city_size:
            mult = entry.get("footprint_multiplier")
            if mult is not None:
                return float(mult)
            radius = entry.get("radius")
            if radius is not None:
                side = max(1, int(radius) * 2 + 1)
                return float(side)
    return DEFAULT_FOOTPRINT_MULTIPLIER.get(system_city_size or "hamlet", 1.0)


def footprint_side_m(world: World, system_city_size: str | None) -> int:
    cs = cell_size_m(world)
    mult = footprint_multiplier(world, system_city_size)
    return max(cs, int(round(mult * cs)))


def settlement_origin(settlement: NamedLocation) -> tuple[int, int, int]:
    origin = settlement_origin_m(settlement)
    return origin.x, origin.y, origin.z


def footprint_gate_line_coords(origin: int, side_m: int, cell_m: int) -> list[int]:
    """Координаты settlement_gate вдоль одной оси (кратны cell_m + far edge)."""
    n_steps = max(1, round(side_m / cell_m))
    coords = [origin + i * cell_m for i in range(n_steps + 1)]
    end = origin + side_m
    if coords[-1] != end:
        coords.append(end)
    return coords


def footprint_gate_coordinates(
    origin_x: int,
    origin_y: int,
    side_m:   int,
    cell_m:   int,
) -> set[tuple[int, int]]:
    """
    Все (x, y) settlement_gate на периметре footprint (метры).
    Общий контракт для plan_city_street_grid и plan_settlement_barriers.
    """
    xs = footprint_gate_line_coords(origin_x, side_m, cell_m)
    ys = footprint_gate_line_coords(origin_y, side_m, cell_m)
    gates: set[tuple[int, int]] = set()
    for x in xs:
        gates.add((x, origin_y))
        gates.add((x, origin_y + side_m))
    for y in ys:
        gates.add((origin_x, y))
        gates.add((origin_x + side_m, y))
    return gates


def settlement_grid_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
):
    cell_m = cell_size_m(world)
    size = system_city_size if system_city_size is not None else settlement.system_city_size
    side_m = footprint_side_m(world, size)
    return _settlement_grid_rect(settlement, cell_m, side_m)


def footprint_grid_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
) -> tuple[int, int, int, int]:
    """
    Прямоугольник footprint в индексах global map grid [gx0, gy0) × [gy0, gy1).
    map_x/map_y поселения — метры; grid = origin // cell_size_m + offset.

    Deprecated name — prefer settlement_grid_rect(...).as_tuple().
    """
    return settlement_grid_rect(world, settlement, system_city_size).as_tuple()


def cell_in_footprint_grid(
    x: int, y: int,
    gx0: int, gy0: int, gx1: int, gy1: int,
) -> bool:
    return gx0 <= x < gx1 and gy0 <= y < gy1


def settlement_meter_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
):
    size = system_city_size if system_city_size is not None else settlement.system_city_size
    side_m = footprint_side_m(world, size)
    return _settlement_meter_rect(settlement, side_m)


def footprint_meter_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
) -> tuple[int, int, int, int, int]:
    """Footprint в метрах [ox, oy) × [x1, y1) и ground z.

    Deprecated name — prefer settlement_meter_rect(...).as_tuple().
    """
    return settlement_meter_rect(world, settlement, system_city_size).as_tuple()


def cell_in_footprint_meters(
    x: int, y: int,
    ox: int, oy: int, x1: int, y1: int,
) -> bool:
    return ox <= x < x1 and oy <= y < y1


def district_templates(world: World) -> list[dict]:
    registry = getattr(world, "district_template_registry", None)
    if registry:
        return list(registry)
    return list(DEFAULT_DISTRICT_TEMPLATES)
