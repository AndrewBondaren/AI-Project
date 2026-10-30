"""Immutable catalog data, without live registry/binding/callback ownership."""

from dataclasses import dataclass, field
from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.runtime.dag.context.resultInvalidation import ResultInvalidation
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import (
    Attempt, ContractId, ContractIdValue, ContractVersion, ContractVersionValue,
    ExecutionId, ExecutionIdValue, ExecutionIdentity, NodeId, NodeIdValue,
)
from app.dataModel.engine.dag.records import OutputRecord
from app.dataModel.validation.immutableValue import validate_immutable


@dataclass(frozen=True, kw_only=True)
class CatalogSnapshot:
    execution_id: ExecutionId
    attempt_counters: tuple[tuple[NodeId, int], ...]
    closed_attempts: tuple[ExecutionIdentity, ...]
    contracts: tuple[tuple[NodeId, ContractId, ContractVersion], ...]
    _records: tuple[OutputRecord[BaseModel], ...] = field(repr=False)
    _errors: tuple[tuple[ExecutionIdentity, NodeError], ...] = field(repr=False)

    @property
    def output_identities(self) -> tuple[ExecutionIdentity, ...]:
        return tuple(record.identity for record in self._records)

    @property
    def error_identities(self) -> tuple[ExecutionIdentity, ...]:
        return tuple(identity for identity, _ in self._errors)

    @property
    def contract_versions(self) -> tuple[tuple[ContractId, ContractVersion], ...]:
        versions: dict[ContractId, ContractVersion] = {}
        for _, contract_id, version in self.contracts:
            if contract_id in versions and versions[contract_id] != version:
                raise ValueError("conflicting versions of one ContractId")
            versions[contract_id] = version
        return tuple(sorted(versions.items()))

    def record[I: BaseModel, O: BaseModel, E: NodeError](
        self, node_id: NodeId, contract: NodeContract[I, O, E],
    ) -> OutputRecord[O] | None:
        self._check_binding(node_id, contract)
        record = next((record for record in self._records if record.identity.node_id == node_id), None)
        if record is None:
            return None
        if not isinstance(record.output, contract.output_type):
            raise TypeError("snapshot Output class does not match requested binding")
        # Saved id/version and actual payload class witness O here. No schema
        # revalidation or payload copies are performed by this typed lookup.
        return cast(OutputRecord[O], record)

    def node_error[I: BaseModel, O: BaseModel, E: NodeError](
        self, node_id: NodeId, contract: NodeContract[I, O, E],
    ) -> E | None:
        self._check_binding(node_id, contract)
        error = next((error for identity, error in self._errors if identity.node_id == node_id), None)
        if error is None:
            return None
        if not isinstance(error, contract.error_types):
            raise TypeError("snapshot error class does not match requested binding")
        return error

    def _check_binding[I: BaseModel, O: BaseModel, E: NodeError](
        self, node_id: NodeId, contract: NodeContract[I, O, E],
    ) -> None:
        saved = next(((key, version) for node, key, version in self.contracts if node == node_id), None)
        if saved is None:
            raise KeyError(f"node '{node_id}' is not part of the snapshot")
        if saved != (contract.contract_id, contract.version):
            raise TypeError("snapshot contract id/version does not match requested binding")

    def __post_init__(self) -> None:
        TypeAdapter[ExecutionId](ExecutionIdValue).validate_python(self.execution_id)
        TypeAdapter[tuple[tuple[NodeId, int], ...]](tuple[tuple[NodeIdValue, Attempt], ...]).validate_python(self.attempt_counters)
        TypeAdapter[tuple[tuple[NodeId, ContractId, ContractVersion], ...]](
            tuple[tuple[NodeIdValue, ContractIdValue, ContractVersionValue], ...],
        ).validate_python(self.contracts)
        validate_immutable(self)
        counters = dict(self.attempt_counters)
        bindings = {node: (key, version) for node, key, version in self.contracts}
        if len(counters) != len(self.attempt_counters) or len(bindings) != len(self.contracts):
            raise ValueError("duplicate snapshot node metadata")
        closed = {identity.result_key: identity for identity in self.closed_attempts}
        if len(closed) != len(self.closed_attempts):
            raise ValueError("duplicate closed snapshot attempt")
        latest: dict[NodeId, int] = {}
        for identity in self.closed_attempts:
            ExecutionIdentity.model_validate(identity)
            if identity.execution_id != self.execution_id or identity.node_id not in bindings:
                raise ValueError("closed attempt belongs to a different execution/node")
            latest[identity.node_id] = max(latest.get(identity.node_id, 0), identity.attempt)
        if counters != latest:
            raise ValueError("attempt counters must match quiescent closed history")
        identities = self.output_identities + self.error_identities
        if len({identity.node_id for identity in identities}) != len(identities):
            raise ValueError("duplicate or overlapping current output/error")
        for identity in identities:
            if closed.get(identity.result_key) != identity or identity.attempt != counters.get(identity.node_id):
                raise ValueError("current record is not the latest closed attempt")
        for record in self._records:
            type(record).model_validate(record)  # metadata only, not the Output schema
            if bindings[record.identity.node_id] != (record.contract_id, record.contract_version):
                raise ValueError("OutputRecord has an incompatible snapshot contract")
        stale = ResultInvalidation.affected(
            {record.identity.node_id: record.identity for record in self._records},
            {record.identity.node_id: record.reads for record in self._records},
        )
        if stale:
            raise ValueError("snapshot contains stale Output read versions")
        _ = self.contract_versions  # Also check conflicts when there are no current records.
