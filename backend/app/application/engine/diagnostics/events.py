"""Application control fields in diagnostics; TaskType stays out of dataModel."""

from app.application.engine.taskType import TaskType
from pydantic import BaseModel, ConfigDict

from app.application.engine.contracts.executionBindings import PassStage
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic, ExecutionEventCode, ExecutionSeverity, Index, Timestamp
from app.dataModel.engine.dag.identity import ExecutionIdValue, PlanRevisionValue
from app.dataModel.engine.dag.nodeStatus import NodeStatus


class ReplanDiagnostic(ExecutionDiagnostic):
    next_task_type: TaskType
    replan_reason: str | None = None


class LevelDiagnostic(ExecutionDiagnostic):
    gate_events: tuple[ReplanDiagnostic, ...] = ()
    gate_conflict: bool = False


class LifecycleDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    execution_id: ExecutionIdValue
    plan_revision: PlanRevisionValue
    pass_number: Index
    stage: PassStage | None
    code: ExecutionEventCode
    severity: ExecutionSeverity
    timestamp: Timestamp
    status: NodeStatus
    message: str
