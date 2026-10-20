"""ResolvedWaterPlacement → BasinSpec; floor/bands context only, no physics, no z."""

from collections.abc import Sequence

from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.application.worldData.placement.adapters.waterTypes import WaterPlacementPreparation
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.placement import ResolvedWaterPlacement


def basin_specs(preparation: WaterPlacementPreparation, records: Sequence[ResolvedWaterPlacement],
                hydrology: WorldHydrology) -> list[BasinSpec]:
    entries = {entry.source.location_uid: entry for entry in preparation.entries}
    specs = []
    for record in records:
        entry = entries.get(record.source_uid)
        if entry is None:
            raise ValueError(f"water record without prepared entry: {record.source_uid}")
        source = entry.source
        if isinstance(source, DeclaredBasin) and source.rim is not None:
            bands = source.rim
        elif record.kind is BasinKind.LAKE:
            bands = hydrology.default_lakes.bands
        else:
            bands = hydrology.default_seas.bands
        specs.append(BasinSpec(
            source_uid=record.source_uid,
            kind=record.kind,
            liquid=record.liquid,
            footprint=record.footprint_cells,
            z_water_level=record.z_water_level,
            floor_z=entry.floor_z,
            bands=bands,
        ))
    return specs
