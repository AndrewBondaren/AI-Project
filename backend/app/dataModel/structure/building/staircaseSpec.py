"""Staircase wire contract — building generator §3.7b + tz_staircase_generation §2."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.spatial.facing import (
    CARDINAL_FACINGS,
    Facing,
    INTERCARDINAL_FACINGS,
    coerce_facing_wire,
)
from app.dataModel.structure.enums.staircaseType import StaircaseType

EMBED_AT_CENTER = "center"
_EMBED_AT_KEYS = frozenset(
    {EMBED_AT_CENTER} | {facing.value for facing in INTERCARDINAL_FACINGS}
)


class ShaftSize(BaseModel):
    """``staircases[].size`` — формы §3.5 применительно к footprint шахты."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    size_type:   DefaultOnWire[str | None] = None
    width_range: DefaultOnWire[list[int] | None] = None
    depth_range: DefaultOnWire[list[int] | None] = None

    @model_validator(mode="after")
    def _single_form(self) -> "ShaftSize":
        if self.size_type is not None:
            if self.width_range is not None or self.depth_range is not None:
                raise ValueError(
                    "size: size_type взаимоисключает width_range/depth_range (§3.5)"
                )
        elif self.width_range is None:
            raise ValueError("size: width_range обязателен без size_type (§3.5)")
        return self


class StaircaseSpec(BaseModel):
    """``staircases[]`` entry — вертикальная связь комнат (§3.7b)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stops:           DefaultOnWire[list[str]] = Field(default_factory=list)
    staircase_id:    DefaultOnWire[str | None] = None
    staircase_type:  DefaultOnWire[StaircaseType] = Field(
        default_factory=StaircaseType.generator_default,
    )
    step_material:   DefaultOnWire[str | None] = None
    size:            DefaultOnWire[ShaftSize | None] = None
    facing:          DefaultOnWire[Facing | None] = None
    # ТЗ §3.7b/§2 декларирует default true; status quo — решение мастера 2026-09-30.
    has_walls:       DefaultOnWire[bool] = False
    outside:         DefaultOnWire[bool] = False
    in_a_room:       DefaultOnWire[bool] = False
    embed_in:        DefaultOnWire[str | None] = None
    embed_at:        DefaultOnWire[str | None] = None
    on_the_edge:     DefaultOnWire[bool] = False
    is_movable:      DefaultOnWire[bool] = False
    has_trapdoor:    DefaultOnWire[bool] = False
    near_wall:       DefaultOnWire[bool] = False
    open_wall_shaft: DefaultOnWire[str | None] = None
    closed_exit:     DefaultOnWire[bool] = False

    @field_validator("staircase_type", mode="before")
    @classmethod
    def _parse_type(cls, value: Any) -> Any:
        parsed = StaircaseType.parse_template(value)
        if parsed is None:
            raise ValueError(f"unknown staircase_type: {value!r}")
        return parsed

    @field_validator("facing", mode="before")
    @classmethod
    def _parse_facing(cls, value: Any) -> Any:
        return coerce_facing_wire(value)

    @field_validator("facing")
    @classmethod
    def _cardinal_facing(cls, value: Facing | None) -> Facing | None:
        if value is not None and value not in CARDINAL_FACINGS:
            raise ValueError("staircase facing must be cardinal")
        return value

    @field_validator("embed_at")
    @classmethod
    def _embed_at_position(cls, value: Any) -> Any:
        if value is None:
            return value
        key = str(value).strip().lower()
        if key in _EMBED_AT_KEYS:
            return key
        raise ValueError(
            "embed_at must be an intercardinal corner or 'center' "
            f"(staircase §2): {value!r}"
        )

    @model_validator(mode="after")
    def _resolve_staircase_id(self) -> "StaircaseSpec":
        """Auto-id ``staircase_{from}_{to}`` по stops (§3.7b); один дефолт вместо 6 мест."""
        if not self.staircase_id:
            auto = (
                f"staircase_{self.stops[0]}_{self.stops[-1]}"
                if len(self.stops) >= 2
                else "staircase"
            )
            object.__setattr__(self, "staircase_id", auto)
        return self

    @model_validator(mode="after")
    def _flag_compat(self) -> "StaircaseSpec":
        if self.outside and not self.has_walls:
            raise ValueError("outside требует has_walls=true (staircase §2)")
        if self.in_a_room and self.outside:
            raise ValueError("in_a_room несовместим с outside (staircase §2)")
        return self
