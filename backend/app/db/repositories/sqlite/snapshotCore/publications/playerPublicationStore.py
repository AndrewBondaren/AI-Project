"""Player head CAS shares the world publication transaction; it never commits independently."""

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.dataModel.identity.uid import EntityUid
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef
from app.dataModel.worldSnapshot.results.publication import CasDecision
from app.db.models.snapshotCore.publicationRows import PlayerPublicationRow
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.validation.rowValues import _UID, _fields
from app.ids.deterministicIds import runtime_uid


class SqlitePlayerPublicationStore:
    def __init__(self, commits: SqlitePublicationCommitStore, access: ScopedSqliteAccess) -> None:
        if access.registry is not commits.registry:
            raise ValueError("adapter/access must share the coordinator's registry")
        self._access, self._registry = access, access.registry
        self._commits = commits

    async def _ref(self, row, scope) -> PlayerSnapshotRef:
        _fields(row, uids=("publication_id", "player_uid", "player_snapshot_id", "operation_id"),
                optional_uids=("predecessor_id",), positives=("publication_seq",))
        parent = None
        if row["predecessor_id"] is not None:
            parent = await self._access.one(scope, "SELECT * FROM player_publications WHERE publication_id=?", (row["predecessor_id"],))
            if parent is None:
                raise PublicationInfrastructureError("missing player publication predecessor")
            _fields(parent, uids=("publication_id", "player_uid", "player_snapshot_id", "operation_id"),
                    optional_uids=("predecessor_id",), positives=("publication_seq",))
            if parent["player_uid"] != row["player_uid"] or row["publication_seq"] != parent["publication_seq"] + 1:
                raise PublicationInfrastructureError("player publication chain mismatch")
        elif row["publication_seq"] != 1:
            raise PublicationInfrastructureError("invalid player publication root")
        stored = await self._access.one(scope,
            "SELECT player_uid, player_snapshot_id, operation_id, parent_player_snapshot_id FROM player_snapshots WHERE player_snapshot_id=?",
            (row["player_snapshot_id"],))
        if stored is None:
            raise PublicationInfrastructureError("missing player snapshot head")
        _fields(stored, uids=("player_uid", "player_snapshot_id", "operation_id"), optional_uids=("parent_player_snapshot_id",))
        if (stored["operation_id"] != row["operation_id"] or stored["player_uid"] != row["player_uid"]
                or stored["parent_player_snapshot_id"] != (None if parent is None else parent["player_snapshot_id"])):
            raise PublicationInfrastructureError("player head ownership/lineage mismatch")
        return PlayerSnapshotRef(player_uid=stored["player_uid"], snapshot_id=stored["player_snapshot_id"])

    async def _latest(self, player_uid, scope):
        return await self._access.one(scope,
            "SELECT * FROM player_publications WHERE player_uid=? ORDER BY publication_seq DESC LIMIT 1", (player_uid,))

    async def _for_operation(self, operation_id, scope):
        rows = await self._access.all(scope, "SELECT * FROM player_publications WHERE operation_id=? ORDER BY player_uid", (operation_id,))
        return tuple([await self._ref(row, scope) for row in rows])

    async def read(self, player_uid: EntityUid, *, scope: CommitReadScope | None = None) -> PlayerSnapshotRef | None:
        player_uid = _UID.validate_python(player_uid, strict=True)
        async with self._commits.read_scope(scope) as pinned:
            row = await self._latest(player_uid, pinned)
            return None if row is None else await self._ref(row, pinned)

    async def compare_append(self, scope: CommitScope, expected: PlayerHeadExpectation,
                             next_ref: PlayerSnapshotRef, operation_id: EntityUid) -> CasDecision:
        entry = self._registry.check(scope, True)
        expected = PlayerHeadExpectation.model_validate(expected, strict=True)
        next_ref = PlayerSnapshotRef.model_validate(next_ref, strict=True)
        operation_id = _UID.validate_python(operation_id, strict=True)
        if entry[2] != operation_id or expected.player_uid != next_ref.player_uid:
            raise ValueError("player publication operation/owner mismatch")
        row = await self._latest(expected.player_uid, scope)
        current = None if row is None else await self._ref(row, scope)
        if current != expected.expected_head:
            return CasDecision.MISMATCH
        await self._access.insert(scope, PlayerPublicationRow(_UID.validate_python(runtime_uid(), strict=True),
            expected.player_uid, None if row is None else row["publication_id"],
            1 if row is None else row["publication_seq"] + 1, next_ref.snapshot_id, operation_id))
        return CasDecision.APPLIED
