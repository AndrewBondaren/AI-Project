from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    DEFAULT_FOOTPRINT_MULTIPLIER,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    DEFAULT_DISTRICT_TEMPLATES,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def cell_size_m(world: World) -> int:
    map_settings = getattr(world, "map_settings", None) or {}
    if isinstance(map_settings, dict):
        val = map_settings.get("global_cell_size_m")
        if val is not None:
            return int(val)
    return int(world.map_cell_size_m or 3000)


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


def grid_dimension(side_m: int, cell_m: int) -> int:
    return max(1, round(side_m / cell_m))


def settlement_origin(settlement: NamedLocation) -> tuple[int, int, int]:
    return (
        settlement.map_x if settlement.map_x is not None else 0,
        settlement.map_y if settlement.map_y is not None else 0,
        settlement.map_z if settlement.map_z is not None else 0,
    )


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


def footprint_grid_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
) -> tuple[int, int, int, int]:
    """
    Прямоугольник footprint в индексах global map grid [gx0, gy0) × [gy0, gy1).
    map_x/map_y поселения — метры; grid = origin // cell_size_m + offset.
    """
    cell_m = cell_size_m(world)
    ox, oy, _ = settlement_origin(settlement)
    size = system_city_size if system_city_size is not None else settlement.system_city_size
    side_m = footprint_side_m(world, size)
    n = grid_dimension(side_m, cell_m)
    gx0 = ox // cell_m
    gy0 = oy // cell_m
    return gx0, gy0, gx0 + n, gy0 + n


def cell_in_footprint_grid(
    x: int, y: int,
    gx0: int, gy0: int, gx1: int, gy1: int,
) -> bool:
    return gx0 <= x < gx1 and gy0 <= y < gy1


def footprint_meter_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
) -> tuple[int, int, int, int, int]:
    """Footprint в метрах [ox, oy) × [x1, y1) и ground z."""
    ox, oy, gz = settlement_origin(settlement)
    size = system_city_size if system_city_size is not None else settlement.system_city_size
    side_m = footprint_side_m(world, size)
    return ox, oy, ox + side_m, oy + side_m, gz


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
