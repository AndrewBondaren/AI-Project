from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.dataModel.lifecycle.results.issues import LifecycleFieldIssue, LifecycleIssue, LifecycleRelationIssue
from app.dataModel.lifecycle.results.refusalKind import LifecycleRefusalKind


class LifecycleFieldError(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal[LifecycleRefusalKind.FIELD_REFUSAL] = LifecycleRefusalKind.FIELD_REFUSAL
    issues: tuple[LifecycleIssue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def requires_field_issue(self) -> Self:
        if not any(type(issue) is LifecycleFieldIssue for issue in self.issues):
            raise ValueError("field refusal requires at least one field issue")
        return self


class LifecycleLogicError(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal[LifecycleRefusalKind.LOGIC_REFUSAL] = LifecycleRefusalKind.LOGIC_REFUSAL
    issues: tuple[LifecycleRelationIssue, ...] = Field(min_length=1)


class LifecycleSectionRefused(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal[LifecycleRefusalKind.SECTION_REFUSAL] = LifecycleRefusalKind.SECTION_REFUSAL
    issues: tuple[LifecycleIssue, ...] = Field(min_length=1)
