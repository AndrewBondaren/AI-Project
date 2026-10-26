"""Compose ready domain observations, topology and region state into LandcoverInputs.

Owners: climate/relief/hydrology domains prepare their request views upstream;
this module only connects them into the fact observation — no World reads,
registry resolves or pack objects here.
"""

from collections.abc import Mapping
from dataclasses import replace

from app.application.worldData.generators.terrain.landcover.types import (
    AnchoredRegion,
    LandcoverInputs,
    StateSnapshotEntry,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.application.worldData.regions.factConsumers import collect_facts
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.topology.worldTopology import WorldTopology


def prepare_landcover_inputs(
    topology: WorldTopology,
    grid: SurfaceGridSettings,
    working: SurfaceWorkingMaps,
    state_snapshot: Mapping[str, StateSnapshotEntry],
    anchor_specs: tuple[AnchoredRegion, ...] = (),
) -> LandcoverInputs:
    """One request-scoped observation built from domain-owned working views."""
    observation = FactConsumerContext(
        surface=None,
        cells=(),
        climate=working.climate,
        terrain=working.terrain,
        hydrology=working.hydrology,
    )
    return _landcover_inputs(topology, grid, observation, state_snapshot, anchor_specs)


def prepare_landcover_inputs_legacy(
    topology: WorldTopology,
    grid: SurfaceGridSettings,
    surface: SurfaceTerrainContext | None,
    climate_profiles: Mapping[str, ClimateZoneProfile] | None,
    state_snapshot: Mapping[str, StateSnapshotEntry],
) -> LandcoverInputs:
    """Migration-only surface channel; removed in PC-11.7 with its remaining callers."""
    observation = FactConsumerContext(surface, (), climate_profiles)
    return _landcover_inputs(topology, grid, observation, state_snapshot, ())


def _landcover_inputs(
    topology: WorldTopology,
    grid: SurfaceGridSettings,
    observation: FactConsumerContext,
    state_snapshot: Mapping[str, StateSnapshotEntry],
    anchor_specs: tuple[AnchoredRegion, ...],
) -> LandcoverInputs:
    def facts_at(point):
        # Region coordinates are fine cells; fact consumers observe macro cells.
        macro = (point[0] // grid.fine_span, point[1] // grid.fine_span)
        return collect_facts(replace(observation, cells=(macro,)))

    return LandcoverInputs(topology, facts_at, state_snapshot, anchor_specs)
