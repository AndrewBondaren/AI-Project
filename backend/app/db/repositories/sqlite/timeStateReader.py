from pydantic import ValidationError

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope
from app.dataModel.time.storage.state import CLOCK_FORMAT, CLOCK_SECTION, PublicationTimeState, StoredTimeState
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef
from app.db.models.timeStates import TimePublicationRow, TimeSnapshotRow
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess


class SqliteTimeStateReader:
    def __init__(self, access: ScopedSqliteAccess):
        self._access = access

    async def read_binding(self, publication: WorldPublicationRef, scope: CommitReadScope) -> PublicationTimeState | None:
        row = await self._access.one_row(scope, TimePublicationRow,
            "SELECT * FROM time_publication_states WHERE publication_id=?", (publication.publication_id,))
        if row is None:
            return None
        try:
            binding = PublicationTimeState.model_validate_json(row.payload)
        except ValidationError as error:
            raise PublicationInfrastructureError("invalid stored publication clock") from error
        if binding.publication != publication:
            raise PublicationInfrastructureError("clock binding addresses another publication")
        return binding

    async def read_section(self, ref: SectionStateRef, scope: CommitReadScope) -> StoredTimeState | None:
        if ref.section_key != CLOCK_SECTION or ref.format_version != CLOCK_FORMAT:
            return None
        if not isinstance(ref.snapshot, WorldSnapshotRef):
            raise PublicationInfrastructureError("clock section requires a world snapshot")
        row = await self._access.one_row(scope, TimeSnapshotRow,
            "SELECT * FROM time_snapshot_states WHERE snapshot_id=?", (ref.snapshot.snapshot_id,))
        if row is None:
            return None
        try:
            payload = StoredTimeState.model_validate_json(row.payload)
        except ValidationError as error:
            raise PublicationInfrastructureError("invalid stored snapshot clock") from error
        if payload.ref != ref:
            raise PublicationInfrastructureError("clock payload addresses another section")
        return payload
