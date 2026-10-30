"""Immutable scheduling metadata; no Output payload or domain state."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.nodeTypes.compiledNode import CompiledNode
from app.application.engine.registration.nodeRegistration import NodeRegistration
from app.dataModel.engine.dag.identity import NodeId


@dataclass(frozen=True)
class LLMGroup:
    """One temperature group is one aggregated request, regardless of levels."""

    temperature: float
    levels: tuple[tuple[NodeId, ...], ...]


@dataclass(frozen=True)
class ExecutionPlan:
    pre_llm_levels: tuple[tuple[NodeId, ...], ...]
    llm_groups: tuple[LLMGroup, ...]
    post_llm_levels: tuple[tuple[NodeId, ...], ...]
    nodes: Mapping[NodeId, CompiledNode[BaseModel, BaseModel, NodeError]]
    registrations: Mapping[NodeId, NodeRegistration[BaseModel, BaseModel, NodeError]]
    estimated_cost: float

    def __post_init__(self) -> None:
        # Own the index, sharing the immutable declarations and node instances.
        object.__setattr__(self, "nodes", MappingProxyType(dict(self.nodes)))
        object.__setattr__(self, "registrations", MappingProxyType(dict(self.registrations)))

    def get[I: BaseModel, O: BaseModel, E: NodeError](
        self, node_id: NodeId, contract: NodeContract[I, O, E],
    ) -> CompiledNode[I, O, E]:
        registration = self.registrations[node_id]
        if registration.contract is not contract:
            raise TypeError(f"contract does not match plan binding '{node_id}'")
        compiled = self.nodes[node_id]
        registration.validate_node(compiled.node)
        # Exact binding identity and factory admission witness I/O at this
        # closed heterogeneous boundary; no casts are needed by consumers.
        return cast(CompiledNode[I, O, E], compiled)
