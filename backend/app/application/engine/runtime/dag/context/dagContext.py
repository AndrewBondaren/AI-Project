"""Single-writer catalog primitives and provenance invalidation."""

from collections.abc import Collection, Mapping
from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.outputRef import RequiredOutput
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.application.engine.runtime.dag.context.resultInvalidation import ResultInvalidation
from app.dataModel.engine.dag.identity import (
    DomainRevision, ExecutionId, ExecutionIdValue, ExecutionIdentity, NodeId, PlanRevision,
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
        self._counters[node_id] = identity.attempt
        self._open[node_id] = identity
        return identity

    def read_view(self, consumer: NodeId) -> PublishedDAGReadView:
        requirements = self._registrations[consumer].contract.reads
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

    def publish[O: BaseModel](self, record: OutputRecord[O]) -> None:
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
        invalidated = self._affected(candidate=(record.identity, record.reads))
        if record.identity.node_id in invalidated:
            raise RuntimeError("candidate reads are no longer current after invalidation")
        # No await or domain I/O between admission and the coordinator's write.
        self._remove_current(invalidated)
        self._current[record.identity.node_id] = record
        self._close(record.identity)

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
