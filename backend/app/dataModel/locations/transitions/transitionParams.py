"""Typed params for current physical transitions; portal projection is deferred."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.annotationPolicy import DefaultEnumWhenMissing, StrictOnWire
from app.dataModel.locations.structure.enums.staircaseType import StaircaseType
from app.dataModel.locations.transitions.transitionType import TransitionType


class PhysicalTransitionParams(BaseModel):
    """Existing passages without type-specific payload still have a strict empty object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GateTransitionParams(PhysicalTransitionParams):
    width_cells: StrictOnWire[Annotated[StrictInt, Field(ge=1)]]


class StaircaseTransitionParams(PhysicalTransitionParams):
    staircase_type: DefaultEnumWhenMissing[StaircaseType] = Field(
        default_factory=StaircaseType.generator_default,
    )


def params_model_for(builtin: TransitionType) -> type[PhysicalTransitionParams]:
    if builtin == TransitionType.PORTAL:
        raise ValueError("operational portal params are deferred (PORTAL-T-1)")
    if builtin == TransitionType.GATE:
        return GateTransitionParams
    if builtin == TransitionType.STAIRCASE:
        return StaircaseTransitionParams
    return PhysicalTransitionParams
