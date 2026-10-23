"""Typed spatial outcomes; the application forwards diagnostics to ResolveReport."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.placement.common import PlacementModel, PlacementText, PlacementUid
from app.dataModel.placement.intent import PlacementIdentity
from app.dataModel.placement.prepared import PlacementFootprint, PreparedPlacement
from app.dataModel.planning.identity.planKey import OutputFingerprint


class PlacementIssueCode(StrEnum):
    MISSING_SPECIFICITY = "PLACEMENT_MISSING_SPECIFICITY"
    MISSING_DEPENDENCY = "PLACEMENT_MISSING_DEPENDENCY"
    FAILED_DEPENDENCY = "PLACEMENT_FAILED_DEPENDENCY"
    DEPENDENCY_CYCLE = "PLACEMENT_DEPENDENCY_CYCLE"
    NO_CANDIDATES = "PLACEMENT_NO_CANDIDATES"
    SPATIAL_CONFLICT = "PLACEMENT_SPATIAL_CONFLICT"
    CONSTRAINT_VIOLATION = "PLACEMENT_CONSTRAINT_VIOLATION"
    UNKNOWN_COASTLINE_WATER = "PLACEMENT_UNKNOWN_COASTLINE_WATER"
    COASTLINE_PRIORITY_LOWERED = "PLACEMENT_COASTLINE_PRIORITY_LOWERED"


class PlacementDiagnostic(PlacementModel):
    code: StrictEnumOnWire[PlacementIssueCode]
    region_uid: StrictOnWire[PlacementUid]
    related_uids: DefaultWhenMissing[tuple[PlacementUid, ...]] = ()
    path: DefaultWhenMissing[tuple[StrictStr | StrictInt, ...]] = ()
    detail: StrictOnWire[PlacementText]

    @property
    def unresolved(self) -> bool:
        return self.code != PlacementIssueCode.COASTLINE_PRIORITY_LOWERED


class ResolvedPlacement(PlacementModel):
    status: DefaultWhenMissing[Literal["resolved"]] = "resolved"
    prepared: StrictOnWire[PreparedPlacement]
    candidate_uid: StrictOnWire[PlacementUid]

    @model_validator(mode="after")
    def valid_selection(self) -> Self:
        if self.prepared.effective_specificity is None:
            raise ValueError("resolved placement requires effective specificity")
        if not any(c.candidate_uid == self.candidate_uid for c in self.prepared.candidates):
            raise ValueError("resolved placement must select an existing candidate")
        return self

    @property
    def identity(self) -> PlacementIdentity:
        return self.prepared.intent.identity

    @property
    def footprint(self) -> PlacementFootprint:
        return next(c.footprint for c in self.prepared.candidates if c.candidate_uid == self.candidate_uid)

    @property
    def original_area(self) -> float:
        return self.prepared.original_area

    @property
    def effective_specificity(self) -> int:
        value = self.prepared.effective_specificity
        if value is None:
            raise ValueError("resolved placement lost effective specificity")
        return value


class UnresolvedPlacement(PlacementModel):
    status: DefaultWhenMissing[Literal["unresolved"]] = "unresolved"
    prepared: StrictOnWire[PreparedPlacement]
    diagnostics: StrictOnWire[tuple[PlacementDiagnostic, ...]] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_failure(self) -> Self:
        uid = self.prepared.intent.identity.region_uid
        if not any(issue.unresolved for issue in self.diagnostics):
            raise ValueError("unresolved placement requires an unresolved diagnostic")
        if any(issue.region_uid != uid for issue in self.diagnostics):
            raise ValueError("unresolved diagnostics must identify the failed placement")
        return self


type PlacementOutcome = Annotated[ResolvedPlacement | UnresolvedPlacement, Field(discriminator="status")]


class PlacementBatchResult(PlacementModel):
    model_config = {**PlacementModel.model_config, "ser_json_bytes": "hex", "val_json_bytes": "hex"}

    world_uid: StrictOnWire[PlacementUid]
    snapshot_uid: StrictOnWire[PlacementUid]
    snapshot_revision: StrictOnWire[OutputFingerprint] = Field(strict=True, min_length=32, max_length=32)
    results: StrictOnWire[tuple[PlacementOutcome, ...]]
    diagnostics: DefaultWhenMissing[tuple[PlacementDiagnostic, ...]] = ()

    @model_validator(mode="after")
    def valid_identities(self) -> Self:
        identities = [item.prepared.intent.identity for item in self.results]
        if any(identity.world_uid != self.world_uid for identity in identities):
            raise ValueError("placement results must belong to batch world")
        uids = [identity.region_uid for identity in identities]
        if len(uids) != len(set(uids)):
            raise ValueError("duplicate placement result region_uid")
        if any(issue.region_uid not in uids for issue in self.diagnostics):
            raise ValueError("batch diagnostic must identify a result")
        return self
