from dataclasses import dataclass


@dataclass
class NodeSection:
    dsl: str
    context_data: dict