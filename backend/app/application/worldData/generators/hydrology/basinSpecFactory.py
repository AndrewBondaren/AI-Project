"""ResolvedWaterPlacement → BasinSpec; floor/bands context only, no physics, no z."""

from collections.abc import Sequence

from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.application.worldData.placement.adapters.waterTypes import WaterPlacementPreparation
from app.dataModel.placement import ResolvedWaterPlacement


def basin_specs(preparation: WaterPlacementPreparation, records: Sequence[ResolvedWaterPlacement]) -> list[BasinSpec]:
    """Project accepted metadata; category/source defaults were resolved upstream."""
    entries = {entry.source.source_uid: entry for entry in preparation.entries}
    if len(entries) != len(preparation.entries):
        raise ValueError("duplicate prepared water source_uid")
    if len({record.source_uid for record in records}) != len(records):
        raise ValueError("duplicate resolved water source_uid")
    specs = []
    for record in records:
        entry = entries.get(record.source_uid)
        if entry is None:
            raise ValueError(f"water record without prepared entry: {record.source_uid}")
        source = entry.source
        if (record.placement.prepared != entry.prepared or record.kind != source.body_kind
                or record.liquid != source.liquid or record.z_water_level != source.level
                or record.placement.identity.world_uid != preparation.world_uid):
            raise ValueError(f"water record does not match the exact prepared metadata: {record.source_uid}")
        # G9 moves the retained profile into BasinSpec and its single writer.
        # Until then the scalar consumer must never silently flatten a profile.
        if entry.floor_profile is not None:
            raise ValueError("profiled water requires the G9 BasinSpec/profile writer")
        specs.append(BasinSpec(
            source_uid=record.source_uid,
            kind=source.body_kind,
            liquid=source.liquid,
            footprint=record.footprint_cells,
            z_water_level=source.level,
            floor_z=entry.floor_z,
            bands=source.bands,
        ))
    return specs
