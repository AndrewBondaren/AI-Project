"""Physics-owned SI settings — PHYSICS-1 PS-CORE-1; no World wire cutover."""

from typing import Annotated, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, ModelWrapValidatorHandler, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.validation.immutableValue import validate_immutable

STANDARD_GRAVITY_M_S2 = 9.80665
type NonnegativeFinite = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]


class WorldPhysicsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PHYSICS-SETTINGS"
    SCHEMA_VERSION: ClassVar[int] = 1

    gravity_acceleration_m_s2: DefaultWhenMissing[NonnegativeFinite] = STANDARD_GRAVITY_M_S2

    @model_validator(mode="wrap")
    @classmethod
    def complete_existing_instance(cls, value: object, handler: ModelWrapValidatorHandler[Self]) -> Self:
        # Missing authoring fields may default; damaged existing POJOs may not.
        if isinstance(value, cls):
            validate_immutable(value)
        return handler(value)
