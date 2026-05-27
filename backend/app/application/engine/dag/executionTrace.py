from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ExecutionTrace:
    node_id: str
    start_time: datetime
    input: dict
    output: dict | None
    end_time: Optional[datetime] = None
    status: str = "running"
    error: Optional[str] = None