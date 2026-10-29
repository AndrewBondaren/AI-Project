"""Seeded value noise on world-fine planar, torus and sphere embeddings."""

from itertools import product
from math import cos, floor, fsum, isfinite, pi, prod, sin

from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.terrain.designedWater.fields.field import ContinentalField, ContinentalFieldValue, FieldChannel, NoiseRecipe
from app.dataModel.terrain.designedWater.input import NoiseWaterDesignInput
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.ids import UidKind, seeded_u01

type _LatticeMemo = dict[tuple[int, tuple[int, ...]], float]


class NoiseFieldGenerator:
    """One sampler for planning and fine floor evaluation, without selection or Z writes."""

    def build(self, input: NoiseWaterDesignInput) -> ContinentalField:
        if not isinstance(input, NoiseWaterDesignInput):
            raise TypeError("noise field requires a typed noise input")
        try:
            input = NoiseWaterDesignInput.model_validate(input, strict=True)
            samples = []
            memo: _LatticeMemo = {}
            previous_y: int | None = None
            for coordinate, _ in input.pre_hydrology.payload.surface_z:
                if coordinate.gy != previous_y:
                    # Local memoization is bounded to one coarse row, not a world
                    # cache or another source of truth for the field.
                    memo.clear()
                    previous_y = coordinate.gy
                value = self._sample(input.field_policy,
                    (coordinate.gx + 0.5) * input.grid.fine_span,
                    (coordinate.gy + 0.5) * input.grid.fine_span, memo)
                samples.append((coordinate, value))
            return ContinentalField(recipe=input.field_policy, samples=tuple(samples))
        except (ValueError, OverflowError) as error:
            raise PlanBuildFailure((FieldPathError(("noise_field",), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error

    def sample(self, recipe: NoiseRecipe, *, x: float, y: float) -> ContinentalFieldValue:
        """Sample a real world-fine position; callers supply centers, including fine cells."""
        if not isinstance(recipe, NoiseRecipe):
            raise TypeError("noise sampling requires a typed noise recipe")
        try:
            recipe = NoiseRecipe.model_validate(recipe, strict=True)
            return self._sample(recipe, x, y, {})
        except (ValueError, OverflowError) as error:
            raise PlanBuildFailure((FieldPathError(("noise_field", "sample"), str(error),
                code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),)) from error

    def _sample(self, recipe: NoiseRecipe, x: float, y: float, memo: _LatticeMemo) -> ContinentalFieldValue:
        if type(x) not in (int, float) or type(y) not in (int, float) or not isfinite(x) or not isfinite(y):
            raise ValueError("noise position requires finite world-fine coordinates")
        embedding = self._embedding(recipe.topology, x, y)
        policy, bounds = recipe.noise_policy, recipe.topology.bounds
        length = max(1.0, min(bounds.width, bounds.height) * policy.length_fraction)
        if not isfinite(length):
            raise ValueError("noise length is not representable")
        weighted: list[float] = []
        weights: list[float] = []
        for octave in range(policy.octaves):
            amplitude = policy.persistence ** octave
            if amplitude == 0.0:
                break
            frequency = policy.lacunarity ** octave / length
            position = tuple(component * frequency for component in embedding)
            if not isfinite(frequency) or any(not isfinite(component) for component in position):
                raise ValueError("noise octave coordinates are not representable")
            base = tuple(floor(component) for component in position)
            smooth = tuple(self._quintic(component - integer) for component, integer in zip(position, base))
            terms: list[float] = []
            for offsets in product((0, 1), repeat=len(position)):
                lattice = tuple(integer + offset for integer, offset in zip(base, offsets))
                key = (octave, lattice)
                value = memo.get(key)
                if value is None:
                    value = 2.0 * seeded_u01(recipe.seed_root, UidKind.WATER_FIELD,
                        channel=FieldChannel.NOISE_LATTICE, octave=octave, lattice=lattice) - 1.0
                    memo[key] = value
                weight = prod(t if offset else 1.0 - t for offset, t in zip(offsets, smooth))
                terms.append(value * weight)
            weighted.append(amplitude * fsum(terms))
            weights.append(amplitude)
        # The exact interpolation is convex. Clamp only floating-point drift at
        # its mathematical range; this is not the water selection threshold.
        return max(-1.0, min(1.0, fsum(weighted) / fsum(weights)))

    @staticmethod
    def _quintic(t: float) -> float:
        return max(0.0, min(1.0, t * t * t * (t * (6.0 * t - 15.0) + 10.0)))

    @staticmethod
    def _embedding(topology: WorldTopology, x: float, y: float) -> tuple[float, ...]:
        if topology.mode is WorldTopologyMode.PLANAR:
            return (x, y)
        bounds = topology.bounds
        width, height = bounds.width, bounds.height
        if topology.mode is WorldTopologyMode.WRAPPED:
            longitude = 2.0 * pi * ((x - bounds.x_min) % width) / width
            latitude = 2.0 * pi * ((y - bounds.y_min) % height) / height
            return (width * cos(longitude) / (2.0 * pi), width * sin(longitude) / (2.0 * pi),
                    height * cos(latitude) / (2.0 * pi), height * sin(latitude) / (2.0 * pi))
        # Fold in fine units before normalizing, so half-cell pole aliases keep
        # exactly the same coordinates (not two close float subtractions).
        folded_y = (y - bounds.y_min) % (2 * height)
        shift = 0.0
        if folded_y > height:
            folded_y = 2 * height - folded_y
            shift = width / 2.0
        radius = height / pi
        if folded_y == 0.0:
            return (0.0, 0.0, -radius)
        if folded_y == height:
            return (0.0, 0.0, radius)
        longitude = 2.0 * pi * ((x - bounds.x_min + shift) % width) / width
        latitude = pi * folded_y / height - pi / 2.0
        return (radius * cos(latitude) * cos(longitude), radius * cos(latitude) * sin(longitude),
                radius * sin(latitude))
