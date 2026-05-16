from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeResult:
    data: Any
    requires_replan: bool = False
    replan_reason: str | None = None