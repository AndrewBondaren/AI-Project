"""Positive terrain water contracts; checked statically by Pyright."""

from typing import assert_type

from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSource, WaterDesignSourceKind
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
from app.dataModel.terrain.designedWater.fields.field import (
    ContinentalField,
    NoiseRecipe,
    PlateNoiseRecipe,
    PlateRecipe,
)
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.terrain.relief.bathymetry.floorProfile import BasinFloorProfile, FieldFloorProfile, FloorProfileKind
from app.dataModel.topology.worldTopology import Coord


def valid_water_contracts(source: WaterDesignSource, metadata: WaterSourceMetadata,
                          field: ContinentalField, profile: BasinFloorProfile) -> None:
    if source.kind is WaterDesignSourceKind.PROCEDURAL:
        assert_type(source.value, ProceduralWaterSource)
    if field.recipe.strategy is Strategy.CONTINENTAL_NOISE:
        assert_type(field.recipe, NoiseRecipe)
    elif field.recipe.strategy is Strategy.PLATE:
        assert_type(field.recipe, PlateRecipe)
    else:
        assert_type(field.recipe, PlateNoiseRecipe)
    assert_type(field.samples[0][0], SurfaceGridCoord)
    assert_type(field.samples[0][1], float)
    assert_type(metadata.level, FineZ)
    if profile.kind is FloorProfileKind.FIELD:
        assert_type(profile, FieldFloorProfile)
        assert_type(profile.z_min, FineZ)
    else:
        assert_type(profile.samples[0][0], Coord)
