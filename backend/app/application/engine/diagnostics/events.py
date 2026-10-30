"""Application control fields in diagnostics; TaskType stays out of dataModel."""

from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic


class ReplanDiagnostic(ExecutionDiagnostic):
    next_task_type: TaskType
    replan_reason: str | None = None


class LevelDiagnostic(ExecutionDiagnostic):
    gate_events: tuple[ReplanDiagnostic, ...] = ()
    gate_conflict: bool = False
