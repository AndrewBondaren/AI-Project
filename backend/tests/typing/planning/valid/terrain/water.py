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
from app.application.worldData.generators.terrain.designedWater.strategies.strategy import DesignedWaterStrategy
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.terrain.designedWater.input import (
    WaterDesignInput, AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput, PlateNoiseWaterDesignInput,
)
from app.dataModel.terrain.designedWater.draft import (
    WaterDesignDraft, WaterDesignDraftKind, AuthoredWaterDesignDraft, ProceduralWaterDesignDraft,
)
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation


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


def valid_strategy_boundary(input: WaterDesignInput, draft: WaterDesignDraft,
                            implementation: DesignedWaterStrategy) -> None:
    assert_type(input.context, ResolvedWaterGenerationContext)
    assert_type(input.budget, BodyCoverageAllocation)
    if input.strategy is Strategy.AUTHORED_REGION:
        assert_type(input, AuthoredWaterDesignInput)
    elif input.strategy is Strategy.CONTINENTAL_NOISE:
        assert_type(input, NoiseWaterDesignInput)
        assert_type(input.field_policy, NoiseRecipe)
    elif input.strategy is Strategy.PLATE:
        assert_type(input, PlateWaterDesignInput)
        assert_type(input.field_policy, PlateRecipe)
    else:
        assert_type(input, PlateNoiseWaterDesignInput)
        assert_type(input.field_policy, PlateNoiseRecipe)
    if draft.kind is WaterDesignDraftKind.AUTHORED:
        assert_type(draft, AuthoredWaterDesignDraft)
    else:
        assert_type(draft, ProceduralWaterDesignDraft)
    factory = DesignedWaterStrategyFactory(authored_region=implementation,
        continental_noise=implementation, plate=implementation, plate_noise=implementation)
    assert_type(factory.get(input.strategy), DesignedWaterStrategy)
    assert_type(factory.get(input.strategy).design(input), WaterDesignDraft)
    assert_type(input.validate_draft(draft), WaterDesignDraft)
