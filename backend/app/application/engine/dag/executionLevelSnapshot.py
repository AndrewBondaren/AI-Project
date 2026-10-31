# TODO(B2/B2-L14): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.dag.executionLevelSnapshot.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionLevelSnapshot:

    phase: str   # "pre_llm" | "post_llm"
    level: int

    node_results: dict[str, Any]
    node_status: dict[str, str]
    shared_context: dict[str, Any]

    execution_order: list[str]
