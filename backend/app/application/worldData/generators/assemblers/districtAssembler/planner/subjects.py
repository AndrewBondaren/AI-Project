"""C22 shell collection — subject resolution (resource/crop/livestock)."""

from __future__ import annotations

import random

from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_warning,
)
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.jsonValidation.worldRow import (
    crops,
    livestock,
    resource_types,
)
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurpose
from app.dataModel.locations.structure.building.buildingCatalog import CatalogPlot
from app.db.models.world import World


def _subjects_for(slot: DistrictSlot, structure_type: str) -> tuple[str, ...]:
    return tuple((slot.subject_tags or {}).get(structure_type, ()))


def _subject_catalog(
    entries: list[CatalogPlot] | tuple[CatalogPlot, ...],
    structure_type: str,
) -> str | None:
    if any(entry.body.resource_kind is not None for entry in entries):
        return "resource"
    if any(entry.body.crop_kind is not None for entry in entries):
        return "crop"
    if (
        any(entry.body.livestock_kind is not None for entry in entries)
        or structure_type == BuildingPurpose.LIVESTOCK.value
    ):
        return "livestock"
    return None


def _fallback_pool(world: World, catalog: str, entries: list[CatalogPlot] | tuple[CatalogPlot, ...]) -> list[str]:
    if catalog == "resource":
        wanted = {entry.body.resource_kind for entry in entries if entry.body.resource_kind is not None}
        return sorted(
            entry.system_resource
            for entry in resource_types(world).root
            if entry.resource_kind in wanted
        )
    if catalog == "crop":
        wanted = {entry.body.crop_kind for entry in entries if entry.body.crop_kind is not None}
        return sorted(
            entry.system_crop
            for entry in crops(world).root
            if entry.crop_kind in wanted
        )
    registry = livestock(world)
    wanted = {entry.body.livestock_kind for entry in entries if entry.body.livestock_kind is not None}
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
    entries: list[CatalogPlot] | tuple[CatalogPlot, ...],
    settlement_uid: str | None,
) -> tuple[str, ...]:
    """Named tokens stay; empty extract/farm/livestock → world RNG (§1.2.1)."""
    catalog = _subject_catalog(entries, structure_type)
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
    pool = _fallback_pool(world, catalog, entries)
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
