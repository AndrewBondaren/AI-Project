import asyncio
from collections.abc import Mapping

from pydantic import BaseModel, TypeAdapter

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionCursor, ExecutionResult, LifecycleBinding, PassStage, ResolveResult
from app.application.engine.contracts.invocation.inputWait import Failed
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.dag.lifecycle.sessionRecovery import SessionRecovery
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.runtime.execution.nodeOutcome import LevelDecision
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.engine.runtime.invocations.ownedExecution import OwnedExecution
from app.application.engine.runtime.repair.repairOrchestrator import cancellation_checkpoint
from app.application.engine.runtime.responseResolver import ResponseResolver
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import CancellationRequest
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import DomainRevision, PlanInstanceId
from app.dataModel.engine.dag.invocations.record import CompletedOutcome, FailedOutcome


class PassExecution[O: BaseModel, S: BaseModel]:
    def __init__(
        self, executor: DAGExecutor, aggregate: LLMAggregateExecutor, registry: NodeRegistry,
        binding: LifecycleBinding[O], request: LLMRequest, snapshots: ExecutionSnapshotService[S],
        store: SnapshotStore[S], sessions: SessionRecovery[O, S], *, enable_stop_intent: bool,
    ) -> None:
        self._executor = executor
        self._aggregate = aggregate
        self._registry = registry
        self._binding = binding
        self._request = request
        self._snapshots = snapshots
        self._store = store
        self._sessions = sessions
        self._enable_stop_intent = enable_stop_intent

    async def run(
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
            # The pass owns state until the cancellation checkpoint and its diagnostic finish.
            saving = asyncio.create_task(self._sessions.save_cancelled(state, durable))
            while not saving.done():
                try:
                    await asyncio.wait((saving,))
                except asyncio.CancelledError:
                    continue
            saving.result()
            raise
        finally:
            state.release()

    @staticmethod
    def _prepare_reuse(state: ExecutionState, confirmed: Mapping[str, DomainRevision] | None) -> None:
        cursor = state.cursor
        if cursor is not None and cursor.stage in (PassStage.PRE_LLM, PassStage.LLM, PassStage.POST_LLM):
            invalidated = state.catalog.invalidate_for_reuse(confirmed or {})
            state.begin_level(())
            if invalidated:
                state.set_cursor(ExecutionCursor(cursor.task_type, PassStage.PRE_LLM))
