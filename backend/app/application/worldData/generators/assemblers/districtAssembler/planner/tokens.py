"""C22 shell collection — candidates, N, priority, packing tokens."""

from __future__ import annotations

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
    lookup_building_template,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    building_tier_compatible,
)
from app.dataModel.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.settlement.district.structurePlacement import (
    resolve_structure_count,
    resolve_structure_priority,
)
from app.dataModel.spatial.facing import Facing
from app.db.models.world import World


def candidate_template_names(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for req in slot.required_structures:
        name = req.building_template
        if name and name not in seen:
            names.append(name)
            seen.add(name)
    allowed = slot.district_template.allowed_structure_types
    if allowed:
        for name in cache.template_names():
            if name in seen:
                continue
            template = lookup_building_template(world, name)
            if template is None:
                continue
            if not building_tier_compatible(template, skeleton, world):
                continue
            st = template.structure_type
            if st in allowed:
                names.append(name)
                seen.add(name)
    return names


def _required_for(slot: DistrictSlot, system_name: str) -> RequiredStructure | None:
    for req in slot.required_structures:
        if req.building_template == system_name:
            return req
    return None


def build_tokens(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: CitySkeleton,
) -> list[PackingToken]:
    district = slot.district_template.system_name
    names = candidate_template_names(slot, cache, world, skeleton)
    if not names:
        packing_warning(
            PackingStep.CACHE, district=district, reason=PackingReason.NO_CANDIDATES,
        )
    tokens: list[PackingToken] = []
    for name in names:
        fp = cache.envelope(name)
        template = lookup_building_template(world, name)
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
        required = _required_for(slot, name)
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
