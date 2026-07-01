"""Settlement perimeter barriers — tz_locations barrier_template_registry."""

from __future__ import annotations

import logging
from random import Random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.masterData import economic_tier_rows
from app.application.worldData.generators.assemblers.settlementAssembler.planner.barrierDefaults import (
    lookup_barrier_template,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_gate_coordinates,
    footprint_side_m,
)
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    settlement_origin_m,
)
from app.application.worldData.generators.road.blockSize import block_size_for_density
from app.application.worldData.generators.barrier.material import pick_barrier_material
from app.application.worldData.generators.barrier.perimeter import perimeter_ring_bbox
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
    """v1 эвристика — polish pass: `.cursor/plans/settlement-assembler.md` § pick_barrier_template_type."""
    registry = economic_tier_rows(world)
    uid = world.world_uid
    tier = skeleton.economic_tier or "standard"
    rank = tier_rank(registry, tier, world_uid=uid) if registry else 2

    if rank <= tier_rank(registry, "basic", world_uid=uid) if registry else False:
        return "wooden_fence"
    if rank >= tier_rank(registry, "quality", world_uid=uid) if registry else False:
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
    return pick_barrier_material(
        world, template, skeleton.economic_tier, rng, default="stone",
    )


def _perimeter_ring(
    origin_x: int,
    origin_y: int,
    side_m:   int,
    step_m:   int,
) -> list[tuple[int, int]]:
    return perimeter_ring_bbox(
        origin_x, origin_y, origin_x + side_m, origin_y + side_m, step_m,
    )


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

    origin = settlement_origin_m(settlement)
    side_m = footprint_side_m(world, skeleton.system_city_size)
    cell_m = cell_size_m(world)
    step_m = block_size_for_density(skeleton.settlement_density)

    gate_coords = footprint_gate_coordinates(origin.x, origin.y, side_m, cell_m)
    ring = set(_perimeter_ring(origin.x, origin.y, side_m, step_m))
    ring |= gate_coords

    material = _pick_template_material(world, template, skeleton, rng)
    cells: list[MapCell] = []

    for x, y in sorted(ring):
        is_gate = (x, y) in gate_coords
        cells.append(MapCell(
            world_uid=world.world_uid,
            x=x,
            y=y,
            z=origin.z,
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
