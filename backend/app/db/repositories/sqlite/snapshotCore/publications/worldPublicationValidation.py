"""Validate persisted world publication facts before exposing them to readers."""

from typing import Any, Mapping

from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.db.mapper import from_row
from app.db.models.snapshotCore.operationRows import PublicationOperationRow
from app.db.models.snapshotCore.publicationRows import WorldPublicationRow
from app.db.repositories.sqlite.shared.validation.rowValues import _values, _wire


def decode_publication(raw: Mapping[str, Any]) -> WorldPublicationRow:
    # Validate SQLite's integer before the mapper converts it to bool.
    _values(booleans=(raw["gameplay_started"],))
    row = from_row(WorldPublicationRow, raw)
    _values(uids=(row.publication_id, row.world_uid), positives=(row.publication_seq,),
            optional_uids=(row.predecessor_id, row.operation_id, row.snapshot_head_id, row.active_timeline_id),
            optional_hashes=(row.pack_hash,))
    return row


def validate_bootstrap(row: WorldPublicationRow) -> None:
    if (row.publication_seq != 1 or row.operation_id is not None or row.pack_hash is not None
            or row.snapshot_head_id is not None or row.active_timeline_id is not None or row.gameplay_started):
        raise PublicationInfrastructureError("invalid bootstrap publication")


def validate_transition(parent: WorldPublicationRow, row: WorldPublicationRow, operation: PublicationOperationRow) -> None:
    if parent.world_uid != row.world_uid or row.publication_seq != parent.publication_seq + 1:
        raise PublicationInfrastructureError("publication chain owner/sequence mismatch")
    _values(uids=(operation.operation_id, operation.world_uid), hashes=(operation.preparation_fingerprint,))
    kind = _wire(OperationKind, operation.kind)
    if operation.world_uid != row.world_uid:
        raise PublicationInfrastructureError("publication operation belongs to another world")
    if parent.gameplay_started:
        if (kind is not OperationKind.SNAPSHOT_APPLY or not row.gameplay_started
                or row.pack_hash != parent.pack_hash or row.active_timeline_id != parent.active_timeline_id):
            raise PublicationInfrastructureError("invalid runtime publication transition")
    elif row.gameplay_started:
        if kind is not OperationKind.GAMEPLAY_START or row.pack_hash != parent.pack_hash or row.snapshot_head_id is not None:
            raise PublicationInfrastructureError("invalid gameplay start publication")
    elif kind is not OperationKind.PACK_ACTIVATION or row.pack_hash is None:
        raise PublicationInfrastructureError("invalid pregame pack publication")
    elif row.snapshot_head_id is not None or row.active_timeline_id is not None:
        raise PublicationInfrastructureError("pregame publication cannot have a runtime head/timeline")
