from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.executionStore import Checkpoint, RestoreFailure
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.application.engine.runtime.invocations.sessionFrame import SessionFrame
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.identity import ExecutionId
from app.dataModel.engine.dag.invocations.record import InvocationGraph


def read_header(
    saved: Checkpoint, execution_id: ExecutionId, settings: InvocationOptions,
    max_passes: int, requested_task: TaskType | None,
) -> tuple[InvocationGraph, SessionFrame]:
    try:
        header = InvocationGraph.model_validate_json(saved.blob)
        if header.session is None or header.execution_id != execution_id:
            raise ValueError("execution has no lifecycle checkpoint")
        if header.interaction_owner is not None:
            InputWaitCoordinator.check_owner(header, settings.interaction)
        frame = SessionFrame.model_validate_json(header.session)
        if frame.metadata.execution_id != execution_id or frame.metadata.plan_revision != header.revision:
            raise RestoreFailure("lifecycle identity mismatch")
        if frame.cursor is None or (saved.stop_intent is None and frame.metadata.pass_number >= max_passes):
            raise ValueError("invalid durable lifecycle cursor")
        initial_task = header.initial_task
        if initial_task is None and frame.metadata.pass_number == 0:
            initial_task = frame.cursor.task_type.value
        if requested_task is not None and initial_task != requested_task.value:
            raise ValueError("duplicate execution request differs")
        return header, frame
    except ValueError as exc:
        raise RestoreFailure("incompatible durable execution") from exc
