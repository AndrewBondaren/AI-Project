"""Generic pass/resume orchestration; integration owns rules, effects and reply."""

from collections.abc import Callable, Mapping
from time import time
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, TypeAdapter

from app.application.engine.contracts.invocation.inputWait import ResumeInput
from app.dataModel.engine.dag.invocations.inputWait import InputReceipt
from app.application.engine.contracts.invocation.executionStore import PackCloser
from app.application.engine.runtime.invocations.recovery.activeCheckpoint import ActiveCheckpoint
from app.application.engine.runtime.invocations.recovery.executionRecovery import ExecutionRecovery
from app.application.engine.runtime.invocations.interaction.executionInteraction import ExecutionInteraction
from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import ExecutionResult, InputDelivery, LifecycleBinding
from app.application.engine.diagnostics.dagLog import emit as emit_diagnostic
from app.application.engine.diagnostics.events import LifecycleDiagnostic
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.dagExecutor import DAGExecutor
from app.application.engine.runtime.dag.lifecycle.executionAdmission import ExecutionAdmission
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.dag.lifecycle.passExecution import PassExecution
from app.application.engine.runtime.dag.lifecycle.sessionRecovery import SessionRecovery
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions, LLMRequest
from app.application.engine.runtime.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import CancellationRequest
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, WaitId

O = TypeVar("O", bound=BaseModel)
S = TypeVar("S", bound=BaseModel)


class DAGEngine(Generic[O, S]):
    def __init__(
        self, executor: DAGExecutor, aggregate: LLMAggregateExecutor, registry: NodeRegistry,
        binding: LifecycleBinding[O], request: LLMRequest, snapshots: ExecutionSnapshotService[S], store: SnapshotStore[S], *,
        enable_stop_intent: bool = False, pack_closer: PackCloser | None = None,
        emit: Callable[[LifecycleDiagnostic], None] = emit_diagnostic, clock: Callable[[], float] = time,
    ) -> None:
        self._interaction = ExecutionInteraction(executor.invocation_options, binding)
        sessions = SessionRecovery(snapshots, registry, store, binding, emit, clock)
        stop_enabled = enable_stop_intent or pack_closer is not None
        passes = PassExecution(
            executor, aggregate, registry, binding, request, snapshots, store, sessions,
            enable_stop_intent=stop_enabled,
        )
        active = ActiveCheckpoint(binding, snapshots, registry, passes, enable_stop_intent=stop_enabled)
        recovery = ExecutionRecovery(binding, active, self._interaction, pack_closer, enable_stop_intent=stop_enabled)
        self._admission = ExecutionAdmission(
            executor.invocation_options, registry, binding, snapshots, store, sessions, recovery, passes,
        )

    async def run(
        self, execution_id: ExecutionId, task_type: TaskType, *, max_passes: int, options: LLMExecutionOptions,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, cancellation: CancellationRequest | None = None,
    ) -> ExecutionResult[O]:
        return await self._admission.run(
            execution_id, task_type, max_passes=max_passes, options=options,
            confirmed_domain_revisions=confirmed_domain_revisions, cancellation=cancellation,
        )

    async def resume(
        self, execution_id: ExecutionId, *, max_passes: int, options: LLMExecutionOptions,
        confirmed_domain_revisions: Mapping[str, DomainRevision] | None = None, cancellation: CancellationRequest | None = None,
    ) -> ExecutionResult[O]:
        return await self._admission.resume(
            execution_id, max_passes=max_passes, options=options,
            confirmed_domain_revisions=confirmed_domain_revisions, cancellation=cancellation,
        )

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
