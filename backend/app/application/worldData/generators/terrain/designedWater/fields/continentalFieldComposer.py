"""Pure composition of aligned signed fields; no selection or height writes."""

from typing import Literal

from pydantic import ValidationError

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.dataModel.terrain.designedWater.fields.field import (
    ContinentalField, ContinentalFieldValue, FineContinentalField, NoiseRecipe, PlateNoiseRecipe,
)
from app.dataModel.terrain.designedWater.fields.plateLayout import PlateLayout
from app.dataModel.terrain.designedWater.input import NativeCoastlineStrategyInput
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionOperator
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.terrain.designedWater.waterDesignTypeError import WaterDesignTypeError
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class ContinentalFieldComposer:
    """The full recipe binds both components, including inactive noise settings."""

    def build_native(self, input: NativeCoastlineStrategyInput) -> FineContinentalField:
        if not isinstance(input, NativeCoastlineStrategyInput):
            raise TypeError("fine field requires an admitted native coastline input")
        try:
            input = NativeCoastlineStrategyInput.model_validate(input, strict=True)
        except ValidationError as error:
            raise PlanBuildFailure(tuple(
                WaterDesignTypeError.at(NativeCoastlineStrategyInput, issue["loc"], issue["msg"],
                                        operation="continental_field")
                for issue in error.errors(include_input=False, include_context=False, include_url=False)
            )) from error
        recipe = input.field_policy
        surface = input.pre_hydrology.payload.surface_z
        notices = ()
        try:
            if isinstance(recipe, NoiseRecipe):
                values = NoiseFieldGenerator().fine_values(recipe, surface)
            else:
                plates = PlateFieldGenerator()
                layout = plates.layout(recipe.plate_recipe if isinstance(recipe, PlateNoiseRecipe) else recipe)
                notices = layout.notices
                plate_values = plates.fine_values(layout, surface)
                values = plate_values
                if isinstance(recipe, PlateNoiseRecipe):
                    weight = self._weight(recipe)
                    if weight != 0.0:
                        detail = NoiseFieldGenerator().fine_values(recipe.noise_recipe, surface)
                        values = (self._value(p, n, weight) for p, n in zip(plate_values, detail, strict=True))
            samples = tuple((cell, value) for (cell, _), value in zip(surface, values, strict=True))
            return FineContinentalField(pre_hydrology_ref=input.pre_hydrology_ref, recipe=recipe,
                                        samples=samples, notices=notices)
        except (ValueError, OverflowError) as error:
            raise self._failure("build_native", error) from error

    # GEO-LEGACY-57: Remove coarse component composition when PlateNoiseStrategy.design migrates.
    def combine(self, plate: ContinentalField, noise: ContinentalField | None,
                recipe: PlateNoiseRecipe) -> ContinentalField:
        if not isinstance(plate, ContinentalField) or (noise is not None and not isinstance(noise, ContinentalField)):
            raise TypeError("composition requires typed component fields")
        if not isinstance(recipe, PlateNoiseRecipe):
            raise TypeError("composition requires the full captured plate-noise recipe")
        try:
            recipe = PlateNoiseRecipe.model_validate(recipe, strict=True)
            plate = ContinentalField.model_validate(plate, strict=True)
            weight = self._weight(recipe)
            if plate.recipe != recipe.plate_recipe:
                raise ValueError("plate component does not match the captured seed/topology/policy")
            if noise is not None:
                noise = ContinentalField.model_validate(noise, strict=True)
                if noise.recipe != recipe.noise_recipe:
                    raise ValueError("noise component does not match the captured seed/topology/policy")
                if tuple(cell for cell, _ in plate.samples) != tuple(cell for cell, _ in noise.samples):
                    raise ValueError("component fields require exactly matching working coordinates")
            if weight == 0.0:
                return ContinentalField(recipe=recipe, samples=plate.samples, notices=plate.notices)
            if noise is None:
                raise ValueError("nonzero detail weight requires an actual noise field")
            samples = tuple((cell, self._value(base, detail, weight))
                for (cell, base), (_, detail) in zip(plate.samples, noise.samples))
            return ContinentalField(recipe=recipe, samples=samples, notices=plate.notices + noise.notices)
        except ValueError as error:
            raise self._failure("combine", error) from error

    def sample(self, recipe: PlateNoiseRecipe, layout: PlateLayout, *, x: float, y: float) -> ContinentalFieldValue:
        """Fine evaluation uses the same captured layout and existing component samplers."""
        if not isinstance(recipe, PlateNoiseRecipe) or not isinstance(layout, PlateLayout):
            raise TypeError("composition sampling requires typed recipe and plate layout")
        try:
            recipe = PlateNoiseRecipe.model_validate(recipe, strict=True)
            layout = PlateLayout.model_validate(layout, strict=True)
            weight = self._weight(recipe)
            if layout.recipe != recipe.plate_recipe:
                raise ValueError("plate layout does not match the captured component recipe")
            base = PlateFieldGenerator().sample(layout, x=x, y=y)
            if weight == 0.0:
                return base
            detail = NoiseFieldGenerator().sample(recipe.noise_recipe, x=x, y=y)
            return self._value(base, detail, weight)
        except ValueError as error:
            raise self._failure("sample", error) from error

    @staticmethod
    def _weight(recipe: PlateNoiseRecipe) -> float:
        if recipe.composition_policy.operator is not FieldCompositionOperator.ADD_CLAMP:
            raise ValueError("unsupported continental-field composition operator")
        return recipe.composition_policy.detail_weight

    @staticmethod
    def _value(base: ContinentalFieldValue, detail: ContinentalFieldValue, weight: float) -> ContinentalFieldValue:
        return max(-1.0, min(1.0, base + weight * detail))

    @staticmethod
    def _failure(operation: Literal["combine", "sample", "build_native"], error: Exception) -> PlanBuildFailure:
        return PlanBuildFailure((FieldPathError(("continental_field_composition", operation), str(error),
            code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))
