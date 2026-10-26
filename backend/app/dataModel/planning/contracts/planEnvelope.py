"""Immutable result and completed envelope; no live source or request state."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.planning.contracts.planDependency import PlanDependency, require_canonical_dependencies
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.planRef import PlanRef


T = TypeVar("T")


class PlanBuildResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    payload: T
    diagnostics: tuple[PlanDiagnostic, ...]


class PlanEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    ref: PlanRef
    dependencies: tuple[PlanDependency, ...]
    payload: T
    diagnostics: tuple[PlanDiagnostic, ...]

    _canonical_dependencies = field_validator("dependencies")(require_canonical_dependencies)
