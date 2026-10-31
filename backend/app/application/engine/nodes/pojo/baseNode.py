# TODO(B2/B2-L03): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.nodeTypes.baseNode.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional, Type

from app.application.engine.taskType import TaskType
from app.application.engine.nodeTypes.support.nodeCost import NodeCost
from app.application.engine.rules.rule import Rule

@dataclass(frozen=True, kw_only=True)
class BaseNode:
    id: str
    name: str
    supported_tasks: list[TaskType]
    rules: list[Rule]
    deps: list[str] = field(default_factory=list)

#    executor: Optional[type] = None
    retry_policy: Optional[dict] = None
    validator: type | None = None

    priority: int = 50
    cost: NodeCost = field(default_factory=NodeCost)
#    repair_policy: RepairPolicy | None = None

    context_fields: ClassVar[list[str]] = []

#    tags: list[str] = field(default_factory=list)