import logging
import random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.settlementAssembler.planner.defaults import (
    CITY_SIZE_ORDER,
    CellZone,
    DISTRICT_TYPE_PREFERENCE,
)
from app.application.worldData.generators.utils.tierRegistry import (
    tier_at_least,
    tier_at_most,
)
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
    condition:   dict,
    origin_x:    int,
    origin_y:    int,
    width_m:     int,
    depth_m:     int,
    terrain_cells: list[MapCell] | None,
) -> bool:
    if not terrain_cells:
        return False
    required = set(condition.get("terrain_types") or [])
    min_count = int(condition.get("min_count") or 1)
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


def check_placement_conditions(
    template:      dict,
    settlement:    NamedLocation,
    skeleton:      CitySkeleton,
    origin_x:      int,
    origin_y:      int,
    width_m:       int,
    depth_m:       int,
    terrain_cells: list[MapCell] | None,
    placed_types:  dict[str, int],
    world:         World,
) -> bool:
    conditions = template.get("placement_conditions") or []
    if not conditions:
        return True

    max_per = template.get("max_per_city")
    dtype = template.get("district_type")
    if max_per is not None and placed_types.get(dtype, 0) >= max_per:
        return False

    registry = world.economic_tier_registry
    city_rank = _city_size_rank(skeleton.system_city_size)

    for cond in conditions:
        ctype = cond.get("type")
        if ctype == "min_city_size":
            if city_rank < _city_size_rank(cond.get("size")):
                return False
        elif ctype == "economic_tier_min":
            if not tier_at_least(registry, skeleton.economic_tier, cond.get("tier")):
                return False
        elif ctype == "economic_tier_max":
            if not tier_at_most(registry, skeleton.economic_tier, cond.get("tier")):
                return False
        elif ctype == "requires_district_type":
            if placed_types.get(cond.get("district_type"), 0) < 1:
                return False
        elif ctype == "excludes_district_type":
            if placed_types.get(cond.get("district_type"), 0) > 0:
                return False
        elif ctype == "adjacent_terrain":
            if not _check_adjacent_terrain(cond, origin_x, origin_y, width_m, depth_m, terrain_cells):
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
    candidates:    list[dict],
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
) -> dict | None:
    eligible = [
        t for t in candidates
        if check_placement_conditions(
            t, settlement, skeleton, origin_x, origin_y, width_m, depth_m,
            terrain_cells, placed_types, world,
        )
    ]
    if not eligible:
        logger.info(
            "DistrictTemplate select | cell=(%d,%d) zone=%s eligible=0 algorithm=none — skipped",
            cell_x, cell_y, _cell_zone(cell_x, cell_y, grid_n).value,
        )
        return None

    eligible.sort(
        key=lambda t: (
            -len(t.get("placement_conditions") or []),
            t.get("system_name", ""),
        )
    )

    zone = _cell_zone(cell_x, cell_y, grid_n)
    preferred = DISTRICT_TYPE_PREFERENCE[zone]
    algorithm = "fallback_random"
    matched_pref: str | None = None

    chosen: dict | None = None
    for pref in preferred:
        typed = [t for t in eligible if t.get("district_type") == pref]
        if typed:
            chosen = rng.choice(typed)
            algorithm = "position_preference"
            matched_pref = pref
            break

    if chosen is None:
        chosen = rng.choice(eligible)

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
        chosen.get("system_name", "?"),
        chosen.get("district_type", "?"),
        chosen.get("placement_conditions") or [],
        chosen.get("street_layout") or "grid",
        chosen.get("density") or "-",
        chosen.get("connections") or [],
    )
    return chosen


def slot_dimensions(
    template: dict,
    cell_m:   int,
    rng:      random.Random,
) -> tuple[int, int]:
    size_pct = template.get("size_pct") or {}
    w_range = size_pct.get("width") or [1.0, 1.0]
    d_range = size_pct.get("depth") or [1.0, 1.0]
    w_frac = rng.uniform(float(w_range[0]), float(w_range[1]))
    d_frac = rng.uniform(float(d_range[0]), float(d_range[1]))
    width_m = max(1, int(cell_m * w_frac))
    depth_m = max(1, int(cell_m * d_frac))
    logger.info(
        "DistrictSlot dimensions | template=%s algorithm=size_pct"
        " cell_m=%d width_frac=%.2f depth_frac=%.2f → %dx%d",
        template.get("system_name", "?"),
        cell_m,
        w_frac,
        d_frac,
        width_m,
        depth_m,
    )
    return width_m, depth_m
