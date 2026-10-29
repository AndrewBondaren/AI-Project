"""Seeded plate permutation and normalized topology-distance blending."""

from math import exp, fsum, gcd, isfinite

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.terrain.designedWater.fields.field import (
    AffinePermutationCoefficient, ContinentalField, ContinentalFieldValue, FieldChannel, PlateRecipe,
)
from app.dataModel.terrain.designedWater.fields.plateLayout import PlateCenter, PlateLayout
from app.dataModel.terrain.designedWater.input import PlateWaterDesignInput, PlateNoiseWaterDesignInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.topology.topologyGeometry import dist2
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.ids import UidKind, seeded_u01


class PlateFieldGenerator:
    """One derived layout and sampler for planning/fine evaluation; no terrain writes."""

    def layout(self, recipe: PlateRecipe) -> PlateLayout:
        if not isinstance(recipe, PlateRecipe):
            raise TypeError("plate layout requires a typed plate recipe")
        try:
            recipe = PlateRecipe.model_validate(recipe, strict=True)
            bounds = recipe.topology.bounds
            size = bounds.width * bounds.height
            requested = recipe.plate_policy.plate_count
            count = min(requested, size)
            multiplier, offset = 1, 0
            if size > 1:
                draw = seeded_u01(recipe.seed_root, UidKind.WATER_FIELD, channel=FieldChannel.PLATE_CENTER,
                    coefficient=AffinePermutationCoefficient.MULTIPLIER, cell_count=size)
                numerator, denominator = draw.as_integer_ratio()
                multiplier = 1 + numerator * (size - 1) // denominator
                while gcd(multiplier, size) != 1:
                    multiplier = multiplier % (size - 1) + 1
                draw = seeded_u01(recipe.seed_root, UidKind.WATER_FIELD, channel=FieldChannel.PLATE_CENTER,
                    coefficient=AffinePermutationCoefficient.OFFSET, cell_count=size)
                numerator, denominator = draw.as_integer_ratio()
                offset = numerator * size // denominator
            centers = []
            for index in range(count):
                position = (multiplier * index + offset) % size
                centers.append(PlateCenter(index=index,
                    cell=(FineX(bounds.x_min + position % bounds.width), FineY(bounds.y_min + position // bounds.width)),
                    buoyancy=2.0 * seeded_u01(recipe.seed_root, UidKind.WATER_FIELD,
                        channel=FieldChannel.PLATE_BUOYANCY, plate_index=index) - 1.0))
            notices = ()
            if count != requested:
                notices = (FieldPathError(("plate_policy", "plate_count"),
                    f"tiny-world plate count adjustment; requested={requested}, effective={count}, fine_cells={size}",
                    code=WaterDesignIssueCode.PLATE_COUNT_ADJUSTED.value),)
            return PlateLayout(recipe=recipe, multiplier=multiplier, offset=offset, centers=tuple(centers), notices=notices)
        except (ValueError, OverflowError) as error:
            raise self._failure("layout", error) from error

    def build(self, input: PlateWaterDesignInput | PlateNoiseWaterDesignInput) -> ContinentalField:
        if not isinstance(input, (PlateWaterDesignInput, PlateNoiseWaterDesignInput)):
            raise TypeError("plate field requires a typed plate input")
        try:
            input = type(input).model_validate(input, strict=True)
            recipe = input.field_policy.plate_recipe if isinstance(input, PlateNoiseWaterDesignInput) else input.field_policy
            layout = self.layout(recipe)
            samples = tuple((coordinate, self._sample(layout,
                (coordinate.gx + 0.5) * input.grid.fine_span, (coordinate.gy + 0.5) * input.grid.fine_span))
                for coordinate, _ in input.pre_hydrology.payload.surface_z)
            return ContinentalField(recipe=recipe, samples=samples, notices=layout.notices)
        except (ValueError, OverflowError) as error:
            raise self._failure("build", error) from error

    def sample(self, layout: PlateLayout, *, x: float, y: float) -> ContinentalFieldValue:
        """Sample a real fine position using an explicitly captured immutable layout."""
        if not isinstance(layout, PlateLayout):
            raise TypeError("plate sampling requires a typed plate layout")
        try:
            layout = PlateLayout.model_validate(layout, strict=True)
            return self._sample(layout, x, y)
        except (ValueError, OverflowError) as error:
            raise self._failure("sample", error) from error

    @staticmethod
    def _sample(layout: PlateLayout, x: float, y: float) -> ContinentalFieldValue:
        if type(x) not in (int, float) or type(y) not in (int, float) or not isfinite(x) or not isfinite(y):
            raise ValueError("plate position requires finite world-fine coordinates")
        recipe = layout.recipe
        bounds = recipe.topology.bounds
        length = max(1.0, min(bounds.width, bounds.height) * recipe.plate_policy.blend_length_fraction)
        if not isfinite(length):
            raise ValueError("plate blend length is not representable")
        # Common topology geometry measures cell-center INDEX coordinates.
        # Convert real fine positions by -.5, while centers already carry indices.
        distances = tuple(float(dist2(recipe.topology, (x - 0.5, y - 0.5), center.cell)) for center in layout.centers)
        if any(not isfinite(distance) for distance in distances):
            raise ValueError("plate distance is not representable")
        nearest = min(distances)
        weights = tuple(exp(-((distance - nearest) / length / length)) for distance in distances)
        # Subtracting nearest guarantees at least one exact weight=1. There is
        # no underflow fallback, nearest-body selection, or noise substitution.
        value = fsum(weight * center.buoyancy for weight, center in zip(weights, layout.centers)) / fsum(weights)
        return max(-1.0, min(1.0, value))

    @staticmethod
    def _failure(operation: str, error: Exception) -> PlanBuildFailure:
        return PlanBuildFailure((FieldPathError(("plate_field", operation), str(error),
            code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))
