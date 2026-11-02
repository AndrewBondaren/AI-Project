"""Real SQL setup for 4C3-B; no lease adapter or application lifecycle substitute."""

from hashlib import sha256

from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.db.models.snapshotCore.operationRows import PublicationOperationRow, PublicationOperationEventRow
from app.db.models.artifacts.leaseRows import ArtifactLeaseEventRow, ArtifactWriterClaimRow
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from app.db.repositories.sqlite.artifacts.catalogStore import SqliteArtifactCatalog
from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata, PlayerSnapshotMetadata
from tests.snapshotCore.support.fixtures import STAMP


def adapters(bundle):
    scopes = SqliteArtifactScope(bundle[1], bundle[2]._access)
    artifacts = bundle[-1]._artifacts
    return (SqliteArtifactCatalog(scopes, bundle[-1], artifacts),
            SqliteArtifactHolders(scopes, bundle[-1], artifacts, bundle[4]))


def descriptor(name="data", *, rows=False):
    return ArtifactRef(kind=ArtifactKind.SQL_ROWS if rows else ArtifactKind.BLOB,
        format_key=RegistryKey[ArtifactFormatRegistry]("test.rows" if rows else "test.blob"),
        format_version=1, content_hash=sha256(name.encode()).hexdigest(), nbytes=len(name),
        row_count=0 if rows else None)


async def preparing(bundle, op="prepare"):
    lease = OperationLeaseRef(operation_id=op, world_uid="w1", kind=OperationKind.SNAPSHOT_APPLY,
        preparation_fingerprint="a" * 64, fence=1)
    async with bundle[1].transaction(op) as scope:
        access = bundle[2]._access
        await access.insert(scope, PublicationOperationRow(op, "w1", lease.kind.value, "a" * 64))
        await access.insert(scope, PublicationOperationEventRow(op + "-event", op, None, 1, "preparing", 1))
        await access.insert(scope, ArtifactLeaseEventRow(op + "-lease", op, None, 1, 1, True))
    return lease


async def writer_fact(bundle, reservation, *, release=False):
    lease = reservation.lease
    async with bundle[1].transaction(lease.operation_id) as scope:
        access = bundle[2]._access
        rows = await access.all_rows(scope, ArtifactWriterClaimRow, """SELECT * FROM artifact_writer_claims
            WHERE artifact_id=? AND operation_id=? AND fence=? ORDER BY event_seq""",
            (reservation.artifact_id, lease.operation_id, lease.fence))
        previous = rows[-1] if rows else None
        seq = 1 if previous is None else previous.event_seq + 1
        await access.insert(scope, ArtifactWriterClaimRow(f"{lease.operation_id}-{reservation.artifact_id}-writer-{seq}",
            reservation.artifact_id, lease.operation_id, lease.fence, None if previous is None else previous.event_id,
            seq, "release" if release else "acquire"))


async def sealed(bundle, catalog, lease, ref):
    reservation = await catalog.reserve(lease, ref)
    await writer_fact(bundle, reservation)
    await catalog.seal(reservation)
    await writer_fact(bundle, reservation, release=True)
    return reservation


async def close_preparation(bundle, lease, *, ready=False):
    async with bundle[1].transaction(lease.operation_id) as scope:
        access = bundle[2]._access
        await access.insert(scope, ArtifactLeaseEventRow(lease.operation_id + "-closed", lease.operation_id,
            lease.operation_id + "-lease", 2, lease.fence, False))
        if ready:
            await access.insert(scope, PublicationOperationEventRow(lease.operation_id + "-ready", lease.operation_id,
                lease.operation_id + "-event", 2, OperationPhase.READY.value, lease.fence))


async def snapshot_metadata(bundle, scope, lease, world_refs=(), player_refs=None):
    ref = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id=lease.operation_id + "-world")
    metadata = WorldSnapshotMetadata(ref=ref, parent=None, operation_id=lease.operation_id, turn_id=1,
        created_at=STAMP, envelope_format_version=1, base_pack_hash="d" * 64,
        state_refs=(), history_refs=(), retained_artifacts=world_refs)
    await bundle[4].append(scope, metadata, ())
    if player_refs is None:
        return (ref,)
    player = PlayerSnapshotRef(player_uid="p1", snapshot_id=lease.operation_id + "-player")
    await bundle[4].append(scope, PlayerSnapshotMetadata(ref=player, parent=None,
        operation_id=lease.operation_id, turn_id=1, created_at=STAMP, envelope_format_version=1,
        state_refs=(), history_refs=(), retained_artifacts=player_refs), ())
    return ref, player
