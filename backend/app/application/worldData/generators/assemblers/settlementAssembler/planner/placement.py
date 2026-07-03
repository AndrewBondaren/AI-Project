import logging
import random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.jsonValidation import economic_tiers
from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    CITY_SIZE_ORDER,
    CellZone,
    DISTRICT_TYPE_PREFERENCE,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    check_district_economic_compat,
)
from app.application.worldData.generators.utils.tierRegistry import (
    tier_at_least,
    tier_at_most,
)
from app.dataModel.roads.enums.streetLayout import StreetLayout
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.placementCondition import PlacementCondition
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _city_size_rank(size: str | None) -> int:
    if not size:
        return 0
    try:
        return CITY_SIZE_ORDER.index(size)
    except ValueError:
        return 0


def _check_adjacent_terrain(
    condition:   PlacementCondition,
    origin_x:    int,
    origin_y:    int,
    width_m:     int,
    depth_m:     int,
    terrain_cells: list[MapCell] | None,
) -> bool:
    if not terrain_cells:
        return False
    required = set(condition.terrain_types or [])
    min_count = int(condition.min_count or 1)
    x0, x1 = origin_x - 1, origin_x + width_m
    y0, y1 = origin_y - 1, origin_y + depth_m
    count = 0
    for cell in terrain_cells:
        if cell.system_terrain not in required:
            continue
        on_west  = cell.x == x0 and y0 <= cell.y < y1
        on_east  = cell.x == x1 and y0 <= cell.y < y1
        on_south = cell.y == y0 and x0 <= cell.x < x1
        on_north = cell.y == y1 and x0 <= cell.x < x1
        if on_west or on_east or on_south or on_north:
            count += 1
    return count >= min_count


def template_specialization_key(template: DistrictTemplateEntry) -> tuple[int, int, int, int]:
    """
    Специализированные шаблоны выше общих (tz_city_generation §9.6).
    Больше условий / ограничений → выше приоритет.
    """
    conditions = template.placement_conditions or []
    return (
        len(conditions),
        1 if template.max_per_city is not None else 0,
        1 if template.required_structures else 0,
        1 if template.economic_tier_range is not None else 0,
    )


def check_placement_conditions(
    template:      DistrictTemplateEntry,
    settlement:    NamedLocation,
    skeleton:      CitySkeleton,
    origin_x:      int,
    origin_y:      int,
    width_m:       int,
    depth_m:       int,
    terrain_cells: list[MapCell] | None,
    placed_types:  dict[str, int],
    world:         World,
    cell_x:        int | None = None,
    cell_y:        int | None = None,
    grid_n:        int | None = None,
) -> bool:
    max_per = template.max_per_city
    dtype = template.district_type
    if max_per is not None and placed_types.get(dtype, 0) >= max_per:
        return False

    if not check_district_economic_compat(template, skeleton, world):
        return False

    conditions = template.placement_conditions or []
    if not conditions:
        return True

    registry = economic_tiers(world).root
    city_rank = _city_size_rank(skeleton.system_city_size)

    for cond in conditions:
        ctype = cond.type
        if ctype == "min_city_size":
            if city_rank < _city_size_rank(cond.size):
                return False
        elif ctype == "economic_tier_min":
            if not tier_at_least(registry, skeleton.economic_tier, cond.tier):
                return False
        elif ctype == "economic_tier_max":
            if not tier_at_most(registry, skeleton.economic_tier, cond.tier):
                return False
        elif ctype == "requires_district_type":
            if placed_types.get(cond.district_type, 0) < 1:
                return False
        elif ctype == "excludes_district_type":
            if placed_types.get(cond.district_type, 0) > 0:
                return False
        elif ctype == "adjacent_terrain":
            if not _check_adjacent_terrain(cond, origin_x, origin_y, width_m, depth_m, terrain_cells):
                return False
        elif ctype == "cell_zone":
            if cell_x is None or grid_n is None:
                return False
            required = cond.zone
            if _cell_zone(cell_x, cell_y or 0, grid_n).value != required:
                return False
        else:
            return False
    return True


def _cell_zone(cell_x: int, cell_y: int, grid_n: int) -> CellZone:
    cx = cy = grid_n // 2
    if cell_x == cx and cell_y == cy:
        return CellZone.CENTER
    on_edge = cell_x == 0 or cell_y == 0 or cell_x == grid_n - 1 or cell_y == grid_n - 1
    if on_edge:
        return CellZone.EDGE
    return CellZone.INNER


def select_district_template(
    candidates:    list[DistrictTemplateEntry],
    settlement:    NamedLocation,
    skeleton:      CitySkeleton,
    world:         World,
    origin_x:      int,
    origin_y:      int,
    width_m:       int,
    depth_m:       int,
    terrain_cells: list[MapCell] | None,
    placed_types:  dict[str, int],
    cell_x:        int,
    cell_y:        int,
    grid_n:        int,
    rng:           random.Random,
) -> DistrictTemplateEntry | None:
    eligible = [
        t for t in candidates
        if check_placement_conditions(
            t, settlement, skeleton, origin_x, origin_y, width_m, depth_m,
            terrain_cells, placed_types, world,
            cell_x, cell_y, grid_n,
        )
    ]
    if not eligible:
        logger.info(
            "DistrictTemplate select | cell=(%d,%d) zone=%s eligible=0 algorithm=none — skipped",
            cell_x, cell_y, _cell_zone(cell_x, cell_y, grid_n).value,
        )
        return None

    eligible.sort(
        key=lambda template: (template_specialization_key(template), template.system_name),
        reverse=True,
    )
    best_key = template_specialization_key(eligible[0])
    pool = [template for template in eligible if template_specialization_key(template) == best_key]

    zone = _cell_zone(cell_x, cell_y, grid_n)
    preferred = DISTRICT_TYPE_PREFERENCE[zone]
    algorithm = "fallback_random"
    matched_pref: str | None = None

    chosen: DistrictTemplateEntry | None = None
    for pref in preferred:
        typed = [template for template in pool if template.district_type == pref]
        if typed:
            chosen = rng.choice(typed)
            algorithm = "specialization+position"
            matched_pref = pref
            break

    if chosen is None:
        chosen = rng.choice(pool)
        algorithm = "specialization"

    logger.info(
        "DistrictTemplate select | cell=(%d,%d) zone=%s eligible=%d algorithm=%s"
        " matched_type=%s template=%s district_type=%s conditions=%s"
        " street_layout=%s density=%s connections=%s",
        cell_x,
        cell_y,
        zone.value,
        len(eligible),
        algorithm,
        matched_pref or "-",
        chosen.system_name,
        chosen.district_type,
        chosen.placement_conditions or [],
        chosen.street_layout or StreetLayout.GRID.value,
        chosen.density or "-",
        chosen.connections or [],
    )
    return chosen


def slot_dimensions(
    template: DistrictTemplateEntry,
    cell_m:   int,
    rng:      random.Random,
) -> tuple[int, int]:
    size_pct = template.size_pct
    w_range = [1.0, 1.0]
    d_range = [1.0, 1.0]
    if size_pct is not None:
        if size_pct.width is not None:
            w_range = [size_pct.width.min, size_pct.width.max]
        if size_pct.depth is not None:
            d_range = [size_pct.depth.min, size_pct.depth.max]
    w_frac = rng.uniform(float(w_range[0]), float(w_range[1]))
    d_frac = rng.uniform(float(d_range[0]), float(d_range[1]))
    width_m = max(1, int(cell_m * w_frac))
    depth_m = max(1, int(cell_m * d_frac))
    logger.info(
        "DistrictSlot dimensions | template=%s algorithm=size_pct"
        " cell_m=%d width_frac=%.2f depth_frac=%.2f → %dx%d",
        template.system_name,
        cell_m,
        w_frac,
        d_frac,
        width_m,
        depth_m,
    )
    return width_m, depth_m
