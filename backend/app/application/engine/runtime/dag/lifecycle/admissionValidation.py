from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError

from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMOptionFields
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.errors.admissionIssue import AdmissionFieldIssue, AdmissionIssueCode
from app.dataModel.engine.dag.identity import ExecutionId, ExecutionIdValue
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


def _require_options(value: object) -> LLMExecutionOptions:
    if not isinstance(value, LLMExecutionOptions):
        raise ValueError("expected LLMExecutionOptions")
    return value


type OptionsArgument = Annotated[LLMOptionFields, BeforeValidator(_require_options)]


class _ExecutionArguments(BaseModel):
    model_config = ConfigDict(strict=True)

    execution_id: ExecutionIdValue
    max_passes: Annotated[int, Field(gt=0)]


class _RunArguments(_ExecutionArguments):
    task_type: TaskType
    options: OptionsArgument


class _ResumeArguments(_ExecutionArguments):
    options: OptionsArgument


def _validate(schema: type[_ExecutionArguments], **arguments: object) -> None:
    try:
        schema.model_validate(arguments)
    except ValidationError as exc:
        issues = ValidatorAggregationHelper((AdmissionFieldIssue,))
        inputs: dict[tuple[str | int, ...], object] = {}
        for error in exc.errors(include_url=False):
            loc = error["loc"]
            path = CheckedPath.from_pydantic_loc(schema, loc)
            if path is None:
                raise RuntimeError(f"unexpected admission diagnostic path {loc!r}") from exc
            code = AdmissionIssueCode(f"invalid_{loc[0]}")
            issues.add(AdmissionFieldIssue(code=code, path=path, message=error["msg"]))
            inputs[loc] = error["input"]

        def failure(collected: tuple[AdmissionFieldIssue, ...]) -> ValidationError:
            details = [
                InitErrorDetails(type=PydanticCustomError(issue.code.value, "{message}", {"message": issue.message}),
                                 loc=issue.path.projection(), input=inputs[issue.path.projection()])
                for issue in collected
            ]
            return ValidationError.from_exception_data("DAG execution arguments", details)

        issues.raise_if_any(failure)


def validate_run(execution_id: ExecutionId, max_passes: int, task_type: TaskType, options: LLMExecutionOptions) -> None:
    _validate(_RunArguments, execution_id=execution_id, max_passes=max_passes, task_type=task_type, options=options)


def validate_resume(execution_id: ExecutionId, max_passes: int, options: LLMExecutionOptions) -> None:
    _validate(_ResumeArguments, execution_id=execution_id, max_passes=max_passes, options=options)
