"""C22 shell collection — layout candidate picks (required + fill)."""

from __future__ import annotations

import random

from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.subjects import (
    _crop_kinds_for,
    _livestock_kinds_for,
    _resolve_subjects,
    _resource_kinds_for,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_warning,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    building_tier_compatible,
)
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.jsonValidation.worldRow import (
    enabled_building_purposes,
)
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.locations.settlement.district.allowedStructureTypes import (
    allowed_fill_structure_types,
)
from app.dataModel.locations.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.locations.settlement.district.requiredStructureResolve import (
    resolve_required_layouts,
)
from app.dataModel.locations.structure.building.buildingCatalog import (
    BuildingCatalog,
    CatalogPlot,
)
from app.dataModel.locations.structure.enums.buildingPurpose import FAMILY_OF, BuildingPurpose, expand_allowed
from app.db.models.world import World


def _tier_pool(
    entries: tuple[CatalogPlot, ...] | list[CatalogPlot],
    skeleton: SettlementSkeleton,
    world: World,
) -> list[CatalogPlot]:
    return [
        entry for entry in entries
        if building_tier_compatible(entry.body, skeleton, world)
    ]


def _choose_layout(
    entries: list[CatalogPlot],
    rng: random.Random,
    subjects: tuple[str, ...],
    resource_kinds: tuple[ResourceKind, ...] = (),
    crop_kinds: tuple[CropKind, ...] = (),
    livestock_kinds: tuple[LivestockKind, ...] = (),
) -> CatalogPlot:
    pool = list(BuildingCatalog.prefer_subjects(
        entries, subjects, resource_kinds, crop_kinds, livestock_kinds,
    ))
    return rng.choice(pool)


def _purpose_keys(catalog: BuildingCatalog, entry: CatalogPlot) -> set[str]:
    return {str(purpose) for purpose in catalog.structures.leaves_of(entry.body)}


def _required_type_keys(required: RequiredStructure) -> set[str]:
    if required.structure_type is not None:
        return {str(required.structure_type)}
    return set()


def _layouts_enabled(
    catalog: BuildingCatalog,
    entries: tuple[CatalogPlot, ...] | list[CatalogPlot],
    enabled: frozenset[BuildingPurpose],
) -> list[CatalogPlot]:
    return [
        entry for entry in entries
        if any(purpose in enabled for purpose in catalog.structures.leaves_of(entry.body))
    ]


def _match_allowed(
    catalog: BuildingCatalog,
    entries: tuple[CatalogPlot, ...] | list[CatalogPlot],
    allowed: list | None,
    match,
    enabled: frozenset[BuildingPurpose],
) -> list[CatalogPlot]:
    live = _layouts_enabled(catalog, entries, enabled)
    if not allowed:
        return live
    filtered = [purpose for purpose in expand_allowed(allowed) if purpose in enabled]
    if not filtered:
        return []
    return list(catalog.matching_allowed(live, filtered, match))


def _buildings_rng(
    world: World,
    slot: DistrictSlot,
    rng: random.Random | None,
    settlement_uid: str | None,
) -> random.Random:
    if rng is not None:
        return rng
    return settlement_cell_rng(
        world.world_uid,
        settlement_uid or world.world_uid,
        slot.cell_x,
        slot.cell_y,
        SettlementCellRngRole.BUILDINGS,
    )


def _pick_layout_picks(
    slot: DistrictSlot,
    world: World,
    skeleton: SettlementSkeleton,
    catalog: BuildingCatalog,
    rng: random.Random,
    settlement_uid: str | None = None,
) -> list[tuple[CatalogPlot, RequiredStructure | None]]:
    picks: list[tuple[CatalogPlot, RequiredStructure | None]] = []
    seen_uids: set[str] = set()
    skip_fill_types: set[str] = set()

    enabled = enabled_building_purposes(world)
    for entry in catalog.entries:
        body = entry.body.main_building
        if body is not None and catalog.structures.resolve(body.structure) is None:
            raise GenerationError(
                f"Plot '{entry.template_uid}': structure '{body.structure}' not found"
            )

    allowed = slot.district_template.allowed_structure_types
    if allowed is None and slot.allowed_structure_types is not None:
        families = {FAMILY_OF[purpose] for purpose in expand_allowed(slot.allowed_structure_types)}
        catalog = BuildingCatalog(
            (entry for entry in catalog.entries if entry.body.plot_type in families),
            catalog.structures,
        )
    match = slot.district_template.allowed_match
    district = slot.district_template.system_name

    for req in slot.required_structures:
        skip_fill_types |= _required_type_keys(req)
        if req.structure_type is not None and req.structure_type not in enabled:
            packing_warning(
                PackingStep.LEFTOVER,
                district=district,
                structure_type=str(req.structure_type),
                reason=PackingReason.LEFTOVER,
            )
            continue
        found: tuple[CatalogPlot, ...] | list[CatalogPlot] = (
            resolve_required_layouts(req, catalog)
        )
        if not found:
            packing_warning(
                PackingStep.CACHE,
                district=district,
                system_name=(
                    str(req.structure_type)
                    if req.structure_type is not None
                    else str(req.plot_template)
                ),
                reason=PackingReason.NO_CACHE,
            )
            continue
        layouts = _match_allowed(catalog, found, allowed, match, enabled)
        layouts = _tier_pool(layouts, skeleton, world)
        if not layouts:
            packing_warning(
                PackingStep.LEFTOVER,
                district=district,
                system_name=(
                    str(req.structure_type)
                    if req.structure_type is not None
                    else str(req.plot_template)
                ),
                reason=PackingReason.LEFTOVER,
            )
            continue
        type_keys = _required_type_keys(req)
        stype = next(
            iter(type_keys),
            next(iter(catalog.structures.leaves_of(layouts[0].body)), None),
        )
        subjects = _resolve_subjects(slot, world, stype, layouts, settlement_uid)
        chosen = _choose_layout(
            layouts, rng, subjects,
            _resource_kinds_for(world, subjects),
            _crop_kinds_for(world, subjects),
            _livestock_kinds_for(world, subjects),
        )
        skip_fill_types |= _purpose_keys(catalog, chosen)
        if chosen.template_uid in seen_uids:
            continue
        seen_uids.add(chosen.template_uid)
        picks.append((chosen, req))

    fill_types = allowed_fill_structure_types(
        allowed,
        catalog.structure_types(),
        enabled,
    )
    if allowed and not fill_types:
        packing_warning(
            PackingStep.CACHE,
            district=district,
            reason=PackingReason.NO_CANDIDATES,
        )
    for structure_type in fill_types:
        if structure_type in skip_fill_types:
            continue
        found = catalog.of_structure_type(structure_type)
        layouts = _match_allowed(catalog, found, allowed, match, enabled)
        layouts = _tier_pool(layouts, skeleton, world)
        if not layouts:
            packing_warning(
                PackingStep.CACHE,
                district=district,
                structure_type=structure_type,
                reason=PackingReason.NO_CACHE,
            )
            continue
        subjects = _resolve_subjects(
            slot, world, structure_type, layouts, settlement_uid,
        )
        chosen = _choose_layout(
            layouts, rng, subjects,
            _resource_kinds_for(world, subjects),
            _crop_kinds_for(world, subjects),
            _livestock_kinds_for(world, subjects),
        )
        skip_fill_types |= _purpose_keys(catalog, chosen)
        if chosen.template_uid in seen_uids:
            continue
        seen_uids.add(chosen.template_uid)
        picks.append((chosen, None))
    return picks
