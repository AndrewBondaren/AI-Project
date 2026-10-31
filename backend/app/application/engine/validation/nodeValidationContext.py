# TODO(B2/B2-L21): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.validation.nodeValidationContext.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass
from typing import Any


@dataclass
class NodeValidationContext:
    node: Any
    output: Any
    state: Any
    pass_num: int = 0
    repair_attempt: int = 0