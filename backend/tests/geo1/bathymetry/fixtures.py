"""Real strategy → shared selection → spec fixtures for absolute floor tests."""
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.continentalNoiseStrategy import ContinentalNoiseStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateStrategy import PlateStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateNoiseStrategy import PlateNoiseStrategy
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.geo1.preparation.fixtures import procedural_case


def designed(*, strategy=Strategy.CONTINENTAL_NOISE, mode=Mode.PLANAR, span=3):
    input,_=procedural_case(strategy=strategy,mode=mode,span=span,allocated=6*span**2,
        bounds=WorldBounds(x_min=-2,x_max=1,y_min=-1,y_max=1))
    implementation={Strategy.CONTINENTAL_NOISE:ContinentalNoiseStrategy(),Strategy.PLATE:PlateStrategy(),
        Strategy.PLATE_NOISE:PlateNoiseStrategy()}[strategy]
    draft=implementation.design(input)
    prepared=DesignedWaterPlacementPreparer().prepare(input,draft,selection_policy=WaterFieldSelectionPolicy())
    m=prepared.metadata
    spec=BasinSpec(source_uid=m.source_uid,kind=m.body_kind,liquid=m.liquid,
        footprint=prepared.candidates[0].footprint.cells,z_water_level=m.level,
        floor_z=prepared.floor_z,bands=m.bands,floor_profile=prepared.floor_profile)
    return input,draft,spec


def surface(input,z=99):
    return SurfaceHeightmap(world_uid=input.pre_hydrology.ref.key.world_uid,bbox=input.pre_hydrology.payload.bbox,
        surface_z={(c.gx,c.gy):z for c,_ in input.pre_hydrology.payload.surface_z})
