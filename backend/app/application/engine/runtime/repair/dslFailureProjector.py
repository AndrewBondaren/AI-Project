"""Project an explicit typed validation result; never recover errors from state."""

from pydantic import BaseModel, TypeAdapter

from app.application.engine.nodeTypes.llmNode import LLMNode
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.application.engine.runtime.repair.pojo.nodeFailureContext import NodeFailureContext
from app.application.engine.validation.validationStatus import ValidationResult
from app.dataModel.engine.dag.diagnostics import Index
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import ExecutionIdentity
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence


class DSLFailureProjector:
    def __init__(self, dsl_resolver: DSLResolver) -> None:
        self._dsl_resolver = dsl_resolver

    def project[I: BaseModel, O: BaseModel, E: NodeError](
        self, node: LLMNode[I, O, E], registration: NodeRegistration[I, O, E],
        identity: ExecutionIdentity, validation: ValidationResult, *, raw_output: str | None,
        dsl_keys: tuple[str, ...] | None = None, reads: tuple[DependencyRead, ...] = (),
        domain_reads: tuple[DomainReadEvidence, ...] = (), pass_number: Index = 0, repair_attempt: Index = 0,
    ) -> NodeFailureContext[O]:
        registration.validate_node(node)
        if registration.kind != NodeKind.LLM or identity.node_id != registration.node_id:
            raise TypeError("repair identity/node must match the LLM binding")
        declared_keys = (node.dsl,) if dsl_keys is None else dsl_keys
        TypeAdapter(tuple[str, ...]).validate_python(declared_keys, strict=True)
        keys = list(declared_keys)
        patches = self._dsl_resolver.resolve_patches(node, validation)
        keys = self._dsl_resolver.update(keys, patches)
        keys = self._dsl_resolver.update(keys, validation.dsl_patch or [])
        return NodeFailureContext(
            identity=identity, validation=validation, output_type=registration.contract.output_type,
            raw_output=raw_output, dsl_task=node.dsl, dsl_keys=tuple(keys), reads=reads,
            domain_reads=domain_reads, pass_number=pass_number, repair_attempt=repair_attempt,
        )
