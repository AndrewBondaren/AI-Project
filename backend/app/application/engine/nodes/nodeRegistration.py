# TODO(B2/B2-L01): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.registration.nodeRegistration.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass, field
from typing import Type

from app.application.engine.nodeTypes.support.nodeKind import NodeKind


@dataclass(frozen=True)
class NodeRegistration:
    node_cls: Type
    kind: NodeKind
    executor_cls: Type | None = None
    context_fields: list[str] = field(default_factory=list)
