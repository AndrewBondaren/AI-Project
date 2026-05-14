from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Rule:
    type: str
    params: dict[str, Any]