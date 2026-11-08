"""Generic pass/resume orchestration; integration owns rules, effects and reply."""

import asyncio
from collections.abc import Callable, Mapping
from time import time
from uuid import uuid4
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, TypeAdapter

from app.application.engine.contracts.invocation.inputWait import Failed, ResumeInput
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.dataModel.engine.dag.invocations.inputWait import InputReceipt
from app.dataModel.engine.dag.invocations.record import CompletedOutcome, FailedOutcome
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.executionStore import PackCloser, OwnershipConflict, RestoreFailure
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.ownedExecution import ExecutionStopping, OwnedExecution
from app.application.engine.runtime.invocations.recovery.checkpointHeader import read_header
from app.application.engine.runtime.invocations.recovery.closeConfirmation import confirm_closed
from app.application.engine.runtime.invocations.recovery.terminalReplay import terminal_result
from app.application.engine.runtime.invocations.interaction.executionInteraction import ExecutionInteraction
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionCursor, ExecutionResult, InputDelivery, LifecycleBinding, PassStage, ResolveResult
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
        self._pack_closer = pack_closer
        self._enable_stop_intent = enable_stop_intent or pack_closer is not None
        self._passes = PassExecution(
            executor, aggregate, registry, binding, request, snapshots, store, self._sessions,
            enable_stop_intent=self._enable_stop_intent,
        )
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
                        return await self._restore_durable(execution_id, settings, max_passes, options,
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
                return await self._restore_durable(execution_id, invocation_options, max_passes, options,
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
                    return await self._restore_durable(execution_id, invocation_options, max_passes, options,
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

    async def _restore_durable(
        self, execution_id: ExecutionId, settings: InvocationOptions, max_passes: int, options: LLMExecutionOptions,
        confirmed: Mapping[str, DomainRevision] | None, cancellation: CancellationRequest | None,
        requested_task: TaskType | None = None,
    ) -> ExecutionResult[O]:
        before = await settings.store.load(execution_id)
        if before.final_revision is not None:
            read_header(before, execution_id, settings, max_passes, requested_task)
            return terminal_result(before, execution_id, self._binding.response_type)
        try:
            claim = await settings.store.claim(execution_id, str(uuid4()), settings.lease_seconds)
        except OwnershipConflict:
            winner = await settings.store.load(execution_id)
            if winner.final_revision is None:
                raise
            read_header(winner, execution_id, settings, max_passes, requested_task)
            return terminal_result(winner, execution_id, self._binding.response_type)

        async def drive_claimed() -> ExecutionResult[O]:
            saved = await settings.store.load(execution_id)
            try:
                header, frame = read_header(saved, execution_id, settings, max_passes, requested_task)
                assert frame.cursor is not None and header.session is not None
                if saved.final_revision is not None:
                    return terminal_result(saved, execution_id, self._binding.response_type)
                if saved.stop_intent is not None:
                    if saved.stop_intent.execution_id != execution_id or saved.stop_intent.stop_revision != saved.revision:
                        raise RestoreFailure("invalid stop intent identity")
                    recovered = await settings.store.record_stop_intent(
                        claim, saved.stop_intent.stop_revision - 1, saved.stop_intent.outcome,
                    )
                    raise ExecutionStopping(recovered)
                revision, plan = self._binding.compile(frame.cursor.task_type, frame.metadata.pass_number)
                graph = await CheckpointCodec.restore(saved.blob, plan)
                if graph.initial_task is None and frame.metadata.pass_number == 0:
                    graph.initial_task = frame.cursor.task_type.value
                if revision != graph.revision or plan.invocation_root != graph.records[graph.root].node_id:
                    raise ValueError("durable plan changed")
                if graph.cancellation is not None or graph.failure is not None:
                    diagnostic = graph.cancellation or graph.failure or "execution failed"
                    if self._enable_stop_intent:
                        await OwnedExecution(settings.store, claim, saved.revision, graph, settings.lease_seconds).stop(
                            FailedOutcome(diagnostic=diagnostic))
                    return Failed(diagnostic)
                if graph.waiting_for_input:
                    return InputWaitCoordinator.waiting(graph, plan)
                if graph.response is not None:
                    result = TypeAdapter[ResolveResult[O]](ResolveResult[self._binding.response_type]).validate_json(graph.response)
                    if self._enable_stop_intent:
                        await OwnedExecution(settings.store, claim, saved.revision, graph, settings.lease_seconds).stop(
                            CompletedOutcome(result_json=graph.response))
                    return result
                state = await self._snapshots.decode(header.session, self._registry)
            except (ValueError, KeyError, TypeError) as exc:
                raise RestoreFailure("incompatible durable execution") from exc
            owned = OwnedExecution(settings.store, claim, saved.revision, graph, settings.lease_seconds)
            return await self._passes.run(state, plan, max_passes, options, confirmed, cancellation, owned)

        async def drive_to_final() -> ExecutionResult[O]:
            try:
                return await drive_claimed()
            except ExecutionStopping as stopped:
                if self._pack_closer is None:
                    raise
                intent = stopped.intent
                closed = await confirm_closed(self._pack_closer, intent)
                final = await settings.store.finalize(claim, intent.stop_revision, closed)
                return terminal_result(final, execution_id, self._binding.response_type)

        task = asyncio.create_task(drive_to_final())
        heartbeat = settings.lease_seconds / 3
        if settings.interaction is not None:
            heartbeat = min(heartbeat, 1.0)
        try:
            try:
                while not task.done():
                    done, _ = await asyncio.wait((task,), timeout=heartbeat)
                    if not done:
                        await settings.store.renew(claim, settings.lease_seconds)
                return task.result()
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await settings.store.release(claim)
        except OwnershipConflict:
            saved = await settings.store.load(execution_id)
            if saved.final_revision is not None:
                read_header(saved, execution_id, settings, max_passes, requested_task)
                return terminal_result(saved, execution_id, self._binding.response_type)
            diagnostic = self._interaction.cancelled_diagnostic(execution_id, saved)
            if diagnostic is None:
                raise
            if self._enable_stop_intent:
                return await self._restore_durable(execution_id, settings, max_passes, options, confirmed, cancellation)
            return Failed(diagnostic)
