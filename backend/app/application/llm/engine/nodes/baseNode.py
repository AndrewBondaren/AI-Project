from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BaseNode:
    id: str
    name: str
    deps: list[str] = field(default_factory=list)
    timeout: Optional[int] = None
    retry_policy: Optional[dict] = None
    tags: list[str] = field(default_factory=list)