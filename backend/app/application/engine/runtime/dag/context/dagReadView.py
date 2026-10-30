"""Fixed published snapshot and consumer-local read evidence. SoT: §7.1."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.outputRef import OptionalOutput, RequiredOutput
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.dataModel.engine.dag.identity import DomainRevision, ExecutionId, NodeId
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence, OutputRecord


@dataclass(frozen=True)
class PublishedDAGReadView:
    consumer: NodeId
    _requirements: tuple[RequiredOutput[BaseModel] | OptionalOutput[BaseModel], ...] = field(repr=False)
    _producers: Mapping[NodeId, NodeRegistration[BaseModel, BaseModel, NodeError]] = field(repr=False)
    _records: Mapping[NodeId, OutputRecord[BaseModel]] = field(repr=False)
    _execution_id: ExecutionId = field(repr=False)
    _reads: list[DependencyRead] = field(default_factory=list[DependencyRead], init=False, repr=False, compare=False)
    _domain_reads: list[DomainReadEvidence] = field(default_factory=list[DomainReadEvidence], init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_producers", MappingProxyType(dict(self._producers)))
        object.__setattr__(self, "_records", MappingProxyType(dict(self._records)))

    @property
    def execution_id(self) -> ExecutionId:
        return self._execution_id

    @property
    def dependency_reads(self) -> tuple[DependencyRead, ...]:
        return tuple(self._reads)

    @property
    def domain_reads(self) -> tuple[DomainReadEvidence, ...]:
        return tuple(self._domain_reads)

    def record_domain_read(self, domain: str, revision: DomainRevision | None) -> None:
        evidence = DomainReadEvidence(domain=domain, revision=revision)
        if evidence not in self._domain_reads:
            self._domain_reads.append(evidence)

    def require[O: BaseModel](self, req: RequiredOutput[O]) -> O:
        output = self._read(req, required=True)
        if output is None:
            raise LookupError(f"consumer '{self.consumer}' requires unavailable producer '{req.ref.producer}'")
        return output

    def optional[O: BaseModel](self, req: OptionalOutput[O]) -> O | None:
        return self._read(req, required=False)

    def _read[O: BaseModel](
        self, req: RequiredOutput[O] | OptionalOutput[O], *, required: bool,
    ) -> O | None:
        if isinstance(req, RequiredOutput) != required:
            raise TypeError("read declaration kind does not match require/optional")
        declarations = tuple(
            declaration for declaration in self._requirements
            if declaration.ref.producer == req.ref.producer
            and isinstance(declaration, RequiredOutput) == required
        )
        if not declarations:
            raise PermissionError(f"consumer '{self.consumer}' has no such read declaration for '{req.ref.producer}'")
        if not any(declaration.ref.output_type is req.ref.output_type for declaration in declarations):
            raise TypeError(f"consumer '{self.consumer}' requested an undeclared Output type for '{req.ref.producer}'")
        producer = self._producers[req.ref.producer]
        contract = producer.contract
        if not issubclass(contract.output_type, req.ref.output_type):
            raise TypeError(f"producer '{req.ref.producer}' has an incompatible Output contract")
        record = self._records.get(req.ref.producer)
        output: O | None = None
        if record is not None:
            if record.identity.execution_id != self._execution_id or record.identity.node_id != req.ref.producer:
                raise ValueError(f"producer '{req.ref.producer}' has a foreign result identity")
            if record.contract_id != contract.contract_id or record.contract_version != contract.version:
                raise TypeError(f"producer '{req.ref.producer}' has an incompatible contract version")
            if not isinstance(record.output, req.ref.output_type):
                raise TypeError(f"producer '{req.ref.producer}' has an incompatible Output payload")
            output = record.output
        evidence = DependencyRead(
            producer=req.ref.producer, contract_id=contract.contract_id,
            contract_version=contract.version, required=required,
            result=None if record is None else record.identity,
        )
        if evidence not in self._reads:
            self._reads.append(evidence)
        return output
