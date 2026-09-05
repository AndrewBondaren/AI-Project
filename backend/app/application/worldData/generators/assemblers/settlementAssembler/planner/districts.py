import logging

from app.application.jsonValidation.worldRow import location_types
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
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.placement import (
    select_district_template,
    slot_dimensions,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import (
    plan_settlement_entries,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.barrierInset import (
    shrink_slot_by_settlement_barrier,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.terrain import (
    column_surface,
    resolve_district_pin_z,
)
from app.dataModel.settlement.district.requiredStructureResolve import (
    union_required_structures,
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
    subtype = (settlement.system_location_subtype or "").strip()
    recipe = (
        location_types(world).subtype_for("settlement", subtype) if subtype else None
    )
    typical: tuple[str, ...] | None = None
    settlement_required: list[str] = []
    if recipe is not None and recipe.has_district_recipe():
        typical = tuple(recipe.typical_district_types)
        settlement_required = list(recipe.required_structure_types)

    logger.info(
        "plan_district_slots | settlement=%s algorithm=uniform_grid"
        " side_m=%d cell_m=%d grid=%dx%d origin=(%d,%d) ground_z=%d"
        " city_size=%s density=%s templates=%d recipe=%s typical=%s",
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
        subtype or "-",
        list(typical) if typical else "-",
    )
    placed_types: dict[str, int] = {}
    slots: list[DistrictSlot] = []
    surface = column_surface(terrain_cells)

    for cell_y in range(n):
        for cell_x in range(n):
            origin_x, origin_y = coarse_cell_meter_xy(origin, cell_x, cell_y, cell_m)
            rng = settlement_cell_rng(
                world.world_uid,
                settlement.location_uid,
                cell_x,
                cell_y,
                SettlementCellRngRole.DISTRICTS,
            )

            template = select_district_template(
                templates, settlement, skeleton, world,
                origin_x, origin_y, cell_m, cell_m,
                terrain_cells, placed_types,
                cell_x, cell_y, n, rng,
                typical_district_types=typical,
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
            slot_ground_z = resolve_district_pin_z(
                settlement, origin_x, origin_y, surface,
            )
            required = union_required_structures(
                settlement_required,
                list(template.required_structures or []),
            )

            slots.append(DistrictSlot(
                origin_x=origin_x,
                origin_y=origin_y,
                width_m=width_m,
                depth_m=depth_m,
                ground_z=slot_ground_z,
                district_template=template,
                required_structures=required,
                cell_x=cell_x,
                cell_y=cell_y,
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

    for slot in slots:
        shrink_slot_by_settlement_barrier(
            slot, skeleton, world, origin.x, origin.y, side_m,
        )

    plan_settlement_entries(
        slots, skeleton, origin.x, origin.y, side_m, world.world_uid, surface,
        world=world,
    )

    logger.info(
        "plan_district_slots done | settlement=%s slots=%d",
        settlement.location_uid,
        len(slots),
    )

    return slots
