from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.executionBindings import LifecycleBinding
from app.application.engine.contracts.invocation.executionOptions import InvocationOptions
from app.application.engine.contracts.invocation.executionStore import Checkpoint, OwnershipConflict, RestoreFailure
from app.application.engine.contracts.invocation.inputWait import InputConflict, ResumeInput
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.invocations.checkpointCodec import CheckpointCodec
from app.application.engine.runtime.invocations.inputWaitCoordinator import InputWaitCoordinator
from app.application.engine.runtime.invocations.ownedExecution import OwnedExecution
from app.application.engine.runtime.invocations.sessionFrame import SessionFrame
from app.dataModel.engine.dag.identity import ExecutionId, Ordinal, WaitId
from app.dataModel.engine.dag.invocations.inputWait import InputReceipt
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationStatus


class ExecutionInteraction[O: BaseModel]:
    def __init__(self, settings: InvocationOptions | None, binding: LifecycleBinding[O]) -> None:
        self._settings = settings
        self._binding = binding

    def cancelled_diagnostic(self, execution_id: ExecutionId, saved: Checkpoint) -> str | None:
        if saved.stop_intent is not None or saved.status != InvocationStatus.CANCELLED:
            return None
        settings = self._settings
        if settings is None or settings.interaction is None:
            return None
        graph, _ = self._interaction_graph(execution_id, settings, saved)
        return graph.cancellation

    def _interaction_settings(self) -> InvocationOptions:
        settings = self._settings
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
