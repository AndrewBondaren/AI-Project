"""Public pure create operation; called directly by the DAG."""
from typing import Protocol
from pydantic import BaseModel

from app.application.lifecycle.contracts.preparationBinding import LifecyclePreparationBinding
from app.application.lifecycle.contracts.preparationPolicy import LifecyclePreparationPolicy
from app.application.lifecycle.validation.transitionValidator import LifecycleTransitionValidator
from app.application.lifecycle.changes.changeBuilder import LifecycleChangeBuilder
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.results.issues import LifecycleFieldIssue
from app.dataModel.lifecycle.results.errors import LifecycleFieldError, LifecycleLogicError


class ILifecycleCreatePipelineOpenPipeline[Q: BaseModel, P: BaseModel](Protocol):
    def prepare_create(self, request: Q) -> P | LifecycleFieldError | LifecycleLogicError: ...


class LifecycleCreatePipelineOpenPipeline[Q: BaseModel, P: BaseModel]:
    def __init__(self, *, binding: LifecyclePreparationBinding[Q, P],
                 policy: LifecyclePreparationPolicy) -> None:
        if binding.operation is not LifecycleOperation.CREATE:
            raise TypeError("public operation requires the matching request/prepared binding")
        self._binding = binding
        self._validator = LifecycleTransitionValidator(binding, policy)
        self._builder = LifecycleChangeBuilder(binding)

    def prepare_create(self, request: Q) -> P | LifecycleFieldError | LifecycleLogicError:
        admitted = self._binding.admit(request)
        issues = self._validator.validate_create(admitted)
        if issues:
            if any(type(issue) is LifecycleFieldIssue for issue in issues):
                return LifecycleFieldError(issues=issues)
            return LifecycleLogicError(issues=issues)
        return self._builder.build_create(admitted)
