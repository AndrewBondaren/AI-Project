from app.application.engine.contracts.invocation.executionStore import CloseReceipt, PackCloser, RestoreFailure
from app.application.publication.errors import UnknownCommitOutcome
from app.dataModel.engine.dag.invocations.record import ExecutionStopIntent


async def confirm_closed(pack: PackCloser, intent: ExecutionStopIntent) -> CloseReceipt:
    receipt = await pack.read_closed(intent)
    if receipt is not None:
        return receipt
    try:
        await pack.close(intent)
    except (UnknownCommitOutcome, OSError):
        receipt = await pack.read_closed(intent)
        if receipt is None:
            raise
        return receipt
    receipt = await pack.read_closed(intent)
    if receipt is None:
        raise RestoreFailure("Pack CLOSED unavailable after close")
    return receipt
