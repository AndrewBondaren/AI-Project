from dataclasses import dataclass, field
from typing import Type

from app.application.engine.nodes.nodeKind import NodeKind


@dataclass(frozen=True)
class NodeRegistration:
    node_cls: Type
    kind: NodeKind
    executor_cls: Type | None = None
    context_fields: list[str] = field(default_factory=list)
