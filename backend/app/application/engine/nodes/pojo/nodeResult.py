# TODO(B2/B2-L07): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.nodeTypes.baseNode, app.application.engine.runtime.execution.nodeOutcome.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass
from typing import Any


@dataclass
class NodeResult:
    data: Any