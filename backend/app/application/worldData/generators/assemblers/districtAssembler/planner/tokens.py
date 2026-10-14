"""C22 shell collection — candidates, N, priority, packing tokens."""

from __future__ import annotations

import random

from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.districtAssembler.planner.layoutPicks import (
    _buildings_rng,
    _pick_layout_picks,
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
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.settlement.district.requiredStructure import RequiredStructure
from app.dataModel.locations.settlement.district.requiredStructureResolve import (
    resolve_required_layouts,
)
from app.dataModel.locations.settlement.district.structurePlacement import (
    resolve_plot_count,
    resolve_plot_priority,
)
from app.dataModel.locations.structure.building.buildingCatalog import BuildingCatalog
from app.db.models.world import World


def pick_layout_uids(
    slot: DistrictSlot,
    world: World,
    skeleton: SettlementSkeleton,
    catalog: BuildingCatalog,
    rng: random.Random | None = None,
    *,
    settlement_uid: str | None = None,
) -> list[str]:
    """One plot member ``template_uid`` per required/fill type (SoT for
    tokens and cache)."""
    rng = _buildings_rng(world, slot, rng, settlement_uid)
    return [
        entry.template_uid
        for entry, _req in _pick_layout_picks(
            slot, world, skeleton, catalog, rng, settlement_uid,
        )
    ]


def candidate_template_uids(
    slot: DistrictSlot,
    world: World,
    skeleton: SettlementSkeleton,
    catalog: BuildingCatalog,
    rng: random.Random | None = None,
    *,
    settlement_uid: str | None = None,
) -> list[str]:
    return pick_layout_uids(
        slot, world, skeleton, catalog, rng, settlement_uid=settlement_uid,
    )


def _required_for(
    slot: DistrictSlot,
    template_uid: str,
    catalog: BuildingCatalog,
) -> RequiredStructure | None:
    for req in slot.required_structures:
        if req.plot_template == template_uid:
            return req
        entries = resolve_required_layouts(req, catalog)
        if any(entry.template_uid == template_uid for entry in entries):
            return req
    return None


def build_tokens(
    slot: DistrictSlot,
    cache: BuildingLayoutCache,
    world: World,
    skeleton: SettlementSkeleton,
    catalog: BuildingCatalog,
    rng: random.Random | None = None,
    *,
    settlement_uid: str | None = None,
) -> list[PackingToken]:
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
    for entry, required in picks:
        uid = entry.template_uid
        fp = cache.envelope(uid)
        if fp is None:
            packing_warning(
                PackingStep.CACHE, district=district,
                system_name=uid, reason=PackingReason.NO_CACHE,
            )
            continue
        packing_info(
            PackingStep.CACHE, district=district,
            system_name=uid, facing=Facing.SOUTH,
            w=fp.width, h=fp.depth, hit=True,
        )
        if required is None:
            required = _required_for(slot, uid, catalog)
        n, n_from = resolve_plot_count(
            uid,
            required=required,
            district_counts=slot.district_template.plot_counts,
            settlement_counts=skeleton.plot_counts,
        )
        priority = resolve_plot_priority(
            uid,
            district_priority=slot.district_template.plot_priority,
            settlement_priority=skeleton.plot_priority,
        )
        position = required.position if required is not None else None
        if n <= 0:
            packing_info(
                PackingStep.TOKENS, district=district,
                uid=f"{uid}#0", w=fp.width, h=fp.depth,
                N=0, priority=priority, n_from=n_from,
            )
            continue
        for i in range(n):
            token = PackingToken(
                uid=f"{uid}#{i}",
                template_uid=uid,
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
