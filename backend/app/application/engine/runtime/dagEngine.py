"""Generic pass/resume orchestration; integration owns rules, effects and reply."""

from collections.abc import Callable, Mapping
from time import time
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, TypeAdapter

from app.application.engine.contracts.invocation.inputWait import ResumeInput
from app.dataModel.engine.dag.invocations.inputWait import InputReceipt
from app.application.engine.contracts.invocation.executionStore import PackCloser
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.recovery.activeCheckpoint import ActiveCheckpoint
from app.application.engine.runtime.invocations.recovery.executionRecovery import ExecutionRecovery
from app.application.engine.runtime.invocations.interaction.executionInteraction import ExecutionInteraction
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionCursor, ExecutionResult, InputDelivery, LifecycleBinding, PassStage
from app.application.engine.diagnostics.dagLog import emit as emit_diagnostic
from app.application.engine.diagnostics.events import LifecycleDiagnostic
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.dag.lifecycle.passExecution import PassExecution
from app.application.engine.runtime.dag.lifecycle.sessionRecovery import SessionRecovery
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import CancellationRequest
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, ExecutionIdValue, WaitId

O = TypeVar("O", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)


class DAGEngine(Generic[O, S]):
    def __init__(
        self, executor: DAGExecutor, aggregate: LLMAggregateExecutor, registry: NodeRegistry,
        binding: LifecycleBinding[O], request: LLMRequest, snapshots: ExecutionSnapshotService[S], store: SnapshotStore[S], *,
        enable_stop_intent: bool = False, pack_closer: PackCloser | None = None,
        emit: Callable[[LifecycleDiagnostic], None] = emit_diagnostic, clock: Callable[[], float] = time,
    ) -> None:
        self._executor, self._registry = executor, registry
        self._binding = binding
        self._interaction = ExecutionInteraction(executor.invocation_options, binding)
        self._snapshots, self._store = snapshots, store
        self._sessions = SessionRecovery(snapshots, registry, store, binding, emit, clock)
        stop_enabled = enable_stop_intent or pack_closer is not None
        self._passes = PassExecution(
            executor, aggregate, registry, binding, request, snapshots, store, self._sessions,
            enable_stop_intent=stop_enabled,
        )
        active = ActiveCheckpoint(binding, snapshots, registry, self._passes, enable_stop_intent=stop_enabled)
        self._recovery = ExecutionRecovery(binding, active, self._interaction, pack_closer, enable_stop_intent=stop_enabled)
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
            settings = self._executor.invocation_options
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
            state.set_cursor(ExecutionCursor(task_type, PassStage.PRE_LLM))
            invocation_options = self._executor.invocation_options
            if invocation_options is not None and plan.invocation_root is not None:
                graph = InvocationCoordinator.create(plan, execution_id, revision, plan.invocation_root,
                                                     invocation_options.invocation_limit, None).graph
                if invocation_options.interaction is not None:
                    graph.interaction_owner = invocation_options.interaction.owner
                elif any(c.input_wait for c in graph.registry):
                    raise ValueError("WAIT_INPUT requires an application interaction binding")
                graph.initial_task = task_type.value
                graph.session = self._snapshots.encode(state, self._registry)
                await invocation_options.store.create(execution_id, CheckpointCodec.encode(graph))
                state.release()
                return await self._recovery.resume(execution_id, invocation_options, max_passes, options,
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
            invocation_options = self._executor.invocation_options
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

    async def accept_input[U: BaseModel](self, execution_id: ExecutionId, request: ResumeInput[U]) -> InputReceipt:
        return await self._interaction.accept_input(execution_id, request)

    async def resume_input[U: BaseModel](self, execution_id: ExecutionId, request: ResumeInput[U], *,
                                         max_passes: int, options: LLMExecutionOptions) -> InputDelivery[O]:
        TypeAdapter(Annotated[int, Field(strict=True, gt=0)]).validate_python(max_passes)
        options.__post_init__()
        receipt = await self.accept_input(execution_id, request)
        result = await self.resume(execution_id, max_passes=max_passes, options=options)
        return InputDelivery(receipt, result)

    async def cancel_waiting_child(self, execution_id: ExecutionId, wait_id: WaitId, *, expected_revision: int) -> None:
        await self._interaction.cancel_waiting_child(execution_id, wait_id, expected_revision=expected_revision)

    async def cancel_execution(self, execution_id: ExecutionId) -> None:
        await self._interaction.cancel_execution(execution_id)
