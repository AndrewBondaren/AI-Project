"""Mountain form / side / Spec POJOs — tz_map_light_bake § Mountain (engine)."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, DefaultEnumOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.terrainMasks.mountain.enums import (
    MountainFormType,
    MountainKind,
    MountainSideKind,
)


def _policy_default_radius_m() -> int:
    # Q8: single SoT — MountainsCategoryPolicy.default_radius_m (avoid literal 500 here).
    from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy

    return int(MountainsCategoryPolicy.model_construct().default_radius_m)


class MountainFormBySides(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    form_type: Literal["by_sides"] = MountainFormType.BY_SIDES.value
    side_count: DefaultOnWire[int] = Field(default=6, ge=3)


class StarForm(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    form_type: Literal["star"] = MountainFormType.STAR.value
    rays: DefaultOnWire[int] = Field(default=5, ge=3)
    inner_ratio: DefaultOnWire[float] = constrained_field(
        default=0.45, greater_equals=0.05, lesser_equals=0.95,
    )


class PeakForm(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    form_type: Literal["peak"] = MountainFormType.PEAK.value
    side_count: DefaultOnWire[int] = Field(default=3, ge=3)


class PlateauForm(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    form_type: Literal["plateau"] = MountainFormType.PLATEAU.value
    side_count: DefaultOnWire[int] = Field(default=6, ge=3)
    hat_fraction: DefaultOnWire[float] = constrained_field(
        default=0.45, greater_equals=0.05, lesser_equals=1.0,
    )


MountainForm = Annotated[
    Union[MountainFormBySides, StarForm, PeakForm, PlateauForm],
    Field(discriminator="form_type"),
]


class MountainSideSpec(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: DefaultEnumOnWire[MountainSideKind] = MountainSideKind.SLOPE
    sheer_band_light: DefaultOnWire[int] = Field(default=1, ge=0)


def default_sides_for_count(
    side_count: int,
    *,
    kind: MountainSideKind = MountainSideKind.SLOPE,
) -> list[MountainSideSpec]:
    n = max(3, int(side_count))
    return [MountainSideSpec(kind=kind) for _ in range(n)]


def form_side_count(form: MountainFormBySides | StarForm | PeakForm | PlateauForm) -> int:
    if isinstance(form, StarForm):
        return int(form.rays)
    return int(form.side_count)


class MountainSpec(BaseModel):
    """Single peak / massif — declare or autoresolve assemble."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    entry_type: Literal["mountain"] = "mountain"
    origin_x_m: int
    origin_y_m: int
    radius_m: DefaultOnWire[int] = Field(default_factory=_policy_default_radius_m, ge=1)
    kind: DefaultEnumOnWire[MountainKind] = MountainKind.ROCKY
    form: MountainForm = Field(default_factory=MountainFormBySides)
    sides: DefaultOnWire[list[MountainSideSpec]] = Field(default_factory=list)
    location_uid: str | None = None

    def resolved_sides(self) -> list[MountainSideSpec]:
        n = form_side_count(self.form)
        if len(self.sides) == n:
            return list(self.sides)
        if self.sides:
            raise ValueError(
                f"MountainSpec.sides length {len(self.sides)} != form side_count {n}"
            )
        return default_sides_for_count(n)

    def identity_key(self) -> tuple[object, ...]:
        return ("mountain", self.location_uid, self.origin_x_m, self.origin_y_m, self.radius_m)


class MountainRangeSides(BaseModel):
    """Lateral + optional end-cap SideFill for a range corridor (tz § Range sides)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    left: MountainSideSpec = Field(
        default_factory=lambda: MountainSideSpec(kind=MountainSideKind.SLOPE),
    )
    right: MountainSideSpec = Field(
        default_factory=lambda: MountainSideSpec(kind=MountainSideKind.SLOPE),
    )
    start: MountainSideSpec | None = None
    end: MountainSideSpec | None = None


class MountainRangeSpec(BaseModel):
    """Elongated ridge — spine + width; peaks use full MountainSpec pipeline."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    entry_type: Literal["range"] = "range"
    spine: list[tuple[int, int]] = Field(min_length=2)
    width_m: DefaultOnWire[int] = Field(default_factory=_policy_default_radius_m, ge=1)
    kind: DefaultEnumOnWire[MountainKind] = MountainKind.ROCKY
    sides: DefaultOnWire[MountainRangeSides] = Field(default_factory=MountainRangeSides)
    peaks: DefaultOnWire[list[MountainSpec]] = Field(default_factory=list)
    location_uid: str | None = None

    def identity_key(self) -> tuple[object, ...]:
        return ("range", self.location_uid, tuple(self.spine), self.width_m)


MountainDeclareEntry = Annotated[
    Union[MountainSpec, MountainRangeSpec],
    Field(discriminator="entry_type"),
]
