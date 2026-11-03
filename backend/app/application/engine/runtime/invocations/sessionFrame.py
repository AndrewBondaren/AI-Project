from pydantic import BaseModel, ConfigDict

from app.application.cancellation.typed.sessionSnapshot import SessionSnapshot
from app.application.engine.contracts.executionBindings import ExecutionCursor
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.catalogSnapshot import CatalogSnapshot
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, ExecutionIdentity, NodeId, PlanInstanceId
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence, OutputRecord
from app.dataModel.engine.dag.snapshotMetadata import SnapshotMetadata


class SavedValue(BaseModel):
    identity: ExecutionIdentity
    data: str
    error_index: int | None = None
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()


class SessionFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    metadata: SnapshotMetadata
    instance: PlanInstanceId
    closed: tuple[ExecutionIdentity, ...]
    contracts: tuple[tuple[NodeId, ContractId, ContractVersion], ...]
    values: tuple[SavedValue, ...]
    statuses: tuple[tuple[NodeId, NodeStatus], ...]
    passes: tuple[tuple[NodeId, int], ...]
    traces: tuple[ExecutionTrace, ...]
    levels: tuple[ExecutionLevelSnapshot, ...]
    decision: LevelDecision
    gate: GateSignal | None
    cursor: ExecutionCursor | None
    extension: str | None
    extension_contract: tuple[ContractId, ContractVersion] | None

    @classmethod
    def capture[S: BaseModel](cls, snapshot: SessionSnapshot[S], registry: NodeRegistry) -> "SessionFrame":
        catalog = snapshot.catalog
        values: list[SavedValue] = []
        errors = {identity.node_id: identity for identity in catalog.error_identities}
        for registration in registry.graph_registrations():
            node, contract = registration.node_id, registration.contract
            record = catalog.record(node, contract)
            if record is not None:
                values.append(SavedValue(identity=record.identity, data=record.output.model_dump_json(round_trip=True),
                                         reads=record.reads, domain_reads=record.domain_reads))
            error = catalog.node_error(node, contract)
            if error is not None:
                index = next(i for i, model in enumerate(contract.error_types) if isinstance(error, model))
                values.append(SavedValue(identity=errors[node], data=error.model_dump_json(round_trip=True), error_index=index))
        return cls(metadata=snapshot.metadata, instance=catalog.plan_instance_id, closed=catalog.closed_attempts,
                   contracts=catalog.contracts, values=tuple(values), statuses=snapshot.statuses, passes=snapshot.attempt_passes,
                   traces=snapshot.traces, levels=snapshot.levels, decision=snapshot.decision, gate=snapshot.gate,
                   cursor=snapshot.cursor, extension_contract=snapshot.extension_contract,
                   extension=snapshot.extension.model_dump_json(round_trip=True) if snapshot.extension is not None else None)

    def restore[S: BaseModel](self, registry: NodeRegistry, extension: S | None) -> SessionSnapshot[S]:
        contracts = {reg.node_id: reg.contract for reg in registry.graph_registrations()}
        records: list[OutputRecord[BaseModel]] = []
        errors: list[tuple[ExecutionIdentity, NodeError]] = []
        if {n: (c.contract_id, c.version) for n, c in contracts.items()} != {n: (k, v) for n, k, v in self.contracts}:
            raise ValueError("registered session contracts changed")
        for value in self.values:
            contract = contracts[value.identity.node_id]
            if value.error_index is None:
                records.append(OutputRecord[BaseModel](identity=value.identity, contract_id=contract.contract_id,
                    contract_version=contract.version, output=contract.output_type.model_validate_json(value.data),
                    reads=value.reads, domain_reads=value.domain_reads))
            else:
                errors.append((value.identity, contract.error_types[value.error_index].model_validate_json(value.data)))
        catalog = CatalogSnapshot(execution_id=self.metadata.execution_id, plan_instance_id=self.instance,
                                  attempt_counters=self.metadata.attempt_counters, closed_attempts=self.closed,
                                  contracts=self.contracts, _records=tuple(records), _errors=tuple(errors))
        return SessionSnapshot[S](metadata=self.metadata, catalog=catalog, statuses=self.statuses, attempt_passes=self.passes,
                                  traces=self.traces, levels=self.levels, decision=self.decision, gate=self.gate,
                                  cursor=self.cursor, extension_contract=self.extension_contract, extension=extension)
