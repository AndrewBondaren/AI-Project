"""Single-writer catalog primitives and provenance invalidation."""

from collections.abc import Collection, Mapping
from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.context.catalogSnapshot import CatalogSnapshot
from app.application.engine.runtime.dag.context.resultInvalidation import ResultInvalidation
from app.application.engine.runtime.validation.contractValidator import ContractValidator
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import (
    DomainRevision, ExecutionId, ExecutionIdValue, ExecutionIdentity, NodeId, NodeIdValue, PlanRevision,
)
from app.dataModel.engine.dag.records import DependencyRead, OutputRecord
from app.dataModel.validation.immutableValue import validate_immutable


def _validate_record(value: object) -> None:
    if not isinstance(value, OutputRecord):
        raise TypeError("catalog publication requires an OutputRecord")
    record = cast(OutputRecord[BaseModel], value)
    validate_immutable(record)
    type(record).model_validate(record)


class DAGContext:
    def __init__(self, execution_id: ExecutionId, registry: NodeRegistry) -> None:
        self._execution_id = TypeAdapter[ExecutionId](ExecutionIdValue).validate_python(execution_id)
        self._registrations = {reg.node_id: reg for reg in registry.graph_registrations()}
        self._counters: dict[NodeId, int] = {}
        self._open: dict[NodeId, ExecutionIdentity] = {}
        self._closed: dict[tuple[ExecutionId, NodeId, int], ExecutionIdentity] = {}
        self._current: dict[NodeId, object] = {}
        self._errors: dict[NodeId, tuple[ExecutionIdentity, NodeError]] = {}

    @property
    def execution_id(self) -> ExecutionId:
        return self._execution_id

    @property
    def attempt_counters(self) -> tuple[tuple[NodeId, int], ...]:
        return tuple(sorted(self._counters.items()))

    @property
    def closed_attempts(self) -> tuple[ExecutionIdentity, ...]:
        return tuple(self._closed.values())

    @property
    def current_outputs(self) -> tuple[ExecutionIdentity, ...]:
        return tuple(self._record(node_id).identity for node_id in sorted(self._current))

    @property
    def is_quiescent(self) -> bool:
        return not self._open

    def capture(self) -> CatalogSnapshot:
        if not self.is_quiescent:
            raise RuntimeError("cannot capture a catalog with open attempts")
        return CatalogSnapshot(
            execution_id=self._execution_id, attempt_counters=self.attempt_counters,
            closed_attempts=self.closed_attempts,
            contracts=tuple((node, reg.contract.contract_id, reg.contract.version)
                            for node, reg in sorted(self._registrations.items())),
            _records=tuple(self._record(node) for node in sorted(self._current)),
            _errors=tuple(self._errors[node] for node in sorted(self._errors)),
        )

    def begin_attempt(self, node_id: NodeId, plan_revision: PlanRevision) -> ExecutionIdentity:
        if node_id not in self._registrations:
            raise KeyError(f"node '{node_id}' is not registered in this execution")
        if node_id in self._open:
            raise RuntimeError(f"node '{node_id}' already has an open attempt")
        identity = ExecutionIdentity(
            execution_id=self._execution_id, node_id=node_id,
            attempt=self._counters.get(node_id, 0) + 1, plan_revision=plan_revision,
        )
        self._remove_current(self._affected(removed=(node_id,)))
        self._errors.pop(node_id, None)
        self._counters[node_id] = identity.attempt
        self._open[node_id] = identity
        return identity

    @classmethod
    def from_snapshot(cls, snapshot: CatalogSnapshot, registry: NodeRegistry) -> "DAGContext":
        snapshot.__post_init__()
        catalog = cls(snapshot.execution_id, registry)
        bindings = {node: (key, version) for node, key, version in snapshot.contracts}
        for node, saved in bindings.items():
            registration = catalog._registrations.get(node)
            if registration is None:
                raise ValueError(f"snapshot producer '{node}' is not registered")
            contract = registration.contract
            if saved != (contract.contract_id, contract.version):
                raise ValueError(f"snapshot producer '{node}' contract id/version mismatch")
            record = snapshot.record(node, contract)
            error = snapshot.node_error(node, contract)
            if record is not None:
                catalog._current[node] = record
            if error is not None:
                identity = next(identity for identity in snapshot.error_identities if identity.node_id == node)
                catalog._errors[node] = (identity, error)
        if set(bindings) != set(catalog._registrations):
            raise ValueError("snapshot registered node set mismatch")
        for node in catalog._current:
            catalog._check_reads(catalog._record(node))
        catalog._counters = dict(snapshot.attempt_counters)
        catalog._closed = {identity.result_key: identity for identity in snapshot.closed_attempts}
        return catalog

    def release(self) -> None:
        """Terminal owner release; immutable snapshots/readers retain their own refs."""
        if not self.is_quiescent:
            raise RuntimeError("cannot release a catalog with open attempts")
        self._current.clear()
        self._errors.clear()
        self._registrations.clear()

    def read_view(self, consumer: NodeId) -> PublishedDAGReadView:
        requirements = self._registrations[consumer].contract.reads
        return self._view(consumer, requirements)

    def callback_view(
        self, consumer: NodeId, requirements: tuple[RequiredOutput[BaseModel] | OptionalOutput[BaseModel], ...],
    ) -> PublishedDAGReadView:
        TypeAdapter[NodeId](NodeIdValue).validate_python(consumer)
        requirements = tuple(requirements)
        producers = {req.ref.producer for req in requirements}
        if producers.difference(self._registrations):
            raise KeyError("callback reads an unregistered producer")
        return self._view(consumer, requirements)

    def _view(
        self, consumer: NodeId, requirements: tuple[RequiredOutput[BaseModel] | OptionalOutput[BaseModel], ...],
    ) -> PublishedDAGReadView:
        producers = {req.ref.producer for req in requirements}
        return PublishedDAGReadView(
            consumer, requirements,
            {node_id: self._registrations[node_id] for node_id in producers if node_id in self._registrations},
            {node_id: self._record(node_id) for node_id in producers if node_id in self._current},
            self._execution_id,
        )

    def close_attempt(self, identity: ExecutionIdentity) -> None:
        self._check_open(identity)
        self._close(identity)

    def close_error[I: BaseModel, O: BaseModel, E: NodeError](
        self, identity: ExecutionIdentity, error: E, contract: NodeContract[I, O, E],
    ) -> None:
        self._check_open(identity)
        self.validate_binding(identity.node_id, contract)
        admitted, validation = ContractValidator().validate_error(error, contract.error_types)
        if admitted is None or not validation.ok:
            raise TypeError("error does not satisfy the declared POJO contract")
        self._errors[identity.node_id] = (identity, admitted)
        self._close(identity)

    def node_error[I: BaseModel, O: BaseModel, E: NodeError](
        self, node_id: NodeId, contract: NodeContract[I, O, E],
    ) -> E | None:
        self.validate_binding(node_id, contract)
        record = self._errors.get(node_id)
        # Only close_error writes, after admission under this exact binding.
        return cast(E, record[1]) if record is not None else None

    def validate_binding[I: BaseModel, O: BaseModel, E: NodeError](
        self, node_id: NodeId, contract: NodeContract[I, O, E],
    ) -> None:
        if self._registrations[node_id].contract is not contract:
            raise TypeError("error contract does not match execution binding")

    def publish[O: BaseModel](self, record: OutputRecord[O]) -> None:
        self._validate_publication(record)
        invalidated = self._affected(candidate=(record.identity, record.reads))
        if record.identity.node_id in invalidated:
            raise RuntimeError("candidate reads are no longer current after invalidation")
        self._remove_current(invalidated)
        self._current[record.identity.node_id] = record
        self._close(record.identity)

    def publish_batch[O: BaseModel](self, records: tuple[OutputRecord[O], ...]) -> None:
        nodes = {record.identity.node_id for record in records}
        if not records or len(nodes) != len(records):
            raise ValueError("batch requires unique nonempty producers")
        for record in records:
            self._validate_publication(record)
            if any(read.producer in nodes for read in record.reads):
                raise ValueError("LLM batch cannot read a sibling Output")
        current = {node: self._record(node).identity for node in self._current}
        reads = {node: self._record(node).reads for node in self._current}
        current.update((record.identity.node_id, record.identity) for record in records)
        reads.update((record.identity.node_id, record.reads) for record in records)
        invalidated = ResultInvalidation.affected(current, reads)
        if nodes.intersection(invalidated):
            raise RuntimeError("batch reads are no longer current after invalidation")
        # All admission precedes the first write. No await/callback or schema
        # validation occurs during this coordinator-owned batch commit.
        self._remove_current(invalidated)
        for record in records:
            self._current[record.identity.node_id] = record
            self._close(record.identity)

    def _validate_publication[O: BaseModel](self, record: OutputRecord[O]) -> None:
        # Metadata/immutability admission only. Output schema and business
        # validation belong to M12/runner, never to this catalog.
        _validate_record(record)
        self._check_open(record.identity)
        contract = self._registrations[record.identity.node_id].contract
        if record.contract_id != contract.contract_id or record.contract_version != contract.version:
            raise TypeError(f"node '{record.identity.node_id}' published an incompatible contract version")
        if not isinstance(record.output, contract.output_type):
            raise TypeError(f"node '{record.identity.node_id}' published an incompatible Output type")
        self._check_reads(record)

    def invalidate_for_reuse(
        self, confirmed_domain_revisions: Mapping[str, DomainRevision],
    ) -> tuple[ExecutionIdentity, ...]:
        seeds = ResultInvalidation.unconfirmed_domains(
            {node_id: self._record(node_id).domain_reads for node_id in self._current},
            confirmed_domain_revisions,
        )
        return self._remove_current(self._affected(removed=seeds))

    def _affected(
        self, *, removed: Collection[NodeId] = (),
        candidate: tuple[ExecutionIdentity, tuple[DependencyRead, ...]] | None = None,
    ) -> frozenset[NodeId]:
        current = {node_id: self._record(node_id).identity for node_id in self._current}
        reads = {node_id: self._record(node_id).reads for node_id in self._current}
        if candidate is not None:
            identity, evidence = candidate
            current[identity.node_id] = identity
            reads[identity.node_id] = evidence
        return ResultInvalidation.affected(current, reads, removed)

    def _remove_current(self, node_ids: Collection[NodeId]) -> tuple[ExecutionIdentity, ...]:
        removed = tuple(self._record(node_id).identity for node_id in sorted(node_ids))
        for node_id in node_ids:
            del self._current[node_id]
        return removed

    def _check_open(self, identity: ExecutionIdentity) -> None:
        ExecutionIdentity.model_validate(identity)
        if identity.execution_id != self._execution_id:
            raise ValueError("attempt belongs to a different execution")
        if identity.result_key in self._closed:
            raise RuntimeError(f"attempt '{identity.result_key}' is already closed")
        if self._open.get(identity.node_id) != identity:
            raise RuntimeError(f"attempt '{identity.result_key}' is not the current open identity")

    def _close(self, identity: ExecutionIdentity) -> None:
        del self._open[identity.node_id]
        self._closed[identity.result_key] = identity

    def _record(self, producer: NodeId) -> OutputRecord[BaseModel]:
        # Only publish writes this closed heterogeneous store, after checking
        # the registered class and identity. Payload references are preserved.
        return cast(OutputRecord[BaseModel], self._current[producer])

    def _check_reads[O: BaseModel](self, record: OutputRecord[O]) -> None:
        requirements = self._registrations[record.identity.node_id].contract.reads
        for read in record.reads:
            declarations = tuple(
                req for req in requirements
                if req.ref.producer == read.producer and isinstance(req, RequiredOutput) == read.required
            )
            if not declarations:
                raise PermissionError(f"node '{record.identity.node_id}' published an undeclared read")
            producer_contract = self._registrations[read.producer].contract
            if read.contract_id != producer_contract.contract_id or read.contract_version != producer_contract.version:
                raise TypeError(f"read from '{read.producer}' has an incompatible contract version")
            if not any(issubclass(producer_contract.output_type, req.ref.output_type) for req in declarations):
                raise TypeError(f"read from '{read.producer}' has an incompatible Output declaration")
            current = self._record(read.producer).identity if read.producer in self._current else None
            if read.result != current:
                raise RuntimeError(f"read from '{read.producer}' is no longer current")
