# TODO(B2/B2-L23): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.prompt.pojo.nodeSection.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass


@dataclass
class NodeSection:
    dsl: str
    context_data: dict