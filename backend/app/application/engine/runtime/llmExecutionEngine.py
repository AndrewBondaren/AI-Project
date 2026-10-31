"""Generic pass/resume orchestration; integration owns rules, effects and reply."""

import asyncio
from collections.abc import Callable, Mapping
from time import time
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, TypeAdapter

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionCursor, LifecycleBinding, PassStage, ResolveResult
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
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, ExecutionIdValue
from app.dataModel.engine.dag.nodeStatus import NodeStatus

O = TypeVar("O", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)


class LLMExecutionEngine(Generic[O, S]):
    def __init__(
        self, executor: DAGExecutor, aggregate: LLMAggregateExecutor, registry: NodeRegistry,
        binding: LifecycleBinding[O], request: LLMRequest, snapshots: ExecutionSnapshotService[S], store: SnapshotStore[S], *,
        emit: Callable[[LifecycleDiagnostic], None] = emit_diagnostic, clock: Callable[[], float] = time,
    ) -> None:
        self._executor, self._aggregate, self._registry = executor, aggregate, registry
        self._binding, self._request = binding, request
        self._snapshots, self._store = snapshots, store
        self._emit, self._clock = emit, clock
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
    ) -> ResolveResult[O]:
        self._enter(execution_id, max_passes)
        try:
            options.__post_init__()
            TypeAdapter(TaskType).validate_python(task_type, strict=True)
            if self._store.load(execution_id) is not None:
                raise ValueError("saved execution requires resume")
            revision, plan = self._binding.compile(task_type, 0)
            state = ExecutionState(execution_id, self._registry, plan_revision=revision)
            state.set_cursor(ExecutionCursor(task_type, PassStage.PRE_LLM))
            return await self._drive(state, plan, max_passes, options, confirmed_domain_revisions, cancellation)
        finally:
            self._active.discard(execution_id)

    async def resume(
        self, execution_id: ExecutionId, *, max_passes: int, options: LLMExecutionOptions,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, cancellation: CancellationRequest | None = None,
    ) -> ResolveResult[O]:
        self._enter(execution_id, max_passes)
        state: ExecutionState | None = None
        try:
            options.__post_init__()
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

    async def _drive(
        self, state: ExecutionState, plan: ExecutionPlan, max_passes: int, options: LLMExecutionOptions,
        confirmed: Mapping[str, DomainRevision] | None, cancellation: CancellationRequest | None,
    ) -> ResolveResult[O]:
        try:
            self._prepare_reuse(state, confirmed)
            while True:
                cancellation_checkpoint()
                cursor, revision = state.cursor, state.plan_revision
                if cursor is None or revision is None:
                    raise RuntimeError("engine execution has no lifecycle context")
                stage, task_type = cursor.stage, cursor.task_type
                if stage in (PassStage.PRE_LLM, PassStage.LLM, PassStage.POST_LLM):
                    if stage == PassStage.LLM:
                        decision = await self._executor.run_llm_phase(
                            plan, state, revision, self._aggregate, self._request, options=options, pass_number=state.pass_number,
                            confirmed_domain_revisions=confirmed, cancellation=cancellation, invalidate_reuse=False,
                        )
                    else:
                        phase = ExecutionPhase.PRE_LLM if stage == PassStage.PRE_LLM else ExecutionPhase.POST_LLM
                        decision = await self._executor.run_python_phase(
                            plan, state, phase, revision, pass_number=state.pass_number,
                            confirmed_domain_revisions=confirmed, cancellation=cancellation, invalidate_reuse=False,
                        )
                    if decision == LevelDecision.CANCEL:
                        raise asyncio.CancelledError
                    if decision == LevelDecision.FAIL:
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
                        next_revision, next_plan = self._binding.compile(target, next_pass)
                        state.set_plan_context(next_revision, next_pass)
                        state.set_cursor(ExecutionCursor(target, PassStage.PRE_LLM))
                        plan = next_plan
                        self._prepare_reuse(state, confirmed)
                elif stage == PassStage.EFFECTS:
                    await self._binding.apply_effects(state.catalog.callback_view(self._binding.consumer, self._binding.reads))
                    cancellation_checkpoint()
                    state.set_cursor(ExecutionCursor(task_type, PassStage.RESPONSE))
                else:
                    result = ResponseResolver(self._binding.response_type).resolve(
                        self._binding, state.catalog.callback_view(self._binding.consumer, self._binding.reads),
                    )
                    cancellation_checkpoint()
                    self._store.delete(state.catalog.execution_id)
                    return result
        except asyncio.CancelledError:
            try:
                await asyncio.sleep(0)  # deliver a synchronous hook's pending task.cancel()
            except asyncio.CancelledError:
                pass
            try:
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
