"""Barrier metadata and control signals, without Output/error payloads."""

from dataclasses import dataclass

from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision
from app.dataModel.engine.dag.diagnostics import Index, Timestamp
from app.dataModel.engine.dag.executionPhase import PythonExecutionPhase
from app.dataModel.engine.dag.identity import ExecutionIdentity


@dataclass(frozen=True)
class ExecutionLevelSnapshot:
    phase: PythonExecutionPhase
    pass_number: Index
    level: Index
    decision: LevelDecision
    traces: tuple[ExecutionTrace, ...]
    saved_outputs: tuple[ExecutionIdentity, ...]
    reused_outputs: tuple[ExecutionIdentity, ...]
    cancel_requested_at: Timestamp | None
    completed_at: Timestamp

    @property
    def gates(self) -> tuple[GateSignal, ...]:
        return tuple(trace.gate for trace in self.traces if trace.gate is not None)

    @property
    def gate_conflict(self) -> bool:
        return len(self.gates) > 1

    @property
    def gate(self) -> GateSignal | None:
        return self.gates[0] if self.decision == LevelDecision.REPLAN else None
