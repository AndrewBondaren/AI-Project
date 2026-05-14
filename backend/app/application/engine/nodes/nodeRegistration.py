from dataclasses import dataclass
from typing import Type


@dataclass
class NodeRegistration:
    node_cls: Type
    executor_cls: Type