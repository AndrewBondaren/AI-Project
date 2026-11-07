"""Stable surface TLV registrations for app.dataModel.terrain.designedWater."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation, WaterCoverageBudget
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateNoiseRecipe, PlateRecipe
from app.dataModel.terrain.designedWater.input import NativeCoastlineStrategyContext, NativeCoastlineStrategyInput
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import (
    FieldCompositionOperator,
    FieldCompositionPolicy,
)
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind, WaterDesignIssueCode
from app.dataModel.terrain.designedWater.waterDesignTypeError import WaterDesignTypeError


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (170, NoiseRecipe, CanonicalTypeKind.RECORD),
    (171, PlateRecipe, CanonicalTypeKind.RECORD),
    (172, PlateNoiseRecipe, CanonicalTypeKind.RECORD),
    (173, DesignedWaterStrategyKind, CanonicalTypeKind.ENUM),
    (174, ContinentalNoisePolicy, CanonicalTypeKind.RECORD),
    (175, PlateGenerationPolicy, CanonicalTypeKind.RECORD),
    (176, FieldCompositionPolicy, CanonicalTypeKind.RECORD),
    (177, FieldCompositionOperator, CanonicalTypeKind.ENUM),
    (250, WaterFieldSelectionPolicy, CanonicalTypeKind.RECORD),
    (274, WaterCoverageBudget, CanonicalTypeKind.RECORD),
    (275, BodyCoverageAllocation, CanonicalTypeKind.RECORD),
    (302, WaterDesignTypeError, CanonicalTypeKind.RECORD),
    (311, WaterDesignIssueCode, CanonicalTypeKind.ENUM),
    (321, NativeCoastlineStrategyInput, CanonicalTypeKind.RECORD),
    (322, NativeCoastlineStrategyContext, CanonicalTypeKind.RECORD),
)
