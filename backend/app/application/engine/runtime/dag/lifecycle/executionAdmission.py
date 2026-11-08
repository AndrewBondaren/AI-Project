from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, Field, TypeAdapter

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionCursor, ExecutionResult, LifecycleBinding, PassStage
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.dag.lifecycle.passExecution import PassExecution
from app.application.engine.runtime.dag.lifecycle.sessionRecovery import SessionRecovery
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.recovery.executionRecovery import ExecutionRecovery
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import CancellationRequest
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, ExecutionIdValue


class ExecutionAdmission[O: BaseModel, S: BaseModel]:
    def __init__(
        self, settings: InvocationOptions | None, registry: NodeRegistry, binding: LifecycleBinding[O],
        snapshots: ExecutionSnapshotService[S], store: SnapshotStore[S], sessions: SessionRecovery[O, S],
        recovery: ExecutionRecovery[O, S], passes: PassExecution[O, S],
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._binding = binding
        self._snapshots = snapshots
        self._store = store
        self._sessions = sessions
        self._recovery = recovery
        self._passes = passes
        self._active: set[ExecutionId] = set()

    def _enter(self, execution_id: ExecutionId, max_passes: int) -> None:
        TypeAdapter[ExecutionId](ExecutionIdValue).validate_python(execution_id)
        TypeAdapter(Annotated[int, Field(strict=True, gt=0)]).validate_python(max_passes)
        if execution_id in self._active:
            raise RuntimeError("execution is already running")
        self._active.add(execution_id)

    async def run(
        self, execution_id: ExecutionId, task_type: TaskType, *, max_passes: int, options: LLMExecutionOptions,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, cancellation: CancellationRequest | None = None,
    ) -> ExecutionResult[O]:
        self._enter(execution_id, max_passes)
        try:
            options.__post_init__()
            TypeAdapter(TaskType).validate_python(task_type, strict=True)
            if self._store.load(execution_id) is not None:
                raise ValueError("saved execution requires resume")
            settings = self._settings
            if settings is not None:
                try:
                    existing = await settings.store.load(execution_id)
                except KeyError:
                    pass
                else:
                    if existing.stop_intent is not None:
                        return await self._recovery.resume(execution_id, settings, max_passes, options,
                                                           confirmed_domain_revisions, cancellation, task_type)
            revision, plan = self._binding.compile(task_type, 0)
            state = ExecutionState(execution_id, self._registry, plan_revision=revision)
            try:
                state.set_cursor(ExecutionCursor(task_type, PassStage.PRE_LLM))
                if settings is not None and plan.invocation_root is not None:
                    graph = InvocationCoordinator.create(
                        plan, execution_id, revision, plan.invocation_root, settings.invocation_limit, None,
                    ).graph
                    if settings.interaction is not None:
                        graph.interaction_owner = settings.interaction.owner
                    elif any(contract.input_wait for contract in graph.registry):
                        raise ValueError("WAIT_INPUT requires an application interaction binding")
                    graph.initial_task = task_type.value
                    graph.session = self._snapshots.encode(state, self._registry)
                    await settings.store.create(execution_id, CheckpointCodec.encode(graph))
            except BaseException:
                state.release()
                raise
            if settings is not None and plan.invocation_root is not None:
                state.release()
                return await self._recovery.resume(execution_id, settings, max_passes, options,
                                                   confirmed_domain_revisions, cancellation, task_type)
            return await self._passes.run(state, plan, max_passes, options, confirmed_domain_revisions, cancellation)
        finally:
            self._active.discard(execution_id)

    async def resume(
        self, execution_id: ExecutionId, *, max_passes: int, options: LLMExecutionOptions,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, cancellation: CancellationRequest | None = None,
    ) -> ExecutionResult[O]:
        self._enter(execution_id, max_passes)
        try:
            options.__post_init__()
            invocation_options = self._settings
            if invocation_options is not None:
                try:
                    await invocation_options.store.load(execution_id)
                except KeyError:
                    pass
                else:
                    return await self._recovery.resume(execution_id, invocation_options, max_passes, options,
                                                       confirmed_domain_revisions, cancellation)
            state, plan = await self._sessions.restore(execution_id, max_passes)
            return await self._passes.run(state, plan, max_passes, options, confirmed_domain_revisions, cancellation)
        finally:
            self._active.discard(execution_id)
