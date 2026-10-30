"""Post-water observation binding for the common landcover projection."""
from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.application.worldData.regions.inputs.landcoverInputs import LandcoverObservations
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.application.worldData.generators.terrain.landcover.planning.capturedSources import CapturedLandcoverSources, capture_landcover_policy


class SupportSources(CapturedLandcoverSources):
    """Bind final climate/hydrology observations; selection belongs to landcover."""

    def __init__(self, world_uid: str, inputs: SurfaceSupportInput, climate_base: ClimateBasePlan,
                 climate_local: ClimateLocalPlan, terrain: TerrainPlan, hydrology: HydrologyPlan):
        profiles = {p.key: ClimateZoneProfile.from_data(p.key, p.values) for p in climate_base.profiles}
        self.climate = ClimateWorkingFields.from_plans(climate_base, climate_local, profiles.__getitem__)
        observations = LandcoverObservations.from_views(inputs.topology, inputs.grid, self.climate,
            TerrainWorkingFields.from_plan(terrain), HydrologyWorkingFields.from_plan(hydrology, inputs.grid))
        landcover_inputs = observations.inputs({s.region_uid: StateSnapshotEntry(s.current_type, s.tombstone,
            s.spec_fingerprint) for s in inputs.region_states})
        registry, policy = capture_landcover_policy(inputs)
        super().__init__(world_uid, inputs, landcover_inputs, registry, policy, self._profile_at)

    def _profile_at(self, gx: GridX, gy: GridY) -> ClimateZoneProfile:
        anchor = self.climate.local_field.nearest(gx, gy)
        sample = self.climate.sample_pole(gx, gy)
        return self.climate.profile_for_key(anchor.system_climate_zone if anchor is not None else sample.system_climate_zone)
