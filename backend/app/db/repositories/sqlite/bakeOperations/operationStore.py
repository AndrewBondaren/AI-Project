import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from uuid import uuid4

from app.dataModel.world.bakeOperation.admission import BakeAdmission, BakeConflict, Joined, Started
from app.dataModel.world.bakeOperation.record import BakeOwner, BakeRecord, BakeResult, BakeStatus, RolledBack, Waiter, PublicationOperationId
from app.dataModel.world.bakeOperation.request import BakeRequest
from app.db.repositories.sqlite.bakeOperations.waiterStore import SQLiteBakeWaiters


class BakeFenceLost(RuntimeError):
    pass


class SQLiteBakeOperations:
    def __init__(self, db: sqlite3.Connection, lease_seconds: int = 30):
        if lease_seconds <= 0:
            raise ValueError("lease must be positive")
        self.db = db
        self.lease_seconds = lease_seconds
        self.waiters = SQLiteBakeWaiters(db)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self.db.in_transaction:
            raise RuntimeError("bake command requires a free connection")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield

    def admit(self, request: BakeRequest, waiter: Waiter) -> BakeAdmission:
        fingerprint = request.fingerprint()
        with self.transaction():
            active = self.db.execute("SELECT operation_id,fingerprint FROM bake_world_claims JOIN bake_operations "
                                     "USING(world_uid,operation_id) WHERE world_uid=?", (request.world_uid,)).fetchone()
            if active:
                operation, current = active
                if current != fingerprint:
                    return BakeConflict(operation)
                result = Joined(operation)
            else:
                operation = str(uuid4())
                owner = BakeOwner(operation, str(uuid4()), 1)
                self.db.execute("INSERT INTO bake_operations(operation_id,world_uid,kind,fingerprint,request_version,"
                                "request_blob,status,owner_id,fence,lease_until) VALUES(?,?,?,?,?,?,?,?,1,unixepoch('subsec')+?)",
                                (operation, request.world_uid, request.kind, fingerprint, request.version, request.canonical(),
                                 BakeStatus.PENDING, owner.owner_id, self.lease_seconds))
                self.db.execute("INSERT INTO bake_world_claims VALUES(?,?)", (request.world_uid, operation))
                result = Started(operation, owner)
            self.waiters.subscribe(operation, waiter)
            return result

    def read(self, operation: str) -> BakeRecord:
        row = self.db.execute("SELECT request_blob,status,result_blob,error,publication_operation_id FROM bake_operations "
                              "WHERE operation_id=?", (operation,)).fetchone()
        if row is None:
            raise KeyError(operation)
        status = BakeStatus(row[1])
        if status in (BakeStatus.PUBLISHING, BakeStatus.RECOVERY_REQUIRED) and row[4] is None:
            raise ValueError(f"bake operation {operation} in {status} requires publication_operation_id")
        return BakeRecord(BakeRequest.model_validate_json(row[0]), status,
                          BakeResult.model_validate_json(row[2]) if row[2] else None, row[3],
                          PublicationOperationId(row[4]) if row[4] is not None else None)

    def cancel_preparation(self, operation: str) -> bool:
        with self.transaction():
            record = self.read(operation)
            if record.status == BakeStatus.CANCELLED:
                return True
            if record.status not in (BakeStatus.PENDING, BakeStatus.RUNNING):
                return False
            self.db.execute("UPDATE bake_operations SET status=?,fence=fence+1 WHERE operation_id=?",
                            (BakeStatus.CANCELLED, operation))
            self.db.execute("DELETE FROM bake_world_claims WHERE operation_id=?", (operation,))
            return True

    def recover(self) -> BakeOwner | None:
        with self.transaction():
            owner = str(uuid4())
            row = self.db.execute("UPDATE bake_operations SET owner_id=?,fence=fence+1,lease_until=unixepoch('subsec')+?, "
                                  "status=CASE WHEN status=? THEN ? ELSE status END "
                                  "WHERE operation_id=(SELECT operation_id FROM bake_operations JOIN bake_world_claims "
                                  "USING(operation_id) WHERE lease_until<=unixepoch('subsec') ORDER BY lease_until LIMIT 1) "
                                  "RETURNING operation_id,fence",
                                  (owner, self.lease_seconds, BakeStatus.RUNNING, BakeStatus.PENDING)).fetchone()
            return BakeOwner(row[0], owner, row[1]) if row else None

    def _guard(self, token: BakeOwner) -> BakeRecord:
        renewed = self.db.execute("UPDATE bake_operations SET lease_until=unixepoch('subsec')+? WHERE operation_id=? "
                                  "AND owner_id=? AND fence=? AND lease_until>unixepoch('subsec') "
                                  "AND operation_id IN (SELECT operation_id FROM bake_world_claims)",
                                  (self.lease_seconds, token.operation_id, token.owner_id, token.fence))
        if renewed.rowcount != 1:
            raise BakeFenceLost(token.operation_id)
        return self.read(token.operation_id)

    def heartbeat(self, token: BakeOwner) -> None:
        with self.transaction():
            self._guard(token)

    def begin(self, token: BakeOwner) -> BakeRecord:
        with self.transaction():
            record = self._guard(token)
            if record.status == BakeStatus.PENDING:
                self.db.execute("UPDATE bake_operations SET status=? WHERE operation_id=?", (BakeStatus.RUNNING, token.operation_id))
            elif record.status == BakeStatus.RUNNING:
                raise ValueError("this fence already started preparation")
            return record

    def publishing(self, token: BakeOwner, publication: PublicationOperationId) -> None:
        if not isinstance(publication, PublicationOperationId):
            raise TypeError("publishing requires a PublicationOperationId")
        with self.transaction():
            if self._guard(token).status != BakeStatus.RUNNING:
                raise ValueError("publication requires a running bake")
            self.db.execute("UPDATE bake_operations SET status=?,publication_operation_id=? WHERE operation_id=?",
                            (BakeStatus.PUBLISHING, publication, token.operation_id))

    def uncertain(self, token: BakeOwner) -> None:
        with self.transaction():
            if self._guard(token).status not in (BakeStatus.PUBLISHING, BakeStatus.RECOVERY_REQUIRED):
                raise ValueError("no publication to recover")
            self.db.execute("UPDATE bake_operations SET status=? WHERE operation_id=?", (BakeStatus.RECOVERY_REQUIRED, token.operation_id))

    def _terminal(self, token: BakeOwner, result: BakeResult | None, error: str | None) -> None:
        self.db.execute("UPDATE bake_operations SET status=?,result_blob=?,error=? WHERE operation_id=?",
                        (BakeStatus.SUCCEEDED if result else BakeStatus.FAILED, result.model_dump_json() if result else None,
                         error, token.operation_id))
        self.db.execute("DELETE FROM bake_world_claims WHERE operation_id=?", (token.operation_id,))

    def prepared_terminal(self, token: BakeOwner, result: BakeResult | None, error: str | None) -> None:
        with self.transaction():
            if self._guard(token).status != BakeStatus.RUNNING or (result is None) == (error is None):
                raise ValueError("invalid preparation outcome")
            self._terminal(token, result, error)

    def publication(self, token: BakeOwner, evidence: Callable[[sqlite3.Connection, BakeRecord], BakeResult | RolledBack | None]) -> None:
        with self.transaction():
            record = self._guard(token)
            if record.status not in (BakeStatus.PUBLISHING, BakeStatus.RECOVERY_REQUIRED):
                raise ValueError("no pending publication")
            outcome = evidence(self.db, record)
            if outcome is None:
                self.db.execute("UPDATE bake_operations SET status=? WHERE operation_id=?", (BakeStatus.RECOVERY_REQUIRED, token.operation_id))
            elif isinstance(outcome, BakeResult):
                self._terminal(token, outcome, None)
            else:
                self._terminal(token, None, outcome.reason)
