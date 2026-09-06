"""C22 shell collection — candidates, N, priority, packing tokens."""

from __future__ import annotations

import random

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.types import (
    PackingToken,
)
from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import (
    BuildingLayoutCache,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_info,
    packing_warning,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    building_tier_compatible,
)
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.jsonValidation.worldRow import crops, livestock, resource_types
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.settlement.district.allowedStructureTypes import (
    allowed_fill_structure_types,
)
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.settlement.district.requiredStructureResolve import (
    resolve_required_layouts,
)
from app.dataModel.settlement.district.structurePlacement import (
    resolve_structure_count,
    resolve_structure_priority,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.db.models.world import World


def _tier_pool(
    layouts: tuple[BuildingLayoutTemplate, ...] | list[BuildingLayoutTemplate],
    skeleton: CitySkeleton,
    world: World,
) -> list[BuildingLayoutTemplate]:
    return [
        layout for layout in layouts
        if building_tier_compatible(layout, skeleton, world)
    ]


def _subjects_for(slot: DistrictSlot, structure_type: str) -> tuple[str, ...]:
    return tuple((slot.subject_tags or {}).get(structure_type, ()))


def _subject_catalog(
    layouts: list[BuildingLayoutTemplate],
    structure_type: str,
) -> str | None:
    if any(layout.resource_kind is not None for layout in layouts):
        return "resource"
    if any(layout.crop_kind is not None for layout in layouts):
        return "crop"
    if (
        any(layout.livestock_kind is not None for layout in layouts)
        or structure_type == "livestock"
    ):
        return "livestock"
    return None


def _fallback_pool(world: World, catalog: str, layouts: list[BuildingLayoutTemplate]) -> list[str]:
    if catalog == "resource":
        wanted = {layout.resource_kind for layout in layouts if layout.resource_kind is not None}
        return sorted(
            entry.system_resource
            for entry in resource_types(world).root
            if entry.resource_kind in wanted
        )
    if catalog == "crop":
        wanted = {layout.crop_kind for layout in layouts if layout.crop_kind is not None}
        return sorted(
            entry.system_crop
            for entry in crops(world).root
            if entry.crop_kind in wanted
        )
    registry = livestock(world)
    wanted = {layout.livestock_kind for layout in layouts if layout.livestock_kind is not None}
    if wanted:
        return sorted(
            entry.system_livestock
            for entry in registry.root
            if entry.livestock_kind in wanted
        )
    return sorted(registry.keys())


def _token_in_catalog(world: World, catalog: str, token: str) -> bool:
    if catalog == "resource":
        return resource_types(world).entry_for(token) is not None
    if catalog == "crop":
        return crops(world).entry_for(token) is not None
    return livestock(world).entry_for(token) is not None


def _subjects_rng(
    world: World,
    slot: DistrictSlot,
    settlement_uid: str | None,
) -> random.Random:
    return settlement_cell_rng(
        world.world_uid,
        settlement_uid or world.world_uid,
        slot.cell_x,
        slot.cell_y,
        SettlementCellRngRole.SUBJECTS,
    )


def _resolve_subjects(
    slot: DistrictSlot,
    world: World,
    structure_type: str,
    layouts: list[BuildingLayoutTemplate],
    settlement_uid: str | None,
) -> tuple[str, ...]:
    """Named tokens stay; empty extract/farm/livestock → world RNG (§1.2.1)."""
    catalog = _subject_catalog(layouts, structure_type)
    subjects = _subjects_for(slot, structure_type)
    district = slot.district_template.system_name
    if subjects:
        if catalog is not None:
            for token in subjects:
                if not _token_in_catalog(world, catalog, token):
                    packing_warning(
                        PackingStep.TOKENS,
                        district=district,
                        structure_type=structure_type,
                        system_name=token,
                        reason=PackingReason.SUBJECT_UNKNOWN,
                    )
        return subjects
    if catalog is None:
        return subjects
    pool = _fallback_pool(world, catalog, layouts)
    if not pool:
        packing_warning(
            PackingStep.TOKENS,
            district=district,
            structure_type=structure_type,
            reason=PackingReason.SUBJECT_POOL_EMPTY,
        )
        return ()
    picked = _subjects_rng(world, slot, settlement_uid).choice(pool)
    slot.subject_tags[structure_type] = (picked,)
    packing_warning(
        PackingStep.TOKENS,
        district=district,
        structure_type=structure_type,
        system_name=picked,
        reason=PackingReason.SUBJECT_FALLBACK,
    )
    return (picked,)


def _resource_kinds_for(world: World, subjects: tuple[str, ...]) -> tuple[ResourceKind, ...]:
    if not subjects:
        return ()
    registry = resource_types(world)
    kinds: list[ResourceKind] = []
    seen: set[ResourceKind] = set()
    for token in subjects:
        kind = registry.kind_for(token)
        if kind is None or kind in seen:
            continue
        seen.add(kind)
        kinds.append(kind)
    return tuple(kinds)


def _crop_kinds_for(world: World, subjects: tuple[str, ...]) -> tuple[CropKind, ...]:
    if not subjects:
        return ()
    registry = crops(world)
    kinds: list[CropKind] = []
    seen: set[CropKind] = set()
    for token in subjects:
        kind = registry.kind_for(token)
        if kind is None or kind in seen:
            continue
        seen.add(kind)
        kinds.append(kind)
    return tuple(kinds)


def _livestock_kinds_for(world: World, subjects: tuple[str, ...]) -> tuple[LivestockKind, ...]:
    if not subjects:
        return ()
    registry = livestock(world)
    kinds: list[LivestockKind] = []
    seen: set[LivestockKind] = set()
    for token in subjects:
        kind = registry.kind_for(token)
        if kind is None or kind in seen:
            continue
        seen.add(kind)
        kinds.append(kind)
    return tuple(kinds)


def _choose_layout(
    layouts: list[BuildingLayoutTemplate],
    rng: random.Random,
    subjects: tuple[str, ...],
    resource_kinds: tuple[ResourceKind, ...] = (),
    crop_kinds: tuple[CropKind, ...] = (),
    livestock_kinds: tuple[LivestockKind, ...] = (),
) -> BuildingLayoutTemplate:
    pool = list(BuildingCatalog.prefer_subjects(
        layouts, subjects, resource_kinds, crop_kinds, livestock_kinds,
    ))
    return rng.choice(pool)


def _required_type_keys(required: RequiredStructure, catalog: BuildingCatalog) -> set[str]:
    keys: set[str] = set()
    if required.structure_type:
        keys.add(required.structure_type)
        return keys
    if catalog.of_structure_type(required.building_template):
        keys.add(required.building_template)
    return keys


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


def pick_layout_names(
    slot: DistrictSlot,
    world: World,
    skeleton: CitySkeleton,
    catalog: BuildingCatalog,
    rng: random.Random | None = None,
    *,
    settlement_uid: str | None = None,
) -> list[str]:
    """One ``system_name`` per required/fill type (SoT for tokens and cache)."""
    rng = _buildings_rng(world, slot, rng, settlement_uid)
    return [
        name
        for name, _req in _pick_layout_picks(
            slot, world, skeleton, catalog, rng, settlement_uid,
        )
    ]


def candidate_template_names(
    slot: DistrictSlot,
    world: World,
    skeleton: CitySkeleton,
    catalog: BuildingCatalog | None = None,
    rng: random.Random | None = None,
    *,
    settlement_uid: str | None = None,
) -> list[str]:
    catalog = catalog or assemble_building_catalog(world)
    return pick_layout_names(
        slot, world, skeleton, catalog, rng, settlement_uid=settlement_uid,
    )


def _pick_layout_picks(
    slot: DistrictSlot,
    world: World,
    skeleton: CitySkeleton,
    catalog: BuildingCatalog,
    rng: random.Random,
    settlement_uid: str | None = None,
) -> list[tuple[str, RequiredStructure | None]]:
    picks: list[tuple[str, RequiredStructure | None]] = []
    seen_names: set[str] = set()
    skip_fill_types: set[str] = set()

    for req in slot.required_structures:
        skip_fill_types |= _required_type_keys(req, catalog)
        layouts = _tier_pool(resolve_required_layouts(req, catalog), skeleton, world)
        if not layouts:
            packing_warning(
                PackingStep.CACHE,
                district=slot.district_template.system_name,
                system_name=req.structure_type or req.building_template,
                reason=PackingReason.NO_CACHE,
            )
            continue
        type_keys = _required_type_keys(req, catalog)
        stype = next(iter(type_keys), layouts[0].structure_type)
        subjects = _resolve_subjects(slot, world, stype, layouts, settlement_uid)
        chosen = _choose_layout(
            layouts, rng, subjects,
            _resource_kinds_for(world, subjects),
            _crop_kinds_for(world, subjects),
            _livestock_kinds_for(world, subjects),
        )
        if chosen.system_name in seen_names:
            continue
        seen_names.add(chosen.system_name)
        picks.append((chosen.system_name, req))

    fill_types = allowed_fill_structure_types(
        slot.district_template.allowed_structure_types,
        catalog.structure_types(),
    )
    for structure_type in fill_types:
        if structure_type in skip_fill_types:
            continue
        layouts = _tier_pool(catalog.of_structure_type(structure_type), skeleton, world)
        if not layouts:
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
        if chosen.system_name in seen_names:
            continue
        seen_names.add(chosen.system_name)
        picks.append((chosen.system_name, None))
    return picks


def _required_for(
    slot: DistrictSlot,
    system_name: str,
    catalog: BuildingCatalog,
) -> RequiredStructure | None:
    for req in slot.required_structures:
        if req.building_template == system_name:
            return req
        layouts = resolve_required_layouts(req, catalog)
        if any(layout.system_name == system_name for layout in layouts):
            return req
    return None


def build_tokens(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
    catalog: BuildingCatalog | None = None,
    rng: random.Random | None = None,
    *,
    settlement_uid: str | None = None,
) -> list[PackingToken]:
    catalog = catalog or assemble_building_catalog(world)
    rng = _buildings_rng(world, slot, rng, settlement_uid)
    district = slot.district_template.system_name
    picks = _pick_layout_picks(
        slot, world, skeleton, catalog, rng, settlement_uid,
    )
    if not picks:
        packing_warning(
            PackingStep.CACHE, district=district, reason=PackingReason.NO_CANDIDATES,
        )
    tokens: list[PackingToken] = []
    for name, required in picks:
        fp = cache.envelope(name)
        template = catalog.by_system_name(name)
        if fp is None or template is None:
            packing_warning(
                PackingStep.CACHE, district=district,
                system_name=name, reason=PackingReason.NO_CACHE,
            )
            continue
        packing_info(
            PackingStep.CACHE, district=district,
            system_name=name, facing=Facing.SOUTH,
            w=fp.width, h=fp.depth, hit=True,
        )
        if required is None:
            required = _required_for(slot, name, catalog)
        n, n_from = resolve_structure_count(
            name,
            required=required,
            district_counts=slot.district_template.structure_counts,
            settlement_counts=skeleton.structure_counts,
        )
        priority = resolve_structure_priority(
            name,
            district_priority=slot.district_template.structure_priority,
            settlement_priority=skeleton.structure_priority,
        )
        position = required.position if required is not None else None
        if n <= 0:
            packing_info(
                PackingStep.TOKENS, district=district,
                uid=f"{name}#0", w=fp.width, h=fp.depth,
                N=0, priority=priority, n_from=n_from,
            )
            continue
        for i in range(n):
            token = PackingToken(
                uid=f"{name}#{i}",
                system_name=name,
                w=fp.width,
                h=fp.depth,
                priority=priority,
                required=required is not None,
                position=position,
                copy_index=i,
                n_from=n_from,
            )
            tokens.append(token)
            packing_info(
                PackingStep.TOKENS, district=district,
                uid=token.uid, w=token.w, h=token.h,
                N=n, priority=priority, n_from=n_from,
            )
    return tokens
