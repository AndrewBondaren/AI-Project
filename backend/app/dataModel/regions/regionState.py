"""Region entity state; only StateChangeConsumer may persist changes."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import StrictEnumOnWire
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey


class RegionTransitionCause(StrEnum):
    DRIFT = "drift"
    DECLARED_EDIT = "declared_edit"
    EVENT = "event"


class RegionStateOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    density: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class RegionStateTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    from_type: TerrainKey
    to_type: TerrainKey
    cause: StrictEnumOnWire[RegionTransitionCause]
    # Replace the placeholder with event/time references when those domains exist.
    at: str | int


class RegionState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    region_uid: str
    current_type: TerrainKey
    pending_target: TerrainKey | None = None
    progress: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    last_eval_tick: int = Field(default=0, ge=0)
    overrides: RegionStateOverrides | None = None
    # Immutable prefix: the future writer appends by constructing a new state.
    # JSON wire remains an array. frozen=True alone would not freeze a list.
    history: tuple[RegionStateTransition, ...] = ()
    # Existing 9a rows allow NULL: unknown revision must force a repaint.
    spec_fingerprint: str | None = None
    tombstone: bool = False
