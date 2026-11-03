from dataclasses import dataclass
from pydantic import BaseModel

from app.application.engine.contracts.invocation.nodeStep import NodeStep
from app.application.engine.runtime.execution.nodeOutcome import GateSignal
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence


@dataclass(frozen=True)
class StepEffect:
    step: NodeStep[BaseModel, BaseModel] | None = None
    prepared: BaseModel | None = None
    error: NodeError | None = None
    cancelled: bool = False
    diagnostics: tuple[ExecutionDiagnostic, ...] = ()
    gate: GateSignal | None = None
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()
