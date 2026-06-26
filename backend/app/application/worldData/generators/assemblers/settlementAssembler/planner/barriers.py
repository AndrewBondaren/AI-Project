"""Settlement perimeter barriers — tz_locations barrier_template_registry."""

from __future__ import annotations

import logging
from random import Random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.settlementAssembler.planner.barrierDefaults import (
    lookup_barrier_template,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    cell_size_m,
    footprint_side_m,
    settlement_origin,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import (
    footprint_gate_coordinates,
)
from app.application.worldData.generators.road.blockSize import block_size_for_density
from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.application.worldData.generators.utils.tierRegistry import tier_rank
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

_WALLED_SIZES = frozenset({"town", "city", "metropolis", "megalopolis"})
_NO_WALL_SIZES = frozenset({"hamlet", "village"})


def should_have_settlement_wall(
    settlement: NamedLocation,
    skeleton:   CitySkeleton,
    rng:        Random,
) -> bool:
    size = skeleton.system_city_size or settlement.system_city_size or "hamlet"
    if size in _NO_WALL_SIZES:
        logger.info(
            "plan_settlement_barriers | settlement=%s size=%s — no wall (size policy)",
            settlement.location_uid,
            size,
        )
        return False
    if size not in _WALLED_SIZES:
        return False
    if size in ("city", "metropolis", "megalopolis"):
        return True
    return rng.random() < 0.75


def pick_barrier_template_type(
    world:    World,
    skeleton: CitySkeleton,
    rng:      Random,
) -> str | None:
    registry = world.economic_tier_registry or []
    tier = skeleton.economic_tier or "standard"
    rank = tier_rank(registry, tier) if registry else 2

    if rank <= tier_rank(registry, "basic") if registry else False:
        return "wooden_fence"
    if rank >= tier_rank(registry, "quality") if registry else False:
        return "city_wall"
    size = skeleton.system_city_size or "town"
    if size in ("city", "metropolis", "megalopolis"):
        return "city_wall"
    return "stone_fence"


def _pick_template_material(
    world:    World,
    template: dict,
    skeleton: CitySkeleton,
    rng:      Random,
) -> str:
    pick_from = (template.get("wall_material") or {}).get("pick_from") or []
    if pick_from:
        return rng.choice(pick_from)
    return resolve_material(
        world, "wall", skeleton.economic_tier, rng, default="stone",
    )


def _perimeter_ring(
    origin_x: int,
    origin_y: int,
    side_m:   int,
    step_m:   int,
) -> list[tuple[int, int]]:
    """Точки периметра footprint (метры), шаг step_m."""
    x0, y0 = origin_x, origin_y
    x1, y1 = origin_x + side_m, origin_y + side_m
    step = max(1, step_m)
    points: list[tuple[int, int]] = []

    for x in range(x0, x1 + 1, step):
        points.append((x, y0))
        if y1 != y0:
            points.append((x, y1))
    for y in range(y0 + step, y1, step):
        points.append((x0, y))
        if x1 != x0:
            points.append((x1, y))

    # углы при крупном шаге
    for corner in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if corner not in points:
            points.append(corner)

    return points


def plan_settlement_barriers(
    world:      World,
    settlement: NamedLocation,
    skeleton:   CitySkeleton,
    rng:        Random,
) -> list[MapCell]:
    """
    Perimeter wall/gate map_cells в метрах на z=ground_z.
    Проёмы — на координатах settlement_gate (как plan_city_street_grid).
    """
    if not should_have_settlement_wall(settlement, skeleton, rng):
        return []

    template_type = pick_barrier_template_type(world, skeleton, rng)
    template = lookup_barrier_template(world, template_type) if template_type else None
    if template is None:
        logger.warning(
            "plan_settlement_barriers | settlement=%s template=%s not found",
            settlement.location_uid,
            template_type,
        )
        return []

    ox, oy, gz = settlement_origin(settlement)
    side_m = footprint_side_m(world, skeleton.system_city_size)
    cell_m = cell_size_m(world)
    step_m = block_size_for_density(skeleton.settlement_density)

    gate_coords = footprint_gate_coordinates(ox, oy, side_m, cell_m)
    ring = set(_perimeter_ring(ox, oy, side_m, step_m))
    ring |= gate_coords

    material = _pick_template_material(world, template, skeleton, rng)
    cells: list[MapCell] = []

    for x, y in sorted(ring):
        is_gate = (x, y) in gate_coords
        cells.append(MapCell(
            world_uid=world.world_uid,
            x=x,
            y=y,
            z=gz,
            system_terrain="gate" if is_gate else "wall",
            system_material=material,
            is_structural=True,
            location_uid=settlement.location_uid,
        ))

    logger.info(
        "plan_settlement_barriers | settlement=%s template=%s material=%s"
        " cells=%d gates=%d step_m=%d side_m=%d",
        settlement.location_uid,
        template_type,
        material,
        len(cells),
        len(gate_coords),
        step_m,
        side_m,
    )
    return cells
