"""Build one procedural draft from the admitted fine coastline input."""

from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.dataModel.terrain.designedWater.draft import FineProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.input import NativeCoastlineStrategyInput


def design_native_coastline(input: NativeCoastlineStrategyInput) -> FineProceduralWaterDesignDraft:
    field = ContinentalFieldComposer().build_native(input)
    return FineProceduralWaterDesignDraft(metadata=input.metadata, field=field, z_min=input.z_min)
