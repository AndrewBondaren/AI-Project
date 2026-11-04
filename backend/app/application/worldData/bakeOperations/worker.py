import asyncio
import sqlite3
from typing import Protocol

from app.application.worldData.bakeOperations.store import BakeStore
from app.dataModel.world.bakeOperation.record import BakeOwner, BakeRecord, BakeResult, BakeStatus, RolledBack, Waiter, PublicationOperationId
from app.dataModel.world.bakeOperation.request import BakeRequest


class BakeBinding(Protocol):
    def authorize(self, request: BakeRequest, waiter: Waiter | None, operation: str | None) -> None: ...
    def ready(self, request: BakeRequest) -> BakeResult | None: ...
    async def stage(self, owner: BakeOwner, request: BakeRequest) -> PublicationOperationId:
        """Write only private staging for this operation and fence. Return the publication operation ID."""
        ...
    def publish(self, db: sqlite3.Connection, record: BakeRecord) -> BakeResult:
        """Publish staged data in the supplied fenced transaction. The store owns commit."""
        ...
    def reconcile(self, db: sqlite3.Connection, record: BakeRecord) -> BakeResult | RolledBack | None:
        """Read authoritative evidence: published result, proven rollback reason, or unresolved."""
        ...


class BakeWorker:
    def __init__(self, store: BakeStore, binding: BakeBinding):
        self.store = store
        self.binding = binding

    async def run(self, owner: BakeOwner) -> None:
        record = self.store.begin(owner)
        if record.status in (BakeStatus.PUBLISHING, BakeStatus.RECOVERY_REQUIRED):
            self.store.publication(owner, self.binding.reconcile)
            return
        preparing = asyncio.create_task(self._prepare(owner, record.request))
        try:
            while not preparing.done():
                done, _ = await asyncio.wait((preparing,), timeout=self.store.lease_seconds / 3)
                if not done:
                    self.store.heartbeat(owner)
            publication = preparing.result()
        finally:
            if not preparing.done():
                preparing.cancel()
            await asyncio.gather(preparing, return_exceptions=True)
        if publication is None:
            return
        self.store.publishing(owner, publication)
        try:
            self.store.publication(owner, self.binding.publish)
        except Exception:
            # The publishing checkpoint survives even if the commit result could not be read.
            self.store.uncertain(owner)
            raise

    async def _prepare(self, owner: BakeOwner, request: BakeRequest) -> PublicationOperationId | None:
        try:
            result = self.binding.ready(request)
            if result is None:
                publication = await self.binding.stage(owner, request)
                if not isinstance(publication, PublicationOperationId):
                    raise TypeError("stage must return a PublicationOperationId")
                return publication
        except Exception as exc:
            self.store.prepared_terminal(owner, None, str(exc) or type(exc).__name__)
            return None
        self.store.prepared_terminal(owner, result, None)
        return None
