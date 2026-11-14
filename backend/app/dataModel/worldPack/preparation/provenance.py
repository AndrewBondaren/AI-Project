"""Stored origin and admission modes of a Pack payload."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.validation.immutableValue import validate_immutable


class _PackProvenanceValue(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    @model_validator(mode="after")
    def immutable_value(self) -> Self:
        validate_immutable(self)
        return self


class PackStoredProvenance(_PackProvenanceValue):
    source_proof: SourceDurableProof
    planning: tuple[PlanDependency, ...]


class PackNewPartProvenance(_PackProvenanceValue):
    kind: Literal["new"]
    provenance: PackStoredProvenance


class PackInheritedPartProvenance(_PackProvenanceValue):
    kind: Literal["inherited"]
    provenance: PackStoredProvenance


PackPartProvenance = Annotated[
    PackNewPartProvenance | PackInheritedPartProvenance,
    Field(discriminator="kind"),
]
