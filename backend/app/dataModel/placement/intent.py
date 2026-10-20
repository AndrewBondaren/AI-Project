"""Immutable authored intentions; spatial competition belongs to P2."""

from typing import ClassVar, Self

from pydantic import BaseModel, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultEnumWhenMissing, DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.placement.common import (
    AbsoluteMovement, DependencyRelation, NonNegativeInt, OverlapRelation, PlacementMode,
    PlacementModel, PlacementUid, Specificity,
)
from app.dataModel.spatial.regionShape import RegionShape


class PlacementIdentity(PlacementModel):
    world_uid: StrictOnWire[PlacementUid]
    source_uid: StrictOnWire[PlacementUid]
    region_uid: StrictOnWire[PlacementUid]


class PlacementDependency(PlacementModel):
    target_uid: StrictOnWire[PlacementUid]
    relation: StrictEnumOnWire[DependencyRelation]


class PlacementOverlap(PlacementModel):
    target_uid: StrictOnWire[PlacementUid]
    relation: StrictEnumOnWire[OverlapRelation]


class PlacementSeparation(PlacementModel):
    target_uid: StrictOnWire[PlacementUid]
    min_xy: StrictOnWire[NonNegativeInt]
    min_z: StrictOnWire[NonNegativeInt]


class PlacementIntent(PlacementModel):
    SCHEMA_ID: ClassVar[str] = "SCH-PLACEMENT-INTENT"

    identity: StrictOnWire[PlacementIdentity]
    mode: StrictEnumOnWire[PlacementMode]
    shape: StrictOnWire[RegionShape | None]
    placement_specificity: DefaultWhenMissing[Specificity | None] = None
    absolute_movement: DefaultEnumWhenMissing[AbsoluteMovement] = AbsoluteMovement.FORBID
    dependencies: StrictOnWire[tuple[PlacementDependency, ...]]
    permitted_overlaps: StrictOnWire[tuple[PlacementOverlap, ...]]
    separations: StrictOnWire[tuple[PlacementSeparation, ...]]

    @field_validator("shape", mode="before")
    @classmethod
    def validate_existing_shape(cls, value):
        # Existing spatial POJOs do not revalidate instances. Validate their
        # actual supplied fields, including copies built outside this boundary.
        # Include the discriminator's declared default when revalidating a
        # typed primitive; exclude_unset would discard kind for constructors.
        return value.model_dump(warnings=False) if isinstance(value, BaseModel) else value

    @model_validator(mode="after")
    def valid_relations(self) -> Self:
        for relations in (self.dependencies, self.permitted_overlaps, self.separations):
            keys = set()
            for relation in relations:
                if relation.target_uid == self.identity.region_uid:
                    raise ValueError("placement relation cannot target its own region_uid")
                key = (relation.target_uid, getattr(relation, "relation", None))
                if key in keys:
                    raise ValueError("duplicate placement relation")
                keys.add(key)
        return self
