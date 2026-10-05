"""Explicit space and optional global geometry — transitions §1/§2/§10.11."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.annotationPolicy import DefaultEnumOnWire, DefaultOnWire, StrictEnumOnWire


class TransitionSpace(StrEnum):
    SURFACE = "surface"
    LEVEL = "level"


type EndpointRef = Annotated[str, Field(min_length=1)]


class EndpointGeometryKind(StrEnum):
    CONCRETE = "concrete"
    SYMBOLIC = "symbolic"


class EndpointIdentityGeometry(BaseModel):
    """Identity-only marker; concrete coordinates remain Endpoint POJO fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    geometry: StrictEnumOnWire[EndpointGeometryKind]


class TransitionEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    space: DefaultEnumOnWire[TransitionSpace] = TransitionSpace.SURFACE
    level_uid: DefaultOnWire[EndpointRef | None] = None
    host_location_uid: DefaultOnWire[EndpointRef | None] = None
    node_uid: DefaultOnWire[EndpointRef | None] = None
    x: DefaultOnWire[StrictInt | None] = None
    y: DefaultOnWire[StrictInt | None] = None
    z: DefaultOnWire[StrictInt | None] = None

    @model_validator(mode="after")
    def _space_and_geometry(self) -> Self:
        if self.space == TransitionSpace.LEVEL and self.level_uid is None:
            raise ValueError("level space requires level_uid")
        if self.space == TransitionSpace.SURFACE and self.level_uid is not None:
            raise ValueError("surface space cannot specify level_uid")
        present = sum(value is not None for value in (self.x, self.y, self.z))
        if present not in (0, 3):
            raise ValueError("endpoint geometry must contain all of x/y/z or none")
        if self.space == TransitionSpace.LEVEL and present == 0:
            raise ValueError("level endpoint requires concrete geometry")
        return self

    @property
    def geometry(self) -> tuple[int, int, int] | None:
        if self.x is None or self.y is None or self.z is None:
            return None
        return self.x, self.y, self.z

    def identity_keys(self) -> dict[str, str | int]:
        """Canonical C3 input: no None, display, side state or inferred refs.

        The wrapper prefixes these keys with a/b, preserving endpoint order.
        A real (0, 0, 0) differs from symbolic surface.
        """
        marker = EndpointIdentityGeometry(
            geometry=(EndpointGeometryKind.CONCRETE if self.geometry is not None
                      else EndpointGeometryKind.SYMBOLIC),
        )
        return {
            **self.model_dump(mode="json", exclude_none=True),
            **marker.model_dump(mode="json"),
        }
