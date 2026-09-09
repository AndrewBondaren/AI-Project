import logging
import random

from app.application.jsonValidation import (
    city_sizes,
    district_zone_preference,
    economic_tiers,
)
from app.application.jsonValidation.settlementSizeResolve import resolve_settlement_size_key
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    check_district_economic_compat,
)
from app.application.worldData.generators.utils.tierRegistry import (
    tier_at_least,
    tier_at_most,
)
from app.dataModel.settlement.district.cellZone import CellZone
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.placementCondition import (
    PlacementCondition,
    PlacementConditionType,
)
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

PlacedCounts = dict[tuple[str, str], int]


def placement_count_key(template: DistrictTemplateEntry) -> tuple[str, str]:
    return (template.district_type, (template.district_subtype or "").strip())


def _placed_type_count(placed: PlacedCounts, district_type: str | None) -> int:
    if not district_type:
        return 0
    return sum(count for (dtype, _), count in placed.items() if dtype == district_type)


def _check_adjacent_terrain(
    condition:   PlacementCondition,
    origin_x:    int,
    origin_y:    int,
    width_fine:     int,
    depth_fine:     int,
    terrain_cells: list[MapCell] | None,
) -> bool:
    if not terrain_cells:
        return False
    required = set(condition.terrain_types or [])
    min_adjacent = int(condition.min_adjacent_cells or 1)
    x0, x1 = origin_x - 1, origin_x + width_fine
    y0, y1 = origin_y - 1, origin_y + depth_fine
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
    return count >= min_adjacent


def template_constraint_key(template: DistrictTemplateEntry) -> tuple[int, int, int, int]:
    """
    More constrained drawings rank higher (tz_city_generation §9.6).
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
    width_fine:       int,
    depth_fine:       int,
    terrain_cells: list[MapCell] | None,
    placed_types:  PlacedCounts,
    world:         World,
    cell_x:        int | None = None,
    cell_y:        int | None = None,
    grid_n:        int | None = None,
) -> bool:
    max_per = template.max_per_city
    key = placement_count_key(template)
    if max_per is not None and placed_types.get(key, 0) >= max_per:
        return False

    if not check_district_economic_compat(template, skeleton, world):
        return False

    conditions = template.placement_conditions or []
    if not conditions:
        return True

    registry = economic_tiers(world).root
    sizes = city_sizes(world)
    world_uid = getattr(world, "world_uid", "") or ""
    city_rank = sizes.rank(
        resolve_settlement_size_key(sizes, skeleton.system_city_size, world_uid=world_uid),
    )

    for cond in conditions:
        try:
            ctype = (
                cond.type
                if isinstance(cond.type, PlacementConditionType)
                else PlacementConditionType(cond.type)
            )
        except ValueError:
            return False
        if ctype is PlacementConditionType.MIN_SETTLEMENT_SIZE:
            min_rank = sizes.rank(
                resolve_settlement_size_key(sizes, cond.size, world_uid=world_uid),
            )
            if city_rank < min_rank:
                return False
        elif ctype is PlacementConditionType.ECONOMIC_TIER_MIN:
            if not tier_at_least(registry, skeleton.economic_tier, cond.tier):
                return False
        elif ctype is PlacementConditionType.ECONOMIC_TIER_MAX:
            if not tier_at_most(registry, skeleton.economic_tier, cond.tier):
                return False
        elif ctype is PlacementConditionType.REQUIRES_DISTRICT_TYPE:
            if _placed_type_count(placed_types, cond.district_type) < 1:
                return False
        elif ctype is PlacementConditionType.EXCLUDES_DISTRICT_TYPE:
            if _placed_type_count(placed_types, cond.district_type) > 0:
                return False
        elif ctype is PlacementConditionType.ADJACENT_TERRAIN:
            if not _check_adjacent_terrain(cond, origin_x, origin_y, width_fine, depth_fine, terrain_cells):
                return False
        elif ctype is PlacementConditionType.CELL_ZONE:
            if cell_x is None or grid_n is None:
                return False
            required = cond.zone
            if _cell_zone(cell_x, cell_y or 0, grid_n) != required:
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


def cell_type_score(
    cell_x: int,
    cell_y: int,
    grid_n: int,
    district_type: str,
    world: World,
) -> tuple[int, int, int, int]:
    """Lower is better: preferred zone rank, then row-major."""
    zone = _cell_zone(cell_x, cell_y, grid_n)
    preferred = district_zone_preference(world).types_for(zone)
    try:
        return (0, preferred.index(district_type), cell_y, cell_x)
    except ValueError:
        return (1, len(preferred), cell_y, cell_x)


def pick_template_for_ref(
    candidates: list[DistrictTemplateEntry],
    ref: TypicalDistrictRef,
    settlement: NamedLocation,
    skeleton: CitySkeleton,
    world: World,
    origin_x: int,
    origin_y: int,
    width_fine: int,
    depth_fine: int,
    terrain_cells: list[MapCell] | None,
    placed_types: PlacedCounts,
    cell_x: int,
    cell_y: int,
    grid_n: int,
    rng: random.Random,
) -> DistrictTemplateEntry | None:
    pin = (ref.system_name or "").strip()
    if pin:
        pinned = next((template for template in candidates if template.system_name == pin), None)
        if pinned is None:
            logger.warning(
                "District pin missing | cell=(%d,%d) system_name=%s — pool of type",
                cell_x, cell_y, pin,
            )
        elif not ref.matches_template(pinned):
            logger.warning(
                "District pin type mismatch | cell=(%d,%d) system_name=%s — pool of type",
                cell_x, cell_y, pin,
            )
        elif check_placement_conditions(
            pinned, settlement, skeleton, origin_x, origin_y, width_fine, depth_fine,
            terrain_cells, placed_types, world, cell_x, cell_y, grid_n,
        ):
            return pinned
        else:
            return None
    pool = [template for template in candidates if ref.matches_template(template)]
    eligible = [
        template for template in pool
        if check_placement_conditions(
            template, settlement, skeleton, origin_x, origin_y, width_fine, depth_fine,
            terrain_cells, placed_types, world, cell_x, cell_y, grid_n,
        )
    ]
    if not eligible:
        return None
    return _pick_constrained(eligible, rng)


def select_district_template(
    candidates:    list[DistrictTemplateEntry],
    settlement:    NamedLocation,
    skeleton:      CitySkeleton,
    world:         World,
    origin_x:      int,
    origin_y:      int,
    width_fine:       int,
    depth_fine:       int,
    terrain_cells: list[MapCell] | None,
    placed_types:  PlacedCounts,
    cell_x:        int,
    cell_y:        int,
    grid_n:        int,
    rng:           random.Random,
    typical_district_types: tuple[str, ...] | None = None,
    unspecialized_only: bool = False,
) -> DistrictTemplateEntry | None:
    zone = _cell_zone(cell_x, cell_y, grid_n)
    if typical_district_types:
        return _select_by_recipe(
            candidates, settlement, skeleton, world,
            origin_x, origin_y, width_fine, depth_fine,
            terrain_cells, placed_types,
            cell_x, cell_y, grid_n, rng, zone, typical_district_types,
            unspecialized_only=unspecialized_only,
        )

    eligible = [
        t for t in candidates
        if not (t.district_subtype or "").strip()
        and check_placement_conditions(
            t, settlement, skeleton, origin_x, origin_y, width_fine, depth_fine,
            terrain_cells, placed_types, world,
            cell_x, cell_y, grid_n,
        )
    ]
    if not eligible:
        logger.info(
            "DistrictTemplate select | cell=(%d,%d) zone=%s eligible=0 algorithm=none — skipped",
            cell_x, cell_y, zone.value,
        )
        return None

    eligible.sort(
        key=lambda template: (template_constraint_key(template), template.system_name),
        reverse=True,
    )
    best_key = template_constraint_key(eligible[0])
    pool = [template for template in eligible if template_constraint_key(template) == best_key]

    preferred = district_zone_preference(world).types_for(zone)
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
        chosen.street_layout,
        chosen.density or "-",
        chosen.connections or [],
    )
    return chosen


def _pick_constrained(
    eligible: list[DistrictTemplateEntry],
    rng: random.Random,
) -> DistrictTemplateEntry:
    eligible.sort(
        key=lambda template: (template_constraint_key(template), template.system_name),
        reverse=True,
    )
    best_key = template_constraint_key(eligible[0])
    pool = [template for template in eligible if template_constraint_key(template) == best_key]
    return rng.choice(pool)


def _select_by_recipe(
    candidates: list[DistrictTemplateEntry],
    settlement: NamedLocation,
    skeleton: CitySkeleton,
    world: World,
    origin_x: int,
    origin_y: int,
    width_fine: int,
    depth_fine: int,
    terrain_cells: list[MapCell] | None,
    placed_types: PlacedCounts,
    cell_x: int,
    cell_y: int,
    grid_n: int,
    rng: random.Random,
    zone: CellZone,
    typical_district_types: tuple[str, ...],
    *,
    unspecialized_only: bool = False,
) -> DistrictTemplateEntry | None:
    typical = set(typical_district_types)
    preferred = district_zone_preference(world).types_for(zone)
    for pref in preferred:
        if pref not in typical:
            continue
        typed = [template for template in candidates if template.district_type == pref]
        if unspecialized_only:
            typed = [
                template for template in typed
                if not (template.district_subtype or "").strip()
            ]
        eligible = [
            template for template in typed
            if check_placement_conditions(
                template, settlement, skeleton, origin_x, origin_y, width_fine, depth_fine,
                terrain_cells, placed_types, world,
                cell_x, cell_y, grid_n,
            )
        ]
        if not eligible:
            continue
        chosen = _pick_constrained(eligible, rng)
        logger.info(
            "DistrictTemplate select | cell=(%d,%d) zone=%s eligible=%d algorithm=recipe"
            " matched_type=%s template=%s district_type=%s district_subtype=%s conditions=%s"
            " street_layout=%s density=%s connections=%s",
            cell_x,
            cell_y,
            zone.value,
            len(eligible),
            pref,
            chosen.system_name,
            chosen.district_type,
            chosen.district_subtype or "-",
            chosen.placement_conditions or [],
            chosen.street_layout,
            chosen.density or "-",
            chosen.connections or [],
        )
        return chosen

    logger.warning(
        "No district type in settlement recipe ∩ zone | cell=(%d,%d) zone=%s typical=%s — skipped",
        cell_x, cell_y, zone.value, list(typical_district_types),
    )
    return None


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
    width_fine = max(1, int(cell_m * w_frac))
    depth_fine = max(1, int(cell_m * d_frac))
    logger.info(
        "DistrictSlot dimensions | template=%s algorithm=size_pct"
        " cell_m=%d width_frac=%.2f depth_frac=%.2f → %dx%d",
        template.system_name,
        cell_m,
        w_frac,
        d_frac,
        width_fine,
        depth_fine,
    )
    return width_fine, depth_fine
