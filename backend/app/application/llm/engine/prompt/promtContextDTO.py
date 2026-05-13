from dataclasses import dataclass
from typing import Any
from typing import List


@dataclass
class PromptContextDTO:
    dsl_keys: List[str]
    message: str
    node_results: dict[str, Any]
    session: dict[str, Any]
    errors: dict[str, Any]