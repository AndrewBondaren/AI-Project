"""Frozen in-memory execution data, separate from the legacy session snapshot."""

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, TypeAdapter

from app.application.engine.runtime.dag.context.catalogSnapshot import CatalogSnapshot
from app.application.engine.runtime.dag.executionLevelSnapshot import ExecutionLevelSnapshot
from app.application.engine.runtime.dag.executionTrace import ExecutionTrace
from app.application.engine.runtime.execution.nodeOutcome import GateSignal, LevelDecision
from app.dataModel.engine.dag.diagnostics import Index
from app.dataModel.engine.dag.identity import ContractId, ContractVersion, NodeId, NodeIdValue
from app.dataModel.engine.dag.nodeStatus import NodeStatus
from app.dataModel.engine.dag.snapshotMetadata import SnapshotMetadata
from app.dataModel.validation.immutableValue import validate_immutable

S = TypeVar("S", bound=BaseModel)


@dataclass(frozen=True, kw_only=True)
class SessionSnapshot(Generic[S]):
    metadata: SnapshotMetadata
    catalog: CatalogSnapshot = field(repr=False)
    statuses: tuple[tuple[NodeId, NodeStatus], ...]
    attempt_passes: tuple[tuple[NodeId, int], ...]
    traces: tuple[ExecutionTrace, ...]
    levels: tuple[ExecutionLevelSnapshot, ...]
    decision: LevelDecision
    gate: GateSignal | None
    extension: S | None = field(default=None, repr=False)
    extension_contract: tuple[ContractId, ContractVersion] | None = None

    def __post_init__(self) -> None:
        SnapshotMetadata.model_validate(self.metadata)
        TypeAdapter[tuple[tuple[NodeId, NodeStatus], ...]](
            tuple[tuple[NodeIdValue, NodeStatus], ...],
        ).validate_python(self.statuses, strict=True)
        TypeAdapter[tuple[tuple[NodeId, int], ...]](
            tuple[tuple[NodeIdValue, Index], ...],
        ).validate_python(self.attempt_passes, strict=True)
        TypeAdapter[LevelDecision](LevelDecision).validate_python(self.decision, strict=True)
        validate_immutable(self)
        if self.metadata.execution_id != self.catalog.execution_id:
            raise ValueError("snapshot execution identities do not match")
        if self.metadata.attempt_counters != self.catalog.attempt_counters:
            raise ValueError("snapshot attempt counters do not match catalog")
        statuses = dict(self.statuses)
        if len(statuses) != len(self.statuses) or set(statuses) != {node for node, _, _ in self.catalog.contracts}:
            raise ValueError("snapshot statuses must cover registered nodes exactly")
        if NodeStatus.RUNNING in statuses.values():
            raise ValueError("snapshot cannot contain running nodes")
        passes = dict(self.attempt_passes)
        if len(passes) != len(self.attempt_passes) or set(passes).difference(statuses):
            raise ValueError("invalid snapshot attempt-pass metadata")
        current = {identity.node_id for identity in self.catalog.output_identities}
        if {node for node, status in statuses.items() if status == NodeStatus.SUCCESS} != current:
            raise ValueError("SUCCESS statuses must match current Outputs")
        if any(statuses[identity.node_id] not in (NodeStatus.FAILED, NodeStatus.GATED)
               for identity in self.catalog.error_identities):
            raise ValueError("error status must be FAILED or GATED")
        if (self.extension is None) != (self.extension_contract is None):
            raise ValueError("extension payload and contract metadata must be present together")
        versions = dict(self.catalog.contract_versions)
        if self.extension_contract is not None:
            key, version = self.extension_contract
            if key in versions and versions[key] != version:
                raise ValueError("conflicting extension contract version")
            versions[key] = version
        if dict(self.metadata.contract_versions) != versions:
            raise ValueError("snapshot contract versions are incomplete or incompatible")
        if (self.decision == LevelDecision.REPLAN) != (self.gate is not None):
            raise ValueError("only REPLAN carries a selected gate")
