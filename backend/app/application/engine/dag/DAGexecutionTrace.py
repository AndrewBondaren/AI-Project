from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ExecutionTrace:
    node_id: str
    start_time: datetime
    end_time: datetime
    input: dict
    output: dict | None
    status: str = "running"
    error: Optional[str] = None