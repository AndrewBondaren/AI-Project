from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.dataModel.lifecycle.results.issues import LifecycleFieldIssue, LifecycleIssue, LifecycleRelationIssue


class LifecycleFieldError(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal["field_refusal"] = "field_refusal"
    issues: tuple[LifecycleIssue, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def requires_field_issue(self) -> Self:
        if not any(type(issue) is LifecycleFieldIssue for issue in self.issues):
            raise ValueError("field refusal requires at least one field issue")
        return self


class LifecycleLogicError(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal["logic_refusal"] = "logic_refusal"
    issues: tuple[LifecycleRelationIssue, ...] = Field(min_length=1)


class LifecycleSectionRefused(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal["section_refusal"] = "section_refusal"
    issues: tuple[LifecycleIssue, ...] = Field(min_length=1)
