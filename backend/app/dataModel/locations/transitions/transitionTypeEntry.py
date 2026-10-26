"""One N+1 ``worlds.transition_type_registry[]`` row, with builtin behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.locations.transitions.transitionType import (
    TransitionType,
    TransitionTypeSpec,
    TransitionVertical,
)
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.locations.transitions.worldTransitionTypeRegistry import (
        WorldTransitionTypeRegistry,
    )


class TransitionTypeEntry(BaseModel):
    """World display types delegate all behavior to the required ``behaves_as``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_type: StrictOnWire[RegistryKey[WorldTransitionTypeRegistry]]
    display_name: StrictOnWire[str]
    behaves_as: StrictEnumOnWire[TransitionType]
    glossary_ref: DefaultWhenMissing[str | None] = None

    @model_validator(mode="after")
    def _builtin_behavior(self) -> Self:
        if self.system_type in TransitionType._value2member_map_:
            if self.behaves_as != TransitionType(self.system_type):
                raise ValueError("builtin transition types cannot change behaves_as")
        return self

    @property
    def spec(self) -> TransitionTypeSpec:
        return self.behaves_as.spec

    @property
    def entry(self) -> bool:
        return self.spec.entry

    @property
    def directional(self) -> bool:
        return self.spec.directional

    @property
    def vertical(self) -> TransitionVertical:
        return self.spec.vertical
