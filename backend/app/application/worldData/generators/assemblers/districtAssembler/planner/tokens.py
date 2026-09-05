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


def _required_type_keys(required: RequiredStructure, catalog: BuildingCatalog) -> set[str]:
    keys: set[str] = set()
    if required.structure_type:
        keys.add(required.structure_type)
        return keys
    if catalog.of_structure_type(required.building_template):
        keys.add(required.building_template)
    return keys


def candidate_template_names(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
    catalog: BuildingCatalog | None = None,
    rng: random.Random | None = None,
) -> list[str]:
    """One ``system_name`` per required/fill type (not one per library file)."""
    catalog = catalog or assemble_building_catalog(world)
    rng = rng or random.Random(0)
    picks = _pick_layout_names(slot, world, skeleton, catalog, rng)
    names = [name for name, _req in picks]
    _ = cache
    return names


def _pick_layout_names(
    slot: DistrictSlot,
    world: World,
    skeleton: CitySkeleton,
    catalog: BuildingCatalog,
    rng: random.Random,
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
        chosen = rng.choice(layouts)
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
        chosen = rng.choice(layouts)
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
) -> list[PackingToken]:
    catalog = catalog or assemble_building_catalog(world)
    rng = rng or random.Random(0)
    district = slot.district_template.system_name
    picks = _pick_layout_names(slot, world, skeleton, catalog, rng)
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
