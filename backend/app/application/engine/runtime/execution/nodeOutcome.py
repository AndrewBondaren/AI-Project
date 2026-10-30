"""Local execution reports; never a node's public Output contract."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, Self, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.taskType import TaskType
from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic, Timestamp
from app.dataModel.engine.dag.identity import ExecutionIdentity
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence

O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)


class LevelDecision(StrEnum):
    CONTINUE = "continue"
    CANCEL = "cancel"
    FAIL = "fail"
    REPLAN = "replan"


class NodeStage(StrEnum):
    ADMISSION = "admission"
    PREPARE = "prepare"
    INPUT_VALIDATION = "input_validation"
    EXECUTE = "execute"
    OUTPUT_VALIDATION = "output_validation"
    SEMANTIC_VALIDATION = "semantic_validation"


@dataclass(frozen=True)
class GateSignal:
    next_task_type: TaskType
    reason: str | None = None

    def __post_init__(self) -> None:
        TypeAdapter[TaskType](TaskType).validate_python(self.next_task_type, strict=True)
        TypeAdapter[str | None](str | None).validate_python(self.reason, strict=True)

    @classmethod
    def validate(cls, value: object) -> Self:
        if not isinstance(value, cls):
            raise TypeError("error policy must return GateSignal or None")
        value.__post_init__()
        return value


@dataclass(frozen=True, kw_only=True)
class NodeOutcome(Generic[O, E]):
    identity: ExecutionIdentity
    status: NodeStatus
    started_at: Timestamp
    completed_at: Timestamp
    output: O | None = field(default=None, repr=False)
    error: E | None = field(default=None, repr=False)
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()
    diagnostics: tuple[ExecutionDiagnostic, ...] = ()
    gate: GateSignal | None = None
    validation: ValidationResult | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        ExecutionIdentity.model_validate(self.identity)
        TypeAdapter[NodeStatus](NodeStatus).validate_python(self.status, strict=True)
        TypeAdapter[float](Timestamp).validate_python(self.started_at)
        TypeAdapter[float](Timestamp).validate_python(self.completed_at)
        if self.completed_at < self.started_at:
            raise ValueError("outcome completed_at precedes started_at")
        if self.status not in (NodeStatus.SUCCESS, NodeStatus.FAILED, NodeStatus.CANCELLED, NodeStatus.GATED):
            raise ValueError("outcome requires a terminal status")
        if (self.status == NodeStatus.SUCCESS) != (self.output is not None):
            raise ValueError("only SUCCESS has an Output")
        if (self.status == NodeStatus.GATED) != (self.gate is not None):
            raise ValueError("only GATED has a gate signal")
        if self.error is not None and self.status not in (NodeStatus.FAILED, NodeStatus.GATED):
            raise ValueError("only FAILED/GATED can carry a declared error")
        if self.status == NodeStatus.GATED and self.error is None:
            raise ValueError("GATED requires its declared error")
        if self.status == NodeStatus.SUCCESS and self.validation is not None and not self.validation.ok:
            raise ValueError("unsuccessful validation cannot produce SUCCESS")
