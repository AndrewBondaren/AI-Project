"""Generic pass/resume orchestration; integration owns rules, effects and reply."""

import asyncio
from collections.abc import Callable, Mapping
from time import time
from uuid import uuid4
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, TypeAdapter

from app.application.engine.contracts.invocation.inputWait import Failed, InputConflict, ResumeInput
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.dataModel.engine.dag.invocations.inputWait import InputReceipt
from app.dataModel.engine.dag.invocations.record import CompletedOutcome, FailedOutcome, InvocationStatus
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.executionStore import Checkpoint, OwnershipConflict, RestoreFailure
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.ownedExecution import ExecutionStopping, OwnedExecution
from app.application.engine.runtime.invocations.sessionFrame import SessionFrame
from app.dataModel.engine.dag.invocations.record import InvocationGraph
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionCursor, ExecutionResult, InputDelivery, LifecycleBinding, PassStage, ResolveResult
from app.application.engine.diagnostics.dagLog import emit as emit_diagnostic
from app.application.engine.diagnostics.events import LifecycleDiagnostic
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision
from app.application.engine.runtime.repair.repairOrchestrator import cancellation_checkpoint
from app.application.engine.runtime.responseResolver import ResponseResolver
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import CancellationRequest, ExecutionEventCode, ExecutionSeverity
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, ExecutionIdValue, Ordinal, PlanInstanceId, WaitId
from app.dataModel.engine.dag.nodeStatus import NodeStatus

O = TypeVar("O", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)


class DAGEngine(Generic[O, S]):
    def __init__(
        self, executor: DAGExecutor, aggregate: LLMAggregateExecutor, registry: NodeRegistry,
        binding: LifecycleBinding[O], request: LLMRequest, snapshots: ExecutionSnapshotService[S], store: SnapshotStore[S], *,
        enable_stop_intent: bool = False,
        emit: Callable[[LifecycleDiagnostic], None] = emit_diagnostic, clock: Callable[[], float] = time,
    ) -> None:
        self._executor, self._aggregate, self._registry = executor, aggregate, registry
        self._binding, self._request = binding, request
        self._snapshots, self._store = snapshots, store
        self._emit, self._clock = emit, clock
        self._enable_stop_intent = enable_stop_intent
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
                graph.session = self._snapshots.encode(state, self._registry)
                await invocation_options.store.create(execution_id, CheckpointCodec.encode(graph))
                state.release()
                return await self._restore_durable(execution_id, invocation_options, max_passes, options,
                                                   confirmed_domain_revisions, cancellation, task_type)
            return await self._drive(state, plan, max_passes, options, confirmed_domain_revisions, cancellation)
        finally:
            self._active.discard(execution_id)

    async def resume(
        self, execution_id: ExecutionId, *, max_passes: int, options: LLMExecutionOptions,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, cancellation: CancellationRequest | None = None,
    ) -> ExecutionResult[O]:
        self._enter(execution_id, max_passes)
        state: ExecutionState | None = None
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
            snapshot = self._store.load(execution_id)
            if snapshot is None:
                raise LookupError("execution snapshot is unavailable")
            try:
                if snapshot.cursor is None or snapshot.metadata.pass_number >= max_passes:
                    raise ValueError("snapshot cursor/pass is incompatible with resume")
                state = await self._snapshots.restore(snapshot, self._registry)
                revision, plan = self._binding.compile(snapshot.cursor.task_type, snapshot.metadata.pass_number)
                if revision != snapshot.metadata.plan_revision:
                    raise ValueError("resume plan revision mismatch")
            except Exception:
                self._emit(LifecycleDiagnostic(
                    execution_id=execution_id, plan_revision=snapshot.metadata.plan_revision, pass_number=snapshot.metadata.pass_number,
                    stage=snapshot.cursor.stage if snapshot.cursor else None, code=ExecutionEventCode.RESTORE_FAILED,
                    severity=ExecutionSeverity.ERROR, timestamp=self._clock(), status=NodeStatus.FAILED, message="snapshot restore failed",
                ))
                raise
            return await self._drive(state, plan, max_passes, options, confirmed_domain_revisions, cancellation)
        finally:
            if state is not None and not state.is_released:
                state.release()
            self._active.discard(execution_id)

    def _interaction_settings(self) -> InvocationOptions:
        settings = self._executor.invocation_options
        if settings is None or settings.interaction is None:
            raise PermissionError("authenticated interaction binding required")
        return settings

    def _interaction_graph(self, execution_id: ExecutionId, settings: InvocationOptions,
                           saved: Checkpoint) -> tuple[InvocationGraph, ExecutionPlan]:
        header = InvocationGraph.model_validate_json(saved.blob)
        InputWaitCoordinator.check_owner(header, settings.interaction)
        if header.execution_id != execution_id or header.session is None:
            raise RestoreFailure("invalid interaction execution")
        frame = SessionFrame.model_validate_json(header.session)
        if frame.cursor is None:
            raise RestoreFailure("missing lifecycle cursor")
        if saved.stop_intent is not None:
            raise InputConflict("execution is stopping")
        revision, plan = self._binding.compile(frame.cursor.task_type, frame.metadata.pass_number)
        graph = CheckpointCodec.decode(saved.blob, plan)
        if revision != graph.revision or plan.invocation_root != graph.records[graph.root].node_id:
            raise RestoreFailure("durable plan changed")
        return graph, plan

    async def accept_input[U: BaseModel](self, execution_id: ExecutionId, request: ResumeInput[U]) -> InputReceipt:
        settings = self._interaction_settings()
        before = await settings.store.load(execution_id)
        if before.stop_intent is not None:
            self._interaction_graph(execution_id, settings, before)
        try:
            claim = await settings.store.claim(execution_id, str(uuid4()), settings.lease_seconds)
        except OwnershipConflict:
            saved = await settings.store.load(execution_id)
            graph, _ = self._interaction_graph(execution_id, settings, saved)
            wait = graph.waits.get(request.wait_id)
            if wait is not None and wait.accepted is None and graph.records[wait.invocation_id].status == InvocationStatus.CANCELLED:
                raise InputConflict("child wait was cancelled") from None
            raise
        try:
            saved = await settings.store.load(execution_id)
            graph, plan = self._interaction_graph(execution_id, settings, saved)
            receipt, fresh = InputWaitCoordinator.accept(graph, plan, request, settings.interaction)
            if fresh:
                owned = OwnedExecution(settings.store, claim, saved.revision, graph, settings.lease_seconds)
                await owned.save()
            return receipt
        finally:
            await settings.store.release(claim)

    async def resume_input[U: BaseModel](self, execution_id: ExecutionId, request: ResumeInput[U], *,
                                         max_passes: int, options: LLMExecutionOptions) -> InputDelivery[O]:
        TypeAdapter(Annotated[int, Field(strict=True, gt=0)]).validate_python(max_passes)
        options.__post_init__()
        receipt = await self.accept_input(execution_id, request)
        result = await self.resume(execution_id, max_passes=max_passes, options=options)
        return InputDelivery(receipt, result)

    async def cancel_waiting_child(self, execution_id: ExecutionId, wait_id: WaitId, *, expected_revision: int) -> None:
        """Cancel the child bound to this wait. Resume drives the caller's join."""
        TypeAdapter[int](Ordinal).validate_python(expected_revision)
        settings = self._interaction_settings()
        while True:
            saved = await settings.store.load(execution_id)
            graph, _ = self._interaction_graph(execution_id, settings, saved)
            wait = graph.waits.get(wait_id)
            if (graph.cancellation is not None or wait is None or wait.accepted is not None
                    or wait.binding.revision != expected_revision):
                raise InputConflict("unknown, consumed or stale child wait")
            child = graph.records[wait.invocation_id]
            if child.caller_invocation_id is None or child.step_index != wait.step_index:
                raise InputConflict("wait does not belong to a child at this step")
            if child.status == InvocationStatus.CANCELLED:
                return
            if child.status != InvocationStatus.WAITING_INPUT:
                raise InputConflict("child is not waiting for input")
            if await settings.store.cancel_child(execution_id, saved.revision, wait_id):
                return

    async def cancel_execution(self, execution_id: ExecutionId) -> None:
        settings = self._interaction_settings()
        while True:
            saved = await settings.store.load(execution_id)
            graph, _ = self._interaction_graph(execution_id, settings, saved)
            if graph.response is not None or graph.failure is not None or graph.cancellation is not None:
                return
            for record in graph.records.values():
                if record.status not in (InvocationStatus.SUCCEEDED, InvocationStatus.FAILED, InvocationStatus.CANCELLED):
                    record.status = InvocationStatus.CANCELLED
            graph.waiting_for_input = False
            graph.cancellation = "execution cancelled"
            if await settings.store.cancel(execution_id, saved.revision, CheckpointCodec.encode(graph)):
                return

    async def _restore_durable(
        self, execution_id: ExecutionId, settings: InvocationOptions, max_passes: int, options: LLMExecutionOptions,
        confirmed: Mapping[str, DomainRevision] | None, cancellation: CancellationRequest | None,
        requested_task: TaskType | None = None,
    ) -> ExecutionResult[O]:
        claim = await settings.store.claim(execution_id, str(uuid4()), settings.lease_seconds)
        async def drive_claimed() -> ExecutionResult[O]:
            saved = await settings.store.load(execution_id)
            try:
                header = InvocationGraph.model_validate_json(saved.blob)
                if header.session is None or header.execution_id != execution_id:
                    raise ValueError("execution has no lifecycle checkpoint")
                if header.interaction_owner is not None:
                    InputWaitCoordinator.check_owner(header, settings.interaction)
                frame = SessionFrame.model_validate_json(header.session)
                if frame.cursor is None or (saved.stop_intent is None and frame.metadata.pass_number >= max_passes):
                    raise ValueError("invalid durable lifecycle cursor")
                if requested_task is not None and frame.metadata.pass_number == 0 and frame.cursor.task_type != requested_task:
                    raise ValueError("duplicate execution request differs")
                if saved.stop_intent is not None:
                    if saved.stop_intent.execution_id != execution_id or saved.stop_intent.stop_revision != saved.revision:
                        raise RestoreFailure("invalid stop intent identity")
                    recovered = await settings.store.record_stop_intent(
                        claim, saved.stop_intent.stop_revision - 1, saved.stop_intent.outcome,
                    )
                    raise ExecutionStopping(recovered)
                revision, plan = self._binding.compile(frame.cursor.task_type, frame.metadata.pass_number)
                graph = await CheckpointCodec.restore(saved.blob, plan)
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
            return await self._drive(state, plan, max_passes, options, confirmed, cancellation, owned)
        task = asyncio.create_task(drive_claimed())
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
            if saved.status != InvocationStatus.CANCELLED or settings.interaction is None:
                raise
            graph, _ = self._interaction_graph(execution_id, settings, saved)
            if graph.cancellation is None:
                raise
            if self._enable_stop_intent:
                return await self._restore_durable(execution_id, settings, max_passes, options, confirmed, cancellation)
            return Failed(graph.cancellation)

    async def _drive(
        self, state: ExecutionState, plan: ExecutionPlan, max_passes: int, options: LLMExecutionOptions,
        confirmed: Mapping[str, DomainRevision] | None, cancellation: CancellationRequest | None,
        durable: OwnedExecution | None = None,
    ) -> ExecutionResult[O]:
        try:
            self._prepare_reuse(state, confirmed)
            while True:
                if durable is not None:
                    durable.graph.session = self._snapshots.encode(state, self._registry)
                    await durable.save()
                cancellation_checkpoint()
                cursor, revision = state.cursor, state.plan_revision
                if cursor is None or revision is None:
                    raise RuntimeError("engine execution has no lifecycle context")
                stage, task_type = cursor.stage, cursor.task_type
                if stage in (PassStage.PRE_LLM, PassStage.LLM, PassStage.POST_LLM):
                    if stage == PassStage.LLM:
                        decision = await self._executor.run_llm_phase(
                            plan, state, revision, self._aggregate, self._request, options=options, pass_number=state.pass_number, durable=durable,
                            confirmed_domain_revisions=confirmed, cancellation=cancellation, invalidate_reuse=False,
                        )
                    else:
                        phase = ExecutionPhase.PRE_LLM if stage == PassStage.PRE_LLM else ExecutionPhase.POST_LLM
                        decision = await self._executor.run_python_phase(
                            plan, state, phase, revision, pass_number=state.pass_number, durable=durable,
                            confirmed_domain_revisions=confirmed, cancellation=cancellation, invalidate_reuse=False,
                        )
                    if decision == LevelDecision.WAIT_INPUT:
                        if durable is None:
                            raise RuntimeError("input wait requires durable execution")
                        return InputWaitCoordinator.waiting(durable.graph, plan)
                    if decision == LevelDecision.CANCEL:
                        raise asyncio.CancelledError
                    if decision == LevelDecision.FAIL:
                        if durable is not None and (self._enable_stop_intent or durable.graph.interaction_owner is not None):
                            root = durable.graph.records[durable.graph.root]
                            durable.graph.failure = root.diagnostics[-1].message if root.diagnostics else "DAG pass failed"
                            if self._enable_stop_intent:
                                await durable.stop(FailedOutcome(diagnostic=durable.graph.failure))
                            await durable.save()
                            return Failed(durable.graph.failure)
                        raise RuntimeError("DAG pass failed")
                    next_stage = {PassStage.PRE_LLM: PassStage.LLM, PassStage.LLM: PassStage.POST_LLM,
                                  PassStage.POST_LLM: PassStage.TRANSITION}[stage]
                    state.set_cursor(ExecutionCursor(task_type, PassStage.TRANSITION if decision == LevelDecision.REPLAN else next_stage))
                elif stage == PassStage.TRANSITION:
                    view = state.catalog.callback_view(self._binding.consumer, self._binding.reads)
                    target = state.gate.next_task_type if state.gate is not None else self._binding.transition(view)
                    TypeAdapter(TaskType | None).validate_python(target, strict=True)
                    cancellation_checkpoint()
                    if target is None:
                        state.set_cursor(ExecutionCursor(task_type, PassStage.EFFECTS))
                    else:
                        next_pass = state.pass_number + 1
                        if next_pass >= max_passes:
                            raise RuntimeError("DAG pass limit exhausted")
                        if durable is not None:
                            await durable.save()
                        next_revision, next_plan = self._binding.compile(target, next_pass)
                        if next_plan.root_members != plan.root_members:
                            state.replace_plan_instance(self._registry, PlanInstanceId(f"pass-{next_pass}"))
                        state.set_plan_context(next_revision, next_pass)
                        state.set_cursor(ExecutionCursor(target, PassStage.PRE_LLM))
                        plan = next_plan
                        self._prepare_reuse(state, confirmed)
                        if durable is not None:
                            settings = self._executor.invocation_options
                            if settings is None or plan.invocation_root is None:
                                raise ValueError("durable pass requires an invocation root")
                            reusable = {item.invocation_id for item in state.catalog.current_outputs
                                        if getattr(plan.nodes[item.node_id].node, "skip_on_replan", True)}
                            coordinator = InvocationCoordinator(plan, durable.graph, settings.invocation_limit)
                            coordinator.next_pass(plan.invocation_root, next_revision, reusable, state.catalog.instance.id)
                elif stage == PassStage.EFFECTS:
                    await self._binding.apply_effects(state.catalog.callback_view(self._binding.consumer, self._binding.reads))
                    cancellation_checkpoint()
                    state.set_cursor(ExecutionCursor(task_type, PassStage.RESPONSE))
                else:
                    result = ResponseResolver(self._binding.response_type).resolve(
                        self._binding, state.catalog.callback_view(self._binding.consumer, self._binding.reads),
                    )
                    cancellation_checkpoint()
                    if durable is not None:
                        if durable.graph.interaction_owner is not None and not result.ok:
                            durable.graph.failure = result.error or "response resolution failed"
                            if self._enable_stop_intent:
                                await durable.stop(FailedOutcome(diagnostic=durable.graph.failure))
                            await durable.save()
                            return Failed(durable.graph.failure)
                        durable.graph.response = TypeAdapter[ResolveResult[O]](
                            ResolveResult[self._binding.response_type],
                        ).dump_json(result).decode()
                        if self._enable_stop_intent:
                            await durable.stop(CompletedOutcome(result_json=durable.graph.response))
                        await durable.save()
                    else:
                        self._store.delete(state.catalog.execution_id)
                    return result
        except asyncio.CancelledError:
            try:
                await asyncio.sleep(0)  # deliver a synchronous hook's pending task.cancel()
            except asyncio.CancelledError:
                pass
            if durable is not None and durable.graph.interaction_owner is not None:
                saved = await durable.store.load(durable.claim.execution_id)
                if saved.status == InvocationStatus.CANCELLED and InvocationGraph.model_validate_json(saved.blob).cancellation is not None:
                    # The cancelling request already persisted the terminal graph and revoked our claim.
                    raise
            try:
                if durable is not None:
                    durable.graph.session = self._snapshots.encode(state, self._registry)
                    await durable.save()
                else:
                    snapshot = self._snapshots.capture(state)
                    self._store.save(snapshot)
            except Exception:
                self._lifecycle_event(state, ExecutionEventCode.SNAPSHOT_FAILED, NodeStatus.FAILED, ExecutionSeverity.ERROR)
                raise
            self._lifecycle_event(state, ExecutionEventCode.SNAPSHOT_SAVED, NodeStatus.CANCELLED, ExecutionSeverity.INFO)
            raise
        finally:
            state.release()

    def _lifecycle_event(self, state: ExecutionState, code: ExecutionEventCode, status: NodeStatus, severity: ExecutionSeverity) -> None:
        revision = state.plan_revision
        if revision is None:
            raise RuntimeError("snapshot lifecycle requires a plan revision")
        self._emit(LifecycleDiagnostic(
            execution_id=state.catalog.execution_id, plan_revision=revision, pass_number=state.pass_number,
            stage=state.cursor.stage if state.cursor else None, code=code, severity=severity,
            timestamp=self._clock(), status=status, message=code.value,
        ))

    @staticmethod
    def _prepare_reuse(state: ExecutionState, confirmed: Mapping[str, DomainRevision] | None) -> None:
        cursor = state.cursor
        if cursor is not None and cursor.stage in (PassStage.PRE_LLM, PassStage.LLM, PassStage.POST_LLM):
            invalidated = state.catalog.invalidate_for_reuse(confirmed or {})
            state.begin_level(())
            if invalidated:
                state.set_cursor(ExecutionCursor(cursor.task_type, PassStage.PRE_LLM))
