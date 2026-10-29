"""Signed continental fields and reproducible recipes (GEO-1 G4-S)."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, field_validator, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable


class FieldChannel(StrEnum):
    NOISE_LATTICE = "noise_lattice"
    PLATE_CENTER = "plate_center"
    PLATE_BUOYANCY = "plate_buoyancy"


class AffinePermutationCoefficient(StrEnum):
    MULTIPLIER = "multiplier"
    OFFSET = "offset"


class _FieldRecipe(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    seed_root: EntityUid
    topology: WorldTopology

    @field_validator("topology", mode="before")
    @classmethod
    def revalidate_topology(cls, value: object) -> object:
        return value.model_dump(warnings=False) if isinstance(value, WorldTopology) else value


class NoiseRecipe(_FieldRecipe, frozen=True):
    strategy: Literal[Strategy.CONTINENTAL_NOISE] = Strategy.CONTINENTAL_NOISE
    noise_policy: ContinentalNoisePolicy


class PlateRecipe(_FieldRecipe, frozen=True):
    strategy: Literal[Strategy.PLATE] = Strategy.PLATE
    plate_policy: PlateGenerationPolicy


class PlateNoiseRecipe(_FieldRecipe, frozen=True):
    strategy: Literal[Strategy.PLATE_NOISE] = Strategy.PLATE_NOISE
    noise_policy: ContinentalNoisePolicy
    plate_policy: PlateGenerationPolicy
    composition_policy: FieldCompositionPolicy

    @property
    def plate_recipe(self) -> PlateRecipe:
        """Readonly component view; preserve actual settings without context changes."""
        return PlateRecipe(seed_root=self.seed_root, topology=self.topology, plate_policy=self.plate_policy)

    @property
    def noise_recipe(self) -> NoiseRecipe:
        return NoiseRecipe(seed_root=self.seed_root, topology=self.topology, noise_policy=self.noise_policy)



type WaterFieldRecipe = Annotated[NoiseRecipe | PlateRecipe | PlateNoiseRecipe, Field(discriminator="strategy")]
type ContinentalFieldValue = Annotated[StrictFloat, Field(ge=-1, le=1, allow_inf_nan=False)]


class ContinentalField(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    recipe: WaterFieldRecipe
    samples: tuple[tuple[SurfaceGridCoord, ContinentalFieldValue], ...]
    notices: tuple[FieldPathError, ...] = ()

    @model_validator(mode="after")
    def ordered_unique_samples(self) -> Self:
        keys = tuple((coord.gy, coord.gx) for coord, _ in self.samples)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise ValueError("field samples require unique coordinates in row-major order")
        validate_immutable(self)
        # Canonical coarse membership requires the input boundary's grid scale.
        return self
