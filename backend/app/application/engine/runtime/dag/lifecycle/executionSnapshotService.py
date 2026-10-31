"""Memory snapshot lifecycle; domain reference admission belongs to bindings."""

from typing import Generic, TypeVar

from pydantic import BaseModel

from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot
from app.application.engine.contracts.executionBindings import SnapshotExtension
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.executionState import ExecutionState
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.dataModel.engine.dag.identity import ContractId, ContractVersion
from app.dataModel.engine.dag.snapshotMetadata import SnapshotMetadata
from app.dataModel.validation.immutableValue import validate_immutable

S = TypeVar("S", bound=BaseModel)


class ExecutionSnapshotService(Generic[S]):
    def __init__(self, extension: SnapshotExtension[S] | None = None) -> None:
        self._extension = extension

    async def restore(self, snapshot: SessionSnapshot[S], registry: NodeRegistry) -> ExecutionState:
        snapshot.__post_init__()
        if snapshot.metadata.format_version != SnapshotMetadata.CURRENT_FORMAT_VERSION:
            raise ValueError("snapshot format version mismatch")
        extension = self._extension
        if snapshot.extension_contract != (None if extension is None else (extension.contract_id, extension.version)):
            raise ValueError("snapshot extension contract id/version mismatch")
        value = snapshot.extension
        if extension is not None:
            if not isinstance(value, extension.snapshot_type):
                raise TypeError("snapshot extension class mismatch")
            validate_immutable(value)
        state = ExecutionState.from_snapshot(snapshot, registry)
        for registration in registry.graph_registrations():
            contract = registration.contract
            record = snapshot.catalog.record(registration.node_id, contract)
            if record is not None and contract.lifecycle is not None:
                try:
                    await contract.lifecycle.validate_restored(record.output)
                except Exception as error:
                    raise ValueError(
                        f"snapshot producer '{record.identity.node_id}' attempt {record.identity.attempt}: {error}"
                    ) from error
        if extension is not None and value is not None:
            try:
                await extension.validate_restored(value)
                await extension.restore(value)
            except Exception as error:
                raise ValueError(f"snapshot extension '{extension.contract_id}': {error}") from error
        return state

    def capture(self, state: ExecutionState) -> SessionSnapshot[S]:
        self._check_quiescent(state)
        payload: S | None = None
        extension_contract: tuple[ContractId, ContractVersion] | None = None
        if self._extension is not None:
            payload, validation = ContractValidator().validate(self._extension.capture(), self._extension.snapshot_type)
            if payload is None or not validation.ok:
                raise TypeError("snapshot extension does not satisfy its immutable POJO contract")
            extension_contract = (self._extension.contract_id, self._extension.version)
        self._check_quiescent(state)
        catalog = state.catalog.capture()
        versions = dict(catalog.contract_versions)
        if extension_contract is not None:
            key, version = extension_contract
            if key in versions and versions[key] != version:
                raise ValueError("conflicting extension contract version")
            versions[key] = version
        revision = state.plan_revision
        if revision is None:
            raise RuntimeError("execution has no plan context")
        metadata = SnapshotMetadata(
            format_version=SnapshotMetadata.CURRENT_FORMAT_VERSION, execution_id=catalog.execution_id,
            plan_revision=revision, pass_number=state.pass_number,
            contract_versions=tuple(sorted(versions.items())), attempt_counters=catalog.attempt_counters,
        )
        return SessionSnapshot[S](
            metadata=metadata, catalog=catalog, statuses=tuple(sorted(state.statuses.items())),
            attempt_passes=state.attempt_passes, traces=state.traces, levels=state.levels,
            decision=state.decision, gate=state.gate, extension=payload, extension_contract=extension_contract, cursor=state.cursor,
        )

    @staticmethod
    def _check_quiescent(state: ExecutionState) -> None:
        if state.is_released:
            raise RuntimeError("execution ownership has been released")
        if state.is_active:
            raise RuntimeError("cannot capture an active execution phase")
        if not state.catalog.is_quiescent:
            raise RuntimeError("cannot capture a catalog with open attempts")
        if state.plan_revision is None:
            raise RuntimeError("execution has no plan context")
