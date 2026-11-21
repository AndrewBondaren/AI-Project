"""Pure terminal wire/row projection; no storage access."""

from pydantic import TypeAdapter
from typing import cast
from app.encoding.canonicalCodec import content_digest, encode, CanonicalEncodingError
from app.application.encoding.boundedCanonicalDecode import decode_bounded
from app.application.publication.contracts.resultBinding import PublicationResultBinding
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled
from app.dataModel.patch.values import FormatVersion
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import PackActivationResult, GameplayStarted
from app.db.repositories.sqlite.shared.validation.rowValues import _values, _wire
from app.db.repositories.sqlite.shared.validation.blobIntegrity import _checked_blob
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.db.models.snapshotCore.operationRows import PublicationOutcomeRow


class StoredTerminalCodec[R: SnapshotApplyResult]:
    def __init__(self, *, binding: PublicationResultBinding[R]) -> None:
        self._binding = binding
        self._manifest = binding.manifest

    @property
    def result_binding(self) -> PublicationResultBinding[R]:
        return self._binding

    def decode(self, row: PublicationOutcomeRow) -> R | PackActivationResult | GameplayStarted | OperationCancelled:
        _values(uids=(row.operation_id,), positives=(row.format_version,), hashes=(row.outcome_checksum,))
        TypeAdapter(FormatVersion).validate_python(row.format_version, strict=True)
        if row.format_version != 1:
            raise PublicationInfrastructureError("unsupported outcome format")
        expected = {"snapshot_apply": self._binding.result_model, "pack_activation": PackActivationResult,
                    "gameplay_start": GameplayStarted, "cancelled": OperationCancelled}.get(row.outcome_kind)
        if expected is None:
            raise PublicationInfrastructureError("unknown terminal storage discriminator")
        if len(row.outcome_data) > self._binding.limits.max_bytes:
            raise PublicationInfrastructureError("terminal exceeds decode budget")
        try:
            result = decode_bounded(_checked_blob(row.outcome_data, row.outcome_checksum), expected,
                                    self._manifest, limits=self._binding.limits)
        except CanonicalEncodingError as exc:
            raise PublicationInfrastructureError("invalid current terminal representation") from exc
        category = _wire(SnapshotApplyOutcomeKind, row.category) if row.category is not None else None
        if result.operation_id != row.operation_id or category != (result.category if isinstance(result, SnapshotApplyResult) else None):
            raise PublicationInfrastructureError("terminal row/body mismatch")
        return cast(R | PackActivationResult | GameplayStarted | OperationCancelled, result)

    def encode(self, outcome: R | PackActivationResult | GameplayStarted | OperationCancelled) -> PublicationOutcomeRow:
        if type(outcome) not in (self._binding.result_model, PackActivationResult, GameplayStarted, OperationCancelled):
            raise TypeError("terminal must be a typed record")
        outcome = type(outcome).model_validate(outcome, strict=True)
        data = encode(outcome, self._manifest)
        if isinstance(outcome, SnapshotApplyResult):
            tag, category = OperationKind.SNAPSHOT_APPLY.value, outcome.category.value
        elif isinstance(outcome, PackActivationResult):
            tag, category = OperationKind.PACK_ACTIVATION.value, None
        elif isinstance(outcome, GameplayStarted):
            tag, category = OperationKind.GAMEPLAY_START.value, None
        else:
            tag, category = "cancelled", None
        return PublicationOutcomeRow(outcome.operation_id, tag, category, 1, data, content_digest(data).hex())
