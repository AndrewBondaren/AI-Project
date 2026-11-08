import asyncio
from collections.abc import Mapping
from uuid import uuid4

from pydantic import BaseModel

from app.application.engine.contracts.executionBindings import ExecutionResult, LifecycleBinding
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.executionStore import Claim, OwnershipConflict, PackCloser, RestoreFailure
from app.application.engine.contracts.invocation.inputWait import Failed
from app.application.engine.runtime.execution.llm.llmRequest import LLMExecutionOptions
from app.application.engine.runtime.invocations.interaction.executionInteraction import ExecutionInteraction
from app.application.engine.runtime.invocations.ownedExecution import ExecutionStopping
from app.application.engine.runtime.invocations.recovery.activeCheckpoint import ActiveCheckpoint
from app.application.engine.runtime.invocations.recovery.checkpointHeader import read_header
from app.application.engine.runtime.invocations.recovery.closeConfirmation import confirm_closed
from app.application.engine.runtime.invocations.recovery.terminalReplay import terminal_result
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.diagnostics import CancellationRequest
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId


class ExecutionRecovery[O: BaseModel, S: BaseModel]:
    def __init__(
        self, binding: LifecycleBinding[O], active: ActiveCheckpoint[O, S], interaction: ExecutionInteraction[O],
        pack_closer: PackCloser | None, *, enable_stop_intent: bool,
    ) -> None:
        self._binding = binding
        self._active = active
        self._interaction = interaction
        self._pack_closer = pack_closer
        self._enable_stop_intent = enable_stop_intent

    async def resume(
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

        task = asyncio.create_task(self._resume_claimed(
            execution_id, claim, settings, max_passes, options, confirmed, cancellation, requested_task,
        ))
        heartbeat = settings.lease_seconds / 3
        if settings.interaction is not None:
            heartbeat = min(heartbeat, 1.0)

        async def run_with_lease() -> ExecutionResult[O]:
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

        owner = asyncio.create_task(run_with_lease())
        try:
            try:
                await asyncio.wait((owner,))
            except asyncio.CancelledError:
                if not task.done():
                    task.cancel()
                # Keep renewal and release alive while the worker finishes its cancellation hooks.
                while not owner.done():
                    try:
                        await asyncio.wait((owner,))
                    except asyncio.CancelledError:
                        continue
                owner.result()
                raise
            return owner.result()
        except OwnershipConflict:
            saved = await settings.store.load(execution_id)
            if saved.final_revision is not None:
                read_header(saved, execution_id, settings, max_passes, requested_task)
                return terminal_result(saved, execution_id, self._binding.response_type)
            diagnostic = self._interaction.cancelled_diagnostic(execution_id, saved)
            if diagnostic is None:
                raise
            if self._enable_stop_intent:
                return await self.resume(execution_id, settings, max_passes, options, confirmed, cancellation)
            return Failed(diagnostic)

    async def _resume_claimed(
        self, execution_id: ExecutionId, claim: Claim, settings: InvocationOptions, max_passes: int,
        options: LLMExecutionOptions, confirmed: Mapping[str, DomainRevision] | None,
        cancellation: CancellationRequest | None, requested_task: TaskType | None,
    ) -> ExecutionResult[O]:
        saved = await settings.store.load(execution_id)
        try:
            try:
                header, frame = read_header(saved, execution_id, settings, max_passes, requested_task)
                if saved.final_revision is not None:
                    return terminal_result(saved, execution_id, self._binding.response_type)
                if saved.stop_intent is not None:
                    if saved.stop_intent.execution_id != execution_id or saved.stop_intent.stop_revision != saved.revision:
                        raise RestoreFailure("invalid stop intent identity")
                    recovered = await settings.store.record_stop_intent(
                        claim, saved.stop_intent.stop_revision - 1, saved.stop_intent.outcome,
                    )
                    raise ExecutionStopping(recovered)
            except (ValueError, KeyError, TypeError) as exc:
                raise RestoreFailure("incompatible durable execution") from exc
            return await self._active.resume(saved, header, frame, claim, settings, max_passes, options, confirmed, cancellation)
        except ExecutionStopping as stopped:
            if self._pack_closer is None:
                raise
            intent = stopped.intent
            closed = await confirm_closed(self._pack_closer, intent)
            final = await settings.store.finalize(claim, intent.stop_revision, closed)
            return terminal_result(final, execution_id, self._binding.response_type)
