"""Request-owned region observations and binding of the caller's state snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
from app.application.worldData.generators.terrain.landcover.types import (
    AnchoredRegion, LandcoverInputs, StateSnapshotEntry,
)
from app.application.worldData.regions.factConsumers import collect_facts
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import RegionFacts
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import Point
from app.dataModel.topology.worldTopology import WorldTopology

if TYPE_CHECKING:
    from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
    from app.application.worldData.planning.legacy.surfaceTerrainContext import SurfaceTerrainContext


@dataclass(frozen=True, slots=True)
class LandcoverObservations:
    """Prepared once per request; state snapshots are bound by each caller."""

    topology: WorldTopology
    grid: SurfaceGridSettings
    context: FactConsumerContext

    @classmethod
    def from_views(
        cls, topology: WorldTopology, grid: SurfaceGridSettings,
        climate: ClimateWorkingFields, terrain: TerrainWorkingFields,
        hydrology: HydrologyWorkingFields,
    ) -> LandcoverObservations:
        return cls(topology, grid, FactConsumerContext(
            surface=None, cells=(), climate=climate, terrain=terrain, hydrology=hydrology,
        ))

    def facts_at(self, point: Point) -> RegionFacts:
        # Region coordinates are fine cells; fact consumers observe macro cells.
        macro = (point[0] // self.grid.fine_span, point[1] // self.grid.fine_span)
        return collect_facts(replace(self.context, cells=(macro,)))

    def inputs(
        self, state_snapshot: Mapping[str, StateSnapshotEntry],
        anchor_specs: tuple[AnchoredRegion, ...] = (),
    ) -> LandcoverInputs:
        return LandcoverInputs(self.topology, self.facts_at, state_snapshot, anchor_specs)


def prepare_landcover_inputs(
    working: SurfaceWorkingMaps,
    state_snapshot: Mapping[str, StateSnapshotEntry],
    anchor_specs: tuple[AnchoredRegion, ...] = (),
) -> LandcoverInputs:
    """Bind state without rebuilding observations or resolving world data."""
    return working.landcover.inputs(state_snapshot, anchor_specs)


def prepare_landcover_inputs_legacy(
    topology: WorldTopology,
    grid: SurfaceGridSettings,
    surface: SurfaceTerrainContext | None,
    climate_profiles: Mapping[str, ClimateZoneProfile] | None,
    state_snapshot: Mapping[str, StateSnapshotEntry],
) -> LandcoverInputs:
    """Migration-only surface channel; removed in PC-11.7 with its remaining callers."""
    observation = LandcoverObservations(topology, grid, FactConsumerContext(surface, (), climate_profiles))
    return observation.inputs(state_snapshot)
