from app.application.jsonValidation import (
    city_sizes,
    district_templates as district_templates_registry,
    location_types,
)
from app.application.jsonValidation.settlementSizeResolve import resolve_settlement_size_key
from app.application.worldData.generators.coordinates import (
    cell_in_fine_rect,
    cell_in_surface_grid_rect,
    map_cell_fine_span,
    grid_dimension,
    settlement_grid_rect as _settlement_grid_rect,
    settlement_fine_rect as _settlement_fine_rect,
    settlement_origin_fine,
)
from app.application.worldData.generators.coordinates.types import (
    GridX,
    GridY,
    FineGridRect,
    FineX,
    FineY,
    FineZ,
    SurfaceGridRect,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.settlement.settlementFootprint import (
    resolve_settlement_footprint_multiplier,
)
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

# Re-export convert hub (legacy import path for settlement stack).
__all__ = [
    "cell_in_footprint_grid",
    "cell_in_footprint_fine",
    "map_cell_fine_span",
    "district_templates",
    "footprint_gate_coordinates",
    "footprint_gate_line_coords",
    "footprint_grid_rect",
    "footprint_fine_rect",
    "footprint_multiplier",
    "footprint_side_fine",
    "grid_dimension",
    "settlement_grid_rect",
    "settlement_fine_rect",
    "settlement_origin",
]


def _size_only_morphology() -> str:
    """Callers that only pass rank: city subtype from engine (not a metre table copy)."""
    settlement = WorldLocationTypeRegistry.canonical_engine().entry_for(
        WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
    )
    if settlement is None or not settlement.subtypes:
        raise RuntimeError("engine settlement subtypes missing")
    for sub in settlement.subtypes:
        if sub.required_structure_types:
            return sub.system_subtype
    return settlement.subtypes[0].system_subtype


def footprint_multiplier(world: World, system_city_size: str | None) -> float:
    sizes = city_sizes(world)
    key = resolve_settlement_size_key(
        sizes,
        system_city_size,
        world_uid=getattr(world, "world_uid", "") or "",
    )
    return resolve_settlement_footprint_multiplier(
        _size_only_morphology(),
        key,
        location_types(world),
        sizes,
    )


def footprint_side_fine(world: World, system_city_size: str | None) -> int:
    cs = map_cell_fine_span(world)
    mult = footprint_multiplier(world, system_city_size)
    return max(cs, int(round(mult * cs)))


def settlement_origin(settlement: NamedLocation) -> tuple[int, int, int]:
    origin = settlement_origin_fine(settlement)
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
    Все (x, y) settlement_gate на периметре footprint (fine grid).
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
    cell_m = map_cell_fine_span(world)
    size = system_city_size if system_city_size is not None else settlement.system_city_size
    side_m = footprint_side_fine(world, size)
    return _settlement_grid_rect(settlement, cell_m, side_m)


def footprint_grid_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
) -> tuple[int, int, int, int]:
    """
    Прямоугольник footprint в индексах global map grid [gx0, gx1) × [gy0, gy1).
    map_x/map_y поселения — WORLD_FINE_GRID; grid via settlement_grid_rect.

    Deprecated name — prefer settlement_grid_rect(...).as_tuple().
    """
    return settlement_grid_rect(world, settlement, system_city_size).as_tuple()


def cell_in_footprint_grid(
    x: int, y: int,
    gx0: int, gy0: int, gx1: int, gy1: int,
) -> bool:
    return cell_in_surface_grid_rect(
        x,
        y,
        SurfaceGridRect(
            gx0=GridX(gx0),
            gy0=GridY(gy0),
            gx1=GridX(gx1),
            gy1=GridY(gy1),
        ),
    )


def settlement_fine_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
):
    size = system_city_size if system_city_size is not None else settlement.system_city_size
    side_m = footprint_side_fine(world, size)
    return _settlement_fine_rect(settlement, side_m)


def footprint_fine_rect(
    world:             World,
    settlement:        NamedLocation,
    system_city_size:  str | None = None,
) -> tuple[int, int, int, int, int]:
    """Footprint в WORLD_FINE_GRID [ox, oy) × [x1, y1) и ground z.

    Deprecated name — prefer settlement_fine_rect(...).as_tuple().
    """
    return settlement_fine_rect(world, settlement, system_city_size).as_tuple()


def cell_in_footprint_fine(
    x: int, y: int,
    ox: int, oy: int, x1: int, y1: int,
) -> bool:
    return cell_in_fine_rect(
        x,
        y,
        FineGridRect(
            x0=FineX(ox),
            y0=FineY(oy),
            x1=FineX(x1),
            y1=FineY(y1),
            z=FineZ(0),
        ),
    )


def district_templates(world: World) -> list[DistrictTemplateEntry]:
    return district_templates_registry(world).root
