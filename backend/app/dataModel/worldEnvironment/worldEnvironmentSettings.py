"""World-owned declaration of the initial ambient atmosphere (SPATIAL-1).

This is configuration, not a gas-distribution solver or a material registry.
An absent atmosphere declaration remains unresolved; it never means air
or vacuum implicitly. Runtime consumers are wired in a separate step (SP-A2).
"""

from __future__ import annotations

from enum import StrEnum
from math import fsum, isclose
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.materials.worldMaterialRegistry import MaterialKey


class AtmosphereMode(StrEnum):
    VACUUM = "vacuum"
    MIXTURE = "mixture"


class AtmosphereGasComponent(BaseModel):
    """A material-registry gas and its normalized share of the base atmosphere."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    system_material: StrictOnWire[MaterialKey]
    fraction: StrictOnWire[Annotated[float, Field(gt=0.0, le=1.0, allow_inf_nan=False)]]


class WorldAtmosphereSettings(BaseModel):
    """Explicit vacuum or an atmospheric gas mixture, never an implicit air."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: StrictEnumOnWire[AtmosphereMode]
    composition: DefaultWhenMissing[list[AtmosphereGasComponent]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_composition(self) -> WorldAtmosphereSettings:
        if self.mode is AtmosphereMode.VACUUM:
            if self.composition:
                raise ValueError("vacuum atmosphere must have no gas components")
            return self
        if not self.composition:
            raise ValueError("mixture atmosphere must declare gas components")
        keys = [component.system_material for component in self.composition]
        if len(keys) != len(set(keys)):
            raise ValueError("atmosphere gas components must have unique system_material")
        if not isclose(fsum(component.fraction for component in self.composition), 1.0,
                       rel_tol=0.0, abs_tol=1e-6):
            raise ValueError("atmosphere gas fractions must sum to 1")
        return self


class WorldEnvironmentSettings(BaseModel):
    """Root POJO for worlds.world_environment JSON; World owns this policy."""

    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-ENVIRONMENT"

    model_config = ConfigDict(extra="forbid", frozen=True)

    # None = unresolved on a legacy or not-yet-configured world, NOT vacuum/air.
    atmosphere: DefaultWhenMissing[WorldAtmosphereSettings | None] = None

    @classmethod
    def canonical_unresolved(cls) -> WorldEnvironmentSettings:
        """No ambient default until a world explicitly declares its atmosphere."""
        return cls()
