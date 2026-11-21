from typing import Protocol

from pydantic import BaseModel
from typing import Any

from app.application.lifecycle.contracts.sectionBinding import LifecycleSectionBinding
from app.application.lifecycle.validation.sectionValidator import LifecycleSectionValidator
from app.application.lifecycle.publication.sectionBuilder import LifecycleSectionBuilder
from app.dataModel.lifecycle.results.errors import LifecycleSectionRefused
from app.dataModel.patch.sections.section import DomainSection


class ILifecycleSectionPipelineOpenPipeline[Q: BaseModel, S: DomainSection[Any]](Protocol):
    def prepare_section(self, request: Q) -> S | LifecycleSectionRefused: ...


class LifecycleSectionPipelineOpenPipeline[Q: BaseModel, S: DomainSection[Any]]:
    def __init__(self, *, binding: LifecycleSectionBinding[Q, S]) -> None:
        self._binding = binding
        self._validator = LifecycleSectionValidator(binding)
        self._builder = LifecycleSectionBuilder(binding)

    def prepare_section(self, request: Q) -> S | LifecycleSectionRefused:
        admitted = self._binding.admit(request)
        issues = self._validator.validate(admitted)
        if issues:
            return LifecycleSectionRefused(issues=issues)
        return self._builder.build(admitted)
