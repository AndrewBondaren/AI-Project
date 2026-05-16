from dataclasses import dataclass
from typing import Any


@dataclass
class NodeValidationContext:
    node: Any
    output: Any
    state: Any
    pass_num: int = 0
    repair_attempt: int = 0