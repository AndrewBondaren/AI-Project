"""Single physical transition aggregate for generation, SQL and pack (C2)."""

from __future__ import annotations

from typing import Annotated, ClassVar, Self

from pydantic import (
    BaseModel, ConfigDict, Field, SerializeAsAny, ValidationInfo,
    model_validator,
)

from app.dataModel.annotationPolicy import (
    DefaultEnumWhenMissing, DefaultWhenMissing, StrictOnWire,
)
from app.dataModel.locations.enums.accessMechanic import AccessMechanic
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.transitionOrigin import TransitionOrigin
from app.dataModel.locations.transitions.transitionParams import (
    GateTransitionParams, PhysicalTransitionParams, StaircaseTransitionParams, params_model_for,
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
    source_side: DefaultWhenMissing[TransitionSide] = Field(default_factory=TransitionSide)
    destination_side: DefaultWhenMissing[TransitionSide] = Field(default_factory=TransitionSide)
    origin: DefaultEnumWhenMissing[TransitionOrigin] = TransitionOrigin.GENERATED
    is_bidirectional: DefaultWhenMissing[bool] = True
    is_active: DefaultWhenMissing[bool] = True
    access_mechanic: DefaultWhenMissing[list[AccessMechanic]] = Field(default_factory=list)
    type_params: DefaultWhenMissing[SerializeAsAny[
        PhysicalTransitionParams | GateTransitionParams | StaircaseTransitionParams
    ]] = Field(
        default_factory=PhysicalTransitionParams,
    )
    display_name: DefaultWhenMissing[str | None] = None
    glossary_ref: DefaultWhenMissing[str | None] = None
    tag_refs: DefaultWhenMissing[list[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _type_contract(self, info: ValidationInfo) -> Self:
        """Normalize during construction using validated fields only.

        The aggregate stays frozen after construction; supplied side objects are
        never mutated. fields_set distinguishes omitted defaults from explicit state.
        """
        builtin = _builtin(self.system_transition_type, info)
        params_model = params_model_for(builtin)
        if type(self.type_params) is PhysicalTransitionParams and params_model is StaircaseTransitionParams:
            object.__setattr__(self, "type_params", StaircaseTransitionParams())
        elif type(self.type_params) is not params_model:
            raise ValueError(f"{builtin.value} requires {params_model.__name__}")
        if builtin == TransitionType.HIDDEN_ENTRANCE and "is_discovered" not in self.destination_side.model_fields_set:
            object.__setattr__(self, "destination_side",
                self.destination_side.model_copy(update={"is_discovered": False}))
        if builtin == TransitionType.FALL and "is_bidirectional" not in self.model_fields_set:
            object.__setattr__(self, "is_bidirectional", False)
        if not builtin.directional and not self.is_bidirectional:
            raise ValueError("non-directional types require is_bidirectional=true")
        if builtin == TransitionType.FALL and self.is_bidirectional:
            raise ValueError("fall requires is_bidirectional=false")
        return self
