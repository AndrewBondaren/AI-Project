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


def district_templates(world: World) -> list[dict]:
    registry = getattr(world, "district_template_registry", None)
    if registry:
        return list(registry)
    return list(DEFAULT_DISTRICT_TEMPLATES)
