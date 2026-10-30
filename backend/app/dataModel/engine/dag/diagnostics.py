"""Payload-free execution diagnostics. SoT: tz_engine_node_context §10."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.engine.dag.identity import (
    ContractIdValue, ContractVersionValue, ExecutionIdentity, NodeIdValue, PlanRevisionValue,
)
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.records import DependencyRead, DomainReadEvidence
from app.dataModel.validation.immutableValue import validate_immutable


class ExecutionEventCode(StrEnum):
    NODE_STARTED = "node_started"
    NODE_FINISHED = "node_finished"
    CANCEL_REQUESTED = "cancel_requested"
    CANCEL_OBSERVED = "cancel_observed"
    LEVEL_FINISHED = "level_finished"
    REPLAN_REQUESTED = "replan_requested"
    SNAPSHOT_SAVED = "snapshot_saved"
    SNAPSHOT_FAILED = "snapshot_failed"
    RESTORE_FAILED = "restore_failed"


class ExecutionSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CancellationSource(StrEnum):
    USER = "user"
    PARENT = "parent"
    NODE = "node"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class CancellationReason(StrEnum):
    REQUESTED = "requested"
    PARENT_CANCELLED = "parent_cancelled"
    NODE_CANCELLED = "node_cancelled"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    UNKNOWN = "unknown"


type Timestamp = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
type Index = Annotated[int, Field(strict=True, ge=0)]
type OutputRequirement = tuple[NodeIdValue, ContractIdValue, ContractVersionValue, bool]


class CancellationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source: CancellationSource = CancellationSource.UNKNOWN
    reason: CancellationReason = CancellationReason.UNKNOWN
    message: str | None = None
    requested_at: Timestamp | None = None


class ExecutionDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    identity: ExecutionIdentity
    pass_number: Index
    phase: ExecutionPhase
    level: Index
    timestamp: Timestamp
    code: ExecutionEventCode
    severity: ExecutionSeverity
    status: NodeStatus
    message: str
    requirements: tuple[OutputRequirement, ...] = ()
    reads: tuple[DependencyRead, ...] = ()
    domain_reads: tuple[DomainReadEvidence, ...] = ()
    saved_outputs: tuple[ExecutionIdentity, ...] = ()
    reused_outputs: tuple[ExecutionIdentity, ...] = ()
    sibling_statuses: tuple[tuple[NodeIdValue, NodeStatus], ...] = ()
    active_plan_revision: PlanRevisionValue | None = None
    started_at: Timestamp | None = None
    cancel_source: CancellationSource | None = None
    cancel_reason: CancellationReason | None = None
    cancel_message: str | None = None
    cancel_requested_at: Timestamp | None = None
    cancel_observed_at: Timestamp | None = None
    completed_at: Timestamp | None = None
    causes: tuple["ExecutionDiagnostic", ...] = ()

    @model_validator(mode="after")
    def check_immutable_event(self) -> Self:
        if self.status == NodeStatus.CANCELLED or self.code in (
            ExecutionEventCode.CANCEL_REQUESTED, ExecutionEventCode.CANCEL_OBSERVED,
        ):
            if self.cancel_source is None or self.cancel_reason is None:
                raise ValueError("cancellation requires typed source and reason (use UNKNOWN if unavailable)")
        validate_immutable(self)
        return self
