"""Physics-owned SI settings — PHYSICS-1 PS-CORE-1; no World wire cutover."""

from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing

STANDARD_GRAVITY_M_S2 = 9.80665
type NonnegativeFinite = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]


class WorldPhysicsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-PHYSICS-SETTINGS"
    SCHEMA_VERSION: ClassVar[int] = 1

    gravity_acceleration_m_s2: DefaultWhenMissing[NonnegativeFinite] = STANDARD_GRAVITY_M_S2
