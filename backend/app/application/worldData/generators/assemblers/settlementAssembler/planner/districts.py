import logging
import random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    district_templates,
    footprint_side_m,
)
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    coarse_cell_meter_xy,
    grid_dimension,
    settlement_origin_m,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.placement import (
    select_district_template,
    slot_dimensions,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import (
    plan_settlement_entries,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.terrain import (
    resolve_ground_z,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


def plan_district_slots(
    world:         World,
    settlement:    NamedLocation,
    skeleton:      CitySkeleton,
    terrain_cells: list[MapCell] | None,
) -> list[DistrictSlot]:
    """
    v1: равномерная прямоугольная сетка глобальных ячеек footprint.
    Для каждой ячейки — выбор district_template; entry_nodes — plan_settlement_entries.
    """
    cell_m = cell_size_m(world)
    side_m = footprint_side_m(world, skeleton.system_city_size)
    n      = grid_dimension(side_m, cell_m)
    origin = settlement_origin_m(settlement)
    templates = district_templates(world)

    logger.info(
        "plan_district_slots | settlement=%s algorithm=uniform_grid"
        " side_m=%d cell_m=%d grid=%dx%d origin=(%d,%d) ground_z=%d"
        " city_size=%s density=%s templates=%d",
        settlement.location_uid,
        side_m,
        cell_m,
        n,
        n,
        origin.x,
        origin.y,
        origin.z,
        skeleton.system_city_size,
        skeleton.settlement_density,
        len(templates),
    )
    rng = random.Random(f"{settlement.location_uid}_{skeleton.system_city_size}")
    placed_types: dict[str, int] = {}
    slots: list[DistrictSlot] = []

    for cell_y in range(n):
        for cell_x in range(n):
            origin_x, origin_y = coarse_cell_meter_xy(origin, cell_x, cell_y, cell_m)

            template = select_district_template(
                templates, settlement, skeleton, world,
                origin_x, origin_y, cell_m, cell_m,
                terrain_cells, placed_types,
                cell_x, cell_y, n, rng,
            )
            if template is None:
                logger.warning(
                    "No district template for cell (%d,%d) settlement=%s — skipped",
                    cell_x, cell_y, settlement.location_uid,
                )
                continue

            width_m, depth_m = slot_dimensions(template, cell_m, rng)
            dtype = template.district_type
            placed_types[dtype] = placed_types.get(dtype, 0) + 1
            slot_ground_z = resolve_ground_z(
                settlement, origin_x, origin_y, width_m, depth_m, terrain_cells,
            )
            required = list(template.required_structures or [])

            slots.append(DistrictSlot(
                origin_x=origin_x,
                origin_y=origin_y,
                width_m=width_m,
                depth_m=depth_m,
                ground_z=slot_ground_z,
                district_template=template,
                required_structures=required,
            ))

            logger.info(
                "DistrictSlot created | cell=(%d,%d) template=%s district_type=%s"
                " origin=(%d,%d) size=%dx%d ground_z=%d required_structures=%d",
                cell_x,
                cell_y,
                template.system_name,
                dtype,
                origin_x,
                origin_y,
                width_m,
                depth_m,
                slot_ground_z,
                len(required),
            )

    plan_settlement_entries(slots, skeleton, origin.x, origin.y, side_m, world.world_uid)

    logger.info(
        "plan_district_slots done | settlement=%s slots=%d",
        settlement.location_uid,
        len(slots),
    )

    return slots
