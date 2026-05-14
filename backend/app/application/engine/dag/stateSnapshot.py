from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StateSnapshot:

    level: int

    node_results: dict[str, Any]
    node_status: dict[str, str]
    shared_context: dict[str, Any]

    execution_order: list[str]