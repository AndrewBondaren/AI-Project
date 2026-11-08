from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.executionBindings import ResolveResult
from app.application.engine.contracts.invocation.executionStore import Checkpoint, RestoreFailure
from app.application.engine.contracts.invocation.inputWait import Failed
from app.dataModel.engine.dag.identity import ExecutionId
from app.dataModel.engine.dag.invocations.record import FailedOutcome


def terminal_result[O: BaseModel](
    saved: Checkpoint, execution_id: ExecutionId, response_type: type[O],
) -> ResolveResult[O] | Failed:
    intent = saved.stop_intent
    if intent is None or intent.execution_id != execution_id or saved.final_revision != intent.stop_revision + 1:
        raise RestoreFailure("invalid finalized execution")
    if isinstance(intent.outcome, FailedOutcome):
        return Failed(intent.outcome.diagnostic)
    try:
        return TypeAdapter[ResolveResult[O]](ResolveResult[response_type]).validate_json(intent.outcome.result_json)
    except ValueError as exc:
        raise RestoreFailure("invalid final response") from exc
