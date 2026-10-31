# TODO(B2/B2-L29): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.repair.pojo.nodeFailureContext.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass


@dataclass
class NodeFailureContext:
    node_id: str
    dsl_task: str
    error_codes: list[str]
    output: dict | None