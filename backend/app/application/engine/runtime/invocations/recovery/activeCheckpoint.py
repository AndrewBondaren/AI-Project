from collections.abc import Mapping

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.executionBindings import ExecutionResult, LifecycleBinding, ResolveResult
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.executionStore import Checkpoint, Claim, RestoreFailure
from app.application.engine.contracts.invocation.inputWait import Failed
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.dag.lifecycle.passExecution import PassExecution
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.application.engine.runtime.invocations.ownedExecution import OwnedExecution
from app.application.engine.runtime.invocations.sessionFrame import SessionFrame
from app.dataModel.engine.dag.diagnostics import CancellationRequest
from app.dataModel.engine.dag.identity import DomainRevision
from app.dataModel.engine.dag.invocations.record import CompletedOutcome, FailedOutcome, InvocationGraph


class ActiveCheckpoint[O: BaseModel, S: BaseModel]:
    def __init__(
        self, binding: LifecycleBinding[O], snapshots: ExecutionSnapshotService[S], registry: NodeRegistry,
        passes: PassExecution[O, S], *, enable_stop_intent: bool,
    ) -> None:
        self._binding = binding
        self._snapshots = snapshots
        self._registry = registry
        self._passes = passes
        self._enable_stop_intent = enable_stop_intent

    async def resume(
        self, saved: Checkpoint, header: InvocationGraph, frame: SessionFrame, claim: Claim,
        settings: InvocationOptions, max_passes: int, options: LLMExecutionOptions,
        confirmed: Mapping[str, DomainRevision] | None, cancellation: CancellationRequest | None,
    ) -> ExecutionResult[O]:
        assert frame.cursor is not None and header.session is not None
        try:
            revision, plan = self._binding.compile(frame.cursor.task_type, frame.metadata.pass_number)
            graph = await CheckpointCodec.restore(saved.blob, plan)
            owned = OwnedExecution(settings.store, claim, saved.revision, graph, settings.lease_seconds)
            if graph.initial_task is None and frame.metadata.pass_number == 0:
                graph.initial_task = frame.cursor.task_type.value
            if revision != graph.revision or plan.invocation_root != graph.records[graph.root].node_id:
                raise ValueError("durable plan changed")
            if graph.cancellation is not None or graph.failure is not None:
                diagnostic = graph.cancellation or graph.failure or "execution failed"
                if self._enable_stop_intent:
                    await owned.stop(FailedOutcome(diagnostic=diagnostic))
                return Failed(diagnostic)
            if graph.waiting_for_input:
                return InputWaitCoordinator.waiting(graph, plan)
            if graph.response is not None:
                result = TypeAdapter[ResolveResult[O]](ResolveResult[self._binding.response_type]).validate_json(graph.response)
                if self._enable_stop_intent:
                    await owned.stop(CompletedOutcome(result_json=graph.response))
                return result
            state = await self._snapshots.decode(header.session, self._registry)
        except (ValueError, KeyError, TypeError) as exc:
            raise RestoreFailure("incompatible durable execution") from exc
        return await self._passes.run(state, plan, max_passes, options, confirmed, cancellation, owned)
