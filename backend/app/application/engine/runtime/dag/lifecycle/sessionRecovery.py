import asyncio
from collections.abc import Callable

from pydantic import BaseModel

from app.application.cancellation.typed.snapshotStore import SnapshotStore
from app.application.engine.contracts.executionBindings import LifecycleBinding
from app.application.engine.diagnostics.events import LifecycleDiagnostic
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.executionPlan import ExecutionPlan
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.dag.lifecycle.executionSnapshotService import ExecutionSnapshotService
from app.application.engine.runtime.invocations.ownedExecution import OwnedExecution
from app.dataModel.engine.dag.diagnostics import ExecutionEventCode, ExecutionSeverity
from app.dataModel.engine.dag.identity import ExecutionId
from app.dataModel.engine.dag.invocations.record import InvocationGraph, InvocationStatus
from app.dataModel.engine.dag.nodeStatus import NodeStatus


class SessionRecovery[O: BaseModel, S: BaseModel]:
    def __init__(
        self, snapshots: ExecutionSnapshotService[S], registry: NodeRegistry, store: SnapshotStore[S],
        binding: LifecycleBinding[O], emit: Callable[[LifecycleDiagnostic], None], clock: Callable[[], float],
    ) -> None:
        self._snapshots = snapshots
        self._registry = registry
        self._store = store
        self._binding = binding
        self._emit = emit
        self._clock = clock

    async def restore(self, execution_id: ExecutionId, max_passes: int) -> tuple[ExecutionState, ExecutionPlan]:
        snapshot = self._store.load(execution_id)
        if snapshot is None:
            raise LookupError("execution snapshot is unavailable")
        try:
            if snapshot.cursor is None or snapshot.metadata.pass_number >= max_passes:
                raise ValueError("snapshot cursor/pass is incompatible with resume")
            state = await self._snapshots.restore(snapshot, self._registry)
            try:
                revision, plan = self._binding.compile(snapshot.cursor.task_type, snapshot.metadata.pass_number)
                if revision != snapshot.metadata.plan_revision:
                    raise ValueError("resume plan revision mismatch")
                return state, plan
            except BaseException:
                state.release()
                raise
        except Exception:
            self._emit(LifecycleDiagnostic(
                execution_id=execution_id, plan_revision=snapshot.metadata.plan_revision, pass_number=snapshot.metadata.pass_number,
                stage=snapshot.cursor.stage if snapshot.cursor else None, code=ExecutionEventCode.RESTORE_FAILED,
                severity=ExecutionSeverity.ERROR, timestamp=self._clock(), status=NodeStatus.FAILED, message="snapshot restore failed",
            ))
            raise

    async def save_cancelled(self, state: ExecutionState, durable: OwnedExecution | None) -> None:
        try:
            await asyncio.sleep(0)  # deliver a synchronous hook's pending task.cancel()
        except asyncio.CancelledError:
            pass
        try:
            if durable is not None:
                if durable.graph.interaction_owner is not None:
                    saved = await durable.store.load(durable.claim.execution_id)
                    if saved.status == InvocationStatus.CANCELLED and InvocationGraph.model_validate_json(saved.blob).cancellation is not None:
                        # The cancelling request already persisted the terminal graph and revoked our claim.
                        return
                durable.graph.session = self._snapshots.encode(state, self._registry)
                await durable.save()
            else:
                snapshot = self._snapshots.capture(state)
                self._store.save(snapshot)
        except Exception:
            self._lifecycle_event(state, ExecutionEventCode.SNAPSHOT_FAILED, NodeStatus.FAILED, ExecutionSeverity.ERROR)
            raise
        self._lifecycle_event(state, ExecutionEventCode.SNAPSHOT_SAVED, NodeStatus.CANCELLED, ExecutionSeverity.INFO)

    def _lifecycle_event(self, state: ExecutionState, code: ExecutionEventCode, status: NodeStatus, severity: ExecutionSeverity) -> None:
        revision = state.plan_revision
        if revision is None:
            raise RuntimeError("snapshot lifecycle requires a plan revision")
        self._emit(LifecycleDiagnostic(
            execution_id=state.catalog.execution_id, plan_revision=revision, pass_number=state.pass_number,
            stage=state.cursor.stage if state.cursor else None, code=code, severity=severity,
            timestamp=self._clock(), status=status, message=code.value,
        ))
