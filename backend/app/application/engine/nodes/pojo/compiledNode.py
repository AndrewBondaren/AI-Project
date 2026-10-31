# TODO(B2/B2-L06): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.nodeTypes.compiledNode.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass

from app.application.engine.nodes.pojo.baseNode import BaseNode


@dataclass(frozen=True)
class CompiledNode:

    node: BaseNode
    compiled_rules: list[callable]