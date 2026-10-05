"""Single physical transition aggregate for generation, SQL and pack (C2)."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Self

from pydantic import (
    BaseModel, ConfigDict, Field, SerializeAsAny, ValidationInfo,
    field_validator, model_validator,
)

from app.dataModel.annotationPolicy import (
    DefaultEnumOnWire, DefaultOnWire, StrictOnWire,
)
from app.dataModel.locations.enums.accessMechanic import AccessMechanic
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionOrigin import TransitionOrigin
from app.dataModel.locations.transitions.transitionParams import (
    PhysicalTransitionParams, params_model_for,
)
from app.dataModel.locations.transitions.transitionSide import TransitionSide
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import (
    TransitionTypeKey, WorldTransitionTypeRegistry,
)


def _builtin(system_type: str, info: ValidationInfo) -> TransitionType:
    registry = (info.context or {}).get("transition_type_registry")
    if registry is None:
        registry = WorldTransitionTypeRegistry.canonical_engine()
    if not isinstance(registry, WorldTransitionTypeRegistry):
        raise ValueError("transition_type_registry context must be typed")
    builtin = registry.type_for(system_type)
    if builtin is None:
        raise ValueError(f"unknown transition type {system_type!r}")
    return builtin


class Transition(BaseModel):
    """Exactly two endpoints and two sides; registry is caller validation context.

    Custom N+1 keys require context={"transition_type_registry": typed_registry}.
    No parent, traversal, discovery or regenerate policy is inferred here.
    """

    SCHEMA_ID: ClassVar[str] = "SCH-LOCATION-TRANSITION"
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    transition_uid: StrictOnWire[Annotated[str, Field(min_length=1)]]
    world_uid: StrictOnWire[Annotated[str, Field(min_length=1)]]
    system_transition_type: StrictOnWire[TransitionTypeKey]
    source: StrictOnWire[TransitionEndpoint]
    destination: StrictOnWire[TransitionEndpoint]
    source_side: DefaultOnWire[TransitionSide] = Field(default_factory=TransitionSide)
    destination_side: DefaultOnWire[TransitionSide] = Field(default_factory=TransitionSide)
    origin: DefaultEnumOnWire[TransitionOrigin] = TransitionOrigin.GENERATED
    is_bidirectional: DefaultOnWire[bool] = True
    is_active: DefaultOnWire[bool] = True
    access_mechanic: DefaultOnWire[list[AccessMechanic]] = Field(default_factory=list)
    type_params: DefaultOnWire[SerializeAsAny[PhysicalTransitionParams]] = Field(
        default_factory=PhysicalTransitionParams,
    )
    display_name: DefaultOnWire[str | None] = None
    glossary_ref: DefaultOnWire[str | None] = None
    tag_refs: DefaultOnWire[list[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _type_defaults(cls, value: Any, info: ValidationInfo) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("system_transition_type"), str):
            return value
        builtin = _builtin(value["system_transition_type"], info)
        data = dict(value)
        if builtin == TransitionType.HIDDEN_ENTRANCE:
            side = data.get("destination_side", {})
            if isinstance(side, dict):
                data["destination_side"] = {"is_discovered": False, **side}
        if builtin == TransitionType.FALL:
            data.setdefault("is_bidirectional", False)
        return data

    @field_validator("type_params", mode="before")
    @classmethod
    def _typed_params(cls, value: Any, info: ValidationInfo) -> PhysicalTransitionParams:
        system_type = info.data.get("system_transition_type")
        if system_type is None:
            raise ValueError("type_params require source valid system_transition_type")
        model = params_model_for(_builtin(system_type, info))
        wire = value.model_dump() if isinstance(value, PhysicalTransitionParams) else value
        return model.model_validate(wire)

    @model_validator(mode="after")
    def _direction(self, info: ValidationInfo) -> Self:
        builtin = _builtin(self.system_transition_type, info)
        if not builtin.directional and not self.is_bidirectional:
            raise ValueError("non-directional types require is_bidirectional=true")
        if builtin == TransitionType.FALL and self.is_bidirectional:
            raise ValueError("fall requires is_bidirectional=false")
        return self
