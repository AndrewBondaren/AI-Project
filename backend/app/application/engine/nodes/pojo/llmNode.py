# TODO(B2/B2-L05): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.nodeTypes.llmNode.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

from dataclasses import dataclass, field
from typing import Optional, Type

from .baseNode import BaseNode

@dataclass(frozen=True, kw_only=True)
class LLMNode(BaseNode):

    dsl: str = field(default="")
    temperature: float = field(default=0.0)
    contract_json: Optional[Type] = field(default=None)
    dsl_patches: dict = field(default_factory=dict)
    enable_thinking: bool = field(default=False)