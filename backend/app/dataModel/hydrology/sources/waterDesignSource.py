"""Derived source wrappers; these are not a second persisted source collection."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.identity.uid import EntityUid

_SOURCE_UID = TypeAdapter(EntityUid)


class WaterDesignSourceKind(StrEnum):
    BASIN = "basin"
    LAKE = "lake"
    COASTLINE = "coastline"
    PROCEDURAL = "procedural"


class _SourceWrapper(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    @field_validator("value", mode="before", check_fields=False)
    @classmethod
    def revalidate_legacy_source(cls, value: object) -> object:
        # Legacy models do not revalidate instances, including model_copy updates.
        expected = cls.model_fields["value"].annotation
        if isinstance(expected, type) and isinstance(value, expected) and isinstance(value, (DeclaredBasin, DeclaredLake, DeclaredCoastline)):
            return value.model_dump(warnings=False)
        return value

    @field_validator("value", check_fields=False)
    @classmethod
    def valid_source_identity(cls, value: object) -> object:
        if isinstance(value, (DeclaredBasin, DeclaredLake, DeclaredCoastline)):
            _SOURCE_UID.validate_python(value.location_uid)
        return value


class AuthoredBasinSource(_SourceWrapper, frozen=True):
    kind: Literal[WaterDesignSourceKind.BASIN] = WaterDesignSourceKind.BASIN
    value: DeclaredBasin


class AuthoredLakeSource(_SourceWrapper, frozen=True):
    kind: Literal[WaterDesignSourceKind.LAKE] = WaterDesignSourceKind.LAKE
    value: DeclaredLake


class CoastlineWaterSource(_SourceWrapper, frozen=True):
    """Current coastline is a water source; purpose exclusion is added at G5-C1."""

    kind: Literal[WaterDesignSourceKind.COASTLINE] = WaterDesignSourceKind.COASTLINE
    value: DeclaredCoastline


class ProceduralSource(_SourceWrapper, frozen=True):
    kind: Literal[WaterDesignSourceKind.PROCEDURAL] = WaterDesignSourceKind.PROCEDURAL
    value: ProceduralWaterSource


type WaterDesignSource = Annotated[
    AuthoredBasinSource | AuthoredLakeSource | CoastlineWaterSource | ProceduralSource,
    Field(discriminator="kind"),
]
