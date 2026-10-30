"""Immutable per-attempt metadata; never retain outcome payloads."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.application.engine.runtime.execution.nodeOutcome import GateSignal, NodeOutcome
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic, Timestamp
from app.dataModel.engine.dag.errors.nodeError import NodeError
from app.dataModel.engine.dag.identity import ExecutionIdentity
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence


@dataclass(frozen=True)
class ExecutionTrace:
    identity: ExecutionIdentity
    status: NodeStatus
    started_at: Timestamp
    completed_at: Timestamp
    reads: tuple[DependencyRead, ...]
    domain_reads: tuple[DomainReadEvidence, ...]
    diagnostics: tuple[ExecutionDiagnostic, ...]
    gate: GateSignal | None

    @classmethod
    def from_outcome[O: BaseModel, E: NodeError](cls, outcome: NodeOutcome[O, E]) -> "ExecutionTrace":
        return cls(
            outcome.identity, outcome.status, outcome.started_at, outcome.completed_at,
            outcome.reads, outcome.domain_reads, outcome.diagnostics, outcome.gate,
        )
