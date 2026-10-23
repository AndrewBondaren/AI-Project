"""A lookup request bound to a concrete immutable input type."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.planning.contracts.planDependency import PlanDependency, require_canonical_dependencies
from app.dataModel.planning.identity.planKey import PlanKey


I = TypeVar("I")


class PlanRequest(BaseModel, Generic[I]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    key: PlanKey
    inputs: I
    dependencies: tuple[PlanDependency, ...]

    _canonical_dependencies = field_validator("dependencies")(require_canonical_dependencies)
