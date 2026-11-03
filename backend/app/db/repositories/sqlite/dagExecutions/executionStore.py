import sqlite3
from hashlib import sha256

from app.application.engine.contracts.invocation.executionStore import (
    Checkpoint, Claim, OwnershipConflict, RestoreFailure,
)
from app.dataModel.engine.dag.identity import ExecutionId


class SQLiteExecutionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection

    def _transaction(self) -> sqlite3.Connection:
        if self.db.in_transaction:
            raise RuntimeError("execution store requires a connection without an active transaction")
        return self.db

    async def create(self, execution_id: ExecutionId, blob: bytes) -> None:
        with self._transaction():
            self.db.execute(
                "INSERT INTO dag_executions(execution_id,schema_version,revision,fence,status,checkpoint_blob,checksum)"
                " VALUES (?,2,0,0,'READY',?,?) ON CONFLICT(execution_id) DO NOTHING", (execution_id, blob, sha256(blob).hexdigest()),
            )

    async def load(self, execution_id: ExecutionId) -> Checkpoint:
        row = self.db.execute(
            "SELECT schema_version,revision,status,checkpoint_blob,checksum FROM dag_executions WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise KeyError(execution_id)
        version, revision, status, blob, checksum = row
        if version != 2 or sha256(blob).hexdigest() != checksum:
            raise RestoreFailure("unsupported or corrupt execution checkpoint")
        return Checkpoint(revision, status, blob)

    async def claim(self, execution_id: ExecutionId, owner_id: str, seconds: int) -> Claim:
        if seconds <= 0 or not owner_id:
            raise ValueError("claim requires an owner and positive duration")
        with self._transaction():
            row = self.db.execute(
                "UPDATE dag_executions SET owner_id=?,fence=fence+1,lease_until=unixepoch()+? "
                "WHERE execution_id=? AND (owner_id IS NULL OR lease_until<=unixepoch()) RETURNING fence",
                (owner_id, seconds, execution_id),
            ).fetchone()
            if row is None:
                raise OwnershipConflict(execution_id)
            return Claim(execution_id, owner_id, row[0])

    async def checkpoint(self, claim: Claim, revision: int, status: str, blob: bytes) -> int:
        with self._transaction():
            cursor = self.db.execute(
                "UPDATE dag_executions SET revision=revision+1,status=?,checkpoint_blob=?,checksum=? "
                "WHERE execution_id=? AND owner_id=? AND fence=? AND revision=? AND lease_until>unixepoch()",
                (status, blob, sha256(blob).hexdigest(), claim.execution_id, claim.owner_id, claim.fence, revision),
            )
            if cursor.rowcount != 1:
                raise OwnershipConflict(claim.execution_id)
        return revision + 1

    async def renew(self, claim: Claim, seconds: int) -> None:
        if seconds <= 0:
            raise ValueError("lease duration must be positive")
        with self._transaction():
            cursor = self.db.execute(
                "UPDATE dag_executions SET lease_until=unixepoch()+? WHERE execution_id=? AND owner_id=? "
                "AND fence=? AND lease_until>unixepoch()", (seconds, claim.execution_id, claim.owner_id, claim.fence),
            )
            if cursor.rowcount != 1:
                raise OwnershipConflict(claim.execution_id)

    async def release(self, claim: Claim) -> None:
        with self._transaction():
            cursor = self.db.execute(
                "UPDATE dag_executions SET owner_id=NULL,lease_until=NULL WHERE execution_id=? AND owner_id=? AND fence=?",
                (claim.execution_id, claim.owner_id, claim.fence),
            )
            if cursor.rowcount != 1:
                raise OwnershipConflict(claim.execution_id)
