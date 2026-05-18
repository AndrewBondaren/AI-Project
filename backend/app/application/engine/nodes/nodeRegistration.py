from dataclasses import dataclass
from typing import Type

from app.application.engine.nodes.nodeKind import NodeKind


@dataclass(frozen=True)
class NodeRegistration:
    node_cls: Type
    kind: NodeKind
    executor_cls: Type | None = None
