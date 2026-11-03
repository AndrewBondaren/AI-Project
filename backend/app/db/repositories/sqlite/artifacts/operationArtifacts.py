"""Read-only active operation artifact holds; no writer or lifecycle policy."""

from pydantic import TypeAdapter

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatKey
from app.dataModel.identity.uid import EntityUid
from app.db.models.artifacts.catalogRows import ArtifactCatalogRow
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _UID, _values, _wire


class SqliteOperationArtifacts:
    def __init__(self, access: ScopedSqliteAccess) -> None:
        self._access = access

    async def read(self, scope: CommitReadScope, operation_id: EntityUid) -> tuple[ArtifactRef, ...]:
        operation_id = _UID.validate_python(operation_id, strict=True)
        held = await self._access.all_rows(scope, ArtifactCatalogRow, """SELECT DISTINCT c.* FROM artifact_catalog c JOIN artifact_holder_events h
            ON h.artifact_id=c.artifact_id WHERE h.holder_kind='operation' AND h.operation_id=? AND h.event_kind='acquire'
            AND NOT EXISTS (SELECT 1 FROM artifact_holder_events n WHERE n.predecessor_id=h.event_id)
            ORDER BY c.kind,c.format_key,c.format_version,c.content_hash""", (operation_id,))
        refs = []
        for artifact in held:
            _values(uids=(artifact.artifact_id,))
            try:
                refs.append(ArtifactRef(kind=_wire(ArtifactKind, artifact.kind),
                    format_key=TypeAdapter(ArtifactFormatKey).validate_python(artifact.format_key, strict=True),
                    format_version=artifact.format_version, content_hash=artifact.content_hash,
                    nbytes=artifact.nbytes, row_count=artifact.row_count))
            except (ValueError, TypeError) as error:
                raise PublicationInfrastructureError("invalid persisted operation artifact descriptor") from error
        return tuple(refs)
