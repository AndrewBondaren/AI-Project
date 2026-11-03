from dataclasses import dataclass
from typing import Protocol

from app.dataModel.engine.dag.identity import ExecutionId


class OwnershipConflict(RuntimeError):
    pass


class RestoreFailure(ValueError):
    pass


@dataclass(frozen=True)
class Claim:
    execution_id: ExecutionId
    owner_id: str
    fence: int


@dataclass(frozen=True)
class Checkpoint:
    revision: int
    status: str
    blob: bytes


class ExecutionStore(Protocol):
    async def create(self, execution_id: ExecutionId, blob: bytes) -> None: ...
    async def load(self, execution_id: ExecutionId) -> Checkpoint: ...
    async def claim(self, execution_id: ExecutionId, owner_id: str, seconds: int) -> Claim: ...
    async def checkpoint(self, claim: Claim, revision: int, status: str, blob: bytes) -> int: ...
    async def renew(self, claim: Claim, seconds: int) -> None: ...
    async def release(self, claim: Claim) -> None: ...
