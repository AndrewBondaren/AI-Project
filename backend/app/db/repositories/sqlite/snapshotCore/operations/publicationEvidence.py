"""Historical publication evidence for terminal outcomes in the caller scope."""

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import PackActivationResult, PackActivationDisposition, GameplayStarted
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _fields
from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore
from app.db.repositories.sqlite.snapshotCore.publications.playerPublicationStore import SqlitePlayerPublicationStore


class SqlitePublicationEvidence:
    def __init__(self, commits: SqlitePublicationCommitStore, world: SqliteWorldPublicationStore,
                 players: SqlitePlayerPublicationStore, access: ScopedSqliteAccess) -> None:
        if (access.registry is not commits.registry or world._commits is not commits
                or players._commits is not commits or world._access is not access or players._access is not access):
            raise ValueError("evidence/publication adapters must share one commit coordinator and access")
        self._commits, self._world, self._players, self._access = commits, world, players, access

    async def check(self, scope: CommitReadScope | CommitScope, result: SnapshotApplyResult | PackActivationResult | GameplayStarted | OperationCancelled) -> None:
        marker = await self._access.one(scope, "SELECT publication_id FROM world_publications WHERE operation_id=?", (result.operation_id,))
        if marker is not None:
            _fields(marker, uids=("publication_id",))
        if isinstance(result, SnapshotApplyResult) and result.category is SnapshotApplyOutcomeKind.COMMITTED:
            actual = None if marker is None else await self._world._by_id(marker["publication_id"], scope)
            refs = result.committed
            if refs is None or actual is None or actual != refs.publication or actual.snapshot_head != refs.world_snapshot:
                raise PublicationInfrastructureError("committed outcome does not match historical publication")
            players = await self._players._for_operation(result.operation_id, scope)
            if players != tuple(sorted(refs.player_snapshots, key=lambda ref: ref.player_uid)):
                raise PublicationInfrastructureError("committed player participants mismatch")
        elif isinstance(result, (PackActivationResult, GameplayStarted)):
            actual = await self._world._by_id(result.publication.publication_id, scope)
            if actual != result.publication:
                raise PublicationInfrastructureError("terminal publication mismatch")
            inactive = isinstance(result, PackActivationResult) and result.disposition is PackActivationDisposition.READY_INACTIVE
            if (inactive and marker is not None) or (not inactive and (marker is None or marker["publication_id"] != actual.publication_id)):
                raise PublicationInfrastructureError("terminal publication disposition mismatch")
        else:
            snapshot = await self._access.one(scope, "SELECT snapshot_id FROM world_snapshots WHERE operation_id=?", (result.operation_id,))
            if marker is not None or snapshot is not None or await self._players._for_operation(result.operation_id, scope):
                raise PublicationInfrastructureError("refusal/cancellation cannot hide committed state")
