"""Single-writer catalog primitives; coordinator and invalidation come later."""

from typing import cast

from pydantic import BaseModel, TypeAdapter

from app.application.engine.contracts.outputRef import RequiredOutput
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.dag.context.dagReadView import PublishedDAGReadView
from app.dataModel.engine.dag.identity import (
    ExecutionId, ExecutionIdValue, ExecutionIdentity, NodeId, PlanRevision,
)
from app.dataModel.engine.dag.records import OutputRecord
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
        # Only the producer's own old result is removed in A2.1. Transitive
        # consumer invalidation is the explicit A2.2 extension point.
        self._current.pop(node_id, None)
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
        # No await or domain I/O between admission and the coordinator's write.
        self._current[record.identity.node_id] = record
        self._close(record.identity)

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
