from dataclasses import dataclass

from app.application.engine.nodes.pojo.baseNode import BaseNode


@dataclass(frozen=True)
class CompiledNode:

    node: BaseNode
    compiled_rules: list[callable]