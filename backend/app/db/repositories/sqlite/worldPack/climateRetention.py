"""Attach a prepared manifest's climate children inside the publication commit."""
from app.application.worldData.pack.encoding.packManifestCodec import encode_candidate_manifest
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, OperationHolder
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
from app.encoding.canonicalCodec import content_digest


async def retain_climate_members(scope: CommitScope, holders: SqliteArtifactHolders,
                                lease: OperationLeaseRef, ref: ArtifactRef, manifest: WorldPackManifest) -> None:
    scopes = holders._scopes
    if (scopes.commits.registry.operation_id(scope) != lease.operation_id
            or lease.kind is not OperationKind.PACK_ACTIVATION or manifest.world_uid != lease.world_uid):
        raise ValueError("publication scope differs from candidate operation")
    payload = encode_candidate_manifest(manifest)
    if (manifest.content_hash is not None or ref.kind is not ArtifactKind.BLOB
            or ref.nbytes != len(payload) or ref.content_hash != content_digest(payload).hex()):
        raise ValueError("retention owner differs from prepared manifest")
    children = manifest.climate_artifacts()
    async with scopes.bind(scope):
        await holders._catalog._lease(scope, lease, writable=False)
        record = await holders._operations._load(lease.operation_id, scope)
        if record is None or record.phase is not OperationPhase.APPLYING:
            raise ValueError("climate retention requires a claimed publication")
        source = OperationHolder(lease=lease)
        for member in (ref, *children):
            if not await holders._catalog.is_sealed(member) or not await holders.is_held(member, source):
                raise ValueError("candidate operation must hold every sealed climate member and manifest")
        owner = ArtifactRetentionHolder(artifact=ref)
        for member in children:
            await holders.acquire(member, owner)
