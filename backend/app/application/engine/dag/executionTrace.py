# TODO(B2/B2-L13): Удалить legacy-модуль целиком после GEN-DAG-1 handoff/B1 и проверки всех usages.
# Замена: app.application.engine.runtime.dag.executionTrace.
# Реестр классов/методов: .cursor/plans/dag-typing-1.md, раздел B2.1.

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