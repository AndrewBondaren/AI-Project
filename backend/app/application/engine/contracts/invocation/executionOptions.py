from dataclasses import dataclass
from pydantic import PositiveInt, TypeAdapter

from app.application.engine.contracts.invocation.executionStore import ExecutionStore


@dataclass(frozen=True)
class InvocationOptions:
    store: ExecutionStore
    workers: int
    invocation_limit: int
    lease_seconds: int = 300

    def __post_init__(self) -> None:
        for value in (self.workers, self.invocation_limit, self.lease_seconds):
            TypeAdapter(PositiveInt).validate_python(value, strict=True)
