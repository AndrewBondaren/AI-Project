import asyncio

from app.application.worldData.bakeOperations.worker import BakeWorker
from app.dataModel.world.bakeOperation.admission import BakeAdmission, Started
from app.dataModel.world.bakeOperation.record import BakeOwner, BakeRecord, BakeResult, BakeStatus, DeliveryStatus, Waiter
from app.dataModel.world.bakeOperation.request import BakeRequest


class BakeService:
    def __init__(self, worker: BakeWorker):
        self.worker = worker
        self._tasks: set[asyncio.Task[None]] = set()

    def _spawn(self, owner: BakeOwner) -> None:
        task = asyncio.create_task(self.worker.run(owner))
        self._tasks.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            task.get_loop().call_exception_handler({"message": "bake worker failed", "exception": error, "task": task})

    @staticmethod
    def _validate_submission(request: object, waiter: object) -> None:
        if not isinstance(request, BakeRequest) or not isinstance(waiter, Waiter):
            raise TypeError("submit requires a BakeRequest and a Waiter")

    def submit(self, request: BakeRequest, waiter: Waiter) -> BakeAdmission | BakeResult:
        self._validate_submission(request, waiter)
        self.worker.binding.authorize(request, waiter, None)
        ready = self.worker.binding.ready(request)
        if ready is not None:
            return ready
        admission = self.worker.store.admit(request, waiter)
        if isinstance(admission, Started):
            self._spawn(admission.owner_token)
        return admission

    def poll(self, operation: str, waiter: Waiter) -> BakeRecord | None:
        store = self.worker.store
        record = store.read(operation)
        self.worker.binding.authorize(record.request, waiter, operation)
        if store.waiters.status(operation, waiter) != DeliveryStatus.SUBSCRIBED:
            return None
        return record if record.status in (BakeStatus.SUCCEEDED, BakeStatus.FAILED, BakeStatus.CANCELLED) else None

    def acknowledge(self, operation: str, waiter: Waiter) -> None:
        if self.poll(operation, waiter) is not None:
            self.worker.store.waiters.finish(operation, waiter, DeliveryStatus.DELIVERED)

    def detach(self, operation: str, waiter: Waiter) -> None:
        store = self.worker.store
        self.worker.binding.authorize(store.read(operation).request, waiter, operation)
        store.waiters.finish(operation, waiter, DeliveryStatus.DETACHED)

    def cancel_operation(self, operation: str) -> bool:
        store = self.worker.store
        self.worker.binding.authorize(store.read(operation).request, None, operation)
        return store.cancel_preparation(operation)

    async def serve(self) -> None:
        """Application lifecycle task. Recover the same operation after lease expiry."""
        try:
            while True:
                owner = self.worker.store.recover()
                if owner is None:
                    await asyncio.sleep(self.worker.store.lease_seconds / 3)
                else:
                    self._spawn(owner)
                    await asyncio.sleep(0)
        finally:
            tasks = tuple(self._tasks)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
