"""Apply manifest-read admission inside the execution pin lifetime guard."""
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead, ManifestReadReason, ManifestReadRefusal
from app.db.repositories.sqlite.worldPack.executionPins import (
    ExecutionPins, PackClosed, PackIdentityConflict, PackMissingHold, PackUnsealed, PinIntent,
)


class PinnedManifestGuard:
    def __init__(self, pins: ExecutionPins, contract: ArtifactFormatContract[bytes], version: int, budget: int):
        if type(budget) is not int or budget <= 0 or version not in contract.supported_versions:
            raise ValueError("invalid manifest admission profile")
        self._pins, self._contract = pins, contract
        self._version, self._budget = version, budget

    @asynccontextmanager
    async def manifest_guard(self, request: ManifestPinRead) -> AsyncIterator[ArtifactRef | ManifestReadRefusal]:
        intent = PinIntent(store_id=request.store_id, execution_id=request.execution_id,
                           invocation_id=request.invocation_id, logical_read_key=request.logical_read_key,
                           pin_id=request.pin_id, world_uid=request.world_uid)
        async with AsyncExitStack() as stack:
            try:
                ref = await stack.enter_async_context(self._pins.hold_open(intent))
            except PackIdentityConflict as exc:
                reason = ManifestReadReason.INVALID_PIN
                if isinstance(exc, PackClosed):
                    reason = ManifestReadReason.CLOSED_PIN
                elif isinstance(exc, PackMissingHold):
                    reason = ManifestReadReason.MISSING_HOLD
                elif isinstance(exc, PackUnsealed):
                    reason = ManifestReadReason.UNSEALED
                yield ManifestReadRefusal(pin_id=request.pin_id, reason=reason,
                                         ref=exc.ref if isinstance(exc, (PackMissingHold, PackUnsealed)) else None)
                return
            if (ref.kind != self._contract.kind or ref.format_key != self._contract.key
                    or ref.format_version != self._version):
                yield ManifestReadRefusal(pin_id=request.pin_id, ref=ref, reason=ManifestReadReason.IDENTITY_MISMATCH)
            elif ref.nbytes > min(request.max_bytes, self._budget):
                yield ManifestReadRefusal(pin_id=request.pin_id, ref=ref, reason=ManifestReadReason.BUDGET_EXCEEDED)
            else:
                yield ref
