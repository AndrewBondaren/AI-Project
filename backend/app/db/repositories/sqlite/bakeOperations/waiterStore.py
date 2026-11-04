import sqlite3
from app.dataModel.world.bakeOperation.record import DeliveryStatus, Waiter


class SQLiteBakeWaiters:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def subscribe(self, operation: str, waiter: Waiter) -> None:
        # Admission owns this transaction, including the subscription.
        self.db.execute("INSERT INTO bake_waiters VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (operation, waiter.execution_id, waiter.invocation_id, waiter.step_index, DeliveryStatus.SUBSCRIBED))

    def status(self, operation: str, waiter: Waiter) -> DeliveryStatus | None:
        row = self.db.execute("SELECT delivery_status FROM bake_waiters WHERE operation_id=? AND execution_id=? "
                              "AND invocation_id=? AND step_index=?",
                              (operation, waiter.execution_id, waiter.invocation_id, waiter.step_index)).fetchone()
        return DeliveryStatus(row[0]) if row else None

    def finish(self, operation: str, waiter: Waiter, status: DeliveryStatus) -> None:
        if self.db.in_transaction:
            raise RuntimeError("waiter command requires a free connection")
        with self.db:
            self.db.execute("UPDATE bake_waiters SET delivery_status=? WHERE operation_id=? AND execution_id=? "
                            "AND invocation_id=? AND step_index=? AND delivery_status=?",
                            (status, operation, waiter.execution_id, waiter.invocation_id, waiter.step_index, DeliveryStatus.SUBSCRIBED))
