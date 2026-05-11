from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime


@dataclass
class ExecutionTrace:
    node_id: str
    start_time: datetime
    end_time: datetime
    input: Any
    output: Any = None
    status: str = "running"
    error: Optional[str] = None