import logging
from dataclasses import dataclass

from app.application.jsonValidation.worldRow import location_types, settlement_specializations
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
    PlacedCounts,
    cell_type_score,
    pick_template_for_ref,
    placement_count_key,
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
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.district.requiredStructureResolve import (
    union_required_structures,
)
from app.dataModel.settlement.settlement.settlementSpecializationEntry import (
    SettlementSpecializationEntry,
)
from app.dataModel.settlement.settlement.typicalDistrictRef import TypicalDistrictRef
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SpecializationResolve:
    spec_refs: tuple[TypicalDistrictRef, ...]
    unknown_roles: tuple[str, ...]
    required_types: tuple[str, ...]
    subject_tags: dict[str, tuple[str, ...]]


def plan_district_slots(
    world:         World,
    settlement:    NamedLocation,
    skeleton:      CitySkeleton,
    terrain_cells: list[MapCell] | None,
) -> list[DistrictSlot]:
    """
    v1: равномерная прямоугольная сетка глобальных ячеек footprint.
    Проходы §1.2: typical_districts города → специализации → морфология.
    """
    cell_m = cell_size_m(world)
    side_m = footprint_side_m(world, skeleton.system_city_size)
    n      = grid_dimension(side_m, cell_m)
    origin = settlement_origin_m(settlement)
    templates = district_templates(world)
    subtype = (settlement.system_location_subtype or "").strip()
    recipe = (
        location_types(world).subtype_for(
            WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT, subtype,
        ) if subtype else None
    )
    typical: tuple[str, ...] | None = None
    if recipe is not None and recipe.has_district_recipe():
        typical = tuple(recipe.typical_district_types)

    resolved = _resolve_specialization(world, skeleton, recipe)
    city_refs = tuple(skeleton.typical_districts or ())
    spec_refs = resolved.spec_refs
    for role in resolved.unknown_roles:
        logger.warning(
            "Unknown settlement specialization | settlement=%s role=%s — skipped",
            settlement.location_uid, role,
        )

    logger.info(
        "plan_district_slots | settlement=%s algorithm=priority_passes"
        " side_m=%d cell_m=%d grid=%dx%d origin=(%d,%d) ground_z=%d"
        " city_size=%s density=%s templates=%d recipe=%s typical=%s"
        " city_refs=%d spec_refs=%d",
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
        len(city_refs),
        len(spec_refs),
    )
    placed_types: PlacedCounts = {}
    slots: list[DistrictSlot] = []
    occupied: set[tuple[int, int]] = set()
    surface = column_surface(terrain_cells)
    settlement_required = list(resolved.required_types)
    subject_tags = dict(resolved.subject_tags)

    def _materialize(cell_x: int, cell_y: int, template: DistrictTemplateEntry | None) -> bool:
        if template is None:
            return False
        origin_x, origin_y = coarse_cell_meter_xy(origin, cell_x, cell_y, cell_m)
        rng = settlement_cell_rng(
            world.world_uid,
            settlement.location_uid,
            cell_x,
            cell_y,
            SettlementCellRngRole.DISTRICTS,
        )
        width_m, depth_m = slot_dimensions(template, cell_m, rng)
        key = placement_count_key(template)
        placed_types[key] = placed_types.get(key, 0) + 1
        occupied.add((cell_x, cell_y))
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
            subject_tags=subject_tags,
        ))
        logger.info(
            "DistrictSlot created | cell=(%d,%d) template=%s district_type=%s"
            " district_subtype=%s origin=(%d,%d) size=%dx%d ground_z=%d"
            " required_structures=%d",
            cell_x,
            cell_y,
            template.system_name,
            template.district_type,
            template.district_subtype or "-",
            origin_x,
            origin_y,
            width_m,
            depth_m,
            slot_ground_z,
            len(required),
        )
        return True

    def _place_one_ref(ref: TypicalDistrictRef, warn: str) -> bool:
        candidates = [
            (cell_x, cell_y)
            for cell_y in range(n)
            for cell_x in range(n)
            if (cell_x, cell_y) not in occupied
        ]
        candidates.sort(
            key=lambda xy: cell_type_score(xy[0], xy[1], n, ref.district_type, world),
        )
        for cell_x, cell_y in candidates:
            origin_x, origin_y = coarse_cell_meter_xy(origin, cell_x, cell_y, cell_m)
            rng = settlement_cell_rng(
                world.world_uid,
                settlement.location_uid,
                cell_x,
                cell_y,
                SettlementCellRngRole.DISTRICTS,
            )
            template = pick_template_for_ref(
                templates, ref, settlement, skeleton, world,
                origin_x, origin_y, cell_m, cell_m,
                terrain_cells, placed_types, cell_x, cell_y, n, rng,
            )
            if _materialize(cell_x, cell_y, template):
                return True
        logger.warning(
            warn,
            settlement.location_uid,
            ref.district_type,
            ref.district_subtype or "-",
            ref.system_name or "-",
        )
        return False

    def _select(
        cell_x: int,
        cell_y: int,
        *,
        typical_district_types: tuple[str, ...] | None = None,
        unspecialized_only: bool = False,
        allow_legacy: bool = False,
    ) -> DistrictTemplateEntry | None:
        origin_x, origin_y = coarse_cell_meter_xy(origin, cell_x, cell_y, cell_m)
        rng = settlement_cell_rng(
            world.world_uid,
            settlement.location_uid,
            cell_x,
            cell_y,
            SettlementCellRngRole.DISTRICTS,
        )
        if not allow_legacy and typical_district_types is None:
            return None
        return select_district_template(
            templates, settlement, skeleton, world,
            origin_x, origin_y, cell_m, cell_m,
            terrain_cells, placed_types,
            cell_x, cell_y, n, rng,
            typical_district_types=typical_district_types,
            unspecialized_only=unspecialized_only,
        )

    for ref in city_refs:
        _place_one_ref(
            ref,
            "City typical_districts entry not placed | settlement=%s"
            " district_type=%s district_subtype=%s pin=%s",
        )

    for ref in spec_refs:
        _place_one_ref(
            ref,
            "Specialization district not placed | settlement=%s"
            " district_type=%s district_subtype=%s pin=%s",
        )

    for cell_y in range(n):
        for cell_x in range(n):
            if (cell_x, cell_y) in occupied:
                continue
            if typical:
                template = _select(
                    cell_x, cell_y,
                    typical_district_types=typical,
                    unspecialized_only=True,
                )
                if _materialize(cell_x, cell_y, template):
                    continue
            elif not city_refs and not spec_refs:
                template = _select(cell_x, cell_y, allow_legacy=True)
                if template is None:
                    logger.warning(
                        "No district template for cell (%d,%d) settlement=%s — skipped",
                        cell_x, cell_y, settlement.location_uid,
                    )
                    continue
                _materialize(cell_x, cell_y, template)

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


def _resolve_specialization(
    world: World,
    skeleton: CitySkeleton,
    recipe,
) -> _SpecializationResolve:
    spec_reg = settlement_specializations(world)
    refs: list[TypicalDistrictRef] = []
    unknown: list[str] = []
    seen_refs: set[tuple[str, str | None]] = set()
    required: list[str] = []
    seen_req: set[str] = set()
    tags: dict[str, list[str]] = {}
    tag_seen: dict[str, set[str]] = {}

    if recipe is not None:
        for type_name in recipe.required_structure_types:
            if type_name in seen_req:
                continue
            seen_req.add(type_name)
            required.append(type_name)

    for bind in skeleton.system_settlement_specializations or ():
        entry = spec_reg.entry_for(bind.system_specialization)
        if entry is None:
            unknown.append(bind.system_specialization)
            continue
        for ref in entry.typical_districts:
            key = (ref.district_type, ref.normalized_subtype())
            if key in seen_refs:
                continue
            seen_refs.add(key)
            refs.append(ref)
        subjects = bind.subject_keys()
        resolved_types = entry.resolved_structure_types(subjects)
        for type_name in resolved_types:
            if type_name in seen_req:
                continue
            seen_req.add(type_name)
            required.append(type_name)
        _accumulate_subject_tags(tags, tag_seen, entry, subjects, resolved_types)

    return _SpecializationResolve(
        spec_refs=tuple(refs),
        unknown_roles=tuple(unknown),
        required_types=tuple(required),
        subject_tags={name: tuple(values) for name, values in tags.items()},
    )


def _accumulate_subject_tags(
    tags: dict[str, list[str]],
    seen: dict[str, set[str]],
    entry: SettlementSpecializationEntry,
    subjects: tuple[str, ...],
    resolved_types: tuple[str, ...],
) -> None:
    mapped: set[str] = set()
    resolved_set = set(resolved_types)
    for subject in subjects:
        mapped_types = entry.subjects_to_structure_types.get(subject) or []
        if not mapped_types:
            continue
        mapped.add(subject)
        for structure_type in mapped_types:
            if structure_type in resolved_set:
                _add_subject_tag(tags, seen, structure_type, subject)
    unmapped = [subject for subject in subjects if subject not in mapped]
    if not unmapped:
        return
    for structure_type in resolved_types:
        for subject in unmapped:
            _add_subject_tag(tags, seen, structure_type, subject)


def _add_subject_tag(
    tags: dict[str, list[str]],
    seen: dict[str, set[str]],
    structure_type: str,
    subject: str,
) -> None:
    used = seen.setdefault(structure_type, set())
    if subject in used:
        return
    used.add(subject)
    tags.setdefault(structure_type, []).append(subject)
