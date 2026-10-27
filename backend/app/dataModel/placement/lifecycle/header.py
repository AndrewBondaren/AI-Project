"""Placement identity and relations available before geometry preparation."""

from typing import Protocol, Self

from pydantic import model_validator

from app.dataModel.placement.common import PlacementMode, PlacementModel
from app.dataModel.placement.intent import (
    PlacementDependency, PlacementIdentity, PlacementIntent, PlacementOverlap, PlacementSeparation,
)
from app.dataModel.placement.prepared import PlacementFootprint


class PlacementHeader(PlacementModel):
    identity: PlacementIdentity
    mode: PlacementMode
    dependencies: tuple[PlacementDependency, ...]
    permitted_overlaps: tuple[PlacementOverlap, ...]
    separations: tuple[PlacementSeparation, ...]

    @model_validator(mode="after")
    def valid_relations(self) -> Self:
        PlacementIntent(identity=self.identity, mode=self.mode, shape=None,
            dependencies=self.dependencies, permitted_overlaps=self.permitted_overlaps, separations=self.separations)
        return self

    @classmethod
    def from_intent(cls, intent: PlacementIntent) -> Self:
        return cls(identity=intent.identity, mode=intent.mode, dependencies=intent.dependencies,
                   permitted_overlaps=intent.permitted_overlaps, separations=intent.separations)


class PreparedGeometry(Protocol):
    @property
    def intent(self) -> PlacementIntent: ...


class ResolvedGeometry(Protocol):
    @property
    def identity(self) -> PlacementIdentity: ...

    @property
    def footprint(self) -> PlacementFootprint: ...

    @property
    def prepared(self) -> PreparedGeometry: ...
